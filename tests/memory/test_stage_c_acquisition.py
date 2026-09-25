from dataclasses import replace
from math import inf, nextafter

import pytest

from dgca_lite import CoreConfig, CoreEngine, SurfaceEvent
from dgca_lite.memory.acquisition import acquire
from dgca_lite.memory.config import MemoryConfig
from dgca_lite.memory.integration import TrustedCoreAdapter
from dgca_lite.memory.session import retrieve_internal
from dgca_lite.memory.types import (
    FailureCode,
    RetrievalAbort,
    RetrievalFailure,
    RetrievalResult,
)
from dgca_lite.model import (
    Assembly,
    Cell,
    SynapseScope,
    Territory,
    TickTransaction,
)

from .helpers import consolidated, retrieval_core, seed_pair


def test_internal_acquisition_materializes_complete_bounded_closure() -> None:
    core = retrieval_core()
    universe = acquire(core, {0: 1.0}, MemoryConfig())
    assert universe.authorized_ids == ()
    assert tuple(item.id for item in universe.snapshot.assemblies) == (0, 1)
    assert {(edge.source_id, edge.target_id) for edge in universe.snapshot.associative_synapses} == {
        (0, 3)
    }
    assert universe.snapshot is not core.network.snapshot()


@pytest.mark.parametrize(
    "cue",
    [
        {0: 0.0},
        {0: -0.1},
        {0: 1.1},
        {0: float("nan")},
        {0: float("inf")},
        {0: float("-inf")},
        {299: 1.0},
        {500: 1.0},
    ],
)
def test_invalid_internal_cues_fail_closed(cue) -> None:
    with pytest.raises(RetrievalAbort) as caught:
        acquire(retrieval_core(), cue, MemoryConfig())
    assert caught.value.code is FailureCode.INVALID_CUE


def test_empty_and_overflow_cues_do_not_truncate() -> None:
    core = retrieval_core()
    with pytest.raises(RetrievalAbort) as empty:
        acquire(core, {}, MemoryConfig())
    assert empty.value.code is FailureCode.EMPTY_CUE
    with pytest.raises(RetrievalAbort) as overflow:
        acquire(core, {0: 1.0, 1: 0.9}, MemoryConfig(K_C=1))
    assert overflow.value.code is FailureCode.CUE_CAPACITY_ABORT


def test_trusted_cue_is_complete_and_overrides_internal_collision() -> None:
    core = CoreEngine(CoreConfig(receptor_fanout=1, K_R=32))
    TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("x"))
    trusted = TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("x"))
    frontier = trusted.receipt.learning_frontier
    assert frontier
    internal = {cell_id: 0.01 for cell_id in frontier}
    universe = acquire(core, internal, MemoryConfig(K_C=128), trusted.receipt)
    assert universe.authorized_ids == frontier
    assert universe.trusted_cue == universe.merged_cue
    assert universe.merged_cue.entries == trusted.receipt.activation.entries


def test_snapshot_is_independent_of_later_core_changes() -> None:
    core = retrieval_core()
    universe = acquire(core, {0: 1.0}, MemoryConfig())
    before = universe.snapshot
    core.network.seed_cell(Cell(20, Territory.LANGUAGE, True, 0.0, 4))
    assert universe.snapshot == before
    assert 20 not in universe.snapshot.cell_map()


def test_snapshot_capacity_aborts_without_partial_fallback() -> None:
    with pytest.raises(RetrievalAbort) as caught:
        acquire(
            retrieval_core(),
            {0: 1.0},
            MemoryConfig(max_snapshot_assemblies=1),
        )
    assert caught.value.code is FailureCode.SNAPSHOT_CAPACITY_ABORT


def test_corrupt_membership_index_fails_closed() -> None:
    core = retrieval_core()
    core.network.memberships[0] = frozenset({999})
    with pytest.raises(RetrievalAbort) as caught:
        acquire(core, {0: 1.0}, MemoryConfig())
    assert caught.value.code is FailureCode.SNAPSHOT_ABORTED


def test_duplicate_membership_entries_fail_closed() -> None:
    core = retrieval_core()
    core.network.memberships[0] = (0, 0)  # type: ignore[assignment]
    with pytest.raises(RetrievalAbort) as caught:
        acquire(core, {0: 1.0}, MemoryConfig())
    assert caught.value.code is FailureCode.SNAPSHOT_ABORTED


def test_existing_assembly_that_does_not_contain_indexed_cell_fails_closed() -> None:
    core = retrieval_core()
    core.network.memberships[6] = frozenset({0})
    with pytest.raises(RetrievalAbort) as caught:
        acquire(core, {6: 1.0}, MemoryConfig())
    assert caught.value.code is FailureCode.SNAPSHOT_ABORTED
    outcome = retrieve_internal(core, {6: 1.0}, MemoryConfig())
    assert isinstance(outcome, RetrievalFailure)
    assert outcome.code is FailureCode.SNAPSHOT_ABORTED


def test_captured_assembly_member_missing_reverse_index_fails_closed() -> None:
    core = retrieval_core()
    core.network.memberships[0] = frozenset()
    with pytest.raises(RetrievalAbort) as caught:
        acquire(core, {1: 1.0}, MemoryConfig())
    assert caught.value.code is FailureCode.SNAPSHOT_ABORTED


def test_valid_overlapping_memberships_succeed() -> None:
    core = retrieval_core()
    for member in (0, 1):
        seed_pair(core, member, 6)
    core.network.seed_assembly(
        Assembly(2, Territory.LANGUAGE, frozenset({0, 1, 6}))
    )
    universe = acquire(core, {0: 1.0}, MemoryConfig())
    assert universe.snapshot.membership_map()[0] == (0, 2)
    assert {item.id for item in universe.snapshot.assemblies} >= {0, 2}


def _assert_membership_snapshot_aborted(core, cue: dict[int, float]) -> None:
    with pytest.raises(RetrievalAbort) as caught:
        acquire(core, cue, MemoryConfig())
    assert caught.value.code is FailureCode.SNAPSHOT_ABORTED
    outcome = retrieve_internal(core, cue, MemoryConfig())
    assert isinstance(outcome, RetrievalFailure)
    assert outcome.code is FailureCode.SNAPSHOT_ABORTED


@pytest.mark.parametrize(
    "membership",
    [
        None,
        frozenset({1, "2"}),
        frozenset({True}),
        frozenset({1.0}),
        frozenset({"1"}),
    ],
    ids=("none", "heterogeneous", "bool-alias", "float", "string"),
)
def test_malformed_source_membership_state_fails_as_snapshot_aborted(
    membership,
) -> None:
    core = retrieval_core()
    core.network.memberships[3] = membership  # type: ignore[assignment]
    _assert_membership_snapshot_aborted(core, {3: 1.0})


@pytest.mark.parametrize(
    "membership",
    [
        None,
        frozenset({1, "2"}),
        frozenset({True}),
        frozenset({0}),
        frozenset({999}),
    ],
    ids=(
        "none",
        "heterogeneous",
        "bool-alias",
        "existing-assembly-without-target",
        "nonexistent-assembly",
    ),
)
def test_malformed_target_membership_state_fails_as_snapshot_aborted(
    membership,
) -> None:
    core = retrieval_core()
    core.network.memberships[3] = membership  # type: ignore[assignment]
    _assert_membership_snapshot_aborted(core, {0: 1.0})


def test_target_assembly_member_missing_reverse_membership_fails_closed() -> None:
    core = retrieval_core()
    core.network.seed_synapse(
        1, consolidated(4, SynapseScope.ASSOCIATIVE, quality=0.8)
    )
    core.network.memberships[3] = frozenset()
    _assert_membership_snapshot_aborted(core, {0: 1.0})


@pytest.mark.parametrize(
    "drive",
    [
        10**10000,
        -(10**10000),
        float("nan"),
        float("inf"),
        float("-inf"),
        0,
        -0.0,
        -1,
        nextafter(1.0, inf),
    ],
    ids=(
        "huge-positive-int",
        "huge-negative-int",
        "nan",
        "positive-infinity",
        "negative-infinity",
        "zero",
        "negative-zero",
        "negative-one",
        "above-one",
    ),
)
def test_public_numeric_validation_is_total_and_returns_invalid_cue(drive) -> None:
    outcome = retrieve_internal(retrieval_core(), {6: drive}, MemoryConfig())
    assert outcome == RetrievalFailure(FailureCode.INVALID_CUE)


@pytest.mark.parametrize("drive", [1.0, float.fromhex("0x0.0000000000001p-1022")])
def test_valid_boundary_cue_drives_remain_accepted(drive: float) -> None:
    outcome = retrieve_internal(retrieval_core(), {6: drive}, MemoryConfig())
    assert isinstance(outcome, RetrievalResult)


class _MutationOnGet(dict):
    def __init__(self, core, values):
        super().__init__(values)
        self.core = core
        self.mutated = False

    def get(self, key, default=None):
        if not self.mutated:
            self.mutated = True
            self.core.network.commit(
                TickTransaction(base_version=self.core.network.version)
            )
        return super().get(key, default)


def test_core_mutation_during_acquisition_aborts() -> None:
    core = retrieval_core()
    core.network.memberships = _MutationOnGet(core, core.network.memberships)
    with pytest.raises(RetrievalAbort) as caught:
        acquire(core, {0: 1.0}, MemoryConfig())
    assert caught.value.code is FailureCode.SNAPSHOT_ABORTED


class _TargetMutationOnGet(dict):
    def __init__(self, core, values):
        super().__init__(values)
        self.core = core
        self.read_keys = []
        self.mutated = False

    def get(self, key, default=None):
        self.read_keys.append(key)
        if key == 3 and not self.mutated:
            self.mutated = True
            self.core.network.commit(
                TickTransaction(base_version=self.core.network.version)
            )
        return super().get(key, default)


def test_core_mutation_during_target_membership_capture_aborts() -> None:
    core = retrieval_core()
    memberships = _TargetMutationOnGet(core, core.network.memberships)
    core.network.memberships = memberships
    with pytest.raises(RetrievalAbort) as caught:
        acquire(core, {0: 1.0}, MemoryConfig())
    assert caught.value.code is FailureCode.SNAPSHOT_ABORTED
    assert memberships.mutated
    assert memberships.read_keys[:3] == [0, 1, 2]
    assert 3 in memberships.read_keys


class _ConfigChangeOnGet(dict):
    def __init__(self, core, values):
        super().__init__(values)
        self.core = core
        self.changed = False

    def get(self, key, default=None):
        if not self.changed:
            self.changed = True
            self.core.config = replace(self.core.config, theta_A=0.2)
        return super().get(key, default)


def test_configuration_change_during_acquisition_aborts() -> None:
    core = retrieval_core()
    core.network.memberships = _ConfigChangeOnGet(core, core.network.memberships)
    with pytest.raises(RetrievalAbort) as caught:
        acquire(core, {0: 1.0}, MemoryConfig())
    assert caught.value.code is FailureCode.SNAPSHOT_ABORTED


class _NoGlobalIteration(dict):
    def __iter__(self):
        raise AssertionError("global iteration attempted")

    def items(self):
        raise AssertionError("global iteration attempted")

    def values(self):
        raise AssertionError("global iteration attempted")


def test_acquisition_never_globally_iterates_core_indexes() -> None:
    core = retrieval_core()
    core.network.cells = _NoGlobalIteration(core.network.cells)
    core.network.assemblies = _NoGlobalIteration(core.network.assemblies)
    core.network.outgoing = _NoGlobalIteration(core.network.outgoing)
    universe = acquire(core, {0: 1.0}, MemoryConfig())
    assert universe.snapshot.assemblies
