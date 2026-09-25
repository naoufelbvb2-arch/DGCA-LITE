from dgca_lite.memory.separation import separate_sources
from dgca_lite.memory.types import FamilyID, SourceID


def test_strict_direct_witness_superset_records_metadata_without_deletion() -> None:
    result = separate_sources(
        {10: frozenset({1}), 20: frozenset({1, 2})},
        {10: frozenset({1, 3}), 20: frozenset({1, 2, 4})},
        frozenset({1, 2}),
    )
    assert result.dominance == ((SourceID.assembly(20), SourceID.assembly(10)),)
    assert result.families[0].sources == (
        SourceID.assembly(10),
        SourceID.assembly(20),
    )
    assert result.families[0].undominated == (SourceID.assembly(20),)


def test_equal_and_incomparable_witnesses_remain_ambiguous() -> None:
    equal = separate_sources(
        {1: frozenset({7}), 2: frozenset({7})},
        {1: frozenset({7, 8}), 2: frozenset({7, 9})},
        frozenset({7}),
    )
    assert equal.dominance == ()
    assert equal.families[0].undominated == (
        SourceID.assembly(1),
        SourceID.assembly(2),
    )
    incomparable = separate_sources(
        {1: frozenset({7}), 2: frozenset({7})},
        {1: frozenset({7, 8}), 2: frozenset({7, 9})},
        frozenset({8, 9}),
    )
    assert incomparable.dominance == ()


def test_internal_only_session_has_no_dominance() -> None:
    result = separate_sources(
        {1: frozenset({7}), 2: frozenset({7})},
        {1: frozenset({7, 8}), 2: frozenset({7, 8, 9})},
        frozenset(),
    )
    assert result.dominance == ()


def test_family_connectivity_does_not_create_transitive_dominance() -> None:
    result = separate_sources(
        {
            1: frozenset({2}),
            2: frozenset({2, 3}),
            3: frozenset({3}),
        },
        {
            1: frozenset({0, 2}),
            2: frozenset({2, 3}),
            3: frozenset({3}),
        },
        frozenset({0}),
    )
    assert result.families[0].family_id == FamilyID((1, 2, 3))
    assert (SourceID.assembly(1), SourceID.assembly(2)) in result.dominance
    assert (SourceID.assembly(1), SourceID.assembly(3)) not in result.dominance


def test_reconstructed_overlap_cannot_create_seed_competition() -> None:
    result = separate_sources(
        {1: frozenset({1}), 2: frozenset({2})},
        {1: frozenset({1, 9}), 2: frozenset({2, 9})},
        frozenset({1}),
    )
    assert tuple(family.family_id for family in result.families) == (
        FamilyID((1,)),
        FamilyID((2,)),
    )
    assert result.dominance == ()


def test_giant_bounded_overlap_is_deterministic() -> None:
    count = 32
    seeds = {assembly_id: frozenset({0}) for assembly_id in range(count)}
    members = {
        assembly_id: frozenset({0, assembly_id + 1})
        for assembly_id in range(count)
    }
    left = separate_sources(seeds, members, frozenset({0}))
    right = separate_sources(
        dict(reversed(tuple(seeds.items()))),
        dict(reversed(tuple(members.items()))),
        frozenset({0}),
    )
    assert left == right
    assert left.families[0].family_id == FamilyID(tuple(range(count)))
    assert left.dominance == ()
