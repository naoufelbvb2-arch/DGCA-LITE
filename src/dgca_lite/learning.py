"""LLA v0 evidence discovery, adjudication and Synaptic updates."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import exp, isfinite

from .activation import ActivationResult
from .config import CoreConfig
from .model import (
    AdjudicatedEvidence,
    EvidenceProposal,
    Synapse,
    SynapseScope,
    SynapseState,
    TemporalEvent,
    TickSnapshot,
)
from .topology import Topology

EvidenceKey = tuple[int, int, int, SynapseScope]
EdgeKey = tuple[int, int, SynapseScope]


@dataclass(frozen=True, slots=True)
class NewEdgeProposal:
    source_id: int
    target_id: int
    scope: SynapseScope
    q: float

    @property
    def key(self) -> EdgeKey:
        return (self.source_id, self.target_id, self.scope)


@dataclass(frozen=True, slots=True)
class AggregatedEvidence:
    source_id: int
    target_id: int
    scope: SynapseScope
    q: float
    y: int

    @property
    def key(self) -> EdgeKey:
        return (self.source_id, self.target_id, self.scope)


@dataclass(frozen=True, slots=True)
class LearningResult:
    existing_updates: Mapping[EdgeKey, Synapse]
    new_edges: tuple[NewEdgeProposal, ...]
    conflicts: frozenset[EdgeKey]
    touched_pairs: frozenset[tuple[int, int]]
    local_pairs_inspected: int
    associative_pairs_inspected: int
    raw_proposal_count: int


class RootEvidenceLedger:
    def __init__(self, root_id: int) -> None:
        self.root_id = root_id
        self._consumed: set[EvidenceKey] = set()

    def consume(self, key: EvidenceKey) -> bool:
        if key in self._consumed:
            return False
        self._consumed.add(key)
        return True

    def __len__(self) -> int:
        return len(self._consumed)


def temporal_kernel(delta: int, config: CoreConfig) -> float:
    if delta < 0 or delta > config.temporal_horizon:
        return 0.0
    return exp(-config.alpha * delta)


def enumerate_evidence(
    snapshot: TickSnapshot,
    activation: ActivationResult,
    temporal_events: Iterable[TemporalEvent],
    topology: Topology,
    config: CoreConfig,
    root_id: int,
    *,
    additional: Iterable[AdjudicatedEvidence] = (),
) -> tuple[list[EvidenceProposal], int, int]:
    proposals: list[EvidenceProposal] = []
    frontier = activation.learning_frontier
    local_inspected = 0
    associative_inspected = 0

    for source in sorted(frontier):
        for target in topology.neighborhood(source, SynapseScope.LOCAL):
            local_inspected += 1
            if target not in frontier or target == source:
                continue
            q = activation.next_activation[source] * activation.next_activation[target]
            proposals.append(
                EvidenceProposal(root_id, source, target, SynapseScope.LOCAL, q, 1, True)
            )

    for event in sorted(temporal_events, key=lambda item: item.tick):
        delta = snapshot.tick - event.tick
        kernel = temporal_kernel(delta, config)
        if delta < 1 or kernel == 0:
            continue
        for source, historical_activation in event.activations:
            for target in topology.neighborhood(source, SynapseScope.ASSOCIATIVE):
                associative_inspected += 1
                if target not in frontier or target == source:
                    continue
                q = historical_activation * activation.next_activation[target] * kernel
                proposals.append(
                    EvidenceProposal(
                        root_id,
                        source,
                        target,
                        SynapseScope.ASSOCIATIVE,
                        q,
                        1,
                        True,
                    )
                )

    for item in additional:
        if item.y not in (0, 1):
            raise ValueError("evidence target must be binary")
        if not isfinite(item.q) or not 0 <= item.q <= 1:
            raise ValueError("evidence quality must be finite and in [0, 1]")
        if item.source_id == item.target_id:
            raise ValueError("self-Synapse evidence is forbidden")
        proposals.append(
            EvidenceProposal(
                root_id,
                item.source_id,
                item.target_id,
                item.scope,
                item.q,
                item.y,
                item.external_origin,
            )
        )
    return proposals, local_inspected, associative_inspected


def aggregate_evidence(
    proposals: Iterable[EvidenceProposal], ledger: RootEvidenceLedger
) -> tuple[tuple[AggregatedEvidence, ...], frozenset[EdgeKey]]:
    grouped: dict[EvidenceKey, dict[int, float]] = {}
    for proposal in proposals:
        if proposal.root_id != ledger.root_id:
            raise ValueError("proposal root does not match ledger")
        if proposal.y not in (0, 1):
            raise ValueError("evidence target must be binary")
        if not proposal.external_origin or proposal.q <= 0:
            continue
        if not isfinite(proposal.q) or not 0 <= proposal.q <= 1:
            raise ValueError("evidence quality must be finite and in [0, 1]")
        grouped.setdefault(proposal.identity, {})[proposal.y] = max(
            proposal.q,
            grouped.get(proposal.identity, {}).get(proposal.y, 0.0),
        )

    accepted: list[AggregatedEvidence] = []
    conflicts: set[EdgeKey] = set()
    for identity in sorted(grouped, key=lambda key: (key[1], key[2], key[3].order)):
        if not ledger.consume(identity):
            continue
        _, source, target, scope = identity
        by_target = grouped[identity]
        if len(by_target) > 1:
            conflicts.add((source, target, scope))
            continue
        y, q = next(iter(by_target.items()))
        accepted.append(AggregatedEvidence(source, target, scope, q, y))
    return tuple(accepted), frozenset(conflicts)


def _resource_valid(
    snapshot: TickSnapshot,
    topology: Topology,
    config: CoreConfig,
    source: int,
    target: int,
    scope: SynapseScope,
    strength: float,
    evidence: float,
) -> bool:
    source_cell = snapshot.cells.get(source)
    target_cell = snapshot.cells.get(target)
    return bool(
        source_cell is not None
        and target_cell is not None
        and source_cell.committed
        and target_cell.committed
        and source != target
        and isfinite(strength)
        and isfinite(evidence)
        and 0 <= strength <= 1
        and 0 <= evidence <= config.E_max
        and topology.scope_eligible(source, target, scope)
        and len(snapshot.outgoing.get(source, {})) <= source_cell.synaptic_budget
    )


def apply_learning(
    snapshot: TickSnapshot,
    aggregated: Iterable[AggregatedEvidence],
    conflicts: frozenset[EdgeKey],
    topology: Topology,
    config: CoreConfig,
    *,
    local_pairs_inspected: int = 0,
    associative_pairs_inspected: int = 0,
    raw_proposal_count: int = 0,
) -> LearningResult:
    updates: dict[EdgeKey, Synapse] = {}
    new_edges: list[NewEdgeProposal] = []
    touched: set[tuple[int, int]] = set()

    for evidence in aggregated:
        if evidence.key in conflicts or evidence.q <= 0:
            continue
        source, target, scope = evidence.key
        current = snapshot.outgoing.get(source, {}).get((target, scope))
        if current is None:
            if (
                evidence.y == 1
                and evidence.q >= config.theta_create
                and _resource_valid(
                    snapshot,
                    topology,
                    config,
                    source,
                    target,
                    scope,
                    1.0,
                    min(evidence.q, config.E_max),
                )
            ):
                new_edges.append(NewEdgeProposal(source, target, scope, evidence.q))
                touched.add(tuple(sorted((source, target))))
            continue

        denominator = current.evidence_mass + evidence.q
        if denominator <= 0:
            continue
        factor = evidence.q / denominator
        strength = current.strength + factor * (evidence.y - current.strength)
        evidence_mass = min(config.E_max, current.evidence_mass + evidence.q)
        state = current.state
        if current.state is SynapseState.CANDIDATE:
            if (
                strength >= config.theta_S
                and evidence_mass / config.E_max >= config.theta_E
                and _resource_valid(
                    snapshot,
                    topology,
                    config,
                    source,
                    target,
                    scope,
                    strength,
                    evidence_mass,
                )
            ):
                state = SynapseState.CONSOLIDATED
        elif strength < config.theta_demote:
            state = SynapseState.CANDIDATE
        updates[evidence.key] = Synapse(target, strength, evidence_mass, state, scope)
        touched.add(tuple(sorted((source, target))))

    new_edges.sort(key=lambda item: (item.source_id, item.target_id, item.scope.order))
    return LearningResult(
        updates,
        tuple(new_edges),
        conflicts,
        frozenset(touched),
        local_pairs_inspected,
        associative_pairs_inspected,
        raw_proposal_count,
    )


def learn_tick(
    snapshot: TickSnapshot,
    activation: ActivationResult,
    temporal_events: Iterable[TemporalEvent],
    topology: Topology,
    config: CoreConfig,
    root_id: int,
    *,
    additional: Iterable[AdjudicatedEvidence] = (),
) -> LearningResult:
    proposals, local_count, associative_count = enumerate_evidence(
        snapshot,
        activation,
        temporal_events,
        topology,
        config,
        root_id,
        additional=additional,
    )
    ledger = RootEvidenceLedger(root_id)
    aggregated, conflicts = aggregate_evidence(proposals, ledger)
    return apply_learning(
        snapshot,
        aggregated,
        conflicts,
        topology,
        config,
        local_pairs_inspected=local_count,
        associative_pairs_inspected=associative_count,
        raw_proposal_count=len(proposals),
    )
