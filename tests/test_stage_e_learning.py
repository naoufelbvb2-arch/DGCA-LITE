from math import exp

import pytest

from dgca_lite.activation import ActivationResult
from dgca_lite.config import CoreConfig
from dgca_lite.learning import (
    RootEvidenceLedger,
    aggregate_evidence,
    apply_learning,
    enumerate_evidence,
)
from dgca_lite.model import (
    Cell,
    EvidenceProposal,
    SparseSignature,
    Synapse,
    SynapseScope,
    SynapseState,
    TemporalEvent,
    Territory,
)
from dgca_lite.network import SparseNetwork


def make_pair(config: CoreConfig) -> tuple[SparseNetwork, int, int]:
    network = SparseNetwork(config)
    source = 1
    target = network.topology.neighborhood(source, SynapseScope.LOCAL)[0]
    network.seed_cell(Cell(source, Territory.LANGUAGE, True, 0.8, 8))
    network.seed_cell(Cell(target, Territory.LANGUAGE, True, 0.7, 8))
    return network, source, target


def activation(source: int, target: int) -> ActivationResult:
    values = {source: 0.8, target: 0.7}
    return ActivationResult(values, frozenset(values), frozenset(values), {})


def test_exhaustive_local_enumeration_generates_both_directions() -> None:
    config = CoreConfig(local_radius=3)
    network, source, target = make_pair(config)
    proposals, _, _ = enumerate_evidence(
        network.snapshot(), activation(source, target), (), network.topology, config, 0
    )
    keys = {(p.source_id, p.target_id, p.scope) for p in proposals}
    assert (source, target, SynapseScope.LOCAL) in keys
    assert (target, source, SynapseScope.LOCAL) in keys


def test_temporal_direction_is_past_to_current_only() -> None:
    config = CoreConfig(associative_radius=4, alpha=0.5)
    network, source, target = make_pair(config)
    # Use a current target that is in the associative neighborhood.
    target = network.topology.neighborhood(source, SynapseScope.ASSOCIATIVE)[0]
    if target not in network.cells:
        network.seed_cell(Cell(target, Territory.LANGUAGE, True, 0.7, 8))
    network.tick = 1
    current = ActivationResult({target: 0.7}, frozenset({target}), frozenset(), {})
    history = TemporalEvent(0, ((source, 0.8),), SparseSignature((b"x",), ()), ())
    proposals, _, _ = enumerate_evidence(
        network.snapshot(), current, (history,), network.topology, config, 0
    )
    assert any(
        p.source_id == source and p.target_id == target and p.scope is SynapseScope.ASSOCIATIVE
        for p in proposals
    )
    assert not any(p.source_id == target and p.target_id == source for p in proposals)


def test_duplicate_paths_use_max_not_sum() -> None:
    proposals = [
        EvidenceProposal(1, 2, 3, SynapseScope.LOCAL, 0.2, 1),
        EvidenceProposal(1, 2, 3, SynapseScope.LOCAL, 0.7, 1),
    ]
    aggregated, conflicts = aggregate_evidence(proposals, RootEvidenceLedger(1))
    assert conflicts == frozenset()
    assert aggregated[0].q == 0.7


def test_conflicting_targets_fail_closed() -> None:
    proposals = [
        EvidenceProposal(1, 2, 3, SynapseScope.LOCAL, 0.9, 1),
        EvidenceProposal(1, 2, 3, SynapseScope.LOCAL, 0.8, 0),
    ]
    aggregated, conflicts = aggregate_evidence(proposals, RootEvidenceLedger(1))
    assert aggregated == ()
    assert (2, 3, SynapseScope.LOCAL) in conflicts


def test_internal_origin_adds_no_evidence() -> None:
    proposal = EvidenceProposal(1, 2, 3, SynapseScope.LOCAL, 1.0, 1, False)
    aggregated, _ = aggregate_evidence((proposal,), RootEvidenceLedger(1))
    assert aggregated == ()


def test_exact_weighted_update_and_saturation_remains_plastic() -> None:
    config = CoreConfig(
        E_max=1, theta_E=0.1, theta_S=0.1, theta_demote=0.05, local_radius=3
    )
    network, source, target = make_pair(config)
    network.seed_synapse(
        source,
        Synapse(target, 1.0, 1.0, SynapseState.CONSOLIDATED, SynapseScope.LOCAL),
    )
    proposal = EvidenceProposal(0, source, target, SynapseScope.LOCAL, 1.0, 0)
    aggregated, conflicts = aggregate_evidence((proposal,), RootEvidenceLedger(0))
    result = apply_learning(network.snapshot(), aggregated, conflicts, network.topology, config)
    updated = result.existing_updates[(source, target, SynapseScope.LOCAL)]
    assert updated.strength == pytest.approx(0.5)
    assert updated.evidence_mass == 1.0


def test_negative_evidence_does_not_create_absent_edge() -> None:
    config = CoreConfig(local_radius=3)
    network, source, target = make_pair(config)
    proposal = EvidenceProposal(0, source, target, SynapseScope.LOCAL, 1.0, 0)
    aggregated, conflicts = aggregate_evidence((proposal,), RootEvidenceLedger(0))
    result = apply_learning(network.snapshot(), aggregated, conflicts, network.topology, config)
    assert result.new_edges == ()


def test_new_edge_is_candidate_only_and_later_root_can_consolidate() -> None:
    config = CoreConfig(E_max=1, theta_E=0.5, theta_S=0.5, local_radius=3)
    network, source, target = make_pair(config)
    positive = EvidenceProposal(0, source, target, SynapseScope.LOCAL, 1.0, 1)
    aggregated, conflicts = aggregate_evidence((positive,), RootEvidenceLedger(0))
    first = apply_learning(network.snapshot(), aggregated, conflicts, network.topology, config)
    assert len(first.new_edges) == 1
    # Creation semantics are fixed regardless of threshold values.
    created = Synapse(target, 1.0, 1.0, SynapseState.CANDIDATE, SynapseScope.LOCAL)
    network.seed_synapse(source, created)
    later = EvidenceProposal(1, source, target, SynapseScope.LOCAL, 1.0, 1)
    aggregated, conflicts = aggregate_evidence((later,), RootEvidenceLedger(1))
    second = apply_learning(network.snapshot(), aggregated, conflicts, network.topology, config)
    assert second.existing_updates[(source, target, SynapseScope.LOCAL)].state is SynapseState.CONSOLIDATED


def test_temporal_kernel_horizon() -> None:
    config = CoreConfig(alpha=0.5, temporal_horizon=2)
    from dgca_lite.learning import temporal_kernel

    assert temporal_kernel(1, config) == pytest.approx(exp(-0.5))
    assert temporal_kernel(3, config) == 0
