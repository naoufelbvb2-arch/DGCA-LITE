"""Novelty, recruitment, competition, expansion and orphan reclamation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import ceil, exp

from .activation import scoped_quality
from .config import CoreConfig
from .learning import LearningResult, NewEdgeProposal
from .model import (
    Assembly,
    RecruitmentProposal,
    Synapse,
    SynapseScope,
    SynapseState,
    TemporalEvent,
    TickSnapshot,
)

EdgeKey = tuple[int, int, SynapseScope]


@dataclass(frozen=True, slots=True)
class NoveltyResult:
    surface_familiarity: float
    context_compatibility: float
    novelty: float


@dataclass(frozen=True, slots=True)
class ResourceResult:
    edge_upserts: Mapping[EdgeKey, Synapse]
    edge_deletes: frozenset[EdgeKey]
    blocked: tuple[NewEdgeProposal, ...]
    ordinary_recruitments: tuple[RecruitmentProposal, ...]
    expansion_recruitments: tuple[RecruitmentProposal, ...]
    touched_pairs: frozenset[tuple[int, int]]
    accepted_new_edges: int
    rejected_new_edges: int
    prunes: int


def compute_novelty(
    snapshot: TickSnapshot,
    receptor_drive: Mapping[int, float],
    temporal_events: Iterable[TemporalEvent],
    config: CoreConfig,
) -> NoveltyResult:
    weight = sum(receptor_drive.values())
    if weight == 0:
        surface = 0.0
    else:
        surface = sum(
            drive
            for cell_id, drive in receptor_drive.items()
            if (cell := snapshot.cells.get(cell_id)) is not None and cell.committed
        ) / weight

    reuse = [
        (cell_id, drive)
        for cell_id, drive in receptor_drive.items()
        if drive > 0
        and (cell := snapshot.cells.get(cell_id)) is not None
        and cell.committed
    ]
    events = tuple(temporal_events)
    lawful_context = tuple(
        (event, source, historical_activation)
        for event in sorted(events, key=lambda item: item.tick)
        if 1 <= snapshot.tick - event.tick <= config.temporal_horizon
        for source, historical_activation in event.activations
    )
    if not reuse:
        surface = 0.0
        context = 1.0
    elif not lawful_context:
        context = 1.0
    else:
        weighted = 0.0
        denominator = 0.0
        for receptor, drive in sorted(reuse):
            residual = 1.0
            for event in sorted(events, key=lambda item: item.tick):
                delta = snapshot.tick - event.tick
                if not 1 <= delta <= config.temporal_horizon:
                    continue
                kernel = exp(-config.alpha * delta)
                for source, historical_activation in event.activations:
                    edge = snapshot.outgoing.get(source, {}).get(
                        (receptor, SynapseScope.ASSOCIATIVE)
                    )
                    if edge is not None:
                        residual *= 1.0 - historical_activation * scoped_quality(edge, config) * kernel
            weighted += drive * (1.0 - residual)
            denominator += drive
        context = weighted / denominator
    novelty = 1.0 - surface * context
    return NoveltyResult(surface, context, novelty)


def ordinary_recruitment(
    snapshot: TickSnapshot,
    receptor_drive: Mapping[int, float],
    novelty: float,
    config: CoreConfig,
) -> tuple[RecruitmentProposal, ...]:
    if novelty < config.theta_R:
        return ()
    requested = min(config.K_R, ceil(config.K_R * novelty))
    eligible = [
        (cell_id, drive)
        for cell_id, drive in receptor_drive.items()
        if cell_id not in snapshot.cells or not snapshot.cells[cell_id].committed
    ]
    eligible.sort(key=lambda item: (-item[1], item[0]))
    return tuple(
        RecruitmentProposal(cell_id, drive, False)
        for cell_id, drive in eligible[:requested]
    )


def arbitrate_synapses(
    snapshot: TickSnapshot,
    learning: LearningResult,
    novelty: float,
    config: CoreConfig,
) -> tuple[dict[EdgeKey, Synapse], set[EdgeKey], list[NewEdgeProposal], int, int, int]:
    upserts = dict(learning.existing_updates)
    deletes: set[EdgeKey] = set()
    blocked: list[NewEdgeProposal] = []
    accepted = rejected = prunes = 0
    by_source: dict[int, list[NewEdgeProposal]] = {}
    for proposal in learning.new_edges:
        by_source.setdefault(proposal.source_id, []).append(proposal)

    for source in sorted(by_source):
        source_cell = snapshot.cells[source]
        overlay = dict(snapshot.outgoing.get(source, {}))
        for (updated_source, target, scope), edge in upserts.items():
            if updated_source == source:
                overlay[(target, scope)] = edge
        preexisting = set(overlay)
        ranked = sorted(
            by_source[source],
            key=lambda proposal: (
                -(min(proposal.q, config.E_max) / config.E_max),
                -proposal.q,
                proposal.target_id,
                proposal.scope.order,
            ),
        )
        for proposal in ranked:
            quality_new = min(proposal.q, config.E_max) / config.E_max
            admitted = False
            if len(overlay) < source_cell.synaptic_budget:
                admitted = True
            else:
                candidates = [
                    (scoped_quality(edge, config), target, scope)
                    for (target, scope), edge in overlay.items()
                    if (target, scope) in preexisting
                    and edge.state is SynapseState.CANDIDATE
                    and scoped_quality(edge, config) < config.theta_prune
                ]
                candidates.sort(key=lambda item: (item[0], item[1], item[2].order))
                if candidates and quality_new > candidates[0][0]:
                    _, target, scope = candidates[0]
                    overlay.pop((target, scope))
                    upserts.pop((source, target, scope), None)
                    deletes.add((source, target, scope))
                    preexisting.discard((target, scope))
                    prunes += 1
                    admitted = True
            if admitted:
                edge = Synapse(
                    proposal.target_id,
                    1.0,
                    min(proposal.q, config.E_max),
                    SynapseState.CANDIDATE,
                    proposal.scope,
                )
                overlay[(proposal.target_id, proposal.scope)] = edge
                upserts[proposal.key] = edge
                accepted += 1
            else:
                rejected += 1
                if proposal.q >= config.theta_create and novelty >= config.theta_R:
                    blocked.append(proposal)
    return upserts, deletes, blocked, accepted, rejected, prunes


def allocate_expansion(
    blocked: Iterable[NewEdgeProposal],
    reserves: Mapping[EdgeKey, tuple[tuple[int, float], ...]],
    snapshot: TickSnapshot,
    ordinary: tuple[RecruitmentProposal, ...],
    novelty: float,
    config: CoreConfig,
) -> tuple[RecruitmentProposal, ...]:
    remaining = config.K_R - len({item.cell_id for item in ordinary})
    if remaining <= 0:
        return ()
    reserved = {item.cell_id for item in ordinary}
    requests = sorted(
        blocked,
        key=lambda item: (-item.q, item.source_id, item.target_id, item.scope.order),
    )
    pools: dict[EdgeKey, list[tuple[int, float]]] = {}
    bounds: dict[EdgeKey, int] = {}
    counts: dict[EdgeKey, int] = {}
    for request in requests:
        eligible = [
            (cell_id, drive)
            for cell_id, drive in reserves.get(request.key, ())
            if cell_id not in reserved
            and (cell_id not in snapshot.cells or not snapshot.cells[cell_id].committed)
        ]
        eligible.sort(key=lambda item: (-item[1], item[0]))
        pools[request.key] = eligible
        bounds[request.key] = min(config.K_R, ceil(config.K_R * novelty), len(eligible))
        counts[request.key] = 0

    result: list[RecruitmentProposal] = []
    while remaining > 0:
        progress = False
        for request in requests:
            key = request.key
            if remaining <= 0:
                break
            if counts[key] >= bounds[key]:
                continue
            while pools[key] and pools[key][0][0] in reserved:
                pools[key].pop(0)
            if not pools[key]:
                continue
            cell_id, drive = pools[key].pop(0)
            reserved.add(cell_id)
            result.append(RecruitmentProposal(cell_id, drive, True))
            counts[key] += 1
            remaining -= 1
            progress = True
        if not progress:
            break
    return tuple(result)


def resolve_resources(
    snapshot: TickSnapshot,
    learning: LearningResult,
    receptor_drive: Mapping[int, float],
    novelty: float,
    expansion_reserves: Mapping[EdgeKey, tuple[tuple[int, float], ...]],
    config: CoreConfig,
) -> ResourceResult:
    ordinary = ordinary_recruitment(snapshot, receptor_drive, novelty, config)
    upserts, deletes, blocked, accepted, rejected, prunes = arbitrate_synapses(
        snapshot, learning, novelty, config
    )
    expansion = allocate_expansion(
        blocked, expansion_reserves, snapshot, ordinary, novelty, config
    )
    touched = set(learning.touched_pairs)
    touched.update(tuple(sorted((source, target))) for source, target, _ in deletes)
    return ResourceResult(
        upserts,
        frozenset(deletes),
        tuple(blocked),
        ordinary,
        expansion,
        frozenset(touched),
        accepted,
        rejected,
        prunes,
    )


def reclaimable_cells(
    snapshot: TickSnapshot,
    candidate_ids: Iterable[int],
    edge_upserts: Mapping[EdgeKey, Synapse],
    edge_deletes: frozenset[EdgeKey],
    references: frozenset[int],
    reservations: frozenset[int],
    temporal_references: frozenset[int],
    config: CoreConfig,
    assembly_upserts: Mapping[int, Assembly] | None = None,
    assembly_deletes: frozenset[int] = frozenset(),
    post_activation: Mapping[int, float] | None = None,
) -> frozenset[int]:
    assembly_upserts = assembly_upserts or {}
    post_activation = post_activation or {}
    result: set[int] = set()
    for cell_id in sorted(set(candidate_ids)):
        cell = snapshot.cells.get(cell_id)
        if (
            cell is None
            or not cell.committed
            or post_activation.get(cell_id, cell.activation) >= config.theta_active
        ):
            continue
        if cell_id in references or cell_id in reservations or cell_id in temporal_references:
            continue
        surviving_memberships = {
            assembly_id
            for assembly_id in snapshot.memberships.get(cell_id, frozenset())
            if assembly_id not in assembly_deletes
            and (
                assembly_id not in assembly_upserts
                or cell_id in assembly_upserts[assembly_id].members
            )
        }
        surviving_memberships.update(
            assembly_id
            for assembly_id, assembly in assembly_upserts.items()
            if cell_id in assembly.members
        )
        if surviving_memberships:
            continue
        outgoing = {
            (target, scope): edge
            for (target, scope), edge in snapshot.outgoing.get(cell_id, {}).items()
            if (cell_id, target, scope) not in edge_deletes
        }
        for (source, target, scope), edge in edge_upserts.items():
            if source == cell_id:
                outgoing[(target, scope)] = edge
        if outgoing:
            continue
        incoming_exists = False
        for source, scope in snapshot.incoming.get(cell_id, frozenset()):
            if (source, cell_id, scope) not in edge_deletes:
                incoming_exists = True
                break
        if not incoming_exists and not any(target == cell_id for _, target, _ in edge_upserts):
            result.add(cell_id)
    return frozenset(result)
