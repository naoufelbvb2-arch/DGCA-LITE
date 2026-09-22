"""Canonical external-event transaction orchestrator for Layer 1 Core v0.4."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .activation import ActivationResult, compute_activation
from .assemblies import AssemblyResult, process_assemblies
from .config import CoreConfig
from .learning import LearningResult, learn_tick
from .model import (
    AdjudicatedEvidence,
    HardBoundary,
    SurfaceEvent,
    SynapseScope,
    TemporalEvent,
    TickTransaction,
)
from .network import SparseNetwork
from .resources import (
    EdgeKey,
    NoveltyResult,
    ResourceResult,
    compute_novelty,
    reclaimable_cells,
    resolve_resources,
)
from .surface import SurfaceCodec
from .temporal import TemporalStream


@dataclass(frozen=True, slots=True)
class TickDiagnostics:
    materialized_cells: int
    active_frontier_size: int
    emission_frontier_size: int
    local_pairs_inspected: int
    associative_pairs_inspected: int
    synaptic_proposals: int
    accepted_new_edges: int
    rejected_new_edges: int
    prunes: int
    ordinary_recruitments: int
    expansion_recruitments: int
    assembly_seeds: int
    bfs_visits: int
    transaction_mutations: int


@dataclass(frozen=True, slots=True)
class TickResult:
    root_id: int
    tick: int
    novelty: NoveltyResult
    activation: ActivationResult
    learning: LearningResult
    resources: ResourceResult
    assemblies: AssemblyResult
    diagnostics: TickDiagnostics


class CoreEngine:
    """Owns canonical Network state and executes one atomic transaction per event."""

    def __init__(self, config: CoreConfig | None = None) -> None:
        self.config = config or CoreConfig()
        self.network = SparseNetwork(self.config)
        self.surface = SurfaceCodec(self.config, self.network.topology)
        self.temporal = TemporalStream(self.config)

    def _expansion_reserves(
        self,
        blocked_keys: Iterable[EdgeKey],
        current_drive: Mapping[int, float],
        context: tuple[TemporalEvent, ...],
    ) -> dict[EdgeKey, tuple[tuple[int, float], ...]]:
        reserves: dict[EdgeKey, tuple[tuple[int, float], ...]] = {}
        current = tuple(sorted(current_drive.items(), key=lambda item: (-item[1], item[0])))
        for key in blocked_keys:
            source, _, scope = key
            if scope is SynapseScope.ASSOCIATIVE:
                historical: dict[int, float] = {}
                for event in context:
                    if any(cell_id == source for cell_id, _ in event.activations):
                        for receptor, drive in event.receptor_drive:
                            historical[receptor] = max(historical.get(receptor, 0.0), drive)
                reserve = tuple(
                    sorted(historical.items(), key=lambda item: (-item[1], item[0]))
                )
            else:
                reserve = current
            reserves[key] = reserve
        return reserves

    @staticmethod
    def _references(
        receptor_drive: Mapping[int, float],
        resources: ResourceResult,
        assemblies: AssemblyResult,
    ) -> frozenset[int]:
        references = set(receptor_drive)
        for source, target, _ in resources.edge_upserts:
            references.update((source, target))
        for proposal in resources.blocked:
            references.update((proposal.source_id, proposal.target_id))
        references.update(item.cell_id for item in resources.ordinary_recruitments)
        references.update(item.cell_id for item in resources.expansion_recruitments)
        for assembly in assemblies.upserts.values():
            references.update(assembly.members)
        return frozenset(references)

    def process_event(
        self,
        event: SurfaceEvent,
        *,
        boundary: bool | HardBoundary = False,
        additional_evidence: Iterable[AdjudicatedEvidence] = (),
    ) -> TickResult:
        boundary_present = boundary.present if isinstance(boundary, HardBoundary) else boundary
        root_id = self.temporal.next_root_id
        signature = self.surface.encode(event)
        receptor_drive = dict(self.surface.receptor_drive(signature))
        snapshot = self.network.snapshot()
        context = () if boundary_present else self.temporal.events
        novelty = compute_novelty(snapshot, receptor_drive, context, self.config)
        activation = compute_activation(
            snapshot, receptor_drive, self.config, boundary_reset=boundary_present
        )
        temporal_event = TemporalEvent(
            tick=snapshot.tick,
            activations=tuple(
                (cell_id, activation.next_activation[cell_id])
                for cell_id in sorted(activation.learning_frontier)
            ),
            signature=signature,
            receptor_drive=tuple(sorted(receptor_drive.items())),
        )
        temporal_transaction = self.temporal.prospective(
            temporal_event, boundary=boundary_present
        )
        learning = learn_tick(
            snapshot,
            activation,
            context,
            self.network.topology,
            self.config,
            root_id,
            additional=additional_evidence,
        )

        # Only historical provenance that survives the prospective append may
        # supply expansion receptors.
        provisional = resolve_resources(
            snapshot, learning, receptor_drive, novelty.novelty, {}, self.config
        )
        reserves = self._expansion_reserves(
            (proposal.key for proposal in provisional.blocked),
            receptor_drive,
            temporal_transaction.surviving_history,
        )
        resources = resolve_resources(
            snapshot,
            learning,
            receptor_drive,
            novelty.novelty,
            reserves,
            self.config,
        )
        assemblies = process_assemblies(
            snapshot,
            resources.edge_upserts,
            resources.edge_deletes,
            resources.touched_pairs,
            self.network.topology,
            self.config,
            self.network.next_assembly_id,
        )
        references = self._references(receptor_drive, resources, assemblies)
        reservations = frozenset(
            item.cell_id
            for item in resources.ordinary_recruitments
            + resources.expansion_recruitments
        )
        reclaim_candidates = set(temporal_transaction.expired_references)
        reclaim_candidates.update(assemblies.removed_members)
        reclaim_candidates.update(
            endpoint
            for source, target, _ in resources.edge_deletes
            for endpoint in (source, target)
        )
        reclaims = reclaimable_cells(
            snapshot,
            reclaim_candidates,
            resources.edge_upserts,
            resources.edge_deletes,
            references,
            reservations,
            temporal_transaction.post_references,
            self.config,
            assemblies.upserts,
            assemblies.deletes,
            activation.next_activation,
        )

        transaction = TickTransaction(base_version=snapshot.version)
        transaction.next_activation.update(activation.next_activation)
        transaction.cell_commits.update(reservations)
        transaction.cell_reclaims.update(reclaims)
        transaction.synapse_upserts.update(resources.edge_upserts)
        transaction.synapse_deletes.update(resources.edge_deletes)
        transaction.assembly_upserts.update(assemblies.upserts)
        transaction.assembly_deletes.update(assemblies.deletes)
        transaction.touched_pairs.update(resources.touched_pairs)
        transaction.references.update(references)
        mutation_count = (
            len(transaction.next_activation)
            + len(transaction.cell_commits)
            + len(transaction.cell_reclaims)
            + len(transaction.synapse_upserts)
            + len(transaction.synapse_deletes)
            + len(transaction.assembly_upserts)
            + len(transaction.assembly_deletes)
        )
        self.temporal.validate(temporal_transaction)
        self.network.commit(transaction)
        self.temporal.publish(temporal_transaction)

        diagnostics = TickDiagnostics(
            materialized_cells=self.network.materialized_cell_count,
            active_frontier_size=len(activation.learning_frontier),
            emission_frontier_size=len(activation.emission_frontier),
            local_pairs_inspected=learning.local_pairs_inspected,
            associative_pairs_inspected=learning.associative_pairs_inspected,
            synaptic_proposals=learning.raw_proposal_count,
            accepted_new_edges=resources.accepted_new_edges,
            rejected_new_edges=resources.rejected_new_edges,
            prunes=resources.prunes,
            ordinary_recruitments=len(resources.ordinary_recruitments),
            expansion_recruitments=len(resources.expansion_recruitments),
            assembly_seeds=assemblies.assembly_seeds,
            bfs_visits=assemblies.bfs_visits,
            transaction_mutations=mutation_count,
        )
        return TickResult(
            root_id,
            snapshot.tick,
            novelty,
            activation,
            learning,
            resources,
            assemblies,
            diagnostics,
        )

    def process_text(
        self, text: str, *, boundary: bool = False
    ) -> tuple[TickResult, ...]:
        events = self.surface.segment(text)
        return tuple(
            self.process_event(event, boundary=boundary and index == 0)
            for index, event in enumerate(events)
        )

    def save(self, path) -> None:
        from .persistence import save_engine

        save_engine(self, path)

    @classmethod
    def load(cls, path) -> CoreEngine:
        from .persistence import load_engine

        return load_engine(path)
