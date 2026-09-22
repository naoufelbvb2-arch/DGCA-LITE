from dgca_lite.config import CoreConfig
from dgca_lite.learning import LearningResult, NewEdgeProposal
from dgca_lite.model import (
    Assembly,
    Cell,
    RecruitmentProposal,
    SparseSignature,
    Synapse,
    SynapseScope,
    SynapseState,
    TemporalEvent,
    Territory,
)
from dgca_lite.network import SparseNetwork
from dgca_lite.resources import (
    allocate_expansion,
    arbitrate_synapses,
    compute_novelty,
    ordinary_recruitment,
    reclaimable_cells,
)


def empty_learning(*new_edges: NewEdgeProposal) -> LearningResult:
    return LearningResult({}, tuple(new_edges), frozenset(), frozenset(), 0, 0, 0)


def test_surface_familiarity_is_drive_weighted_receptor_coverage() -> None:
    config = CoreConfig()
    network = SparseNetwork(config)
    network.seed_cell(Cell(1, Territory.LANGUAGE, True, 0, 4))
    novelty = compute_novelty(network.snapshot(), {1: 0.75, 2: 0.25}, (), config)
    assert novelty.surface_familiarity == 0.75
    assert novelty.context_compatibility == 1.0
    assert novelty.novelty == 0.25


def test_empty_reuse_has_maximal_novelty() -> None:
    config = CoreConfig()
    novelty = compute_novelty(SparseNetwork(config).snapshot(), {1: 1.0}, (), config)
    assert novelty.surface_familiarity == 0
    assert novelty.context_compatibility == 1
    assert novelty.novelty == 1


def test_context_compatibility_uses_associative_edges_only() -> None:
    config = CoreConfig(E_max=1, associative_radius=10)
    network = SparseNetwork(config)
    source = 1
    target = network.topology.neighborhood(source, SynapseScope.ASSOCIATIVE)[0]
    for cell_id in (source, target):
        network.seed_cell(Cell(cell_id, Territory.LANGUAGE, True, 0, 4))
    network.seed_synapse(
        source,
        Synapse(target, 1, 1, SynapseState.CONSOLIDATED, SynapseScope.ASSOCIATIVE),
    )
    network.tick = 1
    event = TemporalEvent(0, ((source, 1.0),), SparseSignature((b"x",), ()), ())
    novelty = compute_novelty(network.snapshot(), {target: 1.0}, (event,), config)
    assert 0 < novelty.context_compatibility < 1


def test_familiar_surface_in_incompatible_context_is_novel() -> None:
    config = CoreConfig(E_max=1, associative_radius=10)
    network = SparseNetwork(config)
    source = 1
    target = network.topology.neighborhood(source, SynapseScope.ASSOCIATIVE)[0]
    for cell_id in (source, target):
        network.seed_cell(Cell(cell_id, Territory.LANGUAGE, True, 0, 4))
    network.tick = 1
    event = TemporalEvent(0, ((source, 1.0),), SparseSignature((b"x",), ()), ())
    novelty = compute_novelty(network.snapshot(), {target: 1.0}, (event,), config)
    assert novelty.surface_familiarity == 1
    assert novelty.context_compatibility == 0
    assert novelty.novelty == 1


def test_ordinary_recruitment_is_ranked_and_bounded() -> None:
    config = CoreConfig(K_R=2, theta_R=0)
    network = SparseNetwork(config)
    result = ordinary_recruitment(
        network.snapshot(), {4: 0.4, 2: 0.9, 3: 0.9}, 1.0, config
    )
    assert result == (
        RecruitmentProposal(2, 0.9, False),
        RecruitmentProposal(3, 0.9, False),
    )


def test_budget_replacement_requires_strictly_better_quality() -> None:
    config = CoreConfig(E_max=1, theta_prune=0.5, local_radius=5)
    network = SparseNetwork(config)
    source = 1
    targets = network.topology.neighborhood(source, SynapseScope.LOCAL)[:2]
    network.seed_cell(Cell(source, Territory.LANGUAGE, True, 0, 1))
    for target in targets:
        network.seed_cell(Cell(target, Territory.LANGUAGE, True, 0, 4))
    network.seed_synapse(
        source,
        Synapse(targets[0], 0.4, 1, SynapseState.CANDIDATE, SynapseScope.LOCAL),
    )
    equal = empty_learning(NewEdgeProposal(source, targets[1], SynapseScope.LOCAL, 0.4))
    _, _, blocked, accepted, rejected, prunes = arbitrate_synapses(
        network.snapshot(), equal, 1.0, config
    )
    assert accepted == prunes == 0
    assert rejected == len(blocked) == 1
    better = empty_learning(NewEdgeProposal(source, targets[1], SynapseScope.LOCAL, 0.5))
    _, deletes, _, accepted, _, prunes = arbitrate_synapses(
        network.snapshot(), better, 1.0, config
    )
    assert accepted == prunes == 1
    assert (source, targets[0], SynapseScope.LOCAL) in deletes


def test_consolidated_edge_is_never_pruned_for_novelty() -> None:
    config = CoreConfig(E_max=1, theta_prune=1, local_radius=5)
    network = SparseNetwork(config)
    source = 1
    targets = network.topology.neighborhood(source, SynapseScope.LOCAL)[:2]
    network.seed_cell(Cell(source, Territory.LANGUAGE, True, 0, 1))
    for target in targets:
        network.seed_cell(Cell(target, Territory.LANGUAGE, True, 0, 4))
    network.seed_synapse(
        source,
        Synapse(targets[0], 0.01, 0.01, SynapseState.CONSOLIDATED, SynapseScope.LOCAL),
    )
    result = arbitrate_synapses(
        network.snapshot(),
        empty_learning(NewEdgeProposal(source, targets[1], SynapseScope.LOCAL, 1)),
        1,
        config,
    )
    assert result[3] == result[5] == 0
    assert result[4] == 1


def test_pruned_updated_candidate_is_not_reinserted_by_same_transaction() -> None:
    config = CoreConfig(E_max=1, theta_prune=0.5, local_radius=5)
    network = SparseNetwork(config)
    source = 1
    old_target, new_target = network.topology.neighborhood(
        source, SynapseScope.LOCAL
    )[:2]
    network.seed_cell(Cell(source, Territory.LANGUAGE, True, 0, 1))
    for target in (old_target, new_target):
        network.seed_cell(Cell(target, Territory.LANGUAGE, True, 0, 4))
    original = Synapse(
        old_target, 0.4, 1, SynapseState.CANDIDATE, SynapseScope.LOCAL
    )
    network.seed_synapse(source, original)
    updated = Synapse(
        old_target, 0.3, 1, SynapseState.CANDIDATE, SynapseScope.LOCAL
    )
    learning = LearningResult(
        {(source, old_target, SynapseScope.LOCAL): updated},
        (NewEdgeProposal(source, new_target, SynapseScope.LOCAL, 0.9),),
        frozenset(),
        frozenset({tuple(sorted((source, old_target))), tuple(sorted((source, new_target)))}),
        0,
        0,
        0,
    )
    upserts, deletes, _, accepted, _, _ = arbitrate_synapses(
        network.snapshot(), learning, 1, config
    )
    assert accepted == 1
    assert (source, old_target, SynapseScope.LOCAL) in deletes
    assert (source, old_target, SynapseScope.LOCAL) not in upserts


def test_expansion_uses_per_request_bounds_and_round_robin() -> None:
    config = CoreConfig(K_R=4, theta_R=0)
    network = SparseNetwork(config)
    blocked = (
        NewEdgeProposal(1, 2, SynapseScope.LOCAL, 0.9),
        NewEdgeProposal(3, 4, SynapseScope.LOCAL, 0.8),
    )
    reserves = {
        blocked[0].key: ((10, 1.0), (11, 0.9)),
        blocked[1].key: ((20, 1.0), (21, 0.9)),
    }
    result = allocate_expansion(blocked, reserves, network.snapshot(), (), 1.0, config)
    assert [item.cell_id for item in result] == [10, 20, 11, 21]


def test_ordinary_and_expansion_share_one_strict_ceiling() -> None:
    config = CoreConfig(K_R=4, theta_R=0)
    network = SparseNetwork(config)
    request = NewEdgeProposal(1, 2, SynapseScope.LOCAL, 1)
    ordinary = (
        RecruitmentProposal(30, 1, False),
        RecruitmentProposal(31, 1, False),
    )
    expansion = allocate_expansion(
        (request,),
        {request.key: ((10, 1), (11, 0.9), (12, 0.8))},
        network.snapshot(),
        ordinary,
        1,
        config,
    )
    assert len(ordinary) + len(expansion) == config.K_R


def test_reclamation_requires_complete_isolation() -> None:
    config = CoreConfig()
    network = SparseNetwork(config)
    network.seed_cell(Cell(1, Territory.LANGUAGE, True, 0, 4))
    eligible = reclaimable_cells(
        network.snapshot(), {1}, {}, frozenset(), frozenset(), frozenset(), frozenset(), config
    )
    assert eligible == frozenset({1})
    referenced = reclaimable_cells(
        network.snapshot(), {1}, {}, frozenset(), frozenset({1}), frozenset(), frozenset(), config
    )
    assert referenced == frozenset()


def test_reclamation_uses_surviving_transaction_membership() -> None:
    config = CoreConfig(K_min=3)
    network = SparseNetwork(config)
    for cell_id in (1, 2, 3):
        network.seed_cell(Cell(cell_id, Territory.LANGUAGE, True, 0, 4))
    for left, right in ((1, 2), (1, 3), (2, 3)):
        network.seed_synapse(left, Synapse(right, 1, config.E_max, SynapseState.CONSOLIDATED, SynapseScope.LOCAL))
        network.seed_synapse(right, Synapse(left, 1, config.E_max, SynapseState.CONSOLIDATED, SynapseScope.LOCAL))
    network.seed_assembly(Assembly(7, Territory.LANGUAGE, frozenset({1, 2, 3})))
    deletes = frozenset(
        (source, target, SynapseScope.LOCAL)
        for source, target in ((1, 2), (2, 1), (1, 3), (3, 1))
    )
    assert reclaimable_cells(
        network.snapshot(), {1}, {}, deletes, frozenset(), frozenset(),
        frozenset(), config,
    ) == frozenset()
    assert reclaimable_cells(
        network.snapshot(), {1}, {}, deletes, frozenset(), frozenset(),
        frozenset(), config, {}, frozenset({7}),
    ) == frozenset({1})
