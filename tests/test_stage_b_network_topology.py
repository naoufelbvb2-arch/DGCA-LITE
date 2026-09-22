from dataclasses import FrozenInstanceError

import pytest

from dgca_lite.config import CoreConfig
from dgca_lite.model import (
    Cell,
    Synapse,
    SynapseScope,
    SynapseState,
    Territory,
    TickTransaction,
)
from dgca_lite.network import SparseNetwork
from dgca_lite.topology import Topology


def test_million_capacity_is_implicit() -> None:
    network = SparseNetwork(CoreConfig())
    assert network.config.logical_capacity == 1_000_000
    assert network.materialized_cell_count == 0


def test_topology_is_deterministic_and_bounded() -> None:
    topology = Topology(CoreConfig(max_neighborhood=20))
    assert topology.position(17) == topology.position(17)
    neighbors = topology.neighborhood(17, SynapseScope.LOCAL)
    assert len(neighbors) <= 20
    assert all(topology.territory(item) is Territory.LANGUAGE for item in neighbors)


def test_snapshot_records_are_immutable() -> None:
    network = SparseNetwork(CoreConfig())
    network.seed_cell(Cell(1, Territory.LANGUAGE, True, 0.2, 4))
    snapshot = network.snapshot()
    with pytest.raises(FrozenInstanceError):
        snapshot.cells[1].activation = 1.0  # type: ignore[misc]


def test_directed_scoped_identity_and_budget() -> None:
    config = CoreConfig(default_synaptic_budget=2, local_radius=3)
    network = SparseNetwork(config)
    topology = network.topology
    source = 1
    targets = topology.neighborhood(source, SynapseScope.LOCAL)[:2]
    for cell_id in (source, *targets):
        network.seed_cell(Cell(cell_id, Territory.LANGUAGE, True, 0.0, 2))
    for target in targets:
        network.seed_synapse(
            source,
            Synapse(target, 1.0, 1.0, SynapseState.CANDIDATE, SynapseScope.LOCAL),
        )
    assert network.synapse_count == 2
    extra = topology.neighborhood(source, SynapseScope.LOCAL)[2]
    network.seed_cell(Cell(extra, Territory.LANGUAGE, True, 0.0, 2))
    with pytest.raises(ValueError):
        network.seed_synapse(
            source,
            Synapse(extra, 1.0, 1.0, SynapseState.CANDIDATE, SynapseScope.LOCAL),
        )


def test_stale_transaction_rejected_without_mutation() -> None:
    network = SparseNetwork(CoreConfig())
    tx = TickTransaction(base_version=1, cell_commits={1})
    with pytest.raises(RuntimeError):
        network.commit(tx)
    assert network.materialized_cell_count == 0


def test_atomic_validation_prevents_partial_commit() -> None:
    network = SparseNetwork(CoreConfig())
    tx = TickTransaction(base_version=0, cell_commits={1}, next_activation={1: 2.0})
    with pytest.raises(ValueError):
        network.commit(tx)
    assert network.materialized_cell_count == 0
    assert network.version == 0
