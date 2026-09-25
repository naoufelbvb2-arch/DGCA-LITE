from math import nextafter

import pytest

from dgca_lite.memory.association import retrieve_associations
from dgca_lite.memory.types import (
    CapturedAssembly,
    CapturedCell,
    CapturedSynapse,
    FrozenParameters,
    RetrievalSnapshot,
    SourceActivity,
    SourceID,
)
from dgca_lite.model import SynapseScope, SynapseState, Territory


def parameters(theta_ar: float = 0.5) -> FrozenParameters:
    return FrozenParameters("x", 0.1, 0.1, 16, 4, 1.0, 64, 0.5, theta_ar)


def edge(
    source: int,
    target: int,
    quality: float,
    *,
    state: SynapseState = SynapseState.CONSOLIDATED,
    scope: SynapseScope = SynapseScope.ASSOCIATIVE,
) -> CapturedSynapse:
    return CapturedSynapse(source, target, quality, 1.0, state, scope)


def snapshot(
    edges,
    memberships=(),
    assemblies=(),
) -> RetrievalSnapshot:
    cell_ids = {
        item
        for relation in edges
        for item in (relation.source_id, relation.target_id)
    }
    return RetrievalSnapshot(
        0,
        0,
        tuple(CapturedCell(item, Territory.LANGUAGE, True, 0.0, 64) for item in sorted(cell_ids)),
        tuple(assemblies),
        tuple(sorted(memberships)),
        (),
        tuple(edges),
    )


def activity(source_id: SourceID, values) -> SourceActivity:
    ordered = tuple(sorted(values))
    return SourceActivity(
        source_id,
        tuple(item[0] for item in ordered),
        tuple((cell_id, drive) for cell_id, drive, _ in ordered),
        tuple((cell_id, exact) for cell_id, _, exact in ordered),
    )


def test_only_forward_consolidated_associative_edges_participate() -> None:
    source = activity(SourceID.assembly(1), ((0, 1.0, True),))
    captured = snapshot(
        (
            edge(0, 10, 0.8),
            edge(0, 11, 1.0, state=SynapseState.CANDIDATE),
            edge(0, 12, 1.0, scope=SynapseScope.CROSS_TERRITORY),
            edge(13, 0, 1.0),
        )
    )
    result = retrieve_associations((source,), captured, parameters())
    assert tuple(hit.cell_id for hit in result.direct_hits) == (10,)


def test_associative_threshold_equality_and_adjacent_failure() -> None:
    threshold = 0.5
    below = nextafter(threshold, 0.0)
    while 1.0 - below <= 1.0 - threshold:
        below = nextafter(below, 0.0)
    source = activity(SourceID.atomic(0), ((0, 1.0, True),))
    result = retrieve_associations(
        (source,), snapshot((edge(0, 10, threshold), edge(0, 11, below))), parameters(threshold)
    )
    assert tuple(hit.cell_id for hit in result.direct_hits) == (10,)


def test_theta_one_requires_exact_one_associative_provenance() -> None:
    captured = snapshot((edge(0, 10, 1.0),))
    exact = retrieve_associations(
        (activity(SourceID.atomic(0), ((0, 1.0, True),)),),
        captured,
        parameters(1.0),
    )
    numeric = retrieve_associations(
        (activity(SourceID.atomic(0), ((0, 1.0, False),)),),
        captured,
        parameters(1.0),
    )
    assert exact.direct_hits[0].exact_one is True
    assert numeric.direct_hits == ()


def test_underflow_does_not_create_exact_one() -> None:
    count = 64
    sources = tuple((item, 0.999999, False) for item in range(count))
    captured = snapshot(tuple(edge(item, 100, 0.999999) for item in range(count)))
    result = retrieve_associations(
        (activity(SourceID.assembly(1), sources),), captured, parameters(1.0)
    )
    assert result.direct_hits == ()


def test_many_weak_contributors_combine_in_canonical_order() -> None:
    source = activity(
        SourceID.assembly(1),
        ((2, 0.5, False), (0, 0.5, False), (1, 0.5, False)),
    )
    captured = snapshot((edge(2, 9, 0.4), edge(0, 9, 0.4), edge(1, 9, 0.4)))
    result = retrieve_associations((source,), captured, parameters(0.48))
    hit = result.direct_hits[0]
    assert hit.supporters == (0, 1, 2)
    assert hit.drive == pytest.approx(1.0 - 0.8**3)


def test_atomic_source_to_unassembled_target_is_preserved() -> None:
    source = activity(SourceID.atomic(0), ((0, 1.0, True),))
    result = retrieve_associations(
        (source,), snapshot((edge(0, 9, 1.0),)), parameters()
    )
    assert tuple(hit.cell_id for hit in result.direct_hits) == (9,)
    assert result.branch_seeds == ()


def test_generic_target_hub_produces_every_membership_branch() -> None:
    source = activity(SourceID.atomic(0), ((0, 1.0, True),))
    assemblies = tuple(
        CapturedAssembly(
            assembly_id,
            Territory.LANGUAGE,
            (10, 20 + 2 * assembly_id, 21 + 2 * assembly_id),
        )
        for assembly_id in range(4)
    )
    captured = snapshot(
        (edge(0, 10, 0.5),),
        ((10, (0, 1, 2, 3)),),
        assemblies,
    )
    result = retrieve_associations((source,), captured, parameters(0.5))
    assert len(result.direct_hits) == 1
    assert tuple(item[0].target_assembly_id for item in result.branch_seeds) == (
        0,
        1,
        2,
        3,
    )
    assert result.direct_hits[0].drive == 0.5


def test_multiple_seeds_into_one_target_assembly_form_one_branch() -> None:
    target = CapturedAssembly(7, Territory.LANGUAGE, (10, 11, 12))
    source = activity(SourceID.atomic(0), ((0, 1.0, True), (1, 1.0, True)))
    captured = snapshot(
        (edge(0, 10, 1.0), edge(1, 11, 0.8)),
        ((10, (7,)), (11, (7,))),
        (target,),
    )
    result = retrieve_associations((source,), captured, parameters())
    assert len(result.branch_seeds) == 1
    assert tuple(cell_id for cell_id, _ in result.branch_seeds[0][1].entries) == (10, 11)


def test_multiple_sources_to_same_target_assembly_remain_distinct() -> None:
    target = CapturedAssembly(7, Territory.LANGUAGE, (10, 11, 12))
    sources = (
        activity(SourceID.assembly(1), ((0, 1.0, True),)),
        activity(SourceID.atomic(1), ((1, 1.0, True),)),
    )
    captured = snapshot(
        (edge(0, 10, 1.0), edge(1, 10, 1.0)),
        ((10, (7,)),),
        (target,),
    )
    result = retrieve_associations(sources, captured, parameters())
    assert len(result.branch_seeds) == 2
    assert result.branch_seeds[0][0] != result.branch_seeds[1][0]


def test_association_is_invariant_to_source_and_edge_insertion_order() -> None:
    sources = (
        activity(SourceID.atomic(0), ((0, 0.8, False),)),
        activity(SourceID.atomic(1), ((1, 0.9, False),)),
    )
    edges = (edge(0, 10, 0.8), edge(1, 11, 0.8))
    left = retrieve_associations(sources, snapshot(edges), parameters())
    right = retrieve_associations(tuple(reversed(sources)), snapshot(tuple(reversed(edges))), parameters())
    assert left == right
