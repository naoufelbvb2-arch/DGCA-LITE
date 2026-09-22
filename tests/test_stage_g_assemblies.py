import pytest

from dgca_lite.assemblies import (
    StructuralOverlay,
    cohesion,
    mean_reciprocal,
    process_assemblies,
)
from dgca_lite.config import CoreConfig
from dgca_lite.model import (
    Assembly,
    Cell,
    Synapse,
    SynapseScope,
    SynapseState,
    Territory,
)
from dgca_lite.network import SparseNetwork


def make_network(config: CoreConfig, ids=(0, 1, 2, 3)) -> SparseNetwork:
    network = SparseNetwork(config)
    for cell_id in ids:
        network.seed_cell(Cell(cell_id, Territory.LANGUAGE, True, 0, 16))
    return network


def consolidated(target: int, scope=SynapseScope.LOCAL, quality=1.0) -> Synapse:
    return Synapse(target, quality, 1.0, SynapseState.CONSOLIDATED, scope)


def reciprocal(upserts: dict, left: int, right: int, scope=SynapseScope.LOCAL) -> None:
    upserts[(left, right, scope)] = consolidated(right, scope)
    upserts[(right, left, scope)] = consolidated(left, scope)


def seed_reciprocal(network: SparseNetwork, left: int, right: int) -> None:
    network.seed_synapse(left, consolidated(right))
    network.seed_synapse(right, consolidated(left))


def test_connected_reciprocal_triangle_forms_once() -> None:
    config = CoreConfig(
        E_max=1, local_radius=3, assembly_radius=3, K_min=3, K_max=8,
        d_min=2, rho=1, theta_A=0.5,
    )
    network = make_network(config, (0, 1, 2))
    upserts = {}
    for left, right in ((0, 1), (0, 2), (1, 2)):
        reciprocal(upserts, left, right)
    result = process_assemblies(
        network.snapshot(), upserts, frozenset(), {(0, 1), (0, 2), (1, 2)},
        network.topology, config, 0,
    )
    assert result.formed == 1
    assert result.upserts[0].members == frozenset({0, 1, 2})
    assert result.assembly_seeds == 3


def test_one_strong_pair_cannot_form_assembly() -> None:
    config = CoreConfig(E_max=1, local_radius=3, K_min=3, theta_A=0.5)
    network = make_network(config, (0, 1))
    upserts = {}
    reciprocal(upserts, 0, 1)
    result = process_assemblies(
        network.snapshot(), upserts, frozenset(), {(0, 1)}, network.topology, config, 0
    )
    assert result.formed == 0


def test_meanr_and_cohesion_keep_missing_pairs_in_denominator() -> None:
    config = CoreConfig(E_max=1, local_radius=4)
    network = make_network(config)
    upserts = {}
    reciprocal(upserts, 0, 1)
    reciprocal(upserts, 1, 2)
    overlay = StructuralOverlay(network.snapshot(), upserts, frozenset())
    assert cohesion(frozenset({0, 1, 2}), overlay, config) == pytest.approx(2 / 3)
    assert mean_reciprocal(0, frozenset({1, 2, 3}), overlay, config) == pytest.approx(1 / 3)


def test_grow_workset_comes_only_from_delta_local_memberships() -> None:
    config = CoreConfig(
        E_max=1, local_radius=5, specificity_radius=5, assembly_radius=5,
        K_min=3, rho_G=0.5, sigma_G=0.3, rho_keep=0.1, sigma_keep=0.05,
        theta_A=0.5,
    )
    network = make_network(config)
    for left, right in ((0, 1), (0, 2), (1, 2), (3, 1)):
        seed_reciprocal(network, left, right)
    network.seed_assembly(Assembly(7, Territory.LANGUAGE, frozenset({0, 1, 2})))
    upserts = {}
    reciprocal(upserts, 0, 3)
    result = process_assemblies(
        network.snapshot(), upserts, frozenset(), {(0, 3)}, network.topology, config, 8
    )
    assert result.grown == 1
    assert result.upserts[7].members == frozenset({0, 1, 2, 3})


def test_maintain_uses_exact_affected_membership_workset() -> None:
    config = CoreConfig(
        E_max=1, local_radius=5, specificity_radius=5, assembly_radius=5,
        K_min=3, rho_keep=0.4, sigma_keep=0.1, theta_A=0.5,
    )
    network = make_network(config, (0, 1, 2, 3, 4, 5, 6))
    for left, right in ((0, 1), (0, 2), (1, 2), (0, 3), (1, 3), (2, 3)):
        seed_reciprocal(network, left, right)
    for left, right in ((4, 5), (4, 6), (5, 6)):
        seed_reciprocal(network, left, right)
    network.seed_assembly(Assembly(3, Territory.LANGUAGE, frozenset({0, 1, 2, 3})))
    # Unrelated Assembly must not be inspected merely because it exists.
    network.seed_assembly(Assembly(9, Territory.LANGUAGE, frozenset({4, 5, 6})))
    deletes = frozenset(
        (source, target, SynapseScope.LOCAL)
        for source, target in ((3, 0), (0, 3), (3, 1), (1, 3), (3, 2), (2, 3))
    )
    result = process_assemblies(
        network.snapshot(), {}, deletes, {(0, 3), (1, 3), (2, 3)}, network.topology, config, 10
    )
    assert result.maintain_workset == (3,)
    assert result.upserts[3].members == frozenset({0, 1, 2})
    assert 9 not in result.upserts and 9 not in result.deletes


def test_associative_support_cannot_directly_form_membership() -> None:
    config = CoreConfig(E_max=1, associative_radius=5, K_min=3)
    network = make_network(config, (0, 1, 2))
    upserts = {}
    for left, right in ((0, 1), (0, 2), (1, 2)):
        reciprocal(upserts, left, right, SynapseScope.ASSOCIATIVE)
    result = process_assemblies(
        network.snapshot(), upserts, frozenset(), {(0, 1), (0, 2), (1, 2)},
        network.topology, config, 0,
    )
    assert result.delta_local == frozenset()
    assert result.formed == 0


def test_form_frontier_fails_closed_instead_of_truncating() -> None:
    config = CoreConfig(
        E_max=1, local_radius=5, assembly_radius=5, K_min=3, K_max=3,
        d_min=1, rho=0.5, theta_A=0.5,
    )
    network = make_network(config)
    upserts = {}
    for left, right in ((0, 1), (1, 2), (2, 3)):
        reciprocal(upserts, left, right)
    result = process_assemblies(
        network.snapshot(), upserts, frozenset(), {(0, 1), (1, 2), (2, 3)},
        network.topology, config, 0,
    )
    assert result.formed == 0
