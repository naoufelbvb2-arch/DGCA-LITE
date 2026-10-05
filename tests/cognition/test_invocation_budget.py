from __future__ import annotations

import copy
import gc
import inspect
import os
import pickle
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from itertools import count
from pathlib import Path
from threading import Barrier, Event, local

import pytest

from dgca_lite import CoreConfig, CoreEngine, SurfaceEvent
from dgca_lite.cognition import ingress as ingress_module
from dgca_lite.cognition import invocation as invocation_module
from dgca_lite.cognition.authority import (
    ExternalOccurrenceCapability,
    FormalSourceOccurrenceCapability,
    IngressAbort,
)
from dgca_lite.cognition.budget import (
    BudgetChargeView,
    BudgetLedgerView,
    BudgetReservation,
)
from dgca_lite.cognition.identity import (
    CanonicalDescriptor,
    ClaimContentID,
    InvocationCauseID,
    ScopeIdentity,
)
from dgca_lite.cognition.ingress import (
    InvocationCauseIngress,
    create_trusted_ingress_boundary,
)
from dgca_lite.cognition.invocation import (
    InvocationAuthority,
    InvocationBudgetLedger,
    InvocationLimits,
    InvocationRuntime,
    InvocationView,
    create_invocation_runtime,
)
from dgca_lite.cognition.serialization import canonical_identity_bytes
from dgca_lite.cognition.types import FailureCode, InvocationState
from dgca_lite.memory.integration import TrustedCoreAdapter
from dgca_lite.memory.session import retrieve_internal
from dgca_lite.persistence import engine_state


def d(kind, *values):
    return CanonicalDescriptor(kind, values)


def claim(value="P"):
    return ClaimContentID(d("GroundAtom", value))


def scope():
    return ScopeIdentity("FORMAL", d("source", "unit3"), d("scope", "main"))


names = count()


@dataclass
class Context:
    core: CoreEngine
    issuer: object
    runtime: InvocationRuntime

    def cause(self, value="P"):
        return self.issuer.authorize_given(
            claim(value), scope(), d("occurrence", next(names))
        )

    def fresh(self):
        capability = self.cause()
        authority = self.runtime.admit(capability)
        return capability, authority, self.runtime.ledger(authority)


def make_context(budget=8, capacity=128):
    core = CoreEngine(CoreConfig(receptor_fanout=1, K_R=32))
    issuer = create_trusted_ingress_boundary(
        core, d("unit3-runtime", next(names)), d("unit3-source"), capacity=512
    )
    runtime = create_invocation_runtime(
        issuer.invocation_causes, InvocationLimits(budget, capacity)
    )
    return Context(core, issuer, runtime)


@pytest.fixture(scope="module")
def context():
    ctx = make_context()
    yield ctx
    ctx.issuer.close()


@pytest.fixture(scope="module")
def other_context():
    ctx = make_context()
    yield ctx
    ctx.issuer.close()


def assert_abort(code, call):
    with pytest.raises(IngressAbort) as caught:
        call()
    assert caught.value.code is code


def finish(ctx, authority, ledger):
    closing = ctx.runtime.begin_close(authority, 0)
    ledger.retire_unused(authority, closing.revision)
    assert ctx.runtime.finalize_close(authority, closing.revision)


HANDLE_TYPES = (
    InvocationAuthority,
    InvocationRuntime,
    InvocationBudgetLedger,
    BudgetReservation,
    InvocationCauseIngress,
)


@pytest.mark.parametrize("handle_type", HANDLE_TYPES)
def test_live_handles_are_nonconstructible(handle_type):
    with pytest.raises(TypeError):
        handle_type()
    with pytest.raises(TypeError):
        handle_type(cause=d("forged"), revision=0)


@pytest.mark.parametrize("handle_type", HANDLE_TYPES)
def test_object_new_forgery_never_validates(context, handle_type):
    token, authority, ledger = context.fresh()
    forged = object.__new__(handle_type)
    if handle_type is InvocationAuthority:
        assert_abort(
            FailureCode.OWNER_AUTHORITY_STALE,
            lambda: context.runtime.validate(forged, 0),
        )
    elif handle_type is InvocationRuntime:
        assert_abort(FailureCode.OWNER_AUTHORITY_STALE, lambda: forged.admit(token))
    elif handle_type is InvocationBudgetLedger:
        assert_abort(
            FailureCode.OWNER_AUTHORITY_STALE,
            lambda: forged.reserve(authority, 0, 1, d("work")),
        )
    elif handle_type is InvocationCauseIngress:
        with pytest.raises(IngressAbort):
            create_invocation_runtime(forged, InvocationLimits(8))
    else:
        assert_abort(
            FailureCode.MISSING_BUDGET_CHARGE,
            lambda: ledger.consume(authority, 0, forged, 0, d("work")),
        )


@pytest.mark.parametrize(
    "operation", (copy.copy, copy.deepcopy, pickle.dumps, canonical_identity_bytes)
)
@pytest.mark.parametrize(
    "kind", ("authority", "runtime", "ledger", "reservation", "cause_ingress")
)
def test_copy_pickle_and_serialization_never_transport_authority(
    context, operation, kind
):
    if kind == "runtime":
        handle = context.runtime
    elif kind == "cause_ingress":
        handle = context.issuer.invocation_causes
    else:
        _, authority, ledger = context.fresh()
        handle = {"authority": authority, "ledger": ledger}.get(kind)
        if kind == "reservation":
            handle = ledger.reserve(authority, 0, 1, d("work"))
    with pytest.raises(TypeError):
        operation(handle)
    with pytest.raises(TypeError):
        canonical_identity_bytes(d("nested", handle))


def test_copied_fields_and_views_cannot_mint_invocations(context):
    token, authority, ledger = context.fresh()
    view = context.runtime.describe(authority)
    assertion = context.issuer.formal_reasoning.accept(token)
    reservation = ledger.reserve(authority, 0, 1, d("work"))
    charge = ledger.consume(authority, 0, reservation, 0, d("work"))
    for value in (
        view,
        view.cause,
        view.canonical_descriptor(),
        copy.deepcopy(view),
        canonical_identity_bytes(view.cause),
        assertion,
        assertion.canonical_descriptor(),
        context.issuer.describe(token),
        charge,
        charge.canonical_descriptor(),
        d("PredictionView", claim()),
        d("HistoricalResult", view.cause),
        None,
        True,
        1,
        d("forged-issuer"),
    ):
        before = context.runtime.registry_status
        with pytest.raises(IngressAbort):
            context.runtime.admit(value)
        assert context.runtime.registry_status == before
    forged = object.__new__(InvocationAuthority)
    for name, value in (
        ("cause", view.cause),
        ("revision", 0),
        ("runtime", view.runtime),
        ("issuer_id", "copied"),
    ):
        with pytest.raises(AttributeError):
            object.__setattr__(forged, name, value)
    assert_abort(
        FailureCode.OWNER_AUTHORITY_STALE, lambda: context.runtime.validate(forged, 0)
    )


def test_one_cause_one_authority_one_nonrenewable_budget(context):
    token, authority, ledger = context.fresh()
    reservation = ledger.reserve(authority, 0, 2, d("work"))
    ledger.consume(authority, 0, reservation, 0, d("work"))
    before = ledger.summary(authority)
    count_before = context.runtime.registry_status
    assert context.runtime.admit(token) is authority
    assert context.runtime.ledger(authority) is ledger
    assert ledger.summary(authority) == before
    assert context.runtime.registry_status == count_before
    with pytest.raises(TypeError):
        context.runtime.admit(token, initial_budget=99)


def test_independent_equal_content_occurrences_are_distinct_causes(context):
    first, second = context.cause(), context.cause()
    left, right = context.runtime.admit(first), context.runtime.admit(second)
    assert left is not right
    assert context.runtime.describe(left).cause != context.runtime.describe(right).cause
    assert context.runtime.ledger(left) is not context.runtime.ledger(right)
    assert (
        context.issuer.formal_reasoning.accept(first).semantic_key
        == context.issuer.formal_reasoning.accept(second).semantic_key
    )


def test_same_cause_concurrent_retry_has_one_linearized_admission(context):
    token = context.cause()
    before = context.runtime.registry_status[0]
    start = Barrier(12)

    def admit():
        start.wait(timeout=5)
        return context.runtime.admit(token)

    with ThreadPoolExecutor(max_workers=12) as pool:
        authorities = list(pool.map(lambda _: admit(), range(12)))
    assert all(value is authorities[0] for value in authorities)
    assert context.runtime.registry_status[0] == before + 1
    assert context.runtime.ledger(authorities[0]).summary(authorities[0]).initial == 8


def test_closing_closed_and_no_reopen(context):
    token, authority, ledger = context.fresh()
    first = context.runtime.describe(authority)
    assert first.state is InvocationState.ACTIVE and first.revision == 0
    assert_abort(
        FailureCode.INVOCATION_NOT_ACTIVE,
        lambda: context.runtime.finalize_close(authority, 0),
    )
    closing = context.runtime.begin_close(authority, 0)
    assert closing.state is InvocationState.CLOSING and closing.revision == 1
    assert context.runtime.admit(token) is authority
    assert context.runtime.begin_close(authority, 1) == closing
    assert_abort(
        FailureCode.OWNER_AUTHORITY_STALE,
        lambda: context.runtime.validate(authority, 0),
    )
    assert_abort(
        FailureCode.INVOCATION_NOT_ACTIVE,
        lambda: context.runtime.validate(authority, 1),
    )
    assert not context.runtime.finalize_close(authority, 1)
    ledger.retire_unused(authority, 1)
    assert context.runtime.finalize_close(authority, 1)
    closed = context.runtime.describe(authority)
    assert closed.state is InvocationState.CLOSED and closed.revision == 2
    assert context.runtime.admit(token) is authority
    assert context.runtime.ledger(authority) is ledger
    for call in (
        lambda: context.runtime.begin_close(authority, 2),
        lambda: context.runtime.finalize_close(authority, 2),
        lambda: context.runtime.validate(authority, 2),
        lambda: ledger.reserve(authority, 2, 1, d("work")),
        lambda: ledger.retire_unused(authority, 2),
    ):
        assert_abort(FailureCode.INVOCATION_NOT_ACTIVE, call)
    assert ledger.summary(authority).retired == 8
    assert context.runtime.describe(authority) == closed


def test_two_concurrent_close_attempts_advance_once(context):
    _, authority, _ = context.fresh()
    start = Barrier(2)

    def close():
        start.wait(timeout=5)
        try:
            return context.runtime.begin_close(authority, 0)
        except IngressAbort as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: close(), range(2)))
    assert sum(type(value) is InvocationView for value in outcomes) == 1
    assert FailureCode.OWNER_AUTHORITY_STALE in outcomes
    assert context.runtime.describe(authority).revision == 1


@pytest.mark.parametrize("revision", (True, False, -1, 1.0, "0", None))
def test_revision_types_are_closed_and_bool_is_not_int(context, revision):
    _, authority, _ = context.fresh()
    assert_abort(
        FailureCode.INVALID_INPUT, lambda: context.runtime.validate(authority, revision)
    )
    assert context.runtime.describe(authority).revision == 0


def test_stale_source_and_cross_runtime_substitution(context, other_context):
    token, authority, ledger = context.fresh()
    _, other, other_ledger = other_context.fresh()
    with pytest.raises(IngressAbort):
        other_context.runtime.admit(token)
    assert_abort(
        FailureCode.OWNER_AUTHORITY_STALE,
        lambda: other_context.runtime.validate(authority, 0),
    )
    assert_abort(
        FailureCode.OWNER_AUTHORITY_STALE,
        lambda: other_ledger.reserve(authority, 0, 1, d("work")),
    )
    assert_abort(
        FailureCode.OWNER_AUTHORITY_STALE,
        lambda: ledger.reserve(other, 0, 1, d("work")),
    )
    ctx = make_context()
    try:
        stale = ctx.cause()
        ctx.issuer.invalidate()
        with pytest.raises(IngressAbort):
            ctx.runtime.admit(stale)
        assert ctx.runtime.registry_status == (0, 128)
    finally:
        ctx.issuer.close()


def test_all_trusted_unit2_cause_paths_and_no_issuer_surface():
    ctx = make_context()
    try:
        given = ctx.cause()
        assumed = ctx.issuer.authorize_assumption(
            claim("H"), scope(), d("assumption", 1)
        )
        constraint = ctx.issuer.authorize_constraint_given(
            ClaimContentID(d("SingleValued", d("slot"))), scope(), d("constraint", 1)
        )
        assumed_constraint = ctx.issuer.authorize_constraint_assumption(
            ClaimContentID(d("FormalNegation", claim("Q"))), d("constraint", 2), assumed
        )
        with ctx.issuer.core_transition():
            event = TrustedCoreAdapter.process_event(
                ctx.core, SurfaceEvent.from_text("x")
            )
            observed = ctx.issuer.authorize_core_observation(event.receipt, scope())
        for token in (given, assumed, constraint, assumed_constraint, observed):
            authority = ctx.runtime.admit(token)
            ctx.runtime.validate(authority, 0)
            assert (
                ctx.runtime.describe(authority).cause.occurrence_descriptor
                == ctx.issuer.describe(token).occurrence
            )
        for handle in (
            ctx.runtime,
            ctx.issuer.invocation_causes,
            authority,
            ctx.runtime.ledger(authority),
        ):
            assert not hasattr(handle, "authorize_given")
            assert not hasattr(handle, "authorize_core_observation")
            assert not hasattr(handle, "issuer")
            assert not hasattr(handle, "core")
        for data in (
            event.receipt,
            event.tick_result,
            ctx.issuer.observations.accept(observed),
        ):
            with pytest.raises(IngressAbort):
                ctx.runtime.admit(data)
        retrieved = retrieve_internal(ctx.core, {})
        with pytest.raises(IngressAbort):
            ctx.runtime.admit(retrieved)
    finally:
        ctx.issuer.close()


def test_basis_identity_cannot_be_swapped_to_create_a_cause(context):
    token = context.cause()
    object.__setattr__(token, "__class__", ExternalOccurrenceCapability)
    try:
        with pytest.raises(IngressAbort):
            context.runtime.admit(token)
    finally:
        object.__setattr__(token, "__class__", FormalSourceOccurrenceCapability)
    assert context.runtime.admit(token) is context.runtime.admit(token)


@pytest.mark.parametrize(
    "kind", ("authority", "runtime", "ledger", "reservation", "cause_ingress")
)
def test_handle_class_recasting_does_not_promote_authority(context, kind):
    token, authority, ledger = context.fresh()
    reservation = ledger.reserve(authority, 0, 1, d("work"))
    original = {
        "authority": authority,
        "runtime": context.runtime,
        "ledger": ledger,
        "reservation": reservation,
        "cause_ingress": context.issuer.invocation_causes,
    }[kind]
    old_type = type(original)
    new_type = (
        BudgetReservation if old_type is not BudgetReservation else InvocationAuthority
    )
    object.__setattr__(original, "__class__", new_type)
    try:
        with pytest.raises(IngressAbort):
            if kind == "runtime":
                InvocationRuntime.admit(original, token)
            elif kind == "ledger":
                InvocationBudgetLedger.reserve(original, authority, 0, 1, d("work"))
            elif kind == "cause_ingress":
                context.runtime.admit(context.cause())
            elif kind == "reservation":
                ledger.consume(authority, 0, original, 0, d("work"))
            else:
                context.runtime.validate(original, 0)
    finally:
        object.__setattr__(original, "__class__", old_type)


def test_budget_conservation_and_exact_charge_binding(context):
    _, authority, ledger = context.fresh()
    assert ledger.summary(authority) == BudgetLedgerView(
        context.runtime.describe(authority).identity, 8, 8, 0, 0, 0
    )
    reservation = ledger.reserve(authority, 0, 3, d("complete-work"))
    descriptor = ledger.reservation_view(authority, 0, reservation)
    assert descriptor.values[1] == (0, 1, 2)
    charge = ledger.consume(authority, 0, reservation, 1, d("complete-work"))
    assert type(charge) is BudgetChargeView
    assert charge.owner_identity == context.runtime.describe(authority).identity
    assert charge.reservation_identity == descriptor.values[0]
    assert charge.work_class == d("complete-work")
    assert charge.unit_identity.values == (descriptor.values[0], 1)
    assert ledger.unit_state(authority, 1) == "CONSUMED"
    ledger.retire(authority, 0, reservation)
    assert (
        ledger.unit_state(authority, 0) == ledger.unit_state(authority, 2) == "RETIRED"
    )
    assert ledger.summary(authority) == BudgetLedgerView(
        charge.owner_identity, 8, 5, 0, 1, 2
    )
    finish(context, authority, ledger)
    assert ledger.summary(authority) == BudgetLedgerView(
        charge.owner_identity, 8, 0, 0, 1, 7
    )


@pytest.mark.parametrize("amount", (0, -1, True, False, 1.0, "1", None))
def test_reservation_amounts_are_exact_positive_integers(context, amount):
    _, authority, ledger = context.fresh()
    before = ledger.summary(authority)
    assert_abort(
        FailureCode.INVALID_INPUT,
        lambda: ledger.reserve(authority, 0, amount, d("work")),
    )
    assert ledger.summary(authority) == before


def test_insufficient_complete_frontier_reservation_changes_nothing(context):
    _, authority, ledger = context.fresh()
    ledger.reserve(authority, 0, 6, d("first"))
    before = ledger.summary(authority)
    for amount in (3, 9, 10**100):
        assert_abort(
            FailureCode.BUDGET_ABORT,
            lambda amount=amount: ledger.reserve(
                authority, 0, amount, d("complete-frontier")
            ),
        )
        assert ledger.summary(authority) == before
    last = ledger.reserve(authority, 0, 2, d("last"))
    assert ledger.reservation_view(authority, 0, last).values[0].values[1] == 1


def test_double_consumption_retired_resurrection_and_reservation_reuse(context):
    _, authority, ledger = context.fresh()
    token = ledger.reserve(authority, 0, 2, d("work"))
    charge = ledger.consume(authority, 0, token, 0, d("work"))
    assert_abort(
        FailureCode.MISSING_BUDGET_CHARGE,
        lambda: ledger.consume(authority, 0, token, 0, d("work")),
    )
    ledger.retire(authority, 0, token)
    assert_abort(
        FailureCode.MISSING_BUDGET_CHARGE,
        lambda: ledger.consume(authority, 0, token, 1, d("work")),
    )
    assert_abort(
        FailureCode.MISSING_BUDGET_CHARGE, lambda: ledger.retire(authority, 0, token)
    )
    for data in (
        copy.deepcopy(charge),
        charge.canonical_descriptor(),
        ledger.reservation_view(authority, 0, token),
    ):
        assert_abort(
            FailureCode.MISSING_BUDGET_CHARGE,
            lambda data=data: ledger.consume(authority, 0, data, 1, d("work")),
        )
    assert ledger.summary(authority).available == 6


def test_cross_invocation_budget_and_work_class_are_not_substitutable(context):
    _, left, left_ledger = context.fresh()
    _, right, right_ledger = context.fresh()
    reserved = left_ledger.reserve(left, 0, 2, d("work"))
    other = right_ledger.reserve(right, 0, 2, d("work"))
    assert_abort(
        FailureCode.AMBIGUOUS_BUDGET_OWNER,
        lambda: left_ledger.reserve(right, 0, 1, d("work")),
    )
    assert_abort(
        FailureCode.MISSING_BUDGET_CHARGE,
        lambda: left_ledger.consume(left, 0, other, 0, d("work")),
    )
    for wrong in (d("other-work"), "work", True):
        assert_abort(
            FailureCode.BUDGET_WORKCLASS_MISMATCH,
            lambda wrong=wrong: left_ledger.consume(left, 0, reserved, 0, wrong),
        )
    with pytest.raises(TypeError):
        left_ledger.reserve(left, 0, 1, d("work"), source_kind="FORECAST_ESCROW")
    assert (
        left_ledger.summary(left).consumed == right_ledger.summary(right).consumed == 0
    )


@pytest.mark.parametrize("index", (True, False, -1, 8, 0.0, "0", None))
def test_charge_unit_indices_distinguish_bool_int_and_membership(context, index):
    _, authority, ledger = context.fresh()
    token = ledger.reserve(authority, 0, 1, d("work"))
    assert_abort(
        FailureCode.INVALID_INPUT,
        lambda: ledger.consume(authority, 0, token, index, d("work")),
    )
    assert ledger.summary(authority).consumed == 0


def test_nonmember_unit_does_not_consume_another_reservation(context):
    _, authority, ledger = context.fresh()
    first = ledger.reserve(authority, 0, 1, d("work"))
    second = ledger.reserve(authority, 0, 1, d("work"))
    assert_abort(
        FailureCode.MISSING_BUDGET_CHARGE,
        lambda: ledger.consume(authority, 0, first, 1, d("work")),
    )
    ledger.consume(authority, 0, second, 1, d("work"))
    assert ledger.unit_state(authority, 0) == "RESERVED"


def test_mutation_cannot_change_private_budget_or_identity_snapshots(context):
    _, authority, ledger = context.fresh()
    work = d("work", d("payload", "frozen"))
    reservation = ledger.reserve(authority, 0, 1, work)
    object.__setattr__(work.values[0], "values", ("changed",))
    assert_abort(
        FailureCode.BUDGET_WORKCLASS_MISMATCH,
        lambda: ledger.consume(authority, 0, reservation, 0, work),
    )
    view = context.runtime.describe(authority)
    object.__setattr__(view.identity, "values", ("forged",))
    assert context.runtime.describe(authority).identity != view.identity
    descriptor = ledger.reservation_view(authority, 0, reservation)
    object.__setattr__(descriptor.values[2].values[0], "values", ("changed-again",))
    charge = ledger.consume(
        authority, 0, reservation, 0, d("work", d("payload", "frozen"))
    )
    assert charge.work_class == d("work", d("payload", "frozen"))


def test_failure_before_reservation_or_consumption_publication_is_atomic(
    context, monkeypatch
):
    _, authority, ledger = context.fresh()
    before = ledger.summary(authority)
    original = invocation_module._snapshot

    def failing(value):
        raise ValueError("staged snapshot failure")

    with monkeypatch.context() as patch:
        patch.setattr(invocation_module, "_snapshot", failing)
        assert_abort(
            FailureCode.INVALID_INPUT,
            lambda: ledger.reserve(authority, 0, 1, d("work")),
        )
    assert ledger.summary(authority) == before
    reservation = ledger.reserve(authority, 0, 1, d("work"))
    assert ledger.reservation_view(authority, 0, reservation).values[0].values[1] == 0
    before = ledger.summary(authority)
    with monkeypatch.context() as patch:
        patch.setattr(invocation_module, "_snapshot", failing)
        with pytest.raises(ValueError):
            ledger.consume(authority, 0, reservation, 0, d("work"))
    assert ledger.summary(authority) == before
    assert invocation_module._snapshot is original


def test_failed_admission_weakref_allocation_leaves_no_authority_or_budget(
    context, monkeypatch
):
    token = context.cause()
    before = context.runtime.registry_status
    original = invocation_module.ref
    calls = 0

    def fail_second(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise MemoryError("injected second index failure")
        return original(*args)

    with monkeypatch.context() as patch:
        patch.setattr(invocation_module, "ref", fail_second)
        with pytest.raises(MemoryError):
            context.runtime.admit(token)
    assert context.runtime.registry_status == before
    authority = context.runtime.admit(token)
    assert context.runtime.ledger(authority).summary(authority).available == 8


def test_container_bound_precedes_semantic_member_inspection(context):
    _, authority, ledger = context.fresh()
    oversized = object.__new__(CanonicalDescriptor)
    object.__setattr__(oversized, "kind", "work")
    object.__setattr__(oversized, "values", (object(),) * 4097)
    before = ledger.summary(authority)
    assert_abort(
        FailureCode.INVALID_INPUT, lambda: ledger.reserve(authority, 0, 1, oversized)
    )
    assert ledger.summary(authority) == before


@pytest.mark.parametrize(
    "kwargs",
    (
        {"initial_budget": False},
        {"initial_budget": float("nan")},
        {"initial_budget": -1},
        {"initial_budget": True},
        {"initial_budget": 1.0},
        {"initial_budget": 257},
        {"initial_budget": 8, "cause_capacity": 0},
        {"initial_budget": 8, "cause_capacity": True},
        {"initial_budget": 8, "cause_capacity": 4097},
    ),
)
def test_frozen_runtime_limits_are_finite_and_strict(kwargs):
    with pytest.raises(ValueError):
        InvocationLimits(**kwargs)


def test_cause_registry_capacity_includes_terminal_tombstones():
    ctx = make_context(budget=1, capacity=2)
    try:
        first, authority, ledger = ctx.fresh()
        finish(ctx, authority, ledger)
        second, other, other_ledger = ctx.fresh()
        finish(ctx, other, other_ledger)
        assert ctx.runtime.registry_status == (2, 2)
        assert ctx.runtime.admit(first) is authority
        assert ctx.runtime.admit(second) is other
        assert_abort(FailureCode.CAPACITY_ABORT, lambda: ctx.runtime.admit(ctx.cause()))
        assert ctx.runtime.describe(authority).state is InvocationState.CLOSED
    finally:
        ctx.issuer.close()


def test_runtime_policy_is_snapshotted_and_cannot_be_refreshed(context):
    with pytest.raises(IngressAbort):
        create_invocation_runtime(
            context.issuer.invocation_causes, InvocationLimits(256)
        )
    ctx_core = CoreEngine()
    issuer = create_trusted_ingress_boundary(
        ctx_core, d("unit3-policy", next(names)), d("source")
    )
    limits = InvocationLimits(3, 2)
    runtime = create_invocation_runtime(issuer.invocation_causes, limits)
    try:
        object.__setattr__(limits, "initial_budget", 256)
        object.__setattr__(limits, "cause_capacity", 4096)
        token = issuer.authorize_given(claim(), scope(), d("occurrence", 0))
        authority = runtime.admit(token)
        assert runtime.registry_status == (1, 2)
        assert runtime.ledger(authority).summary(authority).initial == 3
    finally:
        issuer.close()


def test_runtime_gc_cannot_reset_cause_or_resurrect_retained_handles():
    ctx = make_context()
    token, authority, ledger = ctx.fresh()
    ingress = ctx.issuer.invocation_causes
    del ctx.runtime
    gc.collect()
    assert_abort(
        FailureCode.OWNER_AUTHORITY_STALE,
        lambda: ledger.reserve(authority, 0, 1, d("work")),
    )
    assert_abort(
        FailureCode.INVALID_FORMAL_AUTHORITY,
        lambda: create_invocation_runtime(ingress, InvocationLimits(8)),
    )
    with pytest.raises(TypeError):
        InvocationAuthority(cause=token)
    ctx.issuer.close()


def test_bool_and_int_source_occurrences_are_different_canonical_causes():
    ctx = make_context()
    try:
        first = ctx.issuer.authorize_given(claim(), scope(), d("occurrence", True))
        second = ctx.issuer.authorize_given(claim(), scope(), d("occurrence", 1))
        left, right = ctx.runtime.admit(first), ctx.runtime.admit(second)
        assert left is not right
        assert ctx.runtime.describe(left).cause != ctx.runtime.describe(right).cause
    finally:
        ctx.issuer.close()


def test_reservation_close_race_is_linearizable(context):
    _, authority, ledger = context.fresh()
    start = Barrier(2)

    def reserve():
        start.wait(timeout=5)
        try:
            return ledger.reserve(authority, 0, 3, d("work"))
        except IngressAbort as error:
            return error.code

    def close():
        start.wait(timeout=5)
        return context.runtime.begin_close(authority, 0)

    with ThreadPoolExecutor(max_workers=2) as pool:
        reservation = pool.submit(reserve)
        closing = pool.submit(close).result(timeout=5)
        outcome = reservation.result(timeout=5)
    assert closing.revision == 1
    assert ledger.summary(authority).reserved == (
        3 if type(outcome) is BudgetReservation else 0
    )
    if type(outcome) is BudgetReservation:
        assert_abort(
            FailureCode.OWNER_AUTHORITY_STALE,
            lambda: ledger.consume(authority, 0, outcome, 0, d("work")),
        )
        assert_abort(
            FailureCode.INVOCATION_NOT_ACTIVE,
            lambda: ledger.consume(authority, 1, outcome, 0, d("work")),
        )
    ledger.retire_unused(authority, 1)
    assert context.runtime.finalize_close(authority, 1)


def test_retry_and_close_race_never_publish_new_authority(context):
    token, authority, ledger = context.fresh()
    before = context.runtime.registry_status
    start = Barrier(8)

    def run(index):
        start.wait(timeout=5)
        return (
            context.runtime.begin_close(authority, 0)
            if index == 0
            else context.runtime.admit(token)
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(run, range(8)))
    assert all(result is authority for result in outcomes[1:])
    assert context.runtime.registry_status == before
    assert ledger.summary(authority).initial == 8


def test_active_guard_and_close_are_ordered_and_no_future_child_can_open(context):
    _, authority, ledger = context.fresh()
    entered, release, attempted = Event(), Event(), Event()

    def future_child_gate():
        with context.runtime.active_guard(authority, 0):
            entered.set()
            assert release.wait(timeout=5)

    def close():
        attempted.set()
        return context.runtime.begin_close(authority, 0)

    with ThreadPoolExecutor(max_workers=2) as pool:
        active = pool.submit(future_child_gate)
        assert entered.wait(timeout=5)
        closing = pool.submit(close)
        assert attempted.wait(timeout=5)
        assert not closing.done()
        release.set()
        active.result(timeout=5)
        assert closing.result(timeout=5).revision == 1
    for revision in (0, 1):
        with (
            pytest.raises(IngressAbort),
            context.runtime.active_guard(authority, revision),
        ):
            pytest.fail("new child gate after closing")
    assert not context.runtime.finalize_close(authority, 1)
    # No wait/held barrier after an incomplete finalization: another thread
    # independently drains Unit-3 obligations and reads the lifecycle.
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(ledger.retire_unused, authority, 1).result(timeout=5)
        assert (
            pool.submit(context.runtime.describe, authority).result(timeout=5).state
            is InvocationState.CLOSING
        )
    assert context.runtime.finalize_close(authority, 1)


def test_no_core_guard_can_be_acquired_below_lifecycle(context, other_context):
    token, authority, _ = context.fresh()
    other = other_context.cause()
    with context.runtime.active_guard(authority, 0):
        assert_abort(
            FailureCode.INTERNAL_CONTRACT_VIOLATION,
            lambda: context.runtime.admit(token),
        )
        assert_abort(
            FailureCode.INTERNAL_CONTRACT_VIOLATION,
            lambda: other_context.runtime.admit(other),
        )
        assert_abort(
            FailureCode.INTERNAL_CONTRACT_VIOLATION,
            lambda: create_invocation_runtime(
                context.issuer.invocation_causes, InvocationLimits(8)
            ),
        )


def test_source_invalidation_cannot_overtake_admission(context, monkeypatch):
    token = context.cause()
    entered, release, attempted = Event(), Event(), Event()
    original = ingress_module._snapshot

    def paused(value):
        if type(value) is InvocationCauseID:
            entered.set()
            assert release.wait(timeout=5)
        return original(value)

    # Use a separate source because invalidation must not spoil the module fixture.
    ctx = make_context()
    token = ctx.cause()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(ingress_module, "_snapshot", paused)
            with ThreadPoolExecutor(max_workers=2) as pool:
                admission = pool.submit(ctx.runtime.admit, token)
                assert entered.wait(timeout=5)

                def invalidate():
                    attempted.set()
                    ctx.issuer.invalidate()

                invalidation = pool.submit(invalidate)
                assert attempted.wait(timeout=5)
                assert not invalidation.done()
                release.set()
                authority = admission.result(timeout=5)
                invalidation.result(timeout=5)
        ctx.runtime.validate(authority, 0)
        assert ctx.runtime.registry_status[0] == 1
        with pytest.raises(IngressAbort):
            ctx.runtime.admit(token)
    finally:
        ctx.issuer.close()


def test_inflight_runtime_use_pins_owner_until_quiescence(monkeypatch):
    ctx = make_context()
    _, authority, ledger = ctx.fresh()
    entered, release = Event(), Event()
    original = invocation_module._snapshot

    def paused(value):
        if type(value) is CanonicalDescriptor and value.kind == "work":
            entered.set()
            assert release.wait(timeout=5)
        return original(value)

    with monkeypatch.context() as patch:
        patch.setattr(invocation_module, "_snapshot", paused)
        with ThreadPoolExecutor(max_workers=1) as pool:
            reservation = pool.submit(ledger.reserve, authority, 0, 1, d("work"))
            assert entered.wait(timeout=5)
            del ctx.runtime
            gc.collect()
            release.set()
            assert type(reservation.result(timeout=5)) is BudgetReservation
    gc.collect()
    assert_abort(FailureCode.OWNER_AUTHORITY_STALE, lambda: ledger.summary(authority))
    ctx.issuer.close()


def test_lower_layer_conservation_and_historical_outputs(context):
    before = copy.deepcopy(engine_state(context.core))
    token, authority, ledger = context.fresh()
    reservation = ledger.reserve(authority, 0, 2, d("work"))
    charge = ledger.consume(authority, 0, reservation, 0, d("work"))
    historical = context.runtime.describe(authority)
    signature = canonical_identity_bytes(historical.canonical_descriptor())
    finish(context, authority, ledger)
    assert engine_state(context.core) == before
    assert canonical_identity_bytes(historical.canonical_descriptor()) == signature
    assert copy.deepcopy(charge) == charge
    for value in (
        historical,
        historical.canonical_descriptor(),
        charge.canonical_descriptor(),
    ):
        with pytest.raises(IngressAbort):
            context.runtime.admit(value)
    assert context.runtime.admit(token) is authority


UNIT3_DETERMINISTIC_SCRIPT = """
import hashlib
from dgca_lite import CoreEngine
from dgca_lite.cognition.identity import CanonicalDescriptor as D, ClaimContentID, ScopeIdentity
from dgca_lite.cognition.ingress import create_trusted_ingress_boundary
from dgca_lite.cognition.invocation import InvocationLimits, create_invocation_runtime
from dgca_lite.cognition.serialization import canonical_identity_bytes
owner=create_trusted_ingress_boundary(CoreEngine(),D('runtime',('unit3',)),D('formal-source'))
runtime=create_invocation_runtime(owner.invocation_causes,InvocationLimits(4,4))
scope=ScopeIdentity('FORMAL',D('source'),D('scope'))
outputs=[]
for name in {'gamma','alpha','beta'}:
    token=owner.authorize_given(ClaimContentID(D('GroundAtom',(name,))),scope,D('occurrence',(name,)))
    authority=runtime.admit(token)
    ledger=runtime.ledger(authority)
    reservation=ledger.reserve(authority,0,2,D('complete-work',(name,)))
    charge=ledger.consume(authority,0,reservation,0,D('complete-work',(name,)))
    closing=runtime.begin_close(authority,0)
    ledger.retire_unused(authority,closing.revision)
    assert runtime.finalize_close(authority,closing.revision)
    outputs.append((runtime.describe(authority).canonical_descriptor(),ledger.summary(authority).canonical_descriptor(),charge.canonical_descriptor()))
payload=canonical_identity_bytes(tuple(sorted(outputs,key=canonical_identity_bytes)))
print(payload.hex())
print(hashlib.sha256(payload).hexdigest())
"""


def test_independent_process_hash_seed_and_admission_order_determinism():
    outputs = []
    for seed in ("0", "1", "27", "123", "random"):
        environment = dict(
            os.environ,
            PYTHONHASHSEED=seed,
            PYTHONDONTWRITEBYTECODE="1",
            PYTHONPATH=str(Path("src").resolve()),
        )
        outputs.append(
            subprocess.check_output(
                [sys.executable, "-B", "-c", UNIT3_DETERMINISTIC_SCRIPT],
                env=environment,
                text=True,
            )
        )
    assert all(output == outputs[0] for output in outputs)
    encoded, signature = outputs[0].splitlines()
    assert len(bytes.fromhex(encoded)) == 16500
    assert (
        signature == "ce1eade88899480f60f12e5c9de7344e90f022f4b2b37b3d206f55430abd7fed"
    )


def test_runtime_domain_audit_is_bounded_and_never_recycled():
    script = """
from dgca_lite import CoreEngine
from dgca_lite.cognition.identity import CanonicalDescriptor as D
from dgca_lite.cognition.ingress import create_trusted_ingress_boundary
from dgca_lite.cognition.invocation import InvocationLimits, create_invocation_runtime
from dgca_lite.cognition.authority import IngressAbort
from dgca_lite.cognition.types import FailureCode
for index in range(64):
    owner=create_trusted_ingress_boundary(CoreEngine(),D('runtime',(index,)),D('source'))
    ingress=owner.invocation_causes
    runtime=create_invocation_runtime(ingress,InvocationLimits(1,1))
    del runtime
    try: create_invocation_runtime(ingress,InvocationLimits(2,1))
    except IngressAbort as error: assert error.code is FailureCode.INVALID_FORMAL_AUTHORITY
    else: raise AssertionError('runtime replay refreshed budget')
    owner.close()
print('64 bounded runtime identities; no recycling')
"""
    environment = dict(
        os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(Path("src").resolve())
    )
    output = subprocess.check_output(
        [sys.executable, "-B", "-c", script], env=environment, text=True
    )
    assert "64 bounded runtime identities; no recycling" in output


def test_finalizer_already_has_a_future_child_readiness_guard(context):
    # White-box structural check only: no child authority/type is implemented.
    _, authority, ledger = context.fresh()
    access = inspect.getclosurevars(InvocationRuntime.describe).nonlocals["access"]
    with access(context.runtime, "RUNTIME") as (domain, _):
        record = next(
            value for value in domain.causes.values() if value.authority is authority
        )
        with domain.lifecycle:
            record.nondelegated_children = 1
    context.runtime.begin_close(authority, 0)
    ledger.retire_unused(authority, 1)
    assert not context.runtime.finalize_close(authority, 1)
    with access(context.runtime, "RUNTIME") as (domain, _), domain.lifecycle:
        record.nondelegated_children = 0
    assert context.runtime.finalize_close(authority, 1)


def test_concurrent_consumption_has_one_exact_charge(context):
    _, authority, ledger = context.fresh()
    reservation = ledger.reserve(authority, 0, 1, d("work"))
    start = Barrier(8)

    def consume():
        start.wait(timeout=5)
        try:
            return ledger.consume(authority, 0, reservation, 0, d("work"))
        except IngressAbort as error:
            return error.code

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda _: consume(), range(8)))
    assert sum(type(value) is BudgetChargeView for value in outcomes) == 1
    assert outcomes.count(FailureCode.MISSING_BUDGET_CHARGE) == 7
    assert ledger.summary(authority).consumed == 1


def test_charge_and_close_race_is_linearizable(context):
    _, authority, ledger = context.fresh()
    reservation = ledger.reserve(authority, 0, 1, d("work"))
    start = Barrier(2)

    def consume():
        start.wait(timeout=5)
        try:
            return ledger.consume(authority, 0, reservation, 0, d("work"))
        except IngressAbort as error:
            return error.code

    def close():
        start.wait(timeout=5)
        return context.runtime.begin_close(authority, 0)

    with ThreadPoolExecutor(max_workers=2) as pool:
        charged = pool.submit(consume)
        assert pool.submit(close).result(timeout=5).revision == 1
        result = charged.result(timeout=5)
    ledger.retire_unused(authority, 1)
    consumed = 1 if type(result) is BudgetChargeView else 0
    assert ledger.summary(authority).consumed == consumed
    assert ledger.summary(authority).retired == 8 - consumed
    assert context.runtime.finalize_close(authority, 1)


def test_concurrent_finalization_closes_once(context):
    _, authority, ledger = context.fresh()
    context.runtime.begin_close(authority, 0)
    ledger.retire_unused(authority, 1)
    start = Barrier(2)

    def finalize():
        start.wait(timeout=5)
        try:
            return context.runtime.finalize_close(authority, 1)
        except IngressAbort as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: finalize(), range(2)))
    assert outcomes.count(True) == 1
    assert FailureCode.OWNER_AUTHORITY_STALE in outcomes
    assert context.runtime.describe(authority).revision == 2


def test_all_retired_active_budget_cannot_regenerate(context):
    _, authority, ledger = context.fresh()
    ledger.retire_unused(authority, 0)
    context.runtime.validate(authority, 0)
    assert ledger.summary(authority).retired == 8
    assert_abort(
        FailureCode.BUDGET_ABORT, lambda: ledger.reserve(authority, 0, 1, d("work"))
    )
    for index in range(8):
        assert ledger.unit_state(authority, index) == "RETIRED"
    ledger.retire_unused(authority, 0)
    assert ledger.summary(authority).available == 0


def test_completely_consumed_budget_permits_nonblocking_close(context):
    _, authority, ledger = context.fresh()
    reservation = ledger.reserve(authority, 0, 8, d("work"))
    for index in range(8):
        ledger.consume(authority, 0, reservation, index, d("work"))
    assert ledger.summary(authority).consumed == 8
    context.runtime.begin_close(authority, 0)
    assert context.runtime.finalize_close(authority, 1)
    assert ledger.summary(authority).consumed == 8


def test_maximum_initial_budget_is_exact_and_fully_reservable():
    ctx = make_context(budget=256, capacity=1)
    try:
        _, authority, ledger = ctx.fresh()
        reservation = ledger.reserve(authority, 0, 256, d("complete-frontier"))
        assert ledger.summary(authority).reserved == 256
        assert len(ledger.reservation_view(authority, 0, reservation).values[1]) == 256
        ledger.consume(authority, 0, reservation, 255, d("complete-frontier"))
        finish(ctx, authority, ledger)
        assert ledger.summary(authority).consumed == 1
        assert ledger.summary(authority).retired == 255
    finally:
        ctx.issuer.close()


def test_equal_occurrence_and_content_bytes_do_not_equal_cross_domain_cause(
    context, other_context
):
    occurrence = d("shared-occurrence", next(names))
    left = context.issuer.authorize_given(claim(), scope(), occurrence)
    right = other_context.issuer.authorize_given(claim(), scope(), occurrence)
    a, b = context.runtime.admit(left), other_context.runtime.admit(right)
    assert (
        context.runtime.describe(a).cause.occurrence_descriptor
        == other_context.runtime.describe(b).cause.occurrence_descriptor
    )
    assert context.runtime.describe(a).cause != other_context.runtime.describe(b).cause
    with pytest.raises(IngressAbort):
        context.runtime.admit(right)


def test_terminal_retry_loop_is_bounded_and_budget_never_refreshes():
    ctx = make_context(budget=2, capacity=1)
    try:
        token, authority, ledger = ctx.fresh()
        finish(ctx, authority, ledger)
        before = (
            ctx.runtime.describe(authority),
            ledger.summary(authority),
            ctx.runtime.registry_status,
        )
        for _ in range(200):
            assert ctx.runtime.admit(token) is authority
        assert (
            ctx.runtime.describe(authority),
            ledger.summary(authority),
            ctx.runtime.registry_status,
        ) == before
    finally:
        ctx.issuer.close()


@pytest.mark.parametrize(
    "field,value",
    (("state", "ACTIVE"), ("state", True), ("identity", d("caller-chosen"))),
)
def test_invocation_view_is_closed_canonical_data_not_arbitrary_labels(
    context, field, value
):
    _, authority, _ = context.fresh()
    view = context.runtime.describe(authority)
    fields = {
        name: getattr(view, name)
        for name in ("identity", "cause", "runtime", "revision", "state")
    }
    fields[field] = value
    with pytest.raises((TypeError, ValueError)):
        InvocationView(**fields)


def test_bootstrap_weakref_failure_does_not_consume_runtime_identity(monkeypatch):
    core = CoreEngine()
    issuer = create_trusted_ingress_boundary(
        core, d("failed-bootstrap", next(names)), d("source")
    )

    def failing(*args):
        raise MemoryError("bootstrap registry failure")

    try:
        with monkeypatch.context() as patch:
            patch.setattr(invocation_module, "ref", failing)
            with pytest.raises(MemoryError):
                create_invocation_runtime(issuer.invocation_causes, InvocationLimits(8))
        runtime = create_invocation_runtime(
            issuer.invocation_causes, InvocationLimits(8)
        )
        assert runtime.registry_status == (0, 128)
    finally:
        issuer.close()


def test_canonical_lock_order_is_observed_at_runtime(context):
    token, authority, ledger = context.fresh()
    access = inspect.getclosurevars(InvocationRuntime.describe).nonlocals["access"]
    with access(context.runtime, "RUNTIME") as (domain, _):
        item = next(
            value for value in domain.causes.values() if value.authority is authority
        )
    state_for = inspect.getclosurevars(
        inspect.unwrap(type(context.issuer).core_transition)
    ).nonlocals["state_for"]
    ingress_state = state_for(context.issuer, "ISSUER")
    registry_cell = InvocationRuntime.describe.__closure__[
        InvocationRuntime.describe.__code__.co_freevars.index("registry_lock")
    ]
    held = local()
    trace = []

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

    old_core, old_life, old_budget, old_registry = (
        ingress_state.barrier,
        domain.lifecycle.lock,
        item.budget.lock,
        registry_cell.cell_contents,
    )
    try:
        ingress_state.barrier = OrderedLock(old_core, 0)
        domain.lifecycle.lock = OrderedLock(old_life, 1)
        item.budget.lock = OrderedLock(old_budget, 2)
        registry_cell.cell_contents = OrderedLock(old_registry, 5)
        assert context.runtime.admit(token) is authority
        reservation = ledger.reserve(authority, 0, 1, d("work"))
        ledger.consume(authority, 0, reservation, 0, d("work"))
        context.runtime.describe(authority)
        ledger.summary(authority)
        finish(context, authority, ledger)
        assert {0, 1, 2, 5}.issubset(trace)
    finally:
        (
            ingress_state.barrier,
            domain.lifecycle.lock,
            item.budget.lock,
            registry_cell.cell_contents,
        ) = old_core, old_life, old_budget, old_registry


def test_admission_prospectively_rejects_a_cause_that_cannot_close(context):
    occurrence = d("large-occurrence", next(names), *((None,) * 2600))
    token = context.issuer.authorize_given(claim(), scope(), occurrence)
    # The Unit-2 occurrence itself is genuine, valid and within its own bound.
    assert context.issuer.describe(token).occurrence == occurrence
    before = context.runtime.registry_status
    assert_abort(FailureCode.CAPACITY_ABORT, lambda: context.runtime.admit(token))
    assert context.runtime.registry_status == before
    assert_abort(FailureCode.CAPACITY_ABORT, lambda: context.runtime.admit(token))


def test_reservation_prospectively_rejects_unrepresentable_complete_charge(context):
    occurrence = d("large-occurrence", next(names), *((None,) * 1600))
    token = context.issuer.authorize_given(claim(), scope(), occurrence)
    authority = context.runtime.admit(token)
    ledger = context.runtime.ledger(authority)
    before = ledger.summary(authority)
    assert_abort(
        FailureCode.CAPACITY_ABORT, lambda: ledger.reserve(authority, 0, 1, d("work"))
    )
    assert ledger.summary(authority) == before
    finish(context, authority, ledger)
    assert ledger.summary(authority).retired == 8


def test_zero_initial_budget_is_exact_and_cannot_authorize_charged_work():
    ctx = make_context(budget=0, capacity=1)
    try:
        token, authority, ledger = ctx.fresh()
        summary = ledger.summary(authority)
        assert (
            summary.initial,
            summary.available,
            summary.reserved,
            summary.consumed,
            summary.retired,
        ) == (0, 0, 0, 0, 0)
        assert_abort(
            FailureCode.BUDGET_ABORT, lambda: ledger.reserve(authority, 0, 1, d("work"))
        )
        assert_abort(
            FailureCode.INVALID_INPUT,
            lambda: ledger.reserve(authority, 0, 0, d("work")),
        )
        assert ctx.runtime.admit(token) is authority
        assert ledger.summary(authority) == summary
        ctx.runtime.begin_close(authority, 0)
        assert ctx.runtime.finalize_close(authority, 1)
        assert ledger.summary(authority) == summary
    finally:
        ctx.issuer.close()
