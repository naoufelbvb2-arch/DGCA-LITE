from math import nextafter

import pytest

from dgca_lite.memory.acquisition import acquire
from dgca_lite.memory.config import MemoryConfig
from dgca_lite.memory.reconstruction import (
    build_reconstruction_graph,
    reconstruct_pattern,
)
from dgca_lite.memory.types import (
    ReciprocalLink,
    ReconstructionGraph,
    SeedState,
    SeedValue,
)
from dgca_lite.model import SynapseScope

from .helpers import candidate, retrieval_core


def graph(members, links) -> ReconstructionGraph:
    return ReconstructionGraph(
        0,
        tuple(sorted(members)),
        tuple(ReciprocalLink(min(a, b), max(a, b), quality) for a, b, quality in links),
    )


def seeds(values) -> SeedState:
    return SeedState.from_dict(
        {
            cell_id: SeedValue(drive, exact)
            for cell_id, drive, exact in values
        }
    )


def test_seed_magnitude_changes_reconstruction_and_no_support_stops() -> None:
    assembly = graph((0, 1), ((0, 1, 1.0),))
    weak = reconstruct_pattern(assembly, seeds(((0, 0.4, False),)), 0.5)
    strong = reconstruct_pattern(assembly, seeds(((0, 0.6, False),)), 0.5)
    assert weak.admitted_cells == (0,)
    assert strong.admitted_cells == (0, 1)
    assert strong.drive_map()[1] == pytest.approx(0.6)
    isolated = reconstruct_pattern(graph((0, 1), ()), seeds(((0, 1.0, True),)), 0.1)
    assert isolated.admitted_cells == (0,)


def test_threshold_equality_is_inclusive_with_adjacent_values() -> None:
    threshold = 0.5
    below_quality = nextafter(threshold, 0.0)
    while 1.0 - below_quality <= 1.0 - threshold:
        below_quality = nextafter(below_quality, 0.0)
    exact = reconstruct_pattern(
        graph((0, 1), ((0, 1, threshold),)),
        seeds(((0, 1.0, True),)),
        threshold,
    )
    below = reconstruct_pattern(
        graph((0, 1), ((0, 1, below_quality),)),
        seeds(((0, 1.0, True),)),
        threshold,
    )
    assert exact.admitted_cells == (0, 1)
    assert below.admitted_cells == (0,)


def test_theta_one_requires_exact_one_provenance() -> None:
    assembly = graph((0, 1), ((0, 1, 1.0),))
    exact = reconstruct_pattern(assembly, seeds(((0, 1.0, True),)), 1.0)
    numeric_only = reconstruct_pattern(assembly, seeds(((0, 1.0, False),)), 1.0)
    assert exact.exact_one_map()[1] is True
    assert exact.drive_map()[1] == 1.0
    assert numeric_only.admitted_cells == (0,)


def test_underflow_cannot_manufacture_exact_one() -> None:
    supporters = tuple(range(64))
    target = 64
    assembly = graph(
        (*supporters, target),
        tuple((source, target, 0.999999) for source in supporters),
    )
    seed = seeds(tuple((source, 0.999999, False) for source in supporters))
    result = reconstruct_pattern(assembly, seed, 1.0)
    assert target not in result.admitted_cells


def test_synchronous_admission_and_freeze_on_admission() -> None:
    assembly = graph(
        (0, 1, 2),
        ((0, 1, 1.0), (0, 2, 1.0), (1, 2, 1.0)),
    )
    result = reconstruct_pattern(assembly, seeds(((0, 0.6, False),)), 0.5)
    assert dict(result.admission_rounds) == {0: 0, 1: 1, 2: 1}
    assert result.drive_map()[1] == pytest.approx(0.6)
    assert result.drive_map()[2] == pytest.approx(0.6)


def test_chain_uses_incremental_rounds_and_terminates_on_cycle() -> None:
    assembly = graph(
        (0, 1, 2, 3),
        ((0, 1, 1.0), (1, 2, 1.0), (2, 3, 1.0), (3, 0, 0.4)),
    )
    result = reconstruct_pattern(assembly, seeds(((0, 1.0, True),)), 0.9)
    assert dict(result.admission_rounds) == {0: 0, 1: 1, 2: 2, 3: 3}
    assert result.admitted_cells == (0, 1, 2, 3)


def test_candidate_and_one_direction_local_edges_are_excluded() -> None:
    core = retrieval_core()
    core.network.outgoing[0][(1, SynapseScope.LOCAL)] = candidate(1)
    universe = acquire(core, {0: 1.0}, MemoryConfig())
    built = build_reconstruction_graph(universe.snapshot, 0, universe.parameters)
    assert not any({link.left, link.right} == {0, 1} for link in built.links)

    core = retrieval_core()
    del core.network.outgoing[1][(0, SynapseScope.LOCAL)]
    universe = acquire(core, {0: 1.0}, MemoryConfig())
    built = build_reconstruction_graph(universe.snapshot, 0, universe.parameters)
    assert not any({link.left, link.right} == {0, 1} for link in built.links)


def test_graph_build_and_reconstruction_are_order_invariant() -> None:
    links = ((0, 1, 0.8), (1, 2, 0.8), (0, 2, 0.8))
    left = graph((0, 1, 2), links)
    right = graph((2, 1, 0), tuple(reversed(links)))
    seed = seeds(((0, 0.8, False),))
    assert reconstruct_pattern(left, seed, 0.5) == reconstruct_pattern(right, seed, 0.5)


def test_maximal_calibrated_assembly_remains_bounded() -> None:
    size = 64
    assembly = graph(
        tuple(range(size)),
        tuple((cell_id, cell_id + 1, 1.0) for cell_id in range(size - 1)),
    )
    result = reconstruct_pattern(assembly, seeds(((0, 1.0, True),)), 1.0)
    assert len(result.admitted_cells) == size
    assert max(dict(result.admission_rounds).values()) == size - 1
