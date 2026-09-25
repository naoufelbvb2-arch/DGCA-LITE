"""Coherent, bounded, independently materialized retrieval acquisition."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from math import isfinite

from dgca_lite.engine import CoreEngine
from dgca_lite.model import Assembly, Cell, Synapse, SynapseScope, SynapseState

from .config import MemoryConfig
from .integration import validate_receipt
from .types import (
    CapturedAssembly,
    CapturedCell,
    CapturedSynapse,
    FailureCode,
    FrozenFloatMap,
    FrozenParameters,
    RetrievalAbort,
    RetrievalSnapshot,
    RetrievalUniverse,
)


def _config_payload(core: CoreEngine) -> dict[str, object]:
    payload = core.config.to_dict()
    for owner in (core.network, core.network.topology, core.surface, core.temporal):
        if owner.config.to_dict() != payload:
            raise RetrievalAbort(
                FailureCode.SNAPSHOT_ABORTED, "inconsistent Core configuration views"
            )
    return payload


def _config_fingerprint(core: CoreEngine) -> str:
    encoded = json.dumps(
        _config_payload(core), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _captured_cell(cell: Cell) -> CapturedCell:
    return CapturedCell(
        cell.id,
        cell.territory,
        cell.committed,
        cell.activation,
        cell.synaptic_budget,
    )


def _captured_synapse(source: int, edge: Synapse) -> CapturedSynapse:
    return CapturedSynapse(
        source,
        edge.target_id,
        edge.strength,
        edge.evidence_mass,
        edge.state,
        edge.scope,
    )


class _Capture:
    def __init__(self, core: CoreEngine, memory_config: MemoryConfig) -> None:
        self.core = core
        self.memory_config = memory_config
        self.core_config = core.config
        self.cells: dict[int, CapturedCell] = {}
        self.assemblies: dict[int, CapturedAssembly] = {}
        self.memberships: dict[int, tuple[int, ...]] = {}
        self.local_edges: dict[tuple[int, int], CapturedSynapse] = {}
        self.associative_edges: dict[tuple[int, int], CapturedSynapse] = {}

    @staticmethod
    def _capacity(current: int, maximum: int | None, kind: str) -> None:
        if maximum is not None and current > maximum:
            raise RetrievalAbort(
                FailureCode.SNAPSHOT_CAPACITY_ABORT,
                f"complete snapshot {kind} capacity exceeded",
            )

    def add_cell(self, cell_id: int) -> CapturedCell:
        existing = self.cells.get(cell_id)
        if existing is not None:
            return existing
        cell = self.core.network.cells.get(cell_id)
        if cell is None or not cell.committed:
            raise RetrievalAbort(
                FailureCode.SNAPSHOT_ABORTED, "retrieval closure references invalid Cell"
            )
        captured = _captured_cell(cell)
        self.cells[cell_id] = captured
        self._capacity(
            len(self.cells), self.memory_config.max_snapshot_cells, "Cell"
        )
        return captured

    def memberships_for(self, cell_id: int) -> tuple[int, ...]:
        existing = self.memberships.get(cell_id)
        if existing is not None:
            return existing
        raw = self.core.network.memberships.get(cell_id, frozenset())
        if type(raw) is not frozenset or any(
            type(assembly_id) is not int or assembly_id < 0
            for assembly_id in raw
        ):
            raise RetrievalAbort(
                FailureCode.SNAPSHOT_ABORTED,
                "membership representation is inconsistent",
            )
        values = tuple(sorted(raw))
        if len(values) > self.core_config.M_max:
            raise RetrievalAbort(
                FailureCode.SNAPSHOT_ABORTED, "membership bound is inconsistent"
            )
        for assembly_id in values:
            assembly = self.core.network.assemblies.get(assembly_id)
            if (
                assembly is None
                or assembly.id != assembly_id
                or cell_id not in assembly.members
            ):
                raise RetrievalAbort(
                    FailureCode.SNAPSHOT_ABORTED,
                    "Cell/member index is inconsistent",
                )
        self.memberships[cell_id] = values
        return values

    def add_assembly(self, assembly_id: int) -> CapturedAssembly:
        existing = self.assemblies.get(assembly_id)
        if existing is not None:
            return existing
        assembly = self.core.network.assemblies.get(assembly_id)
        if assembly is None or assembly.id != assembly_id:
            raise RetrievalAbort(
                FailureCode.SNAPSHOT_ABORTED, "membership references missing Assembly"
            )
        self._validate_assembly(assembly)
        captured = CapturedAssembly(
            assembly.id, assembly.territory, tuple(sorted(assembly.members))
        )
        self.assemblies[assembly_id] = captured
        self._capacity(
            len(self.assemblies),
            self.memory_config.max_snapshot_assemblies,
            "Assembly",
        )
        for member in captured.members:
            self.add_cell(member)
            if assembly_id not in self.memberships_for(member):
                raise RetrievalAbort(
                    FailureCode.SNAPSHOT_ABORTED,
                    "Assembly/member index is inconsistent",
                )
        self._capture_local_structure(captured)
        return captured

    def _validate_assembly(self, assembly: Assembly) -> None:
        if not self.core_config.K_min <= len(assembly.members) <= self.core_config.K_max:
            raise RetrievalAbort(
                FailureCode.SNAPSHOT_ABORTED, "Assembly size is inconsistent"
            )
        for member in assembly.members:
            cell = self.core.network.cells.get(member)
            if cell is None or not cell.committed or cell.territory is not assembly.territory:
                raise RetrievalAbort(
                    FailureCode.SNAPSHOT_ABORTED, "Assembly member is inconsistent"
                )

    def _capture_local_structure(self, assembly: CapturedAssembly) -> None:
        for source in assembly.members:
            for target in assembly.members:
                if source == target:
                    continue
                edge = self.core.network.edge(source, target, SynapseScope.LOCAL)
                if edge is not None:
                    self.local_edges[(source, target)] = _captured_synapse(source, edge)
        self._check_synapse_capacity()

    def capture_associative(self, source: int) -> None:
        cell = self.add_cell(source)
        outgoing = self.core.network.outgoing_for(source)
        if len(outgoing) > cell.synaptic_budget:
            raise RetrievalAbort(
                FailureCode.SNAPSHOT_ABORTED, "outgoing budget is inconsistent"
            )
        for edge in outgoing.values():
            if (
                edge.scope is SynapseScope.ASSOCIATIVE
                and edge.state is SynapseState.CONSOLIDATED
            ):
                self.add_cell(edge.target_id)
                self.associative_edges[(source, edge.target_id)] = _captured_synapse(
                    source, edge
                )
        self._check_synapse_capacity()

    def _check_synapse_capacity(self) -> None:
        self._capacity(
            len(self.local_edges) + len(self.associative_edges),
            self.memory_config.max_snapshot_synapses,
            "Synapse",
        )

    def snapshot(self, version: int, tick: int) -> RetrievalSnapshot:
        return RetrievalSnapshot(
            version,
            tick,
            tuple(self.cells[key] for key in sorted(self.cells)),
            tuple(self.assemblies[key] for key in sorted(self.assemblies)),
            tuple((key, self.memberships[key]) for key in sorted(self.memberships)),
            tuple(
                self.local_edges[key]
                for key in sorted(self.local_edges, key=lambda item: (item[0], item[1]))
            ),
            tuple(
                self.associative_edges[key]
                for key in sorted(
                    self.associative_edges, key=lambda item: (item[0], item[1])
                )
            ),
        )


def _validated_internal_cue(
    core: CoreEngine, raw: Mapping[int, float]
) -> dict[int, float]:
    result: dict[int, float] = {}
    try:
        items = tuple(raw.items())
    except Exception as error:
        raise RetrievalAbort(FailureCode.INVALID_CUE, "cue is not materializable") from error
    for cell_id, drive in items:
        if (
            not isinstance(cell_id, int)
            or isinstance(cell_id, bool)
            or not isinstance(drive, (int, float))
            or isinstance(drive, bool)
        ):
            raise RetrievalAbort(FailureCode.INVALID_CUE)
        try:
            reference_drive = float(drive)
        except (OverflowError, TypeError, ValueError) as error:
            raise RetrievalAbort(FailureCode.INVALID_CUE) from error
        if not isfinite(reference_drive) or not 0.0 < reference_drive <= 1.0:
            raise RetrievalAbort(FailureCode.INVALID_CUE)
        try:
            core.network.topology.validate_id(cell_id)
        except ValueError as error:
            raise RetrievalAbort(FailureCode.INVALID_CUE) from error
        cell = core.network.cells.get(cell_id)
        if cell is None or not cell.committed:
            raise RetrievalAbort(FailureCode.INVALID_CUE)
        result[cell_id] = reference_drive
    return result


def acquire(
    core: CoreEngine,
    internal_cue: Mapping[int, float],
    memory_config: MemoryConfig,
    receipt: object | None = None,
) -> RetrievalUniverse:
    """Build the complete immutable retrieval universe or fail closed."""
    version0 = core.network.version
    tick0 = core.network.tick
    fingerprint0 = _config_fingerprint(core)
    core_config = core.config

    trusted: dict[int, float] = {}
    trusted_root_id: int | None = None
    if receipt is not None:
        _, _, trusted_root_id, trusted_frontier, activation_entries = validate_receipt(
            core, receipt, version0, tick0
        )
        activation = dict(activation_entries)
        if tuple(sorted(activation)) != trusted_frontier:
            raise RetrievalAbort(
                FailureCode.SNAPSHOT_ABORTED, "receipt frontier is inconsistent"
            )
        for cell_id in trusted_frontier:
            cell = core.network.cells.get(cell_id)
            value = activation[cell_id]
            if (
                cell is None
                or not cell.committed
                or cell.activation != value
                or value < core_config.theta_active
            ):
                raise RetrievalAbort(
                    FailureCode.SNAPSHOT_ABORTED,
                    "trusted activation does not match committed Core state",
                )
        trusted = activation

    internal = _validated_internal_cue(core, internal_cue)
    merged = dict(internal)
    merged.update(trusted)
    if not merged:
        raise RetrievalAbort(FailureCode.EMPTY_CUE)
    if len(merged) > memory_config.K_C:
        raise RetrievalAbort(FailureCode.CUE_CAPACITY_ABORT)

    capture = _Capture(core, memory_config)
    try:
        source_assemblies: set[int] = set()
        atomic_sources: set[int] = set()
        for cell_id in sorted(merged):
            capture.add_cell(cell_id)
            memberships = capture.memberships_for(cell_id)
            if memberships:
                source_assemblies.update(memberships)
            else:
                atomic_sources.add(cell_id)

        source_cells = set(atomic_sources)
        for assembly_id in sorted(source_assemblies):
            assembly = capture.add_assembly(assembly_id)
            source_cells.update(assembly.members)

        for source in sorted(source_cells):
            capture.capture_associative(source)

        possible_targets = {
            edge.target_id for edge in capture.associative_edges.values()
        }
        possible_target_assemblies: set[int] = set()
        for target in sorted(possible_targets):
            possible_target_assemblies.update(capture.memberships_for(target))
        for assembly_id in sorted(possible_target_assemblies):
            capture.add_assembly(assembly_id)
    except RetrievalAbort:
        raise
    except (KeyError, RuntimeError, ValueError) as error:
        raise RetrievalAbort(
            FailureCode.SNAPSHOT_ABORTED, "bounded snapshot capture failed"
        ) from error

    fingerprint1 = _config_fingerprint(core)
    if (
        core.network.version != version0
        or core.network.tick != tick0
        or fingerprint1 != fingerprint0
    ):
        raise RetrievalAbort(FailureCode.SNAPSHOT_ABORTED, "Core changed during capture")

    snapshot = capture.snapshot(version0, tick0)
    parameters = FrozenParameters(
        fingerprint0,
        core_config.theta_A,
        core_config.theta_active,
        core_config.K_max,
        core_config.M_max,
        core_config.E_max,
        memory_config.K_C,
        memory_config.theta_PC,
        memory_config.theta_AR,
    )
    return RetrievalUniverse(
        trusted_root_id,
        FrozenFloatMap.from_dict(trusted),
        FrozenFloatMap.from_dict(internal),
        FrozenFloatMap.from_dict(merged),
        tuple(sorted(merged)),
        tuple(sorted(trusted)),
        snapshot,
        parameters,
    )
