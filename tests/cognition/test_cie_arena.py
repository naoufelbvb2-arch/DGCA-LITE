from __future__ import annotations

import copy
import gc
import inspect
import os
import pickle
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, fields
from itertools import count
from pathlib import Path
from threading import Barrier, Event, local

import pytest

from dgca_lite import CoreConfig, CoreEngine, SurfaceEvent
from dgca_lite.cognition import cie as cie_module
from dgca_lite.cognition import ingress as ingress_module
from dgca_lite.cognition import invocation as invocation_module
from dgca_lite.cognition.arena import (
    ARENA_CATEGORIES,
    ArenaEntry,
    ArenaSnapshot,
    CIEPolicy,
    CognitiveResultView,
)
from dgca_lite.cognition.authority import IngressAbort
from dgca_lite.cognition.cie import (
    CIEAbort,
    CIERuntime,
    CognitiveInferenceEpoch,
    RoundStagingArena,
    create_cie_runtime,
)
from dgca_lite.cognition.identity import (
    CanonicalDescriptor,
    ClaimContentID,
    CognitiveEnvironmentBinding,
    ScopeIdentity,
    SnapshotBinding,
)
from dgca_lite.cognition.ingress import create_trusted_ingress_boundary
from dgca_lite.cognition.invocation import InvocationLimits, create_invocation_runtime
from dgca_lite.cognition.serialization import canonical_identity_bytes
from dgca_lite.cognition.types import FailureCode
from dgca_lite.memory.config import MemoryConfig
from dgca_lite.memory.integration import TrustedCoreAdapter
from dgca_lite.memory.session import retrieve_internal
from dgca_lite.persistence import engine_state


def d(kind, *values):
    return CanonicalDescriptor(kind, values)


names = count()


@dataclass
class Context:
    core: CoreEngine
    issuer: object
    parent: object
    cie: object

    def fresh(self):
        cap = self.issuer.authorize_given(
            ClaimContentID(d("GroundAtom", "P")),
            ScopeIdentity("FORMAL", d("source"), d("scope")),
            d("occurrence", next(names)),
        )
        auth = self.parent.admit(cap)
        return auth, self.parent.ledger(auth)


def make_context(policy=None, l2=None):
    core = CoreEngine(CoreConfig(receptor_fanout=1))
    issuer = create_trusted_ingress_boundary(
        core, d("unit4", next(names)), d("source"), capacity=2048
    )
    parent = create_invocation_runtime(
        issuer.invocation_causes, InvocationLimits(8, 1024)
    )
    return Context(
        core, issuer, parent, create_cie_runtime(parent, policy=policy, l2_config=l2)
    )


@pytest.fixture(scope="module")
def context():
    return make_context()


@pytest.fixture(scope="module")
def other():
    return make_context()


@pytest.fixture(scope="module")
def small():
    return make_context(
        CIEPolicy(max_entries=2, max_staged_entries=2, max_rounds=2, max_cies=2)
    )


@pytest.fixture
def opened(context):
    auth, ledger = context.fresh()
    cie = context.cie.open(auth, 0)
    yield context, auth, ledger, cie
    if context.cie.status(cie) == "OPEN":
        context.cie.abort(cie)
    if context.parent.describe(auth).revision == 0:
        context.parent.begin_close(auth, 0)
    if context.parent.describe(auth).revision == 1:
        ledger.retire_unused(auth, 1)
        assert context.parent.finalize_close(auth, 1)


def entry(index=0, category="ASSERTION", payload=None):
    return ArenaEntry(
        category, d("entry", index), payload or d("already-produced", index)
    )


def abort(code, call):
    with pytest.raises(IngressAbort) as caught:
        call()
    assert caught.value.code is code
    return caught.value


def epoch_record(handle):
    access = inspect.getclosurevars(CIERuntime.snapshot).nonlocals["access"]
    with access(handle, "CIE") as (_, record):
        return record


@pytest.mark.parametrize(
    "handle_type", [CognitiveInferenceEpoch, RoundStagingArena, CIERuntime]
)
def test_handles_nonconstructible_and_object_new_forgery(opened, handle_type):
    ctx, _, _, cie = opened
    with pytest.raises(TypeError):
        handle_type()
    fake = object.__new__(handle_type)
    if handle_type is CIERuntime:
        abort(FailureCode.CIE_STALE, lambda: fake.snapshot(cie))
    else:
        abort(FailureCode.CIE_STALE, lambda: ctx.cie.snapshot(fake))


@pytest.mark.parametrize(
    "operation", [copy.copy, copy.deepcopy, pickle.dumps, canonical_identity_bytes]
)
@pytest.mark.parametrize("kind", ["CIE", "STAGE", "RUNTIME"])
def test_live_handles_never_copy_or_serialize(opened, operation, kind):
    ctx, _, _, cie = opened
    token = ctx.cie.stage(cie, ctx.cie.snapshot(cie), ())
    handle = {"CIE": cie, "STAGE": token, "RUNTIME": ctx.cie}[kind]
    with pytest.raises((TypeError, ValueError)):
        operation(handle)
    with pytest.raises((TypeError, ValueError)):
        d("nested", (handle,))


def test_cie_identity_and_frozen_ceb_have_exact_components(opened):
    ctx, auth, _, cie = opened
    snapshot = ctx.cie.snapshot(cie)
    binding = snapshot.binding.cie
    assert binding.identity.invocation_cause == ctx.parent.describe(auth).cause
    assert binding.identity.sequence_index == 0
    assert binding.invocation_revision == 0
    assert [f.name for f in fields(CognitiveEnvironmentBinding)] == [
        "core_state",
        "l2_policy",
        "l3_policy",
    ]
    assert binding.environment.core_state.version == ctx.core.network.version
    assert binding.environment.core_state.tick == ctx.core.network.tick
    assert binding.environment.core_state.next_root_id == ctx.core.temporal.next_root_id
    assert snapshot.binding.arena_version == snapshot.binding.round_identity == 0
    with pytest.raises(TypeError):
        ctx.cie.open(auth, 0, environment=binding.environment)


def test_second_simultaneous_cie_rejected_and_sequential_indices_not_reused(opened):
    ctx, auth, _, cie = opened
    before = ctx.cie.snapshot(cie).canonical_bytes
    abort(FailureCode.CIE_STALE, lambda: ctx.cie.open(auth, 0))
    assert ctx.cie.snapshot(cie).canonical_bytes == before
    ctx.cie.abort(cie)
    replacement = ctx.cie.open(auth, 0)
    assert ctx.cie.snapshot(replacement).binding.cie.identity.sequence_index == 1
    abort(FailureCode.CIE_STALE, lambda: ctx.cie.snapshot(cie))
    ctx.cie.abort(replacement)


@pytest.mark.parametrize("revision", [True, False, -1, "0", 1.0, 1])
def test_stale_and_noncanonical_invocation_revision(context, revision):
    auth, _ = context.fresh()
    with pytest.raises(IngressAbort):
        context.cie.open(auth, revision)
    valid = context.cie.open(auth, 0)
    assert context.cie.snapshot(valid).binding.cie.identity.sequence_index == 0
    context.cie.abort(valid)


@pytest.mark.parametrize("category", ARENA_CATEGORIES)
def test_closed_arena_category_envelopes_do_not_execute_semantics(opened, category):
    ctx, _, ledger, cie = opened
    before = ledger.summary(epoch_record(cie).authority)
    old = ctx.cie.snapshot(cie)
    stage = ctx.cie.stage(cie, old, (entry(0, category),))
    assert ctx.cie.snapshot(cie).canonical_bytes == old.canonical_bytes
    new = ctx.cie.publish(cie, stage)
    assert len(new.entries) == 1
    assert new.binding.arena_version == new.binding.round_identity == 1
    assert ledger.summary(epoch_record(cie).authority) == before


def test_unknown_category_and_capability_payloads_fail_closed(opened):
    ctx, auth, ledger, cie = opened
    with pytest.raises(TypeError):
        entry(category="UNKNOWN")
    values = [
        auth,
        ledger,
        ctx.issuer,
        ctx.parent,
        cie,
        ctx.core,
        object(),
        lambda: None,
        retrieve_internal(ctx.core, {}),
    ]
    for value in values:
        with pytest.raises((TypeError, ValueError)):
            entry(payload=d("nested", (value,)))


def test_genuine_l2_receipt_is_not_arena_data(opened):
    ctx, _, _, cie = opened
    with ctx.issuer.core_transition():
        receipt = TrustedCoreAdapter.process_event(ctx.core, SurfaceEvent(b"real"))
    with pytest.raises((TypeError, ValueError)):
        entry(payload=d("receipt", receipt))
    failure = abort(
        FailureCode.ENVIRONMENT_STALE,
        lambda: ctx.cie.stage(cie, ctx.cie.snapshot(cie), ()),
    )
    assert failure.result.status == "ENVIRONMENT_STALE"


def test_mutable_inputs_and_nested_aliases_cannot_change_arena_or_history(opened):
    ctx, _, _, cie = opened
    original = entry(payload=d("outer", (d("nested", 7),)))
    snapshot0 = ctx.cie.snapshot(cie)
    stage = ctx.cie.stage(cie, snapshot0, (original,))
    object.__setattr__(original.payload.values[0][0], "values", (99,))
    snapshot1 = ctx.cie.publish(cie, stage)
    assert snapshot1.entries[0].payload.values[0][0].values == (7,)
    remembered = snapshot1.canonical_bytes
    object.__setattr__(snapshot1.entries[0].payload, "values", ("changed",))
    live = ctx.cie.snapshot(cie)
    assert live.canonical_bytes == remembered
    stage2 = ctx.cie.stage(cie, live, (entry(1),))
    snapshot2 = ctx.cie.publish(cie, stage2)
    assert snapshot0.entries == ()
    assert len(live.entries) == 1 and len(snapshot2.entries) == 2


def test_canonical_order_and_exact_replay_no_overwrite(opened):
    ctx, _, _, cie = opened
    stage = ctx.cie.stage(
        cie, ctx.cie.snapshot(cie), (entry("z"), entry(2), entry("a"), entry(2))
    )
    snapshot = ctx.cie.publish(cie, stage)
    assert len(snapshot.entries) == 3
    stage = ctx.cie.stage(cie, snapshot, tuple(reversed(snapshot.entries)))
    again = ctx.cie.publish(cie, stage)
    assert again.entries == snapshot.entries
    collision = entry(2, payload=d("different"))
    stage = ctx.cie.stage(cie, again, (collision,))
    failure = abort(
        FailureCode.INTERNAL_CONTRACT_VIOLATION, lambda: ctx.cie.publish(cie, stage)
    )
    assert failure.result.snapshot.canonical_bytes == again.canonical_bytes
    assert epoch_record(cie).snapshot is None


def test_hash_collision_is_never_identity(opened, monkeypatch):
    ctx, _, _, cie = opened
    monkeypatch.setattr(CanonicalDescriptor, "__hash__", lambda self: 0)
    stage = ctx.cie.stage(cie, ctx.cie.snapshot(cie), (entry(1), entry("1"), entry(2)))
    assert len(ctx.cie.publish(cie, stage).entries) == 3


def test_cross_runtime_and_cie_snapshot_substitution(opened, other):
    ctx, _, _, cie = opened
    auth2, _ = ctx.fresh()
    cie2 = ctx.cie.open(auth2, 0)
    abort(FailureCode.CIE_STALE, lambda: ctx.cie.stage(cie, ctx.cie.snapshot(cie2), ()))
    abort(FailureCode.CIE_STALE, lambda: other.cie.snapshot(cie))
    ctx.cie.abort(cie2)


def test_stale_snapshot_and_stage_replay_never_advance(opened):
    ctx, _, _, cie = opened
    old = ctx.cie.snapshot(cie)
    stage = ctx.cie.stage(cie, old, (entry(),))
    new = ctx.cie.publish(cie, stage)
    abort(FailureCode.CIE_STALE, lambda: ctx.cie.stage(cie, old, (entry(1),)))
    abort(FailureCode.CIE_STALE, lambda: ctx.cie.publish(cie, stage))
    assert ctx.cie.snapshot(cie).canonical_bytes == new.canonical_bytes


def test_terminal_result_or_snapshot_never_recreates_authority(opened):
    ctx, auth, _, cie = opened
    old = ctx.cie.snapshot(cie)
    stage = ctx.cie.stage(cie, old, (entry(),))
    result = ctx.cie.publish(cie, stage, terminal=True)
    assert result.status == ctx.cie.status(cie) == "PUBLISHED"
    assert result.snapshot.binding.arena_version == 1
    for data in (old, old.binding, result, result.canonical_descriptor()):
        abort(FailureCode.CIE_STALE, lambda data=data: ctx.cie.snapshot(data))
    abort(FailureCode.CIE_STALE, lambda: ctx.cie.abort(cie))
    replacement = ctx.cie.open(auth, 0)
    assert ctx.cie.snapshot(replacement).entries == ()
    assert ctx.cie.snapshot(replacement).binding.cie.identity.sequence_index == 1
    ctx.cie.abort(replacement)


def test_capacity_abort_preserves_prior_snapshot_without_partial_visibility(small):
    auth, _ = small.fresh()
    cie = small.cie.open(auth, 0)
    base = small.cie.snapshot(cie)
    stage = small.cie.stage(cie, base, (entry(0),))
    prior = small.cie.publish(cie, stage)
    stage = small.cie.stage(cie, prior, (entry(1), entry(2)))
    assert small.cie.snapshot(cie).canonical_bytes == prior.canonical_bytes
    failure = abort(FailureCode.CAPACITY_ABORT, lambda: small.cie.publish(cie, stage))
    assert failure.result.snapshot.canonical_bytes == prior.canonical_bytes
    assert failure.result.snapshot.binding.arena_version == 1
    assert small.cie.status(cie) == "CAPACITY_ABORT"
    assert epoch_record(cie).snapshot is epoch_record(cie).pending is None


def test_oversized_outer_batch_rejected_before_member_inspection(small, monkeypatch):
    auth, _ = small.fresh()
    cie = small.cie.open(auth, 0)
    base = small.cie.snapshot(cie)

    def forbidden(*args):
        raise AssertionError("members must not be inspected")

    monkeypatch.setattr(cie_module, "freeze_entry", forbidden)
    failure = abort(
        FailureCode.CAPACITY_ABORT, lambda: small.cie.stage(cie, base, (object(),) * 3)
    )
    assert failure.result.snapshot.canonical_bytes == base.canonical_bytes


def test_oversized_nested_entry_rejected_before_semantic_members(opened):
    ctx, _, _, cie = opened
    bad = object.__new__(CanonicalDescriptor)
    object.__setattr__(bad, "kind", "bad")
    object.__setattr__(bad, "values", (object(),) * 5000)
    value = object.__new__(ArenaEntry)
    object.__setattr__(value, "category", "ASSERTION")
    object.__setattr__(value, "identity", d("id"))
    object.__setattr__(value, "payload", bad)
    with pytest.raises(ValueError, match="bound"):
        value.canonical_descriptor()
    abort(
        FailureCode.INVALID_INPUT,
        lambda: ctx.cie.stage(cie, ctx.cie.snapshot(cie), (value,)),
    )


def test_invalid_final_staged_item_leaves_prior_bytes_unchanged(opened):
    ctx, _, _, cie = opened
    prior = ctx.cie.snapshot(cie)
    failure = abort(
        FailureCode.INVALID_INPUT,
        lambda: ctx.cie.stage(cie, prior, (entry(0), entry(1), object())),
    )
    assert failure.result.snapshot.canonical_bytes == prior.canonical_bytes
    assert failure.result.snapshot.binding.arena_version == 0


def test_stale_ceb_at_publication_terminalizes_without_backdating(opened):
    ctx, _, _, cie = opened
    old = ctx.cie.snapshot(cie)
    stage = ctx.cie.stage(cie, old, (entry(),))
    with ctx.issuer.core_transition():
        ctx.core.process_event(SurfaceEvent(b"new"))
    failure = abort(FailureCode.ENVIRONMENT_STALE, lambda: ctx.cie.publish(cie, stage))
    assert failure.result.snapshot.canonical_bytes == old.canonical_bytes
    assert epoch_record(cie).snapshot is epoch_record(cie).pending is None


def test_policy_is_frozen_from_typed_owned_configuration():
    policy = CIEPolicy(max_entries=4)
    config = MemoryConfig(K_C=17)
    ctx = make_context(policy, config)
    object.__setattr__(policy, "max_entries", 128)
    object.__setattr__(config, "K_C", 99)
    auth, _ = ctx.fresh()
    cie = ctx.cie.open(auth, 0)
    ceb = ctx.cie.snapshot(cie).binding.cie.environment
    assert dict(ceb.l2_policy.values)["K_C"] == 17
    assert dict(ceb.l3_policy.values[0].values)["max_entries"] == 4
    ctx.cie.abort(cie)
    abort(FailureCode.INVALID_FORMAL_AUTHORITY, lambda: create_cie_runtime(ctx.parent))
    with pytest.raises(IngressAbort):
        create_cie_runtime(ctx.parent, l2_config=d("fake"))


def test_close_immediately_aborts_child_then_finalizes_outside_gate(opened):
    ctx, auth, ledger, cie = opened
    ledger.retire_unused(auth, 0)
    assert epoch_record(cie).invocation.nondelegated_children == 1
    abort(FailureCode.INVOCATION_NOT_ACTIVE, lambda: ctx.parent.finalize_close(auth, 0))
    ctx.parent.begin_close(auth, 0)
    assert ctx.cie.status(cie) == "PARENT_AUTHORITY_STALE"
    assert epoch_record(cie).invocation.nondelegated_children == 0
    assert ctx.parent.finalize_close(auth, 1)
    assert epoch_record(cie).snapshot is epoch_record(cie).pending is None


def test_open_after_close_fails_without_sequence_advance(context):
    auth, ledger = context.fresh()
    context.parent.begin_close(auth, 0)
    abort(FailureCode.INVOCATION_NOT_ACTIVE, lambda: context.cie.open(auth, 1))
    ledger.retire_unused(auth, 1)
    assert context.parent.finalize_close(auth, 1)


def test_complete_lower_layer_and_budget_conservation(opened):
    ctx, auth, ledger, cie = opened
    before = engine_state(ctx.core)
    budget = ledger.summary(auth)
    for number in range(3):
        stage = ctx.cie.stage(cie, ctx.cie.snapshot(cie), (entry(number),))
        output = ctx.cie.publish(cie, stage, terminal=number == 2)
    assert output.status == "PUBLISHED"
    record = epoch_record(cie)
    assert record.snapshot is record.pending is None
    assert record.invocation.cie_child is None
    assert record.runtime.stage_ids == set()
    assert engine_state(ctx.core) == before
    assert ledger.summary(auth) == budget
    assert not hasattr(record.runtime, "memory")
    assert not hasattr(ctx.cie, "retrieve")


def test_round_claim_precedes_builder_completion_and_no_partial_snapshot(
    opened, monkeypatch
):
    ctx, _, _, cie = opened
    old = ctx.cie.snapshot(cie)
    started, release = Event(), Event()
    original = cie_module.freeze_entry

    def delayed(value):
        started.set()
        assert release.wait(5)
        return original(value)

    monkeypatch.setattr(cie_module, "freeze_entry", delayed)
    with ThreadPoolExecutor(2) as pool:
        building = pool.submit(ctx.cie.stage, cie, old, (entry(1), entry(2)))
        assert started.wait(5)
        assert ctx.cie.snapshot(cie).canonical_bytes == old.canonical_bytes
        abort(FailureCode.CIE_STALE, lambda: ctx.cie.stage(cie, old, ()))
        release.set()
        stage = building.result(5)
    assert ctx.cie.snapshot(cie).canonical_bytes == old.canonical_bytes
    assert len(ctx.cie.publish(cie, stage).entries) == 2


@pytest.mark.parametrize("close_first", [True, False])
def test_open_and_begin_close_both_linearization_orders(context, close_first):
    auth, ledger = context.fresh()
    if close_first:
        context.parent.begin_close(auth, 0)
        abort(FailureCode.OWNER_AUTHORITY_STALE, lambda: context.cie.open(auth, 0))
    else:
        cie = context.cie.open(auth, 0)
        context.parent.begin_close(auth, 0)
        assert context.cie.status(cie) == "PARENT_AUTHORITY_STALE"
    ledger.retire_unused(auth, 1)
    assert context.parent.finalize_close(auth, 1)


@pytest.mark.parametrize("close_first", [True, False])
def test_publish_and_begin_close_both_linearization_orders(context, close_first):
    auth, ledger = context.fresh()
    cie = context.cie.open(auth, 0)
    stage = context.cie.stage(cie, context.cie.snapshot(cie), (entry(),))
    if close_first:
        context.parent.begin_close(auth, 0)
        abort(
            FailureCode.CIE_STALE,
            lambda: context.cie.publish(cie, stage, terminal=True),
        )
    else:
        result = context.cie.publish(cie, stage, terminal=True)
        context.parent.begin_close(auth, 0)
        assert result.status == "PUBLISHED" and len(result.snapshot.entries) == 1
    ledger.retire_unused(auth, 1)
    assert context.parent.finalize_close(auth, 1)


def test_parallel_open_allows_exactly_one_live_cie(context):
    auth, _ = context.fresh()
    gate = Barrier(8)

    def opening():
        gate.wait()
        try:
            return context.cie.open(auth, 0)
        except IngressAbort as error:
            return error.code

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda _: opening(), range(8)))
    successes = [value for value in results if type(value) is CognitiveInferenceEpoch]
    assert len(successes) == 1
    assert results.count(FailureCode.CIE_STALE) == 7
    context.cie.abort(successes[0])


def test_concurrent_publication_has_exactly_one_commit(opened):
    ctx, _, _, cie = opened
    stage = ctx.cie.stage(cie, ctx.cie.snapshot(cie), (entry(),))
    gate = Barrier(8)

    def publishing():
        gate.wait()
        try:
            return ctx.cie.publish(cie, stage)
        except IngressAbort as error:
            return error.code

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda _: publishing(), range(8)))
    assert sum(type(value) is ArenaSnapshot for value in results) == 1
    assert results.count(FailureCode.CIE_STALE) == 7
    assert ctx.cie.snapshot(cie).binding.arena_version == 1


def test_cie_gc_releases_occupancy_without_reusing_identity(context):
    auth, _ = context.fresh()
    cie = context.cie.open(auth, 0)
    record = epoch_record(cie)
    del cie
    gc.collect()
    assert record.terminal == "ABORTED"
    assert record.snapshot is record.pending is None
    replacement = context.cie.open(auth, 0)
    assert context.cie.snapshot(replacement).binding.cie.identity.sequence_index == 1
    context.cie.abort(replacement)


def test_unbound_method_cannot_use_caller_controlled_validator(opened):
    ctx, _, _, cie = opened

    class FakeRuntime:
        def check_runtime(self, runtime):
            raise AssertionError("caller validator must never execute")

    abort(FailureCode.CIE_STALE, lambda: CIERuntime.snapshot(FakeRuntime(), cie))
    assert ctx.cie.status(cie) == "OPEN"


def test_terminal_shell_is_serializable_but_not_a_completeness_claim(opened):
    ctx, _, _, cie = opened
    snapshot = ctx.cie.snapshot(cie)
    result = ctx.cie.abort(cie)
    for recovered in (copy.deepcopy(result), pickle.loads(pickle.dumps(result))):
        assert recovered.canonical_descriptor() == result.canonical_descriptor()
        abort(
            FailureCode.CIE_STALE,
            lambda recovered=recovered: ctx.cie.snapshot(recovered),
        )
    with pytest.raises(TypeError):
        CognitiveResultView("FIXED_POINT", snapshot)


def test_snapshot_bound_and_numeric_types_precede_member_validation(opened):
    ctx, _, _, cie = opened
    snapshot = ctx.cie.snapshot(cie)
    with pytest.raises(ValueError, match="bound"):
        ArenaSnapshot(snapshot.binding, (object(),) * 129)
    with pytest.raises(TypeError):
        SnapshotBinding(snapshot.binding.cie, True, 0)
    with pytest.raises(ValueError):
        ArenaSnapshot(snapshot.binding, (entry(2), entry(2)))


def test_round_limit_abort_preserves_last_committed_version(small):
    auth, _ = small.fresh()
    cie = small.cie.open(auth, 0)
    for _ in range(2):
        stage = small.cie.stage(cie, small.cie.snapshot(cie), ())
        snapshot = small.cie.publish(cie, stage)
    failure = abort(
        FailureCode.CAPACITY_ABORT, lambda: small.cie.stage(cie, snapshot, ())
    )
    assert isinstance(failure, CIEAbort)
    assert failure.result.snapshot.canonical_bytes == snapshot.canonical_bytes
    assert failure.result.snapshot.binding.arena_version == 2


def test_sequential_cie_limit_cannot_refresh(small):
    auth, _ = small.fresh()
    for expected in range(2):
        cie = small.cie.open(auth, 0)
        assert small.cie.snapshot(cie).binding.cie.identity.sequence_index == expected
        small.cie.abort(cie)
    abort(FailureCode.CAPACITY_ABORT, lambda: small.cie.open(auth, 0))


def test_aggregate_representation_capacity_fails_without_partial_publish(opened):
    ctx, _, _, cie = opened
    old = ctx.cie.snapshot(cie)
    additions = tuple(
        entry(i, payload=d("bounded-tuple", tuple(range(1200)))) for i in range(4)
    )
    stage = ctx.cie.stage(cie, old, additions)
    failure = abort(FailureCode.CAPACITY_ABORT, lambda: ctx.cie.publish(cie, stage))
    assert failure.result.snapshot.canonical_bytes == old.canonical_bytes
    assert epoch_record(cie).pending is None


def test_unrepresentable_open_is_atomic_and_does_not_allocate_sequence():
    ctx = make_context(CIEPolicy(max_snapshot_bytes=1))
    auth, _ = ctx.fresh()
    for _ in range(2):
        abort(FailureCode.CAPACITY_ABORT, lambda: ctx.cie.open(auth, 0))
    access = inspect.getclosurevars(
        invocation_module.InvocationRuntime.describe
    ).nonlocals["access"]
    with access(ctx.parent, "RUNTIME") as (domain, _):
        item = next(
            value for value in domain.causes.values() if value.authority is auth
        )
        assert item.cie_sequence == 0 and item.cie_child is None
        assert item.nondelegated_children == 0


def test_output_construction_failure_preserves_prior_arena_and_releases_child(
    opened, monkeypatch
):
    ctx, _, _, cie = opened
    prior = ctx.cie.snapshot(cie)
    stage = ctx.cie.stage(cie, prior, (entry(),))
    original = cie_module.clone_snapshot

    def failing(snapshot):
        if snapshot.binding.arena_version == 1:
            raise ValueError("injected final output allocation failure")
        return original(snapshot)

    monkeypatch.setattr(cie_module, "clone_snapshot", failing)
    failure = abort(FailureCode.CAPACITY_ABORT, lambda: ctx.cie.publish(cie, stage))
    assert failure.result.snapshot.canonical_bytes == prior.canonical_bytes
    assert epoch_record(cie).invocation.cie_child is None


def test_internal_failure_terminalizes_without_publishing(opened, monkeypatch):
    ctx, _, _, cie = opened
    old = ctx.cie.snapshot(cie)
    stage = ctx.cie.stage(cie, old, (entry(),))

    original = cie_module.clone_snapshot

    def failing(snapshot):
        if snapshot.binding.arena_version == 1:
            raise RuntimeError("injected internal failure")
        return original(snapshot)

    monkeypatch.setattr(cie_module, "clone_snapshot", failing)
    with pytest.raises(RuntimeError):
        ctx.cie.publish(cie, stage)
    record = epoch_record(cie)
    assert record.terminal == "INTERNAL_CONTRACT_VIOLATION"
    assert record.last_binding == old.binding
    assert record.snapshot is record.pending is None


def test_close_does_not_wait_for_private_stage_builder(opened, monkeypatch):
    ctx, auth, ledger, cie = opened
    old = ctx.cie.snapshot(cie)
    started, release = Event(), Event()
    original = cie_module.freeze_entry

    def delayed(value):
        started.set()
        assert release.wait(5)
        return original(value)

    monkeypatch.setattr(cie_module, "freeze_entry", delayed)
    with ThreadPoolExecutor(2) as pool:
        building = pool.submit(ctx.cie.stage, cie, old, (entry(),))
        assert started.wait(5)
        closing = pool.submit(ctx.parent.begin_close, auth, 0)
        assert closing.result(2).revision == 1
        ledger.retire_unused(auth, 1)
        assert ctx.parent.finalize_close(auth, 1)
        release.set()
        with pytest.raises(IngressAbort):
            building.result(5)
    assert old.entries == ()
    assert epoch_record(cie).snapshot is epoch_record(cie).pending is None


def test_open_linearizes_before_concurrent_close(context, monkeypatch):
    auth, ledger = context.fresh()
    started, release, closing_started = Event(), Event(), Event()
    original = cie_module._snapshot

    def delayed(value):
        if type(value).__name__ == "CIEBinding":
            started.set()
            assert release.wait(5)
        return original(value)

    def closing():
        closing_started.set()
        return context.parent.begin_close(auth, 0)

    monkeypatch.setattr(cie_module, "_snapshot", delayed)
    with ThreadPoolExecutor(2) as pool:
        opening = pool.submit(context.cie.open, auth, 0)
        assert started.wait(5)
        close = pool.submit(closing)
        assert closing_started.wait(5) and not close.done()
        release.set()
        cie = opening.result(5)
        assert close.result(5).revision == 1
    assert context.cie.status(cie) == "PARENT_AUTHORITY_STALE"
    ledger.retire_unused(auth, 1)
    assert context.parent.finalize_close(auth, 1)


def test_close_linearizes_before_concurrent_open(context):
    auth, _ = context.fresh()
    with ThreadPoolExecutor(1) as pool:
        with context.parent.active_guard(auth, 0):
            opening = pool.submit(context.cie.open, auth, 0)
            context.parent.begin_close(auth, 0)
        with pytest.raises(IngressAbort):
            opening.result(5)


def test_publication_linearizes_before_concurrent_close(opened, monkeypatch):
    ctx, auth, _, cie = opened
    old = ctx.cie.snapshot(cie)
    stage = ctx.cie.stage(cie, old, (entry(),))
    started, release, closing_started = Event(), Event(), Event()
    original = cie_module.clone_snapshot

    def delayed(snapshot):
        if snapshot.binding.arena_version == 1:
            started.set()
            assert release.wait(5)
        return original(snapshot)

    def closing():
        closing_started.set()
        return ctx.parent.begin_close(auth, 0)

    monkeypatch.setattr(cie_module, "clone_snapshot", delayed)
    with ThreadPoolExecutor(2) as pool:
        publishing = pool.submit(ctx.cie.publish, cie, stage, terminal=True)
        assert started.wait(5)
        close = pool.submit(closing)
        assert closing_started.wait(5) and not close.done()
        release.set()
        result = publishing.result(5)
        close.result(5)
    assert result.status == "PUBLISHED" and len(result.snapshot.entries) == 1


def test_post_ingress_capture_never_observes_network_temporal_tear(
    context, monkeypatch
):
    auth, _ = context.fresh()
    torn, release, capture_started = Event(), Event(), Event()
    original = context.core.network.commit

    def paused(transaction):
        original(transaction)
        torn.set()
        assert release.wait(5)

    monkeypatch.setattr(context.core.network, "commit", paused)

    def event():
        with context.issuer.core_transition():
            context.core.process_event(SurfaceEvent(b"barrier"))

    def capture():
        capture_started.set()
        return context.cie.open(auth, 0)

    with ThreadPoolExecutor(2) as pool:
        transition = pool.submit(event)
        assert torn.wait(5)
        opening = pool.submit(capture)
        assert capture_started.wait(5) and not opening.done()
        release.set()
        transition.result(5)
        cie = opening.result(5)
    binding = context.cie.snapshot(cie).binding.cie.environment.core_state
    assert binding.version == context.core.network.version
    assert binding.tick == context.core.network.tick
    assert binding.next_root_id == context.core.temporal.next_root_id
    context.cie.abort(cie)


def test_canonical_lock_order_covers_core_lifecycle_arena_registry(opened):
    ctx, auth, _, cie = opened
    record = epoch_record(cie)
    access = inspect.getclosurevars(
        invocation_module.InvocationRuntime.describe
    ).nonlocals["access"]
    with access(ctx.parent, "RUNTIME") as (domain, _):
        pass
    state_for = inspect.getclosurevars(
        inspect.unwrap(type(ctx.issuer).core_transition)
    ).nonlocals["state_for"]
    state = state_for(ctx.issuer, "ISSUER")
    cells = []
    for method in (CIERuntime.stage, invocation_module.InvocationRuntime.describe):
        cells.append(
            method.__closure__[method.__code__.co_freevars.index("registry_lock")]
        )
    held, trace = local(), []

    class OrderedLock:
        def __init__(self, lock, rank):
            self.lock, self.rank = lock, rank

        def acquire(self):
            stack = getattr(held, "stack", ())
            assert not stack or self.rank >= stack[-1], (stack, self.rank)
            self.lock.acquire()
            held.stack = stack + (self.rank,)
            trace.append(self.rank)

        def release(self):
            assert held.stack[-1] == self.rank
            held.stack = held.stack[:-1]
            self.lock.release()

        def __enter__(self):
            self.acquire()

        def __exit__(self, *exception):
            self.release()

    originals = (
        state.barrier,
        domain.lifecycle.lock,
        record.lock,
        tuple(cell.cell_contents for cell in cells),
    )
    try:
        state.barrier = OrderedLock(state.barrier, 0)
        domain.lifecycle.lock = OrderedLock(domain.lifecycle.lock, 1)
        record.lock = OrderedLock(record.lock, 3)
        for cell in cells:
            cell.cell_contents = OrderedLock(cell.cell_contents, 5)
        stage = ctx.cie.stage(cie, ctx.cie.snapshot(cie), (entry(),))
        ctx.cie.publish(cie, stage)
        ctx.parent.begin_close(auth, 0)
        assert {0, 1, 3, 5}.issubset(trace)
    finally:
        state.barrier, domain.lifecycle.lock, record.lock, old_cells = originals
        for cell, old in zip(cells, old_cells, strict=True):
            cell.cell_contents = old


def test_no_core_capture_can_nest_below_lifecycle(opened):
    ctx, auth, _, cie = opened
    snapshot = ctx.cie.snapshot(cie)
    with ctx.parent.active_guard(auth, 0):
        abort(FailureCode.INTERNAL_CONTRACT_VIOLATION, lambda: ctx.cie.open(auth, 0))
        abort(
            FailureCode.INTERNAL_CONTRACT_VIOLATION,
            lambda: ctx.cie.stage(cie, snapshot, ()),
        )
    assert ctx.cie.status(cie) == "INTERNAL_CONTRACT_VIOLATION"


def test_live_binding_integrity_violation_is_terminal(opened):
    ctx, _, _, cie = opened
    record = epoch_record(cie)
    object.__setattr__(record.binding.identity, "sequence_index", 999)
    abort(FailureCode.INTERNAL_CONTRACT_VIOLATION, lambda: ctx.cie.snapshot(cie))
    assert record.terminal == "INTERNAL_CONTRACT_VIOLATION"
    assert record.snapshot is record.pending is None


def test_missing_trusted_environment_terminalizes_locally(opened, monkeypatch):
    ctx, _, _, cie = opened
    old = ctx.cie.snapshot(cie)
    stage = ctx.cie.stage(cie, old, (entry(),))
    original = ingress_module._snapshot

    def failure(value):
        if type(value).__name__ == "CoreStateBinding":
            raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
        return original(value)

    monkeypatch.setattr(ingress_module, "_snapshot", failure)
    caught = abort(FailureCode.ENVIRONMENT_STALE, lambda: ctx.cie.publish(cie, stage))
    assert caught.result.snapshot.canonical_bytes == old.canonical_bytes


def test_partial_bypassed_arena_records_fail_closed(opened):
    ctx, _, _, cie = opened
    incomplete = object.__new__(ArenaSnapshot)
    abort(FailureCode.INVALID_INPUT, lambda: ctx.cie.stage(cie, incomplete, ()))
    assert ctx.cie.status(cie) == "OPEN"
    old = ctx.cie.snapshot(cie)
    incomplete_entry = object.__new__(ArenaEntry)
    failure = abort(
        FailureCode.INVALID_INPUT, lambda: ctx.cie.stage(cie, old, (incomplete_entry,))
    )
    assert failure.result.snapshot.canonical_bytes == old.canonical_bytes


def test_open_failure_before_registry_publication_is_atomic(context, monkeypatch):
    auth, _ = context.fresh()
    original = cie_module.ref

    def failing(*args):
        raise MemoryError("injected weak-reference allocation failure")

    monkeypatch.setattr(cie_module, "ref", failing)
    with pytest.raises(MemoryError):
        context.cie.open(auth, 0)
    monkeypatch.setattr(cie_module, "ref", original)
    cie = context.cie.open(auth, 0)
    assert context.cie.snapshot(cie).binding.cie.identity.sequence_index == 0
    context.cie.abort(cie)


def test_stage_failure_before_registration_does_not_change_arena(opened, monkeypatch):
    ctx, _, _, cie = opened
    old = ctx.cie.snapshot(cie)
    original = cie_module.ref

    def failing(*args):
        raise MemoryError("injected staging registration failure")

    monkeypatch.setattr(cie_module, "ref", failing)
    with pytest.raises(MemoryError):
        ctx.cie.stage(cie, old, (entry(),))
    monkeypatch.setattr(cie_module, "ref", original)
    assert ctx.cie.snapshot(cie).canonical_bytes == old.canonical_bytes
    assert epoch_record(cie).pending is None


def test_core_policy_change_invalidates_publication_even_without_tick_change(opened):
    ctx, _, _, cie = opened
    old = ctx.cie.snapshot(cie)
    stage = ctx.cie.stage(cie, old, (entry(),))
    original = ctx.core.config
    values = original.to_dict()
    values["alpha"] += 0.125
    try:
        with ctx.issuer.core_transition():
            ctx.core.config = CoreConfig(**values)
        failure = abort(
            FailureCode.ENVIRONMENT_STALE, lambda: ctx.cie.publish(cie, stage)
        )
        assert failure.result.snapshot.canonical_bytes == old.canonical_bytes
    finally:
        with ctx.issuer.core_transition():
            ctx.core.config = original


def test_invalid_current_core_policy_terminalizes_instead_of_leaving_cie_live(opened):
    ctx, _, _, cie = opened
    old = ctx.cie.snapshot(cie)
    stage = ctx.cie.stage(cie, old, (entry(),))
    original = ctx.core.config
    try:
        with ctx.issuer.core_transition():
            ctx.core.config = object()
        failure = abort(
            FailureCode.ENVIRONMENT_STALE, lambda: ctx.cie.publish(cie, stage)
        )
        assert failure.result.snapshot.canonical_bytes == old.canonical_bytes
    finally:
        with ctx.issuer.core_transition():
            ctx.core.config = original


def test_runtime_retirement_clears_payloads_and_cannot_refresh_attachment():
    ctx = make_context()
    auth, _ = ctx.fresh()
    cie = ctx.cie.open(auth, 0)
    stage = ctx.cie.stage(cie, ctx.cie.snapshot(cie), (entry(),))
    record = epoch_record(cie)
    ctx.cie = None
    gc.collect()
    assert record.snapshot is record.pending is None
    assert record.runtime.epochs == {} and record.runtime.stage_ids == set()
    abort(FailureCode.INVALID_FORMAL_AUTHORITY, lambda: create_cie_runtime(ctx.parent))
    del stage


@pytest.mark.parametrize("kind", ["RUNTIME", "CIE", "STAGE"])
def test_class_recasting_cannot_change_authority_role(opened, kind):
    ctx, _, _, cie = opened
    stage = ctx.cie.stage(cie, ctx.cie.snapshot(cie), ())
    handle = {"RUNTIME": ctx.cie, "CIE": cie, "STAGE": stage}[kind]
    original = type(handle)
    snapshot_method = ctx.cie.snapshot
    replacement = (
        RoundStagingArena
        if original is not RoundStagingArena
        else CognitiveInferenceEpoch
    )
    object.__setattr__(handle, "__class__", replacement)
    try:
        abort(FailureCode.CIE_STALE, lambda: snapshot_method(handle))
    finally:
        object.__setattr__(handle, "__class__", original)


def test_empty_successful_terminal_publication_is_not_budget_work(opened):
    ctx, auth, ledger, cie = opened
    before = ledger.summary(auth)
    stage = ctx.cie.stage(cie, ctx.cie.snapshot(cie), ())
    result = ctx.cie.publish(cie, stage, terminal=True)
    assert result.snapshot.entries == ()
    assert (
        result.snapshot.binding.arena_version
        == result.snapshot.binding.round_identity
        == 1
    )
    assert ledger.summary(auth) == before


def test_staging_handle_cannot_cross_cie_or_runtime(opened, other):
    ctx, _, _, cie = opened
    auth2, _ = ctx.fresh()
    cie2 = ctx.cie.open(auth2, 0)
    stage2 = ctx.cie.stage(cie2, ctx.cie.snapshot(cie2), (entry(),))
    old = ctx.cie.snapshot(cie)
    abort(FailureCode.CIE_STALE, lambda: ctx.cie.publish(cie, stage2))
    assert ctx.cie.snapshot(cie).canonical_bytes == old.canonical_bytes
    ctx.cie.abort(cie2)
    auth3, _ = other.fresh()
    cie3 = other.cie.open(auth3, 0)
    stage3 = other.cie.stage(cie3, other.cie.snapshot(cie3), ())
    abort(FailureCode.CIE_STALE, lambda: ctx.cie.publish(cie, stage3))
    other.cie.abort(cie3)


def test_conflicting_members_of_one_staged_batch_never_publish(opened):
    ctx, _, _, cie = opened
    old = ctx.cie.snapshot(cie)
    failure = abort(
        FailureCode.INTERNAL_CONTRACT_VIOLATION,
        lambda: ctx.cie.stage(cie, old, (entry(), entry(payload=d("different")))),
    )
    assert failure.result.snapshot.canonical_bytes == old.canonical_bytes
    assert epoch_record(cie).snapshot is epoch_record(cie).pending is None


def test_terminal_flag_requires_exact_bool_without_changing_live_state(opened):
    ctx, _, _, cie = opened
    stage = ctx.cie.stage(cie, ctx.cie.snapshot(cie), ())
    abort(FailureCode.INVALID_INPUT, lambda: ctx.cie.publish(cie, stage, terminal=1))
    assert ctx.cie.snapshot(cie).binding.arena_version == 0
    assert ctx.cie.publish(cie, stage).binding.arena_version == 1


UNIT4_DETERMINISTIC_SCRIPT = """
from hashlib import sha256
from dgca_lite import CoreConfig, CoreEngine
from dgca_lite.cognition.arena import ArenaEntry
from dgca_lite.cognition.cie import create_cie_runtime
from dgca_lite.cognition.identity import CanonicalDescriptor as D, ClaimContentID, ScopeIdentity
from dgca_lite.cognition.ingress import create_trusted_ingress_boundary
from dgca_lite.cognition.invocation import InvocationLimits, create_invocation_runtime
from dgca_lite.cognition.serialization import canonical_identity_bytes
core=CoreEngine(CoreConfig(receptor_fanout=1))
issuer=create_trusted_ingress_boundary(core,D('runtime',('fixed',)),D('source'))
parent=create_invocation_runtime(issuer.invocation_causes,InvocationLimits(8))
runtime=create_cie_runtime(parent)
cap=issuer.authorize_given(ClaimContentID(D('GroundAtom',('P',))),ScopeIdentity('FORMAL',D('source'),D('scope')),D('occurrence',(1,)))
auth=parent.admit(cap)
cie=runtime.open(auth,0)
data={name:ArenaEntry('STAGING_RECORD',D('entry',(name,)),D('value',(name,))) for name in {'c','a','b'}}
stage=runtime.stage(cie,runtime.snapshot(cie),tuple(data.values()))
result=runtime.publish(cie,stage,terminal=True)
encoded=canonical_identity_bytes(result.canonical_descriptor())
print(encoded.hex())
print(sha256(encoded).hexdigest())
"""


def test_independent_process_hash_seeds_produce_identical_unit4_bytes():
    results = []
    for seed in ("0", "1", "27", "123", "random"):
        env = dict(
            os.environ,
            PYTHONHASHSEED=seed,
            PYTHONDONTWRITEBYTECODE="1",
            PYTHONPATH=str(Path("src").resolve()),
        )
        results.append(
            subprocess.check_output(
                [sys.executable, "-B", "-c", UNIT4_DETERMINISTIC_SCRIPT],
                env=env,
                text=True,
            )
        )
    assert len(set(results)) == 1
    encoded, signature = results[0].splitlines()
    assert len(bytes.fromhex(encoded)) == 4995
    assert (
        signature == "fce32c535be52c8eb1655972a2ce1812fbfc44832e5965034cec0d8a19b3f9fd"
    )


@pytest.mark.parametrize("field_name", [f.name for f in fields(CIEPolicy)])
@pytest.mark.parametrize(
    "value", [True, False, 0, -1, float("nan"), float("inf"), "1", 99999999]
)
def test_policy_bounds_are_exact_finite_positive_integers(field_name, value):
    with pytest.raises(ValueError):
        CIEPolicy(**{field_name: value})
