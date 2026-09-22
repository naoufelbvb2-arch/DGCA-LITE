import random

import pytest

from dgca_lite.activation import compute_activation, effective_quality, scoped_quality
from dgca_lite.config import CoreConfig
from dgca_lite.model import Cell, Synapse, SynapseScope, SynapseState, Territory
from dgca_lite.network import SparseNetwork


def edge(target: int, strength: float, evidence: float, scope=SynapseScope.LOCAL) -> Synapse:
    return Synapse(target, strength, evidence, SynapseState.CANDIDATE, scope)


def test_quality_uses_evidence_confidence() -> None:
    config = CoreConfig(E_max=10)
    assert scoped_quality(edge(2, 1.0, 1.0), config) == pytest.approx(0.1)


def test_multiple_scopes_combine_once() -> None:
    config = CoreConfig(E_max=10)
    edges = [edge(2, 1, 5, SynapseScope.LOCAL), edge(2, 1, 5, SynapseScope.ASSOCIATIVE)]
    assert effective_quality(edges, config) == pytest.approx(0.75)


def test_activation_is_bounded_and_recovers() -> None:
    config = CoreConfig(delta_A=0.5, gamma_A=1.0)
    network = SparseNetwork(config)
    network.seed_cell(Cell(1, Territory.LANGUAGE, True, 0.8, 4))
    result = compute_activation(network.snapshot(), {}, config)
    assert result.next_activation[1] == pytest.approx(0.4)
    assert all(0 <= value <= 1 for value in result.next_activation.values())


def test_supported_inputs_accumulate_without_explosion() -> None:
    config = CoreConfig(E_max=1, theta_emit=0.1, local_radius=3)
    network = SparseNetwork(config)
    target = 1
    sources = network.topology.neighborhood(target, SynapseScope.LOCAL)[:2]
    for cell_id in (target, *sources):
        network.seed_cell(Cell(cell_id, Territory.LANGUAGE, True, 1.0 if cell_id in sources else 0, 4))
    for source in sources:
        network.seed_synapse(source, edge(target, 0.6, 1.0))
    result = compute_activation(network.snapshot(), {}, config)
    assert result.drives[target] == pytest.approx(1 - 0.4 * 0.4)
    assert 0 <= result.next_activation[target] <= 1


def test_boundary_blocks_old_activation_propagation() -> None:
    config = CoreConfig(E_max=1, theta_emit=0.1, local_radius=3)
    network = SparseNetwork(config)
    source = 1
    target = network.topology.neighborhood(source, SynapseScope.LOCAL)[0]
    network.seed_cell(Cell(source, Territory.LANGUAGE, True, 1.0, 4))
    network.seed_cell(Cell(target, Territory.LANGUAGE, True, 0.0, 4))
    network.seed_synapse(source, edge(target, 1.0, 1.0))
    result = compute_activation(network.snapshot(), {}, config, boundary_reset=True)
    assert result.emission_frontier == frozenset()
    assert result.next_activation[source] == 0
    assert target not in result.next_activation or result.next_activation[target] == 0


def test_insertion_order_does_not_change_activation() -> None:
    config = CoreConfig(E_max=1, theta_emit=0.1, local_radius=4)
    source = 10
    targets = SparseNetwork(config).topology.neighborhood(source, SynapseScope.LOCAL)[:3]
    states = []
    for seed in range(4):
        network = SparseNetwork(config)
        ids = [source, *targets]
        random.Random(seed).shuffle(ids)
        for cell_id in ids:
            network.seed_cell(Cell(cell_id, Territory.LANGUAGE, True, 1.0 if cell_id == source else 0.0, 8))
        edges = [edge(target, 0.4 + index * 0.1, 1.0) for index, target in enumerate(targets)]
        random.Random(seed).shuffle(edges)
        for item in edges:
            network.seed_synapse(source, item)
        states.append(dict(compute_activation(network.snapshot(), {}, config).next_activation))
    assert all(state == states[0] for state in states)


def test_logical_capacity_does_not_change_fixed_frontier_result() -> None:
    outputs = []
    for capacity in (300, 1_000_000):
        config = CoreConfig(logical_capacity=capacity)
        network = SparseNetwork(config)
        network.seed_cell(Cell(1, Territory.LANGUAGE, True, 0.4, 4))
        outputs.append(compute_activation(network.snapshot(), {}, config).next_activation[1])
    assert outputs[0] == outputs[1]
