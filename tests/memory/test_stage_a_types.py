from dataclasses import FrozenInstanceError

import pytest

from dgca_lite.memory.config import MemoryConfig
from dgca_lite.memory.types import (
    BranchID,
    FailureCode,
    FamilyID,
    FrozenFloatMap,
    RetrievalFailure,
    SeedState,
    SeedValue,
    SourceID,
    immutable_value_tree,
)


def test_typed_source_identity_cannot_alias() -> None:
    assert SourceID.assembly(12) != SourceID.atomic(12)
    assert SourceID.assembly(12).as_tuple() == ("ASM", 12)
    assert SourceID.atomic(12).as_tuple() == ("ATOM", 12)
    assert SourceID.assembly(12).canonical_key() < SourceID.atomic(12).canonical_key()


def test_family_and_branch_identity_are_canonical() -> None:
    family = FamilyID((2, 5, 9))
    branch = BranchID(SourceID.atomic(7), 3)
    assert family.as_tuple() == ("FAM", (2, 5, 9))
    assert branch.as_tuple() == (("ATOM", 7), ("ASM", 3))
    with pytest.raises(ValueError):
        FamilyID((5, 2))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"K_C": 0},
        {"K_C": True},
        {"theta_PC": 0},
        {"theta_PC": float("nan")},
        {"theta_AR": float("inf")},
        {"theta_AR": 1.1},
        {"max_snapshot_cells": 0},
    ],
)
def test_invalid_layer2_config_is_rejected(kwargs) -> None:
    with pytest.raises(ValueError):
        MemoryConfig(**kwargs)


def test_seed_state_and_maps_are_immutable_and_sorted() -> None:
    seeds = SeedState.from_dict({8: SeedValue(0.5, False), 3: SeedValue(1.0, True)})
    cue = FrozenFloatMap.from_dict({8: 0.5, 3: 1.0})
    assert tuple(cell_id for cell_id, _ in seeds.entries) == (3, 8)
    assert tuple(cell_id for cell_id, _ in cue.entries) == (3, 8)
    assert immutable_value_tree(seeds)
    with pytest.raises(FrozenInstanceError):
        seeds.entries = ()  # type: ignore[misc]


def test_failure_record_is_immutable() -> None:
    failure = RetrievalFailure(FailureCode.INVALID_CUE, "invalid")
    assert immutable_value_tree(failure)
    with pytest.raises(FrozenInstanceError):
        failure.detail = "changed"  # type: ignore[misc]
