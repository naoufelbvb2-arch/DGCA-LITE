"""Sparse canonical Network state and atomic transaction commit."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from types import MappingProxyType
from typing import Any

from .config import CoreConfig
from .model import (
    Assembly,
    Cell,
    Synapse,
    SynapseScope,
    SynapseState,
    TickSnapshot,
    TickTransaction,
)
from .topology import Topology


class _ReadOnlyAdjacency(Mapping[int, Mapping[tuple[int, SynapseScope], Synapse]]):
    """Lazy read-only facade; constructing a snapshot does not scan sources."""

    def __init__(self, adjacency: dict[int, dict[tuple[int, SynapseScope], Synapse]]) -> None:
        self._adjacency = adjacency

    def __getitem__(self, source: int) -> Mapping[tuple[int, SynapseScope], Synapse]:
        return MappingProxyType(self._adjacency[source])

    def __iter__(self) -> Iterator[int]:
        return iter(self._adjacency)

    def __len__(self) -> int:
        return len(self._adjacency)

    def get(  # type: ignore[override]
        self, source: int, default: Any = None
    ) -> Mapping[tuple[int, SynapseScope], Synapse] | Any:
        edges = self._adjacency.get(source)
        return default if edges is None else MappingProxyType(edges)


class _ReadOnlyIncoming(Mapping[int, frozenset[tuple[int, SynapseScope]]]):
    """Lazy incoming-index facade; no snapshot-time global copy."""

    def __init__(self, incoming: dict[int, set[tuple[int, SynapseScope]]]) -> None:
        self._incoming = incoming

    def __getitem__(self, target: int) -> frozenset[tuple[int, SynapseScope]]:
        return frozenset(self._incoming[target])

    def __iter__(self) -> Iterator[int]:
        return iter(self._incoming)

    def __len__(self) -> int:
        return len(self._incoming)

    def get(  # type: ignore[override]
        self, target: int, default: Any = None
    ) -> frozenset[tuple[int, SynapseScope]] | Any:
        sources = self._incoming.get(target)
        return default if sources is None else frozenset(sources)


class SparseNetwork:
    def __init__(self, config: CoreConfig) -> None:
        self.config = config
        self.topology = Topology(config)
        self.cells: dict[int, Cell] = {}
        self.outgoing: dict[int, dict[tuple[int, SynapseScope], Synapse]] = {}
        self.incoming: dict[int, set[tuple[int, SynapseScope]]] = {}
        self.assemblies: dict[int, Assembly] = {}
        self.memberships: dict[int, frozenset[int]] = {}
        self._assembly_by_members: dict[frozenset[int], int] = {}
        self.active_ids: set[int] = set()
        self.version = 0
        self.tick = 0
        self.next_assembly_id = 0

    @property
    def materialized_cell_count(self) -> int:
        return len(self.cells)

    @property
    def synapse_count(self) -> int:
        return sum(len(edges) for edges in self.outgoing.values())

    def implicit_cell(self, cell_id: int) -> Cell:
        self.topology.validate_id(cell_id)
        existing = self.cells.get(cell_id)
        if existing is not None:
            return existing
        return Cell(
            id=cell_id,
            territory=self.topology.territory(cell_id),
            committed=False,
            activation=0.0,
            synaptic_budget=self.config.default_synaptic_budget,
        )

    def edge(self, source: int, target: int, scope: SynapseScope) -> Synapse | None:
        return self.outgoing.get(source, {}).get((target, scope))

    def outgoing_for(self, source: int) -> Mapping[tuple[int, SynapseScope], Synapse]:
        return MappingProxyType(self.outgoing.get(source, {}))

    def incoming_for(self, target: int) -> frozenset[tuple[int, SynapseScope]]:
        return frozenset(self.incoming.get(target, set()))

    def snapshot(self) -> TickSnapshot:
        return TickSnapshot(
            version=self.version,
            tick=self.tick,
            cells=MappingProxyType(self.cells),
            outgoing=_ReadOnlyAdjacency(self.outgoing),
            incoming=_ReadOnlyIncoming(self.incoming),
            assemblies=MappingProxyType(self.assemblies),
            assembly_index=MappingProxyType(self._assembly_by_members),
            memberships=MappingProxyType(self.memberships),
            active_ids=frozenset(self.active_ids),
        )

    def seed_cell(self, cell: Cell) -> None:
        """Validated administrative constructor used by tests/loaders."""
        self.topology.validate_id(cell.id)
        cell.validate()
        if cell.territory is not self.topology.territory(cell.id):
            raise ValueError("Cell territory does not match topology")
        self.cells[cell.id] = cell
        if cell.activation > 0:
            self.active_ids.add(cell.id)

    def seed_synapse(self, source: int, synapse: Synapse) -> None:
        if source not in self.cells or synapse.target_id not in self.cells:
            raise ValueError("Synapse endpoints must be materialized")
        if not self.cells[source].committed or not self.cells[synapse.target_id].committed:
            raise ValueError("Synapse endpoints must be committed")
        synapse.validate(source, self.config.E_max)
        if not self.topology.scope_eligible(source, synapse.target_id, synapse.scope):
            raise ValueError("Synapse scope/spatial eligibility failed")
        edges = self.outgoing.setdefault(source, {})
        key = (synapse.target_id, synapse.scope)
        if key in edges:
            raise ValueError("duplicate scoped Synapse identity")
        if len(edges) >= self.cells[source].synaptic_budget:
            raise ValueError("outgoing Synaptic budget exceeded")
        edges[key] = synapse
        self.incoming.setdefault(synapse.target_id, set()).add((source, synapse.scope))

    def seed_assembly(self, assembly: Assembly) -> None:
        assembly.validate()
        if assembly.id in self.assemblies:
            raise ValueError("duplicate Assembly ID")
        if assembly.members in self._assembly_by_members:
            raise ValueError("duplicate Assembly member set")
        if not self.config.K_min <= len(assembly.members) <= self.config.K_max:
            raise ValueError("Assembly size invalid")
        if self.topology.diameter(assembly.members) > self.config.assembly_radius:
            raise ValueError("Assembly diameter invalid")
        for member in assembly.members:
            cell = self.cells.get(member)
            if cell is None or not cell.committed or cell.territory is not assembly.territory:
                raise ValueError("invalid Assembly member")
            if len(self.memberships.get(member, ())) >= self.config.M_max:
                raise ValueError("Assembly membership bound exceeded")
        seen = {min(assembly.members)}
        pending = [min(assembly.members)]
        while pending:
            source = pending.pop()
            for target in sorted(assembly.members - seen):
                forward = self.edge(source, target, SynapseScope.LOCAL)
                reverse = self.edge(target, source, SynapseScope.LOCAL)
                if (
                    forward is not None
                    and reverse is not None
                    and forward.state is SynapseState.CONSOLIDATED
                    and reverse.state is SynapseState.CONSOLIDATED
                    and min(
                        forward.strength * forward.evidence_mass / self.config.E_max,
                        reverse.strength * reverse.evidence_mass / self.config.E_max,
                    )
                    >= self.config.theta_A
                ):
                    seen.add(target)
                    pending.append(target)
        if seen != set(assembly.members):
            raise ValueError("Assembly lacks qualifying reciprocal LOCAL connectivity")
        self.assemblies[assembly.id] = assembly
        self._assembly_by_members[assembly.members] = assembly.id
        for member in assembly.members:
            self.memberships[member] = self.memberships.get(member, frozenset()) | {assembly.id}
        self.next_assembly_id = max(self.next_assembly_id, assembly.id + 1)

    def _prospective_edges(
        self, transaction: TickTransaction
    ) -> dict[int, dict[tuple[int, SynapseScope], Synapse]]:
        affected = {
            source for source, _, _ in transaction.synapse_upserts
        } | {source for source, _, _ in transaction.synapse_deletes}
        result = {source: dict(self.outgoing.get(source, {})) for source in affected}
        for source, target, scope in sorted(
            transaction.synapse_deletes, key=lambda key: (key[0], key[1], key[2].order)
        ):
            result[source].pop((target, scope), None)
        for key, edge in sorted(
            transaction.synapse_upserts.items(),
            key=lambda item: (item[0][0], item[0][1], item[0][2].order),
        ):
            source, target, scope = key
            if edge.target_id != target or edge.scope is not scope:
                raise ValueError("Synapse key/record mismatch")
            result[source][(target, scope)] = edge
        return result

    def commit(self, transaction: TickTransaction) -> None:
        """Validate the complete local write set, then publish it atomically."""
        if transaction.base_version != self.version:
            raise RuntimeError("stale transaction version")
        prospective_edges = self._prospective_edges(transaction)

        for cell_id in transaction.cell_commits | transaction.cell_reclaims | set(transaction.next_activation):
            self.topology.validate_id(cell_id)
        for cell_id, activation in transaction.next_activation.items():
            if not 0 <= activation <= 1:
                raise ValueError("activation outside [0, 1]")
            existing = self.cells.get(cell_id)
            newly_committed = cell_id in transaction.cell_commits and (
                existing is None or not existing.committed
            )
            if existing is None and cell_id not in transaction.cell_commits:
                raise ValueError("activation target must be committed")
            if newly_committed and activation != 0:
                raise ValueError("newly recruited Cell must have activation zero")

        for source, edges in prospective_edges.items():
            source_cell = self.cells.get(source)
            if source_cell is None or not source_cell.committed:
                raise ValueError("Synapse source must already be committed")
            if len(edges) > source_cell.synaptic_budget:
                raise ValueError("outgoing Synaptic budget exceeded")
            for (target, scope), edge in edges.items():
                target_cell = self.cells.get(target)
                if target_cell is None or not target_cell.committed:
                    raise ValueError("Synapse target must already be committed")
                edge.validate(source, self.config.E_max)
                if not self.topology.scope_eligible(source, target, scope):
                    raise ValueError("Synapse scope/spatial eligibility failed")

        affected_members = {
            member
            for assembly_id in transaction.assembly_deletes | set(transaction.assembly_upserts)
            for assembly in (self.assemblies.get(assembly_id), transaction.assembly_upserts.get(assembly_id))
            if assembly is not None
            for member in assembly.members
        }
        counts = {member: len(self.memberships.get(member, frozenset())) for member in affected_members}
        for assembly_id in transaction.assembly_deletes | set(transaction.assembly_upserts):
            old = self.assemblies.get(assembly_id)
            if old is not None:
                for member in old.members:
                    counts[member] -= 1
        seen_members: dict[frozenset[int], int] = {}
        for assembly_id, assembly in transaction.assembly_upserts.items():
            assembly.validate()
            if assembly.id != assembly_id:
                raise ValueError("Assembly key/record mismatch")
            if not self.config.K_min <= len(assembly.members) <= self.config.K_max:
                raise ValueError("Assembly size invalid")
            indexed = self._assembly_by_members.get(assembly.members)
            if (
                assembly.members in seen_members
                or indexed is not None
                and indexed != assembly_id
                and indexed not in transaction.assembly_deletes
                and indexed not in transaction.assembly_upserts
            ):
                raise ValueError("duplicate Assembly member set")
            seen_members[assembly.members] = assembly_id
            if self.topology.diameter(assembly.members) > self.config.assembly_radius:
                raise ValueError("Assembly diameter invalid")
            for member in assembly.members:
                cell = self.cells.get(member)
                if cell is None or not cell.committed or cell.territory is not assembly.territory:
                    raise ValueError("invalid Assembly member")
                counts[member] = counts.get(member, len(self.memberships.get(member, frozenset()))) + 1
                if counts[member] > self.config.M_max:
                    raise ValueError("Assembly membership bound exceeded")
            # Every persisted Assembly must remain connected exclusively through
            # reciprocal CONSOLIDATED LOCAL support in the transaction overlay.
            seen = {min(assembly.members)}
            pending = [min(assembly.members)]
            while pending:
                source = pending.pop()
                source_edges = prospective_edges.get(source, self.outgoing.get(source, {}))
                for target in sorted(assembly.members - seen):
                    target_edges = prospective_edges.get(target, self.outgoing.get(target, {}))
                    forward = source_edges.get((target, SynapseScope.LOCAL))
                    reverse = target_edges.get((source, SynapseScope.LOCAL))
                    if (
                        forward is not None
                        and reverse is not None
                        and forward.state is SynapseState.CONSOLIDATED
                        and reverse.state is SynapseState.CONSOLIDATED
                        and min(
                            forward.strength * forward.evidence_mass / self.config.E_max,
                            reverse.strength * reverse.evidence_mass / self.config.E_max,
                        )
                        >= self.config.theta_A
                    ):
                        seen.add(target)
                        pending.append(target)
            if seen != set(assembly.members):
                raise ValueError("Assembly lacks qualifying reciprocal LOCAL connectivity")

        # Reclamation can only remove already-isolated Cells.
        for cell_id in transaction.cell_reclaims:
            if cell_id in transaction.references or cell_id in transaction.cell_commits:
                raise ValueError("referenced/reserved Cell cannot be reclaimed")
            outgoing = prospective_edges.get(cell_id, self.outgoing.get(cell_id, {}))
            incoming = self.incoming.get(cell_id, set())
            incoming_survivors = [
                (source, scope)
                for source, scope in incoming
                if (source, cell_id, scope) not in transaction.synapse_deletes
            ]
            incoming_new = any(target == cell_id for _, target, _ in transaction.synapse_upserts)
            if outgoing or incoming_survivors or incoming_new or counts.get(
                cell_id, len(self.memberships.get(cell_id, frozenset()))
            ):
                raise ValueError("structurally referenced Cell cannot be reclaimed")

        # All validation completed: publish in canonical order.
        for cell_id in sorted(transaction.cell_commits):
            if cell_id not in self.cells:
                self.cells[cell_id] = Cell(
                    cell_id,
                    self.topology.territory(cell_id),
                    True,
                    0.0,
                    self.config.default_synaptic_budget,
                )
            elif not self.cells[cell_id].committed:
                old = self.cells[cell_id]
                self.cells[cell_id] = Cell(old.id, old.territory, True, 0.0, old.synaptic_budget)

        for source, target, scope in sorted(
            transaction.synapse_deletes, key=lambda key: (key[0], key[1], key[2].order)
        ):
            if self.outgoing.get(source, {}).pop((target, scope), None) is not None:
                self.incoming.get(target, set()).discard((source, scope))
        for (source, target, scope), edge in sorted(
            transaction.synapse_upserts.items(),
            key=lambda item: (item[0][0], item[0][1], item[0][2].order),
        ):
            self.outgoing.setdefault(source, {})[(target, scope)] = edge
            self.incoming.setdefault(target, set()).add((source, scope))

        for assembly_id in sorted(transaction.assembly_deletes | set(transaction.assembly_upserts)):
            old = self.assemblies.pop(assembly_id, None)
            if old is not None:
                self._assembly_by_members.pop(old.members, None)
                for member in old.members:
                    remaining = self.memberships.get(member, frozenset()) - {assembly_id}
                    if remaining:
                        self.memberships[member] = remaining
                    else:
                        self.memberships.pop(member, None)
        for assembly_id, assembly in sorted(transaction.assembly_upserts.items()):
            self.assemblies[assembly_id] = assembly
            self._assembly_by_members[assembly.members] = assembly_id
            for member in assembly.members:
                self.memberships[member] = self.memberships.get(member, frozenset()) | {assembly_id}

        for cell_id, activation in sorted(transaction.next_activation.items()):
            old = self.cells.get(cell_id)
            if old is not None and old.committed:
                self.cells[cell_id] = Cell(
                    old.id, old.territory, old.committed, activation, old.synaptic_budget
                )
                if activation > 0:
                    self.active_ids.add(cell_id)
                else:
                    self.active_ids.discard(cell_id)

        for cell_id in sorted(transaction.cell_reclaims):
            self.cells.pop(cell_id, None)
            self.active_ids.discard(cell_id)
            self.outgoing.pop(cell_id, None)
            self.incoming.pop(cell_id, None)
            self.memberships.pop(cell_id, None)

        if transaction.assembly_upserts:
            self.next_assembly_id = max(
                self.next_assembly_id, max(transaction.assembly_upserts) + 1
            )
        self.version += 1
        self.tick += 1

    def canonical_state(self) -> dict[str, Any]:
        """Deterministic diagnostic/serialization view; not a runtime cognition path."""
        return {
            "version": self.version,
            "tick": self.tick,
            "next_assembly_id": self.next_assembly_id,
            "cells": [
                {
                    "id": cell.id,
                    "territory": cell.territory.value,
                    "committed": cell.committed,
                    "activation": cell.activation,
                    "synaptic_budget": cell.synaptic_budget,
                }
                for cell in sorted(self.cells.values(), key=lambda item: item.id)
            ],
            "synapses": [
                {
                    "source_id": source,
                    "target_id": edge.target_id,
                    "strength": edge.strength,
                    "evidence_mass": edge.evidence_mass,
                    "state": edge.state.value,
                    "scope": edge.scope.value,
                }
                for source in sorted(self.outgoing)
                for edge in sorted(
                    self.outgoing[source].values(),
                    key=lambda item: (item.target_id, item.scope.order),
                )
            ],
            "assemblies": [
                {
                    "id": assembly.id,
                    "territory": assembly.territory.value,
                    "members": sorted(assembly.members),
                }
                for assembly in sorted(self.assemblies.values(), key=lambda item: item.id)
            ],
        }
