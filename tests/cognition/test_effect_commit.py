from __future__ import annotations

import copy
import gc
import hashlib
import os
import pickle
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, fields, replace
from functools import wraps
from itertools import count
from pathlib import Path
from threading import Barrier, Event
from uuid import UUID

import pytest

from dgca_lite import CoreConfig, CoreEngine, SurfaceEvent
from dgca_lite.cognition import effect as effect_module
from dgca_lite.cognition import effects as effects_module
from dgca_lite.cognition.authority import IngressAbort
from dgca_lite.cognition.budget import BudgetReservation
from dgca_lite.cognition.cie import create_cie_runtime
from dgca_lite.cognition.effect import (
    CanonicalEffectDescriptor,
    EffectCommitID,
    EffectCommitView,
    EffectPolicy,
    PreparedEffect,
)
from dgca_lite.cognition.effect_types import _MechanicalEffectOperation
from dgca_lite.cognition.effects import (
    EffectRuntime,
    _create_mechanical_effect_harness,
    create_effect_runtime,
)
from dgca_lite.cognition.identity import (
    CanonicalDescriptor,
    ClaimContentID,
    ScopeIdentity,
)
from dgca_lite.cognition.ingress import create_trusted_ingress_boundary
from dgca_lite.cognition.invocation import (
    InvocationLimits,
    _pinned_cie_parent,
    create_invocation_runtime,
)
from dgca_lite.cognition.locks import RankedBarrier
from dgca_lite.cognition.operation import OperationType
from dgca_lite.cognition.serialization import canonical_identity_bytes
from dgca_lite.cognition.types import FailureCode, InvocationState
from dgca_lite.cognition.work import WorkExecutionPermit, create_work_runtime
from dgca_lite.memory.integration import TrustedCoreAdapter
from dgca_lite.memory.session import retrieve_internal
from dgca_lite.persistence import engine_state


def d(kind, *values):
    return CanonicalDescriptor(kind, values)


names = count()


def isolated_test(function):
    @wraps(function)
    def independent_process():
        env = dict(
            os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src")
        )
        script = f"import runpy; ns=runpy.run_path({str(Path(__file__).resolve())!r}); ns[{function.__name__!r}].__wrapped__()"
        subprocess.run(
            [sys.executable, "-B", "-c", script],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )

    return independent_process


@dataclass
class Context:
    core: object
    issuer: object
    parent: object
    cie: object
    work: object
    effects: object

    def fresh(self):
        cap = self.issuer.authorize_given(
            ClaimContentID(d("GroundAtom", "P")),
            ScopeIdentity("FORMAL", d("source"), d("scope")),
            d("occurrence", next(names)),
        )
        auth = self.parent.admit(cap)
        return auth, self.parent.ledger(auth), self.cie.open(auth, 0)


def make_context(*, production=False, policy=None):
    core = CoreEngine(CoreConfig(receptor_fanout=1))
    issuer = create_trusted_ingress_boundary(
        core, d("unit6", next(names)), d("source"), capacity=2048
    )
    parent = create_invocation_runtime(
        issuer.invocation_causes, InvocationLimits(8, 1024)
    )
    cie = create_cie_runtime(parent)
    work = create_work_runtime(parent, cie)
    factory = create_effect_runtime if production else _create_mechanical_effect_harness
    effects = factory(parent, cie, policy=policy)
    return Context(core, issuer, parent, cie, work, effects)


@pytest.fixture(scope="module")
def context():
    # One shared domain: preserve the existing 64 lifetime-runtime bound when
    # running ALL prior unit tests in the same process. Other roots are isolated.
    return make_context()


@pytest.fixture
def opened(context):
    auth, ledger, cie = context.fresh()
    yield context, auth, ledger, cie
    if context.parent.describe(auth).revision == 0:
        context.parent.begin_close(auth, 0)
    if context.parent.describe(auth).revision == 1:
        ledger.retire_unused(auth, 1)
        assert context.parent.finalize_close(auth, 1)


def plan(opened, payload=None, *, target=0, scope="test", bound=False):
    ctx, auth, ledger, cie = opened
    operation = (
        _MechanicalEffectOperation.CIE_AUDIT_ONLY
        if bound
        else _MechanicalEffectOperation.AUDIT_ONLY
    )
    effect = ctx.effects.prepare_effect(
        auth,
        0,
        d("MechanicalTarget", target),
        d("payload", 1) if payload is None else payload,
        d("MechanicalScope", scope),
        operation=operation,
    )
    snapshot = ctx.cie.snapshot(cie).binding if bound else None
    reservation, prepared = ctx.effects.reserve(
        auth, 0, ledger, effect, cie=cie if bound else None, snapshot=snapshot
    )
    return effect, reservation, prepared


def commit(opened, reservation, prepared, *, revision=0):
    ctx, auth, ledger, cie = opened
    return ctx.effects.authorize_charge_and_commit(
        auth,
        revision,
        ledger,
        reservation,
        prepared,
        cie=cie if prepared.snapshot_binding is not None else None,
    )


def abort(call, code=None):
    with pytest.raises(IngressAbort) as error:
        call()
    if code is not None:
        assert error.value.code is code
    return error.value


def state(opened):
    ctx, auth, ledger, cie = opened
    with _pinned_cie_parent(ctx.parent, auth) as (_, item, _):
        owner = item.effect_owner
        index = None if owner is None else tuple(owner.index)
    return (
        ledger.summary(auth),
        ctx.effects.registry_status(auth),
        index,
        ctx.cie.snapshot(cie).canonical_bytes,
    )


def test_exact_seven_effect_fields_and_complete_identity(opened):
    effect, reservation, prepared = plan(opened)
    assert tuple(f.name for f in fields(CanonicalEffectDescriptor)) == (
        "effect_type",
        "target_identity",
        "canonical_payload",
        "scope_binding",
        "environment_revision",
        "owner_binding",
        "execution_contract",
    )
    view = commit(opened, reservation, prepared)
    assert type(view) is EffectCommitView and type(view.commit_id) is EffectCommitID
    assert view.commit_id.effect.canonical_descriptor() == effect.canonical_descriptor()
    assert view.commit_id.authority_context.values == (
        effect.owner_binding,
        effect.environment_revision,
        None,
    )
    assert view.status == "COMMITTED"


def test_logical_commit_has_no_core_l2_arena_or_child_effect(opened):
    ctx, auth, ledger, cie = opened
    core = engine_state(ctx.core)
    l2 = retrieve_internal(ctx.core, {})
    snapshot = ctx.cie.snapshot(cie).canonical_bytes
    with _pinned_cie_parent(ctx.parent, auth) as (_, item, _):
        children = item.nondelegated_children
    _, reservation, prepared = plan(opened)
    view = commit(opened, reservation, prepared)
    assert ledger.summary(auth).consumed == 1
    assert ctx.effects.registry_status(auth)[0] == 1
    assert engine_state(ctx.core) == core and retrieve_internal(ctx.core, {}) == l2
    assert ctx.cie.snapshot(cie).canonical_bytes == snapshot
    with _pinned_cie_parent(ctx.parent, auth) as (_, item, _):
        assert item.nondelegated_children == children
    canonical_identity_bytes(view.canonical_descriptor())


@isolated_test
def test_production_catalogue_is_empty_and_no_placeholder_promoted():
    ctx = make_context(production=True)
    auth, ledger, cie = ctx.fresh()
    before = ledger.summary(auth)
    for operation in (
        None,
        _MechanicalEffectOperation.AUDIT_ONLY,
        OperationType.EFFECT_CLASSIFICATION_ONLY,
        "sealForecast",
    ):
        abort(
            lambda operation=operation: ctx.effects.prepare_effect(
                auth,
                0,
                d("MechanicalTarget", 0),
                (),
                d("MechanicalScope", "test"),
                operation=operation,
            ),
            FailureCode.UNKNOWN_OPERATION_TYPE,
        )
    assert ledger.summary(auth) == before and ctx.effects.registry_status(auth)[0] == 0
    assert (
        ctx.cie.snapshot(cie).binding.cie.environment.l3_policy.kind
        == "L3Unit6PolicyBinding"
    )


@pytest.mark.parametrize(
    "action", [copy.copy, copy.deepcopy, pickle.dumps, canonical_identity_bytes]
)
def test_effect_runtime_cannot_copy_or_serialize(opened, action):
    with pytest.raises((TypeError, ValueError)):
        action(opened[0].effects)


def test_forged_runtime_authority_reservation_and_incomplete_descriptor(opened):
    ctx, auth, ledger, _ = opened
    _, reservation, prepared = plan(opened)
    with pytest.raises(TypeError):
        EffectRuntime()
    abort(
        lambda: EffectRuntime.authorize_charge_and_commit(
            object.__new__(EffectRuntime), auth, 0, ledger, reservation, prepared
        )
    )
    abort(
        lambda: ctx.effects.authorize_charge_and_commit(
            prepared.effect.owner_binding, 0, ledger, reservation, prepared
        )
    )
    abort(lambda: commit(opened, object.__new__(BudgetReservation), prepared))
    abort(
        lambda: ctx.effects.authorize_charge_and_commit(
            auth, 0, ledger, reservation, object.__new__(PreparedEffect)
        )
    )
    forged = replace(prepared, effect=prepared.effect)
    object.__setattr__(forged, "effect", object.__new__(CanonicalEffectDescriptor))
    abort(lambda: commit(opened, reservation, forged))
    assert ledger.summary(auth).consumed == 0


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {1},
        ([],),
        lambda: None,
        object(),
        float("inf"),
        float("nan"),
        UUID(int=1),
    ],
)
def test_unknown_mutable_callback_nonfinite_and_runtime_metadata_fail_closed(
    opened, payload
):
    ctx, auth, ledger, _ = opened
    before = ledger.summary(auth)
    abort(
        lambda: ctx.effects.prepare_effect(
            auth, 0, d("MechanicalTarget", 0), payload, d("MechanicalScope", "test")
        )
    )
    assert ledger.summary(auth) == before and ctx.effects.registry_status(auth)[0] == 0


@pytest.mark.parametrize(
    "target",
    [
        d("Placeholder"),
        d("MechanicalTarget"),
        d("MechanicalTarget", None),
        d("MechanicalTarget", True),
        d("MechanicalTarget", -1),
        d("MechanicalTarget", "late"),
    ],
)
def test_placeholder_late_or_nontyped_target_never_authorized(opened, target):
    ctx, auth, ledger, _ = opened
    before = ledger.summary(auth)
    abort(
        lambda: ctx.effects.prepare_effect(
            auth, 0, target, (), d("MechanicalScope", "test")
        )
    )
    assert ledger.summary(auth) == before


def test_nested_alias_capture_and_post_commit_payload_target_mutation(opened):
    ctx, auth, _, _ = opened
    payload = d("payload", d("nested", 1))
    effect, reservation, prepared = plan(opened, payload)
    object.__setattr__(payload.values[0], "values", (999,))
    assert effect.canonical_payload.values[0].values == (1,)
    view = commit(opened, reservation, prepared)
    original = canonical_identity_bytes(view.canonical_descriptor())
    object.__setattr__(view.effect, "canonical_payload", d("mutated", 888))
    object.__setattr__(view.effect.target_identity, "values", (99,))
    object.__setattr__(effect, "canonical_payload", d("caller", 777))
    replay = commit(opened, reservation, prepared)
    assert canonical_identity_bytes(replay.canonical_descriptor()) == original
    assert ctx.effects.registry_status(auth)[0] == 1


@pytest.mark.parametrize(
    "field",
    [
        "target_identity",
        "canonical_payload",
        "scope_binding",
        "environment_revision",
        "owner_binding",
        "execution_contract",
        "effect_type",
    ],
)
def test_altered_retry_requires_new_lawful_commit_and_charge(opened, field):
    ctx, auth, ledger, _ = opened
    effect, reservation, prepared = plan(opened)
    committed = commit(opened, reservation, prepared)
    values = {
        "target_identity": d("MechanicalTarget", 1),
        "canonical_payload": d("payload", 2),
        "scope_binding": d("MechanicalScope", "other"),
        "environment_revision": replace(
            effect.environment_revision,
            core_state=replace(
                effect.environment_revision.core_state,
                tick=effect.environment_revision.core_state.tick + 1,
            ),
        ),
        "owner_binding": d("EffectOwnerBinding", d("wrong-owner"), 0),
        "execution_contract": d("forged-contract"),
        "effect_type": d("EffectType", "UNKNOWN"),
    }
    altered = replace(prepared, effect=replace(effect, **{field: values[field]}))
    before = ledger.summary(auth)
    abort(lambda: commit(opened, reservation, altered))
    assert ledger.summary(auth) == before
    assert (
        commit(opened, reservation, prepared).commit_id.canonical_bytes
        == committed.commit_id.canonical_bytes
    )
    assert ctx.effects.registry_status(auth)[0] == 1


def test_different_effect_fresh_charge_and_same_effect_new_reservation_retry(opened):
    ctx, auth, ledger, _ = opened
    _, first, p0 = plan(opened)
    v0 = commit(opened, first, p0)
    _, second, p1 = plan(opened)
    same = commit(opened, second, p1)
    assert same.commit_id.canonical_bytes == v0.commit_id.canonical_bytes
    assert same.charge == v0.charge
    assert ledger.summary(auth).consumed == 1 and ledger.summary(auth).reserved == 1
    _, third, p2 = plan(opened, target=1)
    other = commit(opened, third, p2)
    assert other.commit_id.canonical_bytes != v0.commit_id.canonical_bytes
    assert (
        ledger.summary(auth).consumed == 2 and ctx.effects.registry_status(auth)[0] == 2
    )


def test_exact_retry_after_closed_and_changed_environment_is_history_only(opened):
    ctx, auth, ledger, cie = opened
    _, reservation, prepared = plan(opened, bound=True)
    original = commit(opened, reservation, prepared)
    ctx.parent.begin_close(auth, 0)
    ledger.retire_unused(auth, 1)
    assert ctx.parent.finalize_close(auth, 1)
    before = ledger.summary(auth)
    TrustedCoreAdapter.process_event(ctx.core, SurfaceEvent(b"environment change"))
    # Old descriptor/snapshot and old revision are genuine historical context,
    # not current publication authority. No live CIE is required for retry.
    replay = ctx.effects.authorize_charge_and_commit(
        auth, 0, ledger, reservation, prepared
    )
    assert canonical_identity_bytes(
        replay.canonical_descriptor()
    ) == canonical_identity_bytes(original.canonical_descriptor())
    assert ledger.summary(auth) == before
    assert ctx.cie.status(cie) == FailureCode.PARENT_AUTHORITY_STALE.value
    altered = replace(
        prepared,
        effect=replace(prepared.effect, target_identity=d("MechanicalTarget", 2)),
    )
    abort(
        lambda: ctx.effects.authorize_charge_and_commit(
            auth, 0, ledger, reservation, altered
        ),
        FailureCode.OPERATIONAL_EFFECT_AUTHORITY_STALE,
    )


def test_close_first_consumes_nothing_and_publishes_nothing(opened):
    ctx, auth, ledger, _ = opened
    _, reservation, prepared = plan(opened)
    ctx.parent.begin_close(auth, 0)
    before = ledger.summary(auth)
    abort(
        lambda: commit(opened, reservation, prepared),
        FailureCode.OPERATIONAL_EFFECT_AUTHORITY_STALE,
    )
    assert ledger.summary(auth) == before and ctx.effects.registry_status(auth)[0] == 0


def test_commit_wins_close_race_and_history_survives(opened, monkeypatch):
    ctx, auth, ledger, _ = opened
    _, reservation, prepared = plan(opened)
    inside, release, closing_started = Event(), Event(), Event()

    def pause():
        inside.set()
        assert release.wait(5)

    monkeypatch.setattr(effects_module, "_before_effect_publish", pause)

    def close():
        closing_started.set()
        return ctx.parent.begin_close(auth, 0)

    with ThreadPoolExecutor(max_workers=2) as pool:
        committing = pool.submit(commit, opened, reservation, prepared)
        assert inside.wait(5)
        closing = pool.submit(close)
        assert closing_started.wait(5) and not closing.done()
        release.set()
        result = committing.result(5)
        assert closing.result(5).state is InvocationState.CLOSING
    assert ledger.summary(auth).consumed == 1
    assert (
        commit(opened, reservation, prepared).commit_id.canonical_bytes
        == result.commit_id.canonical_bytes
    )


@pytest.mark.parametrize("same_reservation", [True, False])
def test_concurrent_duplicate_commits_converge_and_consume_once(
    opened, same_reservation
):
    ctx, auth, ledger, _ = opened
    _, first, p0 = plan(opened)
    _, second, p1 = plan(opened)
    start = Barrier(2)

    def dispatch(pair):
        start.wait(5)
        return commit(opened, *pair)

    requests = ((first, p0), (first, p0) if same_reservation else (second, p1))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(dispatch, requests))
    assert canonical_identity_bytes(
        results[0].canonical_descriptor()
    ) == canonical_identity_bytes(results[1].canonical_descriptor())
    assert (
        ledger.summary(auth).consumed == 1 and ctx.effects.registry_status(auth)[0] == 1
    )


@pytest.mark.parametrize(
    "charge_field",
    ["owner_identity", "reservation_identity", "unit_identity", "work_class"],
)
def test_forged_charge_fields_never_commit(opened, charge_field):
    _, reservation, prepared = plan(opened)
    forged = replace(
        prepared, charge=replace(prepared.charge, **{charge_field: d("forged")})
    )
    before = state(opened)
    abort(lambda: commit(opened, reservation, forged))
    assert state(opened) == before


@pytest.mark.parametrize("ordinal", [1, True, -1, 256])
def test_wrong_unit_or_bool_alias_never_commits(opened, ordinal):
    _, reservation, prepared = plan(opened)
    before = state(opened)
    if type(ordinal) is not int or not 0 <= ordinal < 256:
        with pytest.raises(TypeError):
            replace(prepared, unit_ordinal=ordinal)
    else:
        abort(
            lambda: commit(opened, reservation, replace(prepared, unit_ordinal=ordinal))
        )
    assert state(opened) == before


def test_wrong_reservation_ledger_owner_and_wep_fail_closed(opened):
    ctx, auth, ledger, _ = opened
    _, reservation, prepared = plan(opened)
    _, second, _ = plan(opened)
    before = state(opened)
    abort(lambda: commit(opened, second, prepared))
    abort(
        lambda: ctx.effects.authorize_charge_and_commit(
            object.__new__(WorkExecutionPermit), 0, ledger, reservation, prepared
        )
    )
    abort(lambda: commit(opened, object.__new__(WorkExecutionPermit), prepared))
    other_auth, other_ledger, other_cie = ctx.fresh()
    abort(
        lambda: ctx.effects.authorize_charge_and_commit(
            auth, 0, other_ledger, reservation, prepared
        )
    )
    abort(
        lambda: ctx.effects.authorize_charge_and_commit(
            other_auth, 0, ledger, reservation, prepared
        )
    )
    assert state(opened) == before
    ctx.parent.begin_close(other_auth, 0)
    other_ledger.retire_unused(other_auth, 1)
    assert ctx.parent.finalize_close(other_auth, 1)
    assert ctx.cie.status(other_cie) == FailureCode.PARENT_AUTHORITY_STALE.value


def test_pure_charge_wep_and_worker_output_cannot_authorize_effect(opened):
    ctx, auth, ledger, cie = opened
    pure = ctx.work.prepare_work(auth, 0, ctx.cie.snapshot(cie).binding, d("pure"))
    token, pp = ctx.work.reserve(auth, 0, cie, ledger, pure)
    wep = ctx.work.authorize_and_charge(auth, 0, cie, ledger, token, pp)
    result = ctx.work.execute(wep, pure)
    effect, _, _ = plan(opened)
    forged = PreparedEffect(effect, None, pp.charge, pp.unit_ordinal)
    abort(lambda: commit(opened, token, forged), FailureCode.BUDGET_WORKCLASS_MISMATCH)
    for fake in (wep, result, result.canonical_descriptor(), pp, pp.charge):
        abort(
            lambda fake=fake: ctx.effects.authorize_charge_and_commit(
                auth, 0, ledger, token, fake
            )
        )
    assert (
        ledger.summary(auth).consumed == 1 and ctx.effects.registry_status(auth)[0] == 0
    )


@pytest.mark.parametrize(
    "failure",
    [
        "serialization",
        "charge",
        "commit_id",
        "view",
        "registry_stage",
        "prepublication",
    ],
)
def test_precommit_injected_failures_are_atomic(opened, monkeypatch, failure):
    _, reservation, prepared = plan(opened)
    before = state(opened)

    def failing(*args, **kwargs):
        raise MemoryError(f"injected {failure}")

    with monkeypatch.context() as patch:
        if failure == "serialization":
            patch.setattr(effects_module, "canonical_identity_bytes", failing)
        elif failure == "charge":
            patch.setattr(effects_module, "_prepare_consumption", failing)
        elif failure == "commit_id":
            patch.setattr(effects_module, "EffectCommitID", failing)
        elif failure == "view":
            patch.setattr(effects_module, "EffectCommitView", failing)
        elif failure == "registry_stage":
            patch.setattr(effects_module, "dict", failing, raising=False)
        else:
            patch.setattr(effects_module, "_before_effect_publish", failing)
        with pytest.raises(MemoryError):
            commit(opened, reservation, prepared)
    assert state(opened) == before
    assert commit(opened, reservation, prepared).status == "COMMITTED"


def test_interruption_after_budget_swap_rolls_back_before_logical_commit(
    opened, monkeypatch
):
    ctx, auth, _, _ = opened
    # First commit gives an actual protected owner class for targeted injection.
    _, reservation, prepared = plan(opened)
    commit(opened, reservation, prepared)
    _, reservation, prepared = plan(opened, target=1)
    before = state(opened)
    with _pinned_cie_parent(ctx.parent, auth) as (_, item, _):
        owner = item.effect_owner
    original = type(owner).__setattr__
    fired = []

    def fail_once(self, name, value):
        if self is owner and name == "index" and not fired:
            fired.append(True)
            raise MemoryError("interruption at final logical pointer")
        return original(self, name, value)

    with monkeypatch.context() as patch:
        patch.setattr(type(owner), "__setattr__", fail_once)
        with pytest.raises(MemoryError):
            commit(opened, reservation, prepared)
    assert fired == [True] and state(opened) == before
    assert commit(opened, reservation, prepared).status == "COMMITTED"


def test_failure_immediately_before_budget_publication_is_atomic(opened, monkeypatch):
    ctx, auth, ledger, _ = opened
    _, reservation, prepared = plan(opened)
    before = state(opened), engine_state(ctx.core)
    with _pinned_cie_parent(ctx.parent, auth) as (_, item, _):
        budget = item.budget
    original = type(budget).__setattr__
    fired = []

    def fail_once(self, name, value):
        if self is budget and name == "index" and not fired:
            fired.append(True)
            raise MemoryError("before budget pointer publication")
        return original(self, name, value)

    with monkeypatch.context() as patch:
        patch.setattr(type(budget), "__setattr__", fail_once)
        with pytest.raises(MemoryError):
            commit(opened, reservation, prepared)
    assert fired == [True]
    assert (state(opened), engine_state(ctx.core)) == before
    assert ledger.summary(auth).consumed == 0
    commit(opened, reservation, prepared)


def test_mutation_at_commit_boundary_cannot_retarget_frozen_effect(opened, monkeypatch):
    ctx, _, _, _ = opened
    effect, reservation, prepared = plan(opened)
    original_bytes = canonical_identity_bytes(prepared.effect.canonical_descriptor())

    def mutate_caller_data():
        object.__setattr__(prepared.effect, "canonical_payload", d("late", 999))
        object.__setattr__(prepared.effect.target_identity, "values", (99,))
        object.__setattr__(effect, "target_identity", d("MechanicalTarget", 88))

    monkeypatch.setattr(effects_module, "_before_effect_publish", mutate_caller_data)
    view = commit(opened, reservation, prepared)
    assert (
        canonical_identity_bytes(view.effect.canonical_descriptor()) == original_bytes
    )
    assert view.effect.target_identity.values == (0,)
    assert ctx.effects.registry_status(opened[1])[0] == 1


@pytest.mark.parametrize("revision", [True, False, 1, -1])
def test_owner_revision_is_current_and_boolean_distinct(opened, revision):
    _, reservation, prepared = plan(opened)
    before = state(opened)
    abort(lambda: commit(opened, reservation, prepared, revision=revision))
    assert state(opened) == before


def test_no_internal_reingress_or_deferred_children_after_close(opened):
    ctx, auth, ledger, _ = opened
    _, reservation, prepared = plan(opened)
    view = commit(opened, reservation, prepared)
    for data in (
        view,
        view.commit_id,
        view.canonical_descriptor(),
        view.effect.canonical_payload,
    ):
        abort(lambda data=data: ctx.issuer.formal_reasoning.accept(data))
        abort(lambda data=data: ctx.issuer.observations.accept(data))
        abort(lambda data=data: ctx.issuer.formal_constraints.accept(data))
    ctx.parent.begin_close(auth, 0)
    ledger.retire_unused(auth, 1)
    assert ctx.parent.finalize_close(auth, 1)
    for data in (view, view.commit_id, view.canonical_descriptor()):
        abort(lambda data=data: ctx.cie.open(data, 0))
    abort(lambda: ctx.cie.open(auth, 2), FailureCode.INVOCATION_NOT_ACTIVE)
    assert (
        commit(opened, reservation, prepared).commit_id.canonical_bytes
        == view.commit_id.canonical_bytes
    )


@isolated_test
def test_descriptor_capacity_rejects_reservation_without_partial_accounting():
    ctx = make_context(policy=EffectPolicy(max_descriptor_bytes=1))
    auth, ledger, _ = ctx.fresh()
    before = ledger.summary(auth)
    abort(
        lambda: ctx.effects.prepare_effect(
            auth, 0, d("MechanicalTarget", 0), (), d("MechanicalScope", "test")
        ),
        FailureCode.INVALID_INPUT,
    )
    assert ledger.summary(auth) == before
    assert ctx.effects.registry_status(auth)[0] == 0


@isolated_test
def test_registry_capacity_before_publication_and_retry_at_capacity():
    ctx = make_context(policy=EffectPolicy(max_commits_per_owner=1))
    opened = (ctx, *ctx.fresh())
    _, reservation, prepared = plan(opened)
    original = commit(opened, reservation, prepared)
    _, second, p2 = plan(opened, target=1)
    before = state(opened)
    abort(lambda: commit(opened, second, p2), FailureCode.CAPACITY_ABORT)
    assert state(opened) == before
    assert (
        commit(opened, reservation, prepared).commit_id.canonical_bytes
        == original.commit_id.canonical_bytes
    )


def test_view_id_and_serialized_data_do_not_create_authority(opened):
    ctx, auth, ledger, _ = opened
    _, reservation, prepared = plan(opened)
    view = commit(opened, reservation, prepared)
    forms = (
        view,
        view.commit_id,
        copy.deepcopy(view),
        pickle.loads(pickle.dumps(view)),
        view.canonical_descriptor(),
        canonical_identity_bytes(view.canonical_descriptor()),
    )
    for form in forms:
        abort(
            lambda form=form: ctx.effects.authorize_charge_and_commit(
                form, 0, ledger, reservation, prepared
            )
        )
        abort(
            lambda form=form: ctx.effects.authorize_charge_and_commit(
                auth, 0, ledger, reservation, form
            )
        )
        abort(lambda form=form: ctx.cie.open(form, 0))
    assert ledger.summary(auth).consumed == 1


@pytest.mark.parametrize(
    "extra",
    [
        "executor",
        "transport",
        "callback",
        "child_factory",
        "core_mutator",
        "target_selector",
    ],
)
def test_no_callback_transport_or_deferred_child_interface(opened, extra):
    ctx, auth, ledger, _ = opened
    _, reservation, prepared = plan(opened)
    called = []

    def executor():
        called.append(True)

    with pytest.raises(TypeError):
        ctx.effects.authorize_charge_and_commit(
            auth, 0, ledger, reservation, prepared, **{extra: executor}
        )
    assert not called and ledger.summary(auth).consumed == 0
    assert not any(
        hasattr(ctx.effects, name)
        for name in ("execute", "transport", "create_child", "delegate", "mint_fda")
    )


def test_cie_requirements_and_no_unnecessary_arena_lock(opened, monkeypatch):
    _, r0, p0 = plan(opened)
    _, r1, p1 = plan(opened, target=1, bound=True)
    trace = []
    original = RankedBarrier.acquire

    def acquire(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        if result:
            trace.append(self.rank)
        return result

    monkeypatch.setattr(RankedBarrier, "acquire", acquire)
    commit(opened, r0, p0)
    assert {0, 1, 2, 4, 5}.issubset(trace) and 3 not in trace
    trace.clear()
    commit(opened, r1, p1)
    assert {0, 1, 2, 3, 4, 5}.issubset(trace)
    assert (
        trace.index(0)
        < trace.index(1, trace.index(0))
        < trace.index(2, trace.index(0))
        < trace.index(3)
        < trace.index(4, trace.index(3))
    )


def test_stale_cie_snapshot_and_environment_fail_without_charge(opened):
    ctx, auth, ledger, cie = opened
    _, reservation, prepared = plan(opened, bound=True)
    old = ctx.cie.snapshot(cie)
    staging = ctx.cie.stage(cie, old, ())
    ctx.cie.publish(cie, staging)
    before = ledger.summary(auth)
    abort(lambda: commit(opened, reservation, prepared), FailureCode.CIE_STALE)
    assert ledger.summary(auth) == before
    _, reservation, prepared = plan(opened)
    TrustedCoreAdapter.process_event(ctx.core, SurfaceEvent(b"change"))
    abort(lambda: commit(opened, reservation, prepared), FailureCode.ENVIRONMENT_STALE)
    assert (
        ledger.summary(auth).consumed == 0 and ctx.effects.registry_status(auth)[0] == 0
    )


@pytest.mark.parametrize("pair", [(1, 0), (2, 1), (3, 2), (4, 3), (5, 4)])
def test_every_adjacent_lock_inversion_is_rejected(pair):
    outer, inner = map(RankedBarrier, pair)
    with outer:
        abort(lambda: inner.acquire(), FailureCode.INTERNAL_CONTRACT_VIOLATION)
    with inner:
        pass


def test_actual_effect_gate_cannot_enter_beneath_later_locks(opened):
    ctx, auth, ledger, _ = opened
    _, reservation, prepared = plan(opened)
    before = state(opened)
    for rank in (2, 3, 4, 5):
        with RankedBarrier(rank):
            abort(
                lambda: ctx.effects.authorize_charge_and_commit(
                    auth, 0, ledger, reservation, prepared
                )
            )
    assert state(opened) == before


def test_digest_and_scalar_hash_collisions_do_not_merge_effects(opened, monkeypatch):
    ctx, auth, ledger, _ = opened

    class ConstantDigest:
        def hexdigest(self):
            return "0" * 64

    monkeypatch.setattr(effect_module.hashlib, "sha256", lambda value: ConstantDigest())
    assert hash(-1) == hash(-2)
    _, r0, p0 = plan(opened, payload=-1)
    _, r1, p1 = plan(opened, payload=-2)
    a, b = commit(opened, r0, p0), commit(opened, r1, p1)
    assert a.commit_id.index_digest == b.commit_id.index_digest
    assert a.commit_id.canonical_bytes != b.commit_id.canonical_bytes
    assert ctx.effects.registry_status(auth)[0] == ledger.summary(auth).consumed == 2


def test_policy_container_bounds_and_nested_live_capability_rejection(opened):
    ctx, auth, ledger, cie = opened

    class Poison:
        def __getattribute__(self, name):
            raise AssertionError("oversized member traversed")

    abort(
        lambda: ctx.effects.prepare_effect(
            auth,
            0,
            d("MechanicalTarget", 0),
            (Poison(),) * 65,
            d("MechanicalScope", "test"),
        ),
        FailureCode.INVALID_INPUT,
    )
    for handle in (auth, ledger, cie, ctx.core, ctx.effects, ctx.work, ctx.issuer):
        abort(
            lambda handle=handle: ctx.effects.prepare_effect(
                auth,
                0,
                d("MechanicalTarget", 0),
                (handle,),
                d("MechanicalScope", "test"),
            )
        )
    assert ledger.summary(auth).consumed == 0


@pytest.mark.parametrize(
    "field,kind,count",
    [
        ("effect_type", "EffectType", 1),
        ("target_identity", "MechanicalTarget", 1),
        ("scope_binding", "MechanicalScope", 1),
        ("owner_binding", "EffectOwnerBinding", 2),
        ("execution_contract", "OperationContract", 7),
    ],
)
def test_metadata_outer_envelopes_reject_before_member_inspection(
    opened, field, kind, count
):
    _, reservation, prepared = plan(opened)

    class Poison:
        def __getattribute__(self, name):
            raise AssertionError("oversized metadata member inspected")

    malformed = object.__new__(CanonicalDescriptor)
    object.__setattr__(malformed, "kind", kind)
    object.__setattr__(malformed, "values", (Poison(),) * (count + 1))
    object.__setattr__(prepared.effect, field, malformed)
    before = state(opened)
    abort(lambda: commit(opened, reservation, prepared), FailureCode.INVALID_INPUT)
    assert state(opened) == before


def test_mutated_metadata_kind_cannot_execute_comparison_hook(opened):
    _, reservation, prepared = plan(opened)

    class PoisonKind:
        def __eq__(self, other):
            raise AssertionError("untrusted metadata comparison executed")

        def __ne__(self, other):
            raise AssertionError("untrusted metadata comparison executed")

    object.__setattr__(prepared.effect.effect_type, "kind", PoisonKind())
    before = state(opened)
    abort(lambda: commit(opened, reservation, prepared), FailureCode.INVALID_INPUT)
    assert state(opened) == before


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_commits_per_owner": True},
        {"max_commits_per_owner": 257},
        {"max_payload_nodes": 129},
        {"max_payload_depth": 0},
        {"max_scalar_bytes": 8193},
        {"max_descriptor_bytes": -1},
    ],
)
def test_policy_is_finite_exact_typed_and_nonrenewable(kwargs):
    with pytest.raises(ValueError):
        EffectPolicy(**kwargs)


@isolated_test
def test_policy_root_currentness_cross_runtime_and_gc():
    left, right = make_context(), make_context()
    opened = (left, *left.fresh())
    _, reservation, prepared = plan(opened)
    auth, ledger, _ = opened[1:]
    abort(
        lambda: right.effects.authorize_charge_and_commit(
            auth, 0, ledger, reservation, prepared
        )
    )
    abort(
        lambda: create_effect_runtime(left.parent, left.cie),
        FailureCode.INVALID_POLICY_BINDING,
    )
    view = commit(opened, reservation, prepared)
    with _pinned_cie_parent(left.parent, auth) as (_, item, _):
        owner = item.effect_owner
    left.effects = None
    gc.collect()
    assert owner.closed and owner.index == {}
    # Historical bytes remain data. Root retirement cannot refresh authority.
    canonical_identity_bytes(view.canonical_descriptor())
    abort(
        lambda: _create_mechanical_effect_harness(left.parent, left.cie),
        FailureCode.INVALID_POLICY_BINDING,
    )


UNIT6_DETERMINISTIC_SCRIPT = """
from dgca_lite import CoreEngine, CoreConfig
from dgca_lite.cognition.identity import CanonicalDescriptor, ClaimContentID, ScopeIdentity
from dgca_lite.cognition.ingress import create_trusted_ingress_boundary
from dgca_lite.cognition.invocation import create_invocation_runtime, InvocationLimits
from dgca_lite.cognition.cie import create_cie_runtime
from dgca_lite.cognition.work import create_work_runtime
from dgca_lite.cognition.effects import _create_mechanical_effect_harness
from dgca_lite.cognition.effect_types import _MechanicalEffectOperation
from dgca_lite.cognition.serialization import canonical_identity_bytes
def d(k,*v): return CanonicalDescriptor(k,v)
core=CoreEngine(CoreConfig(receptor_fanout=1))
issuer=create_trusted_ingress_boundary(core,d("unit6-deterministic"),d("source"))
parent=create_invocation_runtime(issuer.invocation_causes,InvocationLimits(8))
cie_runtime=create_cie_runtime(parent)
work_runtime=create_work_runtime(parent,cie_runtime)
effects=_create_mechanical_effect_harness(parent,cie_runtime)
source=issuer.authorize_given(ClaimContentID(d("GroundAtom","P")),ScopeIdentity("FORMAL",d("source"),d("scope")),d("occurrence",0))
auth=parent.admit(source); ledger=parent.ledger(auth); cie=cie_runtime.open(auth,0)
views=[]
for i in range(2):
    bound=i==1
    effect=effects.prepare_effect(auth,0,d("MechanicalTarget",i),d("payload",True,1,-0.0,(b"x","y")),d("MechanicalScope","test"),operation=_MechanicalEffectOperation.CIE_AUDIT_ONLY if bound else _MechanicalEffectOperation.AUDIT_ONLY)
    token,prepared=effects.reserve(auth,0,ledger,effect,cie=cie if bound else None,snapshot=cie_runtime.snapshot(cie).binding if bound else None)
    view=effects.authorize_charge_and_commit(auth,0,ledger,token,prepared,cie=cie if bound else None)
    replay=effects.authorize_charge_and_commit(auth,0,ledger,token,prepared)
    assert view.commit_id.canonical_bytes==replay.commit_id.canonical_bytes
    views.append(view.canonical_descriptor())
parent.begin_close(auth,0); ledger.retire_unused(auth,1); assert parent.finalize_close(auth,1)
assert ledger.summary(auth).consumed==2
print(canonical_identity_bytes(d("Unit6Audit",*views)).hex())
"""


@pytest.mark.parametrize("seed", ["0", "1", "27", "123", "random"])
def test_independent_process_commit_identity_and_retry_determinism(seed):
    env = dict(
        os.environ,
        PYTHONHASHSEED=seed,
        PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"),
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", UNIT6_DETERMINISTIC_SCRIPT],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stderr == ""
    data = bytes.fromhex(result.stdout.strip())
    assert hashlib.sha256(data).hexdigest() == UNIT6_SIGNATURE


UNIT6_SIGNATURE = "6623bcc294c7c3d6093f5ef69b079735a8b1861bebdd6adef8302bbb79ce9ccd"
