from __future__ import annotations

import copy
import gc
import hashlib
import inspect
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

import pytest

from dgca_lite import CoreConfig, CoreEngine, SurfaceEvent
from dgca_lite.cognition import ingress as ingress_module
from dgca_lite.cognition import operation as operation_module
from dgca_lite.cognition import work as work_module
from dgca_lite.cognition.authority import IngressAbort
from dgca_lite.cognition.budget import BudgetChargeView, BudgetReservation
from dgca_lite.cognition.cie import create_cie_runtime
from dgca_lite.cognition.contracts import ControlPlaneOperation
from dgca_lite.cognition.identity import (
    CanonicalDescriptor,
    ClaimContentID,
    ScopeIdentity,
)
from dgca_lite.cognition.ingress import (
    FormalReasoningIngress,
    TrustedObservationAdapter,
    create_trusted_ingress_boundary,
)
from dgca_lite.cognition.invocation import (
    InvocationLimits,
    _pinned_cie_parent,
    create_invocation_runtime,
)
from dgca_lite.cognition.locks import RankedBarrier
from dgca_lite.cognition.operation import (
    BudgetClass,
    FrozenWork,
    OperationContract,
    OperationType,
    PreparedDispatch,
    PublicationPolicy,
    PureWorkResultView,
    ResourceEnvelope,
    WorkPolicy,
)
from dgca_lite.cognition.serialization import canonical_identity_bytes
from dgca_lite.cognition.types import (
    BudgetSourceKind,
    FailureCode,
    InvocationState,
    WorkEffectClass,
)
from dgca_lite.cognition.work import (
    WorkExecutionPermit,
    WorkRuntime,
    create_work_runtime,
)
from dgca_lite.memory.integration import TrustedCoreAdapter
from dgca_lite.memory.session import retrieve_internal
from dgca_lite.persistence import engine_state


def d(kind, *values):
    return CanonicalDescriptor(kind, values)


names = count()


def isolated_runtime_test(function):
    """Do not weaken the 64 lifetime-runtime audit bound for test isolation."""

    @wraps(function)
    def independent_process():
        env = dict(os.environ)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
        script = f"import runpy; ns = runpy.run_path({str(Path(__file__).resolve())!r}); ns[{function.__name__!r}].__wrapped__()"
        subprocess.run(
            [sys.executable, "-B", "-c", script],
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    return independent_process


@dataclass
class Context:
    core: object
    issuer: object
    parent: object
    cie: object
    work: object

    def fresh(self):
        cap = self.issuer.authorize_given(
            ClaimContentID(d("GroundAtom", "P")),
            ScopeIdentity("FORMAL", d("source"), d("scope")),
            d("occurrence", next(names)),
        )
        auth = self.parent.admit(cap)
        ledger = self.parent.ledger(auth)
        cie = self.cie.open(auth, 0)
        return auth, ledger, cie


def make_context(*, work=True, budget=8, policy=None):
    core = CoreEngine(CoreConfig(receptor_fanout=1))
    issuer = create_trusted_ingress_boundary(
        core, d("unit5", next(names)), d("source"), capacity=2048
    )
    parent = create_invocation_runtime(
        issuer.invocation_causes, InvocationLimits(budget, 1024)
    )
    cie = create_cie_runtime(parent)
    return Context(
        core,
        issuer,
        parent,
        cie,
        create_work_runtime(parent, cie, policy=policy) if work else None,
    )


@pytest.fixture(scope="module")
def context():
    return make_context()


@pytest.fixture(scope="module")
def other():
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


def plan(opened, value=None):
    ctx, auth, ledger, cie = opened
    snapshot = ctx.cie.snapshot(cie).binding
    work = ctx.work.prepare_work(
        auth, 0, snapshot, d("input", 1) if value is None else value
    )
    reservation, prepared = ctx.work.reserve(auth, 0, cie, ledger, work)
    return work, reservation, prepared


def authorize(opened, reservation, prepared):
    ctx, auth, ledger, cie = opened
    return ctx.work.authorize_and_charge(auth, 0, cie, ledger, reservation, prepared)


def private_permit(permit):
    access = inspect.getclosurevars(WorkRuntime.execute).nonlocals["access"]
    with access(permit, "PERMIT") as (_, record):
        return record


def abort(call, code=None):
    with pytest.raises(IngressAbort) as caught:
        call()
    if code is not None:
        assert caught.value.code is code
    return caught.value


def test_contract_has_exact_seven_fields_and_closed_catalogue(opened):
    work, _, _ = plan(opened)
    assert tuple(f.name for f in fields(OperationContract)) == (
        "operation_type",
        "budget_class",
        "effect_class",
        "authority_requirements",
        "work_class",
        "resource_envelope",
        "publication_policy",
    )
    contract = work.contract
    assert contract.operation_type is OperationType.CLONE_CLOSED_VALUE
    assert contract.budget_class is BudgetClass.CHARGED_WORK
    assert contract.effect_class is WorkEffectClass.PURE_COMPUTE
    assert contract.resource_envelope.charge_units == 1
    assert contract.publication_policy is PublicationPolicy.STAGED_IMMUTABLE_ONLY
    assert len(contract.authority_requirements) == 4
    assert tuple(r.value for r in contract.authority_requirements) == tuple(
        sorted(r.value for r in contract.authority_requirements)
    )


def test_basic_gate_consumes_exactly_once_and_does_not_publish(opened):
    ctx, auth, ledger, cie = opened
    core = engine_state(ctx.core)
    l2_result = retrieve_internal(ctx.core, {})
    old = ctx.cie.snapshot(cie)
    work, reservation, prepared = plan(opened)
    permit = authorize(opened, reservation, prepared)
    assert ledger.summary(auth).consumed == 1
    assert ledger.summary(auth).reserved == 0
    result = ctx.work.execute(permit, work)
    assert type(result) is PureWorkResultView
    assert canonical_identity_bytes(result.output) == canonical_identity_bytes(
        work.frozen_input
    )
    assert ctx.cie.snapshot(cie).canonical_bytes == old.canonical_bytes
    assert engine_state(ctx.core) == core
    assert retrieve_internal(ctx.core, {}) == l2_result
    abort(lambda: ctx.work.execute(permit, work))
    abort(
        lambda: authorize(opened, reservation, prepared),
        FailureCode.MISSING_BUDGET_CHARGE,
    )
    assert ledger.summary(auth).consumed == 1


@pytest.mark.parametrize("handle", [WorkExecutionPermit, WorkRuntime])
def test_direct_constructor_is_not_authority(handle):
    with pytest.raises(TypeError):
        handle()


def test_object_new_forgery_and_wrong_self(opened):
    ctx, auth, ledger, cie = opened
    work, reservation, prepared = plan(opened)
    abort(lambda: ctx.work.execute(object.__new__(WorkExecutionPermit), work))
    abort(
        lambda: WorkRuntime.authorize_and_charge(
            object.__new__(WorkRuntime), auth, 0, cie, ledger, reservation, prepared
        )
    )
    abort(lambda: authorize(opened, object.__new__(BudgetReservation), prepared))
    assert ledger.summary(auth).consumed == 0


@pytest.mark.parametrize(
    "action", [copy.copy, copy.deepcopy, pickle.dumps, canonical_identity_bytes]
)
def test_wep_cannot_copy_or_serialize(opened, action):
    work, reservation, prepared = plan(opened)
    permit = authorize(opened, reservation, prepared)
    with pytest.raises((TypeError, ValueError)):
        action(permit)
    assert type(opened[0].work.execute(permit, work)) is PureWorkResultView


def test_class_recast_is_detected(opened):
    ctx, _, _, _ = opened
    work, reservation, prepared = plan(opened)
    permit = authorize(opened, reservation, prepared)
    object.__setattr__(permit, "__class__", BudgetReservation)
    try:
        abort(lambda: ctx.work.execute(permit, work))
    finally:
        object.__setattr__(permit, "__class__", WorkExecutionPermit)
    ctx.work.execute(permit, work)


@pytest.mark.parametrize(
    "bad",
    [
        "CLONE_CLOSED_VALUE",
        "seventh",
        None,
        True,
        1,
        lambda: None,
        object.__new__(OperationType),
    ],
    ids=["string", "unknown", "none", "bool", "int", "callback", "forged-enum"],
)
def test_unknown_operation_fails_closed(opened, bad):
    ctx, auth, ledger, cie = opened
    before = ledger.summary(auth)
    abort(
        lambda: ctx.work.prepare_work(
            auth, 0, ctx.cie.snapshot(cie).binding, (), operation=bad
        ),
        FailureCode.UNKNOWN_OPERATION_TYPE,
    )
    assert ledger.summary(auth) == before


def test_effect_contract_can_be_represented_but_not_run(opened):
    ctx, auth, ledger, cie = opened
    work = ctx.work.prepare_work(
        auth,
        0,
        ctx.cie.snapshot(cie).binding,
        (),
        operation=OperationType.EFFECT_CLASSIFICATION_ONLY,
    )
    assert work.contract.effect_class is WorkEffectClass.OPERATIONAL_EFFECT
    before = ledger.summary(auth)
    abort(
        lambda: ctx.work.reserve(auth, 0, cie, ledger, work),
        FailureCode.EXEMPTION_CONTRACT_VIOLATION,
    )
    assert ledger.summary(auth) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("effect_class", WorkEffectClass.OPERATIONAL_EFFECT),
        ("work_class", d("different-work")),
        ("resource_envelope", ResourceEnvelope(2, 128, 30)),
        ("authority_requirements", ()),
        ("publication_policy", PublicationPolicy.SEPARATE_EFFECT_GATE_REQUIRED),
    ],
)
def test_caller_contract_classification_cannot_override_policy(opened, field, value):
    ctx, auth, ledger, cie = opened
    work, _, _ = plan(opened)
    forged = replace(work, contract=replace(work.contract, **{field: value}))
    before = ledger.summary(auth)
    abort(lambda: ctx.work.reserve(auth, 0, cie, ledger, forged))
    assert ledger.summary(auth) == before


@pytest.mark.parametrize(
    "field", ["owner_identity", "reservation_identity", "unit_identity", "work_class"]
)
def test_exact_charge_fields_substitution_fails_atomic(opened, field):
    _, auth, ledger, _ = opened
    _, reservation, prepared = plan(opened)
    forged = replace(prepared, charge=replace(prepared.charge, **{field: d("forged")}))
    before = ledger.summary(auth)
    abort(lambda: authorize(opened, reservation, forged))
    assert ledger.summary(auth) == before


@pytest.mark.parametrize("ordinal", [1, True, -1, 256])
def test_wrong_unit_or_boolean_alias_cannot_charge(opened, ordinal):
    _, auth, ledger, _ = opened
    _, reservation, prepared = plan(opened)
    before = ledger.summary(auth)
    if type(ordinal) is not int or not 0 <= ordinal < 256:
        with pytest.raises(TypeError):
            replace(prepared, unit_ordinal=ordinal)
    else:
        abort(
            lambda: authorize(
                opened, reservation, replace(prepared, unit_ordinal=ordinal)
            )
        )
    assert ledger.summary(auth) == before


def test_wrong_reservation_cross_owner_and_cross_runtime(opened, other):
    ctx, auth, ledger, cie = opened
    _, first, prepared = plan(opened)
    _, second, _ = plan(opened)
    other_auth, other_ledger, other_cie = other.fresh()
    before = ledger.summary(auth)
    abort(
        lambda: authorize(opened, second, prepared), FailureCode.MISSING_BUDGET_CHARGE
    )
    abort(
        lambda: ctx.work.authorize_and_charge(
            other_auth, 0, cie, ledger, first, prepared
        )
    )
    abort(
        lambda: ctx.work.authorize_and_charge(
            auth, 0, cie, other_ledger, first, prepared
        )
    )
    abort(
        lambda: other.work.authorize_and_charge(
            auth, 0, other_cie, ledger, first, prepared
        )
    )
    permit = authorize(opened, first, prepared)
    abort(lambda: other.work.permit_binding(permit))
    assert ledger.summary(auth).consumed == before.consumed + 1
    other.parent.begin_close(other_auth, 0)
    other_ledger.retire_unused(other_auth, 1)
    assert other.parent.finalize_close(other_auth, 1)


def test_charge_descriptor_and_low_level_consumption_are_never_permission(opened):
    ctx, auth, ledger, _ = opened
    work, reservation, prepared = plan(opened)
    charge = ledger.consume(
        auth, 0, reservation, prepared.unit_ordinal, work.contract.work_class
    )
    for data in (
        charge,
        charge.canonical_descriptor(),
        canonical_identity_bytes(charge.canonical_descriptor()),
        pickle.loads(pickle.dumps(charge)),
    ):
        abort(lambda data=data: ctx.work.execute(data, work))
    abort(
        lambda: authorize(opened, reservation, prepared),
        FailureCode.MISSING_BUDGET_CHARGE,
    )
    assert ledger.summary(auth).consumed == 1


def test_wrong_budget_source_binding_cannot_replay(opened):
    _, reservation, prepared = plan(opened)
    record = object.__new__(BudgetChargeView)
    for f in fields(BudgetChargeView):
        object.__setattr__(record, f.name, getattr(prepared.charge, f.name))
    original = BudgetChargeView.canonical_descriptor
    # Fault injection in the accounting-data codec, NOT trusted issuer data.
    # Gate detects full binding disagreement even when four visible fields match.
    with pytest.MonkeyPatch.context() as patch:

        def wrong(self):
            data = original(self)
            return (
                d(data.kind, BudgetSourceKind.FORECAST_ESCROW, *data.values[1:])
                if self is record
                else data
            )

        patch.setattr(BudgetChargeView, "canonical_descriptor", wrong)
        forged = PreparedDispatch(prepared.work, record, prepared.unit_ordinal)
        abort(lambda: authorize(opened, reservation, forged))


@pytest.mark.parametrize("revision", [1, True, -1])
def test_stale_revision_cannot_authorize(opened, revision):
    ctx, auth, ledger, cie = opened
    _, reservation, prepared = plan(opened)
    before = ledger.summary(auth)
    abort(
        lambda: ctx.work.authorize_and_charge(
            auth, revision, cie, ledger, reservation, prepared
        )
    )
    assert ledger.summary(auth) == before


def test_close_first_forbids_authorization_and_execution(opened):
    ctx, auth, ledger, cie = opened
    work, reservation, prepared = plan(opened)
    permit = authorize(opened, reservation, prepared)
    _, unused, next_plan = plan(opened)
    ctx.parent.begin_close(auth, 0)
    before = ledger.summary(auth)
    abort(
        lambda: ctx.work.authorize_and_charge(auth, 1, cie, ledger, unused, next_plan),
        FailureCode.INVOCATION_NOT_ACTIVE,
    )
    abort(lambda: ctx.work.execute(permit, work))
    assert ledger.summary(auth) == before
    record = private_permit(permit)
    assert record.state == "RETIRED"
    assert record.work is record.image is record.binding is record.output is None


def test_two_concurrent_authorizations_cannot_share_charge(opened):
    _, auth, ledger, _ = opened
    _, reservation, prepared = plan(opened)
    start = Barrier(2)

    def contender():
        start.wait(5)
        try:
            return authorize(opened, reservation, prepared)
        except IngressAbort as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outputs = tuple(pool.map(lambda _: contender(), range(2)))
    assert sum(type(v) is WorkExecutionPermit for v in outputs) == 1
    assert FailureCode.MISSING_BUDGET_CHARGE in outputs
    assert ledger.summary(auth).consumed == 1
    assert (
        private_permit(
            next(v for v in outputs if type(v) is WorkExecutionPermit)
        ).owner.index[0]
        == 1
    )


def test_two_concurrent_execution_claims_run_worker_once(opened):
    ctx, _, _, _ = opened
    work, reservation, prepared = plan(opened)
    permit = authorize(opened, reservation, prepared)
    start = Barrier(2)

    def contender():
        start.wait(5)
        try:
            return ctx.work.execute(permit, work)
        except IngressAbort as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outputs = tuple(pool.map(lambda _: contender(), range(2)))
    assert sum(type(v) is PureWorkResultView for v in outputs) == 1


def test_injected_mint_failure_changes_no_budget_owner_or_epoch(opened, monkeypatch):
    ctx, auth, ledger, _ = opened
    _, reservation, prepared = plan(opened)
    before = ledger.summary(auth)
    original = work_module.PureWorkResultView

    def fail(*args):
        raise MemoryError("allocation failure before commit")

    monkeypatch.setattr(work_module, "PureWorkResultView", fail)
    with pytest.raises(MemoryError):
        authorize(opened, reservation, prepared)
    assert ledger.summary(auth) == before
    with _pinned_cie_parent(ctx.parent, auth) as (_, item, _):
        assert item.work_owner is None
    monkeypatch.setattr(work_module, "PureWorkResultView", original)
    permit = authorize(opened, reservation, prepared)
    assert ctx.work.permit_binding(permit).values[-1] == 0


def test_authorization_precedes_close_without_gap(opened, monkeypatch):
    ctx, auth, ledger, _ = opened
    _, reservation, prepared = plan(opened)
    inside, release, close_started = Event(), Event(), Event()
    original = work_module._prepare_consumption

    def paused(*args):
        candidate = original(*args)
        inside.set()
        assert release.wait(5)
        return candidate

    monkeypatch.setattr(work_module, "_prepare_consumption", paused)

    def close():
        close_started.set()
        return ctx.parent.begin_close(auth, 0)

    with ThreadPoolExecutor(max_workers=2) as pool:
        dispatch = pool.submit(authorize, opened, reservation, prepared)
        assert inside.wait(5)
        closing = pool.submit(close)
        assert close_started.wait(5)
        assert not closing.done()
        release.set()
        permit = dispatch.result(5)
        assert closing.result(5).state is InvocationState.CLOSING
    assert ledger.summary(auth).consumed == 1
    assert private_permit(permit).state == "RETIRED"


def test_final_registry_insertion_failure_is_atomic(opened):
    ctx, auth, ledger, _ = opened
    _, reservation, prepared = plan(opened)
    before = ledger.summary(auth)
    fn = WorkRuntime.authorize_and_charge
    cells = dict(zip(fn.__code__.co_freevars, fn.__closure__, strict=True))
    cell = cells["handles"]
    original = cell.cell_contents

    class FailingIndex(dict):
        def __setitem__(self, key, value):
            raise MemoryError("final registry allocation")

    cell.cell_contents = FailingIndex(original)
    try:
        with pytest.raises(MemoryError):
            authorize(opened, reservation, prepared)
        assert ledger.summary(auth) == before
        with _pinned_cie_parent(ctx.parent, auth) as (_, item, _):
            assert item.work_owner is None
    finally:
        cell.cell_contents = original
    permit = authorize(opened, reservation, prepared)
    assert ctx.work.permit_binding(permit).values[-1] == 0


def test_return_value_failure_is_not_partial_staging(opened, monkeypatch):
    ctx, auth, ledger, _ = opened
    work, reservation, prepared = plan(opened)
    permit = authorize(opened, reservation, prepared)

    def fail(*args):
        raise MemoryError("result allocation")

    monkeypatch.setattr(work_module, "PureWorkResultView", fail)
    with pytest.raises(MemoryError):
        ctx.work.execute(permit, work)
    record = private_permit(permit)
    assert record.state == "RETIRED"
    assert record.work is record.output is record.image is record.binding is None
    assert ledger.summary(auth).consumed == 1


def test_serialized_exact_work_is_data_but_not_permit(opened):
    ctx, _, _, _ = opened
    work, reservation, prepared = plan(opened)
    reconstructed = pickle.loads(pickle.dumps(work))
    assert canonical_identity_bytes(
        work.canonical_descriptor()
    ) == canonical_identity_bytes(reconstructed.canonical_descriptor())
    for data in (
        work,
        reconstructed,
        prepared,
        work.canonical_descriptor(),
        canonical_identity_bytes(work.canonical_descriptor()),
    ):
        abort(lambda data=data: ctx.work.execute(data, work))
    permit = authorize(opened, reservation, prepared)
    # Equivalent closed data is permitted ONLY with the genuine one-shot WEP.
    ctx.work.execute(permit, reconstructed)


def test_running_worker_finishes_after_close_without_publication(opened, monkeypatch):
    ctx, auth, ledger, cie = opened
    work, reservation, prepared = plan(opened)
    permit = authorize(opened, reservation, prepared)
    inside, release = Event(), Event()
    original = work_module._closed_value_worker
    received = []

    def paused(value, token, execution_context):
        received.extend((value, token, execution_context))
        # Authority locks are absent during physical work.
        with RankedBarrier(0):
            pass
        inside.set()
        assert release.wait(5)
        return original(value, token, execution_context)

    monkeypatch.setattr(work_module, "_closed_value_worker", paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(ctx.work.execute, permit, work)
        assert inside.wait(5)
        ctx.parent.begin_close(auth, 0)
        ledger.retire_unused(auth, 1)
        assert ctx.parent.finalize_close(auth, 1)  # no physical child drain wait
        release.set()
        result = pending.result(5)
    assert received[1] is permit
    canonical_identity_bytes(received[0])
    canonical_identity_bytes(received[2])
    assert ctx.cie.status(cie) == FailureCode.PARENT_AUTHORITY_STALE.value
    abort(lambda: ctx.cie.publish(cie, permit))
    abort(lambda: ctx.work.execute(permit, work))
    abort(
        lambda: ctx.work.control(
            ControlPlaneOperation.ATTACH_ALREADY_PRODUCED_DESCRIPTOR,
            auth,
            2,
            permit=permit,
        )
    )
    record = private_permit(permit)
    assert record.state == "DONE"
    assert record.work is record.binding is record.image is record.output is None
    canonical_identity_bytes(result.canonical_descriptor())


def test_exact_work_substitution_does_not_spend_permit(opened):
    ctx, _, _, _ = opened
    work, reservation, prepared = plan(opened)
    permit = authorize(opened, reservation, prepared)
    wrong = replace(work, frozen_input=d("different", 999))
    # Refreshing envelope to match the new value cannot change protected identity.
    ctx_auth = opened[1]
    wrong = ctx.work.prepare_work(
        ctx_auth, 0, work.snapshot_binding, wrong.frozen_input
    )
    abort(lambda: ctx.work.execute(permit, wrong), FailureCode.INVALID_INPUT)
    assert private_permit(permit).state == "ISSUED"
    ctx.work.execute(permit, work)


def test_hash_collision_does_not_define_work_equality(opened):
    ctx, _, _, _ = opened
    work, reservation, prepared = plan(opened, d("integer", -1))
    other_work = ctx.work.prepare_work(
        opened[1], 0, work.snapshot_binding, d("integer", -2)
    )
    assert hash(-1) == hash(-2)
    assert canonical_identity_bytes(
        work.canonical_descriptor()
    ) != canonical_identity_bytes(other_work.canonical_descriptor())
    permit = authorize(opened, reservation, prepared)
    abort(lambda: ctx.work.execute(permit, other_work))
    ctx.work.execute(permit, work)


def test_stale_snapshot_and_environment_change_do_not_charge(opened):
    ctx, auth, ledger, cie = opened
    _, reservation, prepared = plan(opened)
    old = ctx.cie.snapshot(cie)
    stage = ctx.cie.stage(cie, old, ())
    ctx.cie.publish(cie, stage)
    before = ledger.summary(auth)
    abort(lambda: authorize(opened, reservation, prepared), FailureCode.CIE_STALE)
    assert ledger.summary(auth) == before
    _, reservation, prepared = plan(opened)
    TrustedCoreAdapter.process_event(ctx.core, SurfaceEvent(b"change"))
    abort(
        lambda: authorize(opened, reservation, prepared), FailureCode.ENVIRONMENT_STALE
    )
    assert ledger.summary(auth).consumed == 0
    assert ctx.cie.status(cie) == FailureCode.ENVIRONMENT_STALE.value


def test_cie_token_swap_even_same_owner_cannot_charge(opened):
    ctx, auth, ledger, cie = opened
    _, reservation, prepared = plan(opened)
    ctx.cie.abort(cie)
    replacement = ctx.cie.open(auth, 0)
    abort(
        lambda: ctx.work.authorize_and_charge(
            auth, 0, replacement, ledger, reservation, prepared
        ),
        FailureCode.CIE_STALE,
    )
    assert ledger.summary(auth).consumed == 0


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {1},
        lambda: 1,
        float("nan"),
        float("inf"),
        object(),
    ],
)
def test_closed_inputs_reject_mutable_opaque_and_nonfinite(opened, payload):
    ctx, auth, ledger, cie = opened
    before = ledger.summary(auth)
    abort(
        lambda: ctx.work.prepare_work(auth, 0, ctx.cie.snapshot(cie).binding, payload),
        FailureCode.INVALID_INPUT,
    )
    assert ledger.summary(auth) == before


def test_live_authority_cannot_leak_nested_into_worker(opened):
    ctx, auth, ledger, cie = opened
    work, reservation, prepared = plan(opened)
    permit = authorize(opened, reservation, prepared)
    for handle in (
        auth,
        ledger,
        ctx.issuer,
        ctx.parent,
        ctx.cie,
        ctx.work,
        cie,
        permit,
        reservation,
    ):
        abort(
            lambda handle=handle: ctx.work.prepare_work(
                auth, 0, work.snapshot_binding, (handle,)
            ),
            FailureCode.INVALID_INPUT,
        )


def test_frozen_input_capture_and_result_no_external_alias(opened):
    ctx, auth, _, cie = opened
    value = d("private", d("nested", 7))
    work = ctx.work.prepare_work(auth, 0, ctx.cie.snapshot(cie).binding, value)
    object.__setattr__(value, "values", (d("nested", 99),))
    assert work.frozen_input.values[0].values == (7,)
    reservation, prepared = ctx.work.reserve(auth, 0, cie, opened[2], work)
    permit = authorize(opened, reservation, prepared)
    result = ctx.work.execute(permit, work)
    before = ctx.work.control(
        ControlPlaneOperation.ATTACH_ALREADY_PRODUCED_DESCRIPTOR, auth, 0, permit=permit
    )
    object.__setattr__(result, "output", d("caller-mutated", 999))
    after = ctx.work.control(
        ControlPlaneOperation.ATTACH_ALREADY_PRODUCED_DESCRIPTOR, auth, 0, permit=permit
    )
    assert canonical_identity_bytes(after) == canonical_identity_bytes(before)


def test_oversized_outer_tuple_rejected_before_member_inspection(opened):
    ctx, auth, _, cie = opened

    class Poison:
        def __getattribute__(self, name):
            raise AssertionError("oversized member inspected")

    value = (Poison(),) * 129
    abort(
        lambda: ctx.work.prepare_work(auth, 0, ctx.cie.snapshot(cie).binding, value),
        FailureCode.INVALID_INPUT,
    )
    work, _, _ = plan(opened)
    with pytest.raises(ValueError, match="bound"):
        replace(work.contract, authority_requirements=(Poison(),) * 5)


def test_supplied_work_checks_tighter_input_bound_before_full_encoding(
    opened, monkeypatch
):
    ctx, auth, ledger, _ = opened
    work, reservation, prepared = plan(opened)
    unchecked = object.__new__(FrozenWork)
    for f in fields(FrozenWork):
        object.__setattr__(unchecked, f.name, getattr(work, f.name))
    poison = object()
    oversized = (poison,) * 129
    object.__setattr__(unchecked, "frozen_input", oversized)
    # Construct unchecked dispatch data without invoking its general codec.
    forged = object.__new__(PreparedDispatch)
    for f in fields(PreparedDispatch):
        object.__setattr__(forged, f.name, getattr(prepared, f.name))
    object.__setattr__(forged, "work", unchecked)
    calls = []
    original = operation_module.canonical_identity_bytes

    def watched(value, *args):
        calls.append(value)
        return original(value, *args)

    monkeypatch.setattr(operation_module, "canonical_identity_bytes", watched)
    with pytest.raises(ValueError, match="node bound"):
        operation_module.freeze_work(WorkPolicy(), unchecked)
    assert len(calls) == 1 and calls[0] is oversized
    calls.clear()
    before = ledger.summary(auth)
    abort(lambda: authorize(opened, reservation, forged), FailureCode.INVALID_INPUT)
    assert len(calls) == 1 and calls[0] is oversized
    assert ledger.summary(auth) == before
    # Neither the reservation nor dispatch ordinal was consumed.
    permit = authorize(opened, reservation, prepared)
    assert ctx.work.permit_binding(permit).values[-1] == 0


def test_tighter_bound_is_rechecked_during_private_copy(opened, monkeypatch):
    ctx, auth, _, cie = opened
    source = d("input", (1,))
    original = ingress_module._validated_record_fields
    changed = []

    def raced(item, remaining):
        data = original(item, remaining)
        if item is source:
            # Simulate frozen-field bypass after initial encoding, during copy.
            changed.append(True)
            return tuple(
                (name, (object(),) * 129 if name == "values" else value)
                for name, value in data
            )
        return data

    monkeypatch.setattr(ingress_module, "_validated_record_fields", raced)
    abort(
        lambda: ctx.work.prepare_work(auth, 0, ctx.cie.snapshot(cie).binding, source),
        FailureCode.INVALID_INPUT,
    )
    assert changed == [True]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_input_nodes": True},
        {"max_input_nodes": 257},
        {"max_input_depth": 33},
        {"max_scalar_bytes": 8193},
        {"max_input_bytes": 0},
    ],
)
def test_policy_bounds_are_exact_and_finite(kwargs):
    with pytest.raises(ValueError):
        WorkPolicy(**kwargs)


@isolated_runtime_test
def test_trusted_policy_is_frozen_and_cannot_attach_late_or_refresh():
    policy = WorkPolicy()
    ctx = make_context(work=False)
    ctx.work = create_work_runtime(ctx.parent, ctx.cie, policy=policy)
    object.__setattr__(policy, "max_input_nodes", 1)
    auth, ledger, cie = ctx.fresh()
    work = ctx.work.prepare_work(auth, 0, ctx.cie.snapshot(cie).binding, (1, 2, 3))
    assert work.contract.resource_envelope.max_nodes == 128
    binding = ctx.cie.snapshot(cie).binding.cie.environment.l3_policy
    assert binding.kind == "L3Unit5PolicyBinding"
    abort(
        lambda: create_work_runtime(ctx.parent, ctx.cie),
        FailureCode.INVALID_POLICY_BINDING,
    )
    ctx.parent.begin_close(auth, 0)
    ledger.retire_unused(auth, 1)
    ctx.parent.finalize_close(auth, 1)
    late = make_context(work=False)
    _, _, token = late.fresh()
    late.cie.abort(token)
    del token
    gc.collect()
    abort(
        lambda: create_work_runtime(late.parent, late.cie),
        FailureCode.INVALID_POLICY_BINDING,
    )


def test_complete_nonrenewable_budget_bounds_registry_and_epochs(opened):
    ctx, auth, ledger, _ = opened
    permits = []
    for ordinal in range(8):
        work, reservation, prepared = plan(opened, d("input", ordinal))
        token = authorize(opened, reservation, prepared)
        permits.append(token)
        assert ctx.work.permit_binding(token).values[-1] == ordinal
        ctx.work.execute(token, work)
    before = ledger.summary(auth)
    abort(lambda: plan(opened), FailureCode.BUDGET_ABORT)
    assert before.initial == before.consumed == 8
    assert ledger.summary(auth) == before
    owner = private_permit(permits[0]).owner
    assert len(owner.index[1]) == owner.index[0] == 8
    ctx.parent.begin_close(auth, 0)
    for record in owner.index[1].values():
        assert record.work is record.binding is record.image is record.output is None
    assert (
        ctx.work.control(
            ControlPlaneOperation.RELEASE_TERMINAL_REGISTRY_CAPACITY, auth, 1
        )
        == 8
    )
    assert owner.index == (8, {})
    assert ledger.summary(auth) == before


def test_worker_failure_burns_permit_without_refund(opened, monkeypatch):
    ctx, auth, ledger, _ = opened
    work, reservation, prepared = plan(opened)
    permit = authorize(opened, reservation, prepared)

    def failing(*args):
        raise RuntimeError("physical worker failure")

    monkeypatch.setattr(work_module, "_closed_value_worker", failing)
    with pytest.raises(RuntimeError):
        ctx.work.execute(permit, work)
    abort(lambda: ctx.work.execute(permit, work))
    assert ledger.summary(auth).consumed == 1
    assert private_permit(permit).work is None


def test_exact_six_exempt_handlers_are_administrative_only(opened):
    ctx, auth, ledger, cie = opened
    assert len(ControlPlaneOperation) == 6
    before = ctx.cie.snapshot(cie).canonical_bytes
    assert (
        ctx.work.control(ControlPlaneOperation.READ_IMMUTABLE_LIFECYCLE_FLAG, auth, 0)
        is InvocationState.ACTIVE
    )
    work, reservation, prepared = plan(opened)
    permit = authorize(opened, reservation, prepared)
    abort(
        lambda: ctx.work.control(
            ControlPlaneOperation.ATTACH_ALREADY_PRODUCED_DESCRIPTOR,
            auth,
            0,
            permit=permit,
        )
    )
    ctx.work.execute(permit, work)
    assert (
        ctx.work.control(
            ControlPlaneOperation.CANONICAL_COMPARE_WITHIN_ALREADY_CHARGED_PARENT_WORK,
            auth,
            0,
            permit=permit,
        )
        is True
    )
    canonical_identity_bytes(
        ctx.work.control(
            ControlPlaneOperation.ATTACH_ALREADY_PRODUCED_DESCRIPTOR,
            auth,
            0,
            permit=permit,
        )
    )
    assert ctx.cie.snapshot(cie).canonical_bytes == before
    ctx.work.control(
        ControlPlaneOperation.AUTHORITY_REDUCING_LIFECYCLE_BOOKKEEPING, auth, 0
    )
    ctx.work.control(ControlPlaneOperation.RETIRE_UNUSED_CHARGE_UNITS, auth, 1)
    assert ledger.summary(auth).retired == 7
    assert (
        ctx.work.control(
            ControlPlaneOperation.RELEASE_TERMINAL_REGISTRY_CAPACITY, auth, 1
        )
        == 1
    )
    assert ctx.parent.finalize_close(auth, 1)


@pytest.mark.parametrize("operation", list(ControlPlaneOperation))
@pytest.mark.parametrize(
    "extra", ["callback", "frontier", "arena", "helper", "publication"]
)
def test_exempt_dispatch_cannot_hide_callbacks_traversal_or_publication(
    opened, operation, extra
):
    ctx, auth, ledger, _ = opened
    called = []

    def charged_helper():
        called.append(True)
        return plan(opened)

    before = ledger.summary(auth)
    with pytest.raises(TypeError):
        ctx.work.control(operation, auth, 0, **{extra: charged_helper})
    assert called == []
    assert ledger.summary(auth) == before


@pytest.mark.parametrize(
    "operation",
    [
        "READ_IMMUTABLE_LIFECYCLE_FLAG",
        "REASON_FREE",
        "RETRIEVE",
        "PUBLISH",
        "SEVENTH",
        None,
        True,
    ],
)
def test_seventh_and_semantic_exemptions_fail_closed(opened, operation):
    ctx, auth, _, _ = opened
    abort(
        lambda: ctx.work.control(operation, auth, 0), FailureCode.UNKNOWN_OPERATION_TYPE
    )


@pytest.mark.parametrize("ranks", [(3, 2), (2, 1), (1, 0)])
def test_explicit_lock_inversion_is_rejected_before_acquisition(ranks):
    outer, forbidden = map(RankedBarrier, ranks)
    with outer:
        abort(lambda: forbidden.acquire(), FailureCode.INTERNAL_CONTRACT_VIOLATION)
    with forbidden:
        pass


def test_real_runtime_lock_inversions_cannot_call_accounting_or_core(opened):
    ctx, auth, ledger, cie = opened
    _, reservation, prepared = plan(opened)
    with RankedBarrier(3):
        abort(
            lambda: ledger.consume(
                auth,
                0,
                reservation,
                prepared.unit_ordinal,
                prepared.work.contract.work_class,
            )
        )
    with RankedBarrier(2):
        abort(lambda: ctx.parent.validate(auth, 0))
    with ctx.parent.active_guard(auth, 0):
        abort(
            lambda: ctx.work.authorize_and_charge(
                auth, 0, cie, ledger, reservation, prepared
            )
        )
    assert ledger.summary(auth).consumed == 0


def test_complete_gate_uses_all_six_lock_ranks(opened, monkeypatch):
    _, reservation, prepared = plan(opened)
    trace = []
    original = RankedBarrier.acquire

    def acquire(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        if result:
            trace.append(self.rank)
        return result

    monkeypatch.setattr(RankedBarrier, "acquire", acquire)
    authorize(opened, reservation, prepared)
    assert {0, 1, 2, 3, 4, 5}.issubset(trace)
    assert (
        trace.index(0)
        < trace.index(1)
        < trace.index(2)
        < trace.index(3)
        < trace.index(4)
    )


@isolated_runtime_test
def test_gc_cleanup_is_reducing_and_drained_after_outer_lock():
    ctx = make_context()
    auth, ledger, cie = ctx.fresh()
    with _pinned_cie_parent(ctx.parent, auth) as (_, item, _):
        assert item.cie_child is not None
    with RankedBarrier(4):
        del cie
        gc.collect()
        # GC must not try to acquire lifecycle beneath owner.
    with _pinned_cie_parent(ctx.parent, auth) as (_, item, _):
        assert item.cie_child is None
    ctx.parent.begin_close(auth, 0)
    ledger.retire_unused(auth, 1)
    assert ctx.parent.finalize_close(auth, 1)


@isolated_runtime_test
def test_operational_root_gc_removes_semantic_permit_payload():
    ctx = make_context()
    opened = (ctx, *ctx.fresh())
    work, reservation, prepared = plan(opened)
    permit = authorize(opened, reservation, prepared)
    record = private_permit(permit)
    ctx.work = None
    gc.collect()
    assert record.work is record.image is record.binding is record.output is None
    assert record.owner.index[1] == {}
    abort(lambda: WorkRuntime.execute(object.__new__(WorkRuntime), permit, work))


def test_worker_result_is_not_formal_or_trusted_ingress(opened):
    ctx, _, _, _ = opened
    work, reservation, prepared = plan(opened)
    permit = authorize(opened, reservation, prepared)
    result = ctx.work.execute(permit, work)
    # Narrow genuine adapters reject all internal descriptor/permit/result data.
    for value in (
        result,
        result.canonical_descriptor(),
        result.output,
        ctx.work.permit_binding(permit),
        permit,
        retrieve_internal(ctx.core, {}),
    ):
        abort(
            lambda value=value: FormalReasoningIngress.accept(
                ctx.issuer.formal_reasoning, value
            )
        )
        abort(
            lambda value=value: TrustedObservationAdapter.accept(
                ctx.issuer.observations, value
            )
        )


def test_dispatch_epoch_is_authorization_order_not_completion(opened, monkeypatch):
    ctx, _, _, _ = opened
    first, reservation, prepared = plan(opened, d("input", 0))
    p0 = authorize(opened, reservation, prepared)
    second, reservation, prepared = plan(opened, d("input", 1))
    p1 = authorize(opened, reservation, prepared)
    inside, release = Event(), Event()
    original = work_module._closed_value_worker

    def worker(value, permit, execution_context):
        if permit is p0:
            inside.set()
            assert release.wait(5)
        return original(value, permit, execution_context)

    monkeypatch.setattr(work_module, "_closed_value_worker", worker)
    with ThreadPoolExecutor(max_workers=2) as pool:
        earlier = pool.submit(ctx.work.execute, p0, first)
        assert inside.wait(5)
        later = pool.submit(ctx.work.execute, p1, second).result(5)
        assert later.permit_binding.values[-1] == 1
        release.set()
        assert earlier.result(5).permit_binding.values[-1] == 0


UNIT5_DETERMINISTIC_SCRIPT = """
from dgca_lite import CoreConfig, CoreEngine
from dgca_lite.cognition.identity import CanonicalDescriptor, ClaimContentID, ScopeIdentity
from dgca_lite.cognition.ingress import create_trusted_ingress_boundary
from dgca_lite.cognition.invocation import create_invocation_runtime, InvocationLimits
from dgca_lite.cognition.cie import create_cie_runtime
from dgca_lite.cognition.work import create_work_runtime
from dgca_lite.cognition.serialization import canonical_identity_bytes
def d(k, *v): return CanonicalDescriptor(k, v)
core = CoreEngine(CoreConfig(receptor_fanout=1))
issuer = create_trusted_ingress_boundary(core, d("deterministic-unit5"), d("source"))
parent = create_invocation_runtime(issuer.invocation_causes, InvocationLimits(8))
cie_runtime = create_cie_runtime(parent)
work_runtime = create_work_runtime(parent, cie_runtime)
source = issuer.authorize_given(ClaimContentID(d("GroundAtom", "P")), ScopeIdentity("FORMAL", d("source"), d("scope")), d("occurrence", 0))
auth = parent.admit(source)
ledger = parent.ledger(auth)
cie = cie_runtime.open(auth, 0)
results = []
for i in range(2):
    work = work_runtime.prepare_work(auth, 0, cie_runtime.snapshot(cie).binding, d("input", i, True, -0.0, (b"x", "y")))
    reservation, prepared = work_runtime.reserve(auth, 0, cie, ledger, work)
    permit = work_runtime.authorize_and_charge(auth, 0, cie, ledger, reservation, prepared)
    results.append(work_runtime.execute(permit, work).canonical_descriptor())
print(canonical_identity_bytes(d("Unit5Audit", *results)).hex())
"""


@pytest.mark.parametrize("seed", ["0", "1", "27", "123", "random"])
def test_independent_process_deterministic_authority_free_results(seed):
    env = dict(os.environ, PYTHONHASHSEED=seed)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
    output = subprocess.run(
        [sys.executable, "-B", "-c", UNIT5_DETERMINISTIC_SCRIPT],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    data = bytes.fromhex(output.stdout.strip())
    assert output.stderr == ""
    # Fixed sequence audit uses full canonical identities, no live token bytes.
    assert hashlib.sha256(data).hexdigest() == UNIT5_SIGNATURE


UNIT5_SIGNATURE = "8479e8a9713577256304bf191c9c536015345af2763a9b3fcc66fc038438b148"
