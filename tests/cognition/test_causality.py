"""Unit 9: complete Causality, closed replay and authority adversarial checks.

The mechanical toy domain below is TEST ONLY. Production accepts only genuine
trusted controller receipts; it exposes no executor, script, or plugin hook.
"""

import copy
import hashlib
import inspect
import os
import pickle
import subprocess
import sys
from dataclasses import replace
from functools import wraps
from itertools import count
from pathlib import Path
from threading import Event, Thread

import pytest

from dgca_lite import CoreConfig, CoreEngine, SurfaceEvent
from dgca_lite.cognition.authority import IngressAbort
from dgca_lite.cognition.causality.adapters import causal_result_view, reasoning_view
from dgca_lite.cognition.causality.contracts import (
    CausalityPolicy,
    CausalOperation,
    contract,
    d,
    work_frontier,
)
from dgca_lite.cognition.causality.intervention import (
    ExposureDescriptor,
    TreatmentDescriptor,
    treatment_pair,
)
from dgca_lite.cognition.causality.measurement import (
    ExactOutcomeClassification,
    MeasurementContract,
    OutcomeSpec,
)
from dgca_lite.cognition.causality.replay import (
    ClosedReplayDomainContract,
    ReplayEnvironmentBinding,
    contrast_identity,
    identification_basis,
)
from dgca_lite.cognition.causality.runtime import (
    create_causality_runtime,
)
from dgca_lite.cognition.causality.study import (
    CaseSlot,
    CausalHypothesis,
    CausalStudyAuthority,
    CausalStudyPlan,
    Comparison,
)
from dgca_lite.cognition.identity import ScopeIdentity
from dgca_lite.cognition.ingress import create_trusted_ingress_boundary
from dgca_lite.cognition.invocation import InvocationLimits
from dgca_lite.cognition.reasoning.fab import ground
from dgca_lite.cognition.serialization import canonical_identity_bytes
from dgca_lite.cognition.types import AssertionBasis, BudgetSourceKind, WorkEffectClass
from dgca_lite.persistence import engine_state

SCOPE = ScopeIdentity("FORMAL", d("source"), d("scope"))
OUTCOMES = tuple(d("Outcome", value) for value in range(4))
SPEC = OutcomeSpec(OUTCOMES)
CLASSIFIER = ExactOutcomeClassification(OUTCOMES[0], (OUTCOMES[1],))
MEASUREMENT = MeasurementContract(d("MeasurementTarget", "counter"), 1, SPEC)
DOMAIN = d("Domain", "counter")
STATE = d("CompleteCounterState", 0)
SCHEDULE = ((0, d("Exogenous", 0)), (1, d("Exogenous", 0)))
TREATMENTS = tuple(
    TreatmentDescriptor(
        d("SetCounter", value),
        d("Mechanism", "assignment"),
        d("Assignment", "fixed"),
        ExposureDescriptor(),
        DOMAIN,
        0,
    )
    for value in (0, 1)
)
REPLAY_CONTRACT = ClosedReplayDomainContract(
    STATE,
    SCHEDULE,
    1,
    TREATMENTS,
    d("BranchIsolation", "separate-state"),
    2,
    MEASUREMENT,
    d("TrustedDeterminism", "complete-counter-assign"),
)
_NAMES = count()


def context(*, budget=128, policy=None, effect_policy=None):
    core = CoreEngine(CoreConfig(logical_capacity=300))
    issuer = create_trusted_ingress_boundary(
        core, d("unit9", next(_NAMES)), d("source"), capacity=256
    )
    runtime = create_causality_runtime(
        issuer.invocation_causes,
        invocation_limits=InvocationLimits(budget),
        policy=policy,
        effect_policy=effect_policy,
    )
    return core, issuer, runtime


def invocation(ctx):
    _, issuer, runtime = ctx
    given = issuer.authorize_given(
        ground("GroundAtom", "p"), SCOPE, d("source-occurrence")
    )
    authority = runtime.invocations.admit(given)
    ledger = runtime.invocations.ledger(authority)
    cie = runtime.cie.open(authority, 0)
    return authority, ledger, cie


def prospective(
    ctx,
    query="CLOSED_REPLAY",
    *,
    repetitions=1,
    attempts=1,
    resolved=True,
    randomization=False,
    execute=(0, 1),
    domain=None,
):
    runtime = ctx[2]
    root = domain or runtime.trusted_domain(
        ctx[1],
        DOMAIN,
        d("Environment", "A"),
        MEASUREMENT,
        replay_contract=REPLAY_CONTRACT if query == "CLOSED_REPLAY" else None,
    )
    origin, origin_cap = (
        root.capture_origin(STATE) if query == "CLOSED_REPLAY" else (None, None)
    )
    plan = CausalStudyPlan(
        query,
        root.environment,
        (d("Condition", 0), d("Condition", 1)),
        SPEC,
        tuple(
            CaseSlot(
                d("Condition", i),
                None if query == "OBSERVATIONAL" else TREATMENTS[i],
                attempts,
            )
            for i in range(2)
        ),
        (Comparison(0, 1, requires_resolved=resolved),),
        execute,
        CLASSIFIER,
        d("Protocol", "prospective-complete"),
        runtime.policy,
        origin,
        repetitions,
        randomization,
    )
    return root, plan, origin_cap


def start(ctx, query="CLOSED_REPLAY", **options):
    root, plan, origin_cap = prospective(ctx, query, **options)
    authority, ledger, cie = invocation(ctx)
    study = ctx[2].open_study(
        authority, 0, ledger, root, plan, origin_authority=origin_cap
    )
    return root, plan, authority, ledger, cie, study


def execute_counter(
    root, plan, rce, *, outcomes=None, status="MEASURED", reverse=False
):
    """A genuinely closed mechanical harness, not a production execution API.

    Copy complete origin into independent branches, share exact frozen exogenous
    schedule, apply only the assigned treatment, measure one declared target.
    """
    application, protocol, isolation, execution, measurement = root.controllers
    receipts = []
    branches = {}
    for branch in (1, 0) if reverse else (0, 1):
        state = [plan.origin.state.values[0]]  # independent fork, no alias
        branches[branch] = state
        state[0] = plan.slots[branch].treatment.operation.values[0]
        applied = application.receipt(rce, branch)
        isolated = isolation.receipt(rce, branch)
        for _, exogenous in SCHEDULE:
            state[0] += exogenous.values[0]
        executed = execution.receipt(
            rce,
            branch,
            actual_origin=plan.origin.canonical_descriptor(),
            actual_schedule=SCHEDULE,
            consumed_steps=2,
        )
        outcome = OUTCOMES[state[0]] if outcomes is None else outcomes[branch]
        measured = measurement.receipt(
            rce,
            branch,
            outcome if status == "MEASURED" else None,
            measurement_status=status,
            target=MEASUREMENT.target,
            logical_slot=1,
            treatment_label_blind=True,
        )
        receipts.extend((applied, isolated, executed, measured))
    assert branches[0] is not branches[1]
    if plan.randomization_required:
        receipts.append(protocol.receipt(rce))
    return tuple(receipts)


def replay(ctx, *, outcomes=None, repetitions=1, resolved=True, reverse=False):
    root, plan, authority, ledger, cie, study = start(
        ctx, repetitions=repetitions, resolved=resolved
    )
    results = []
    for repeat in range(repetitions):
        rce = ctx[2].open_rce(authority, 0, ledger, study, repeat=repeat)
        receipts = execute_counter(root, plan, rce, outcomes=outcomes, reverse=reverse)
        ctx[2].admit_bundle(authority, 0, ledger, study, rce, receipts)
        results.append(ctx[2].compare(authority, 0, ledger, cie, study, rce=rce))
    report = ctx[2].finish_study(authority, 0, ledger, study)
    return report, results, ledger.summary(authority)


def fail_hook():
    raise RuntimeError("publication fault")


@pytest.mark.parametrize(
    "outcome,expected",
    [(0, "MATCH"), (1, "CONFLICT"), (2, "UNRESOLVED"), (3, "UNRESOLVED")],
)
def test_exact_prospective_classifier(outcome, expected):
    assert CLASSIFIER.classify(OUTCOMES[outcome], SPEC) == expected


@pytest.mark.parametrize(
    "status", ["MISSING", "FAILED", "INVALID", "UNAVAILABLE", "INCOMPLETE"]
)
def test_missing_is_unresolved_not_negative(status):
    assert CLASSIFIER.classify(None, SPEC, measurement_status=status) == "UNRESOLVED"
    with pytest.raises(ValueError):
        CLASSIFIER.classify(OUTCOMES[1], SPEC, measurement_status=status)


@pytest.mark.parametrize(
    "conflicts",
    [(OUTCOMES[0],), (OUTCOMES[1], OUTCOMES[1]), (OUTCOMES[2], OUTCOMES[1])],
)
def test_classifier_overlap_duplicate_order_rejected(conflicts):
    with pytest.raises(ValueError):
        ExactOutcomeClassification(OUTCOMES[0], conflicts)


@pytest.mark.parametrize(
    "field",
    ["operation", "mechanism", "assignment", "exposure", "domain", "protocol_revision"],
)
def test_full_treatment_identity(field):
    value = replace(
        TREATMENTS[0],
        **{
            field: {
                "operation": d("SetCounter", 2),
                "mechanism": d("Mechanism", "other"),
                "assignment": d("Assignment", "random"),
                "exposure": ExposureDescriptor(d("Dose", 2)),
                "domain": d("Domain", "other"),
                "protocol_revision": 1,
            }[field]
        },
    )
    assert canonical_identity_bytes(
        value.canonical_descriptor()
    ) != canonical_identity_bytes(TREATMENTS[0].canonical_descriptor())
    assert treatment_pair(TREATMENTS[0], value) == treatment_pair(value, TREATMENTS[0])


@pytest.mark.parametrize("operation", list(CausalOperation))
def test_compiled_operation_contract(operation):
    value = contract(operation)
    assert value.resource_envelope.charge_units == 1
    assert value.effect_class is (
        WorkEffectClass.PURE_COMPUTE
        if operation
        in (
            CausalOperation.CLASSIFY_CASE,
            CausalOperation.COMPARE_CASES,
            CausalOperation.COMPARE_REPLAY,
        )
        else WorkEffectClass.OPERATIONAL_EFFECT
    )


def test_replay_complete_rict_e_and_budget(context):
    before = engine_state(context[0])
    report, results, budget = replay(context)
    assert report.status == "COMPLETE"
    assert report.results == tuple(results)
    assert results[0].result_class == "REPLAY_IDENTIFIED_TREATMENT_EFFECT"
    assert results[0].outcome_relation == "DIFFERENT"
    assert [v.classification for v in report.slots] == ["MATCH", "CONFLICT"]
    assert budget.consumed == 6 and budget.reserved == budget.retired == 0
    assert engine_state(context[0]) == before
    assert context[2].registry_status().values == (1, 0, 1)


def test_equal_outcomes_not_no_effect(context):
    report, _, _ = replay(context, outcomes=(OUTCOMES[0], OUTCOMES[0]))
    assert report.results[0].result_class == "NO_PRESPECIFIED_OUTCOME_DISCRIMINATION"
    assert "NO_EFFECT" not in repr(report)


def test_repetitions_one_identity_not_new_evidence(context):
    report, results, budget = replay(context, repetitions=2)
    assert results[0].identity == results[1].identity
    assert len(report.results) == 1
    assert budget.consumed == 10 and context[2].registry_status().values[2] == 1


@pytest.mark.parametrize("resolved", [True, False])
def test_unresolved_not_coerced_to_conflict(context, resolved):
    report, _, _ = replay(
        context, outcomes=(OUTCOMES[0], OUTCOMES[2]), resolved=resolved
    )
    assert report.slots[1].classification == "UNRESOLVED"
    assert report.status == ("INCOMPLETE" if resolved else "COMPLETE")
    assert len(report.results) == (0 if resolved else 1)


def test_observational_occurrence_idempotent_and_distinct(context):
    root, _, authority, ledger, cie, study = start(context, "OBSERVATIONAL")
    case = root.capture_case(study, 0, OUTCOMES[0])
    assert root.capture_case(study, 0, OUTCOMES[0]) is case
    a = context[2].admit_case(authority, 0, ledger, cie, study, case)
    used = ledger.summary(authority)
    assert context[2].admit_case(authority, 0, ledger, cie, study, case) == a
    assert ledger.summary(authority) == used
    b = root.capture_case(study, 1, OUTCOMES[0])
    b_report = context[2].admit_case(authority, 0, ledger, cie, study, b)
    assert a.occurrence != b_report.occurrence
    report = context[2].compare(authority, 0, ledger, cie, study)
    assert report.results[0].result_class == "OBSERVATIONAL_COMPARISON"


def test_independent_comparator_reuse_rejected(context):
    root, _, authority, ledger, cie, study = start(context, "OBSERVATIONAL")
    source = root.capture_case(study, 0, OUTCOMES[0])
    context[2].admit_case(authority, 0, ledger, cie, study, source)
    reused = root.bind_case(study, 1, source)
    budget = ledger.summary(authority)
    with pytest.raises(IngressAbort):
        context[2].admit_case(authority, 0, ledger, cie, study, reused)
    assert ledger.summary(authority) == budget


def test_interventional_request_not_application(context):
    root, _, authority, ledger, cie, study = start(
        context, "INTERVENTIONAL", randomization=True
    )
    case = root.capture_case(study, 0, OUTCOMES[0])
    context[2].request_case(authority, 0, ledger, study, 0)
    budget = ledger.summary(authority)
    with pytest.raises(IngressAbort):
        context[2].admit_case(authority, 0, ledger, cie, study, case)
    assert ledger.summary(authority) == budget
    application, protocol, *_ = root.controllers
    for slot in range(2):
        context[2].request_case(authority, 0, ledger, study, slot)
        current = case if slot == 0 else root.capture_case(study, slot, OUTCOMES[slot])
        context[2].admit_case(
            authority,
            0,
            ledger,
            cie,
            study,
            current,
            application=application.receipt(study, slot),
            protocol=protocol.receipt(study),
        )
    report = context[2].compare(authority, 0, ledger, cie, study)
    assert report.results[0].result_class == "INTERVENTIONAL_PROTOCOL_COMPARISON"


def test_failed_measurement_predeclared_substitution(context):
    root, _, authority, ledger, cie, study = start(context, "OBSERVATIONAL", attempts=2)
    failed = root.capture_case(study, 0, None, measurement_status="FAILED")
    context[2].admit_case(authority, 0, ledger, cie, study, failed)
    replacement = root.capture_case(study, 0, OUTCOMES[0], attempt=1)
    context[2].admit_case(authority, 0, ledger, cie, study, replacement)
    peer = root.capture_case(study, 1, OUTCOMES[1])
    context[2].admit_case(authority, 0, ledger, cie, study, peer)
    report = context[2].compare(authority, 0, ledger, cie, study)
    assert report.status == "COMPLETE"
    assert ledger.summary(authority).retired == 2


def test_outcome_based_substitution_rejected(context):
    root, _, authority, ledger, cie, study = start(context, "OBSERVATIONAL", attempts=2)
    unresolved = root.capture_case(study, 0, OUTCOMES[2])
    context[2].admit_case(authority, 0, ledger, cie, study, unresolved)
    replacement = root.capture_case(study, 0, OUTCOMES[0], attempt=1)
    before = ledger.summary(authority)
    with pytest.raises(IngressAbort):
        context[2].admit_case(authority, 0, ledger, cie, study, replacement)
    assert ledger.summary(authority) == before


def test_incomplete_slots_no_selection_or_partial_result(context):
    root, _, authority, ledger, cie, study = start(
        context, "OBSERVATIONAL", execute=(0,)
    )
    case = root.capture_case(study, 0, OUTCOMES[0])
    context[2].admit_case(authority, 0, ledger, cie, study, case)
    with pytest.raises(IngressAbort):
        root.capture_case(study, 1, OUTCOMES[1])
    report = context[2].compare(authority, 0, ledger, cie, study)
    assert report.status == "INCOMPLETE" and report.results == ()
    assert report.slots[1].terminal_state == "LAWFULLY_UNEXECUTED"


@pytest.mark.parametrize(
    "kind",
    [
        "STUDY",
        "RCE",
        "CASE",
        "APPLICATION",
        "ISOLATION",
        "EXECUTION",
        "MEASUREMENT",
        "ORIGIN",
        "DOMAIN",
    ],
)
def test_opaque_handles_constructor_copy_serialization_forgery(context, kind):
    root, plan, authority, ledger, _cie, study = start(context)
    rce = context[2].open_rce(authority, 0, ledger, study)
    receipts = execute_counter(root, plan, rce)
    _, origin_cap = root.capture_origin(STATE)
    if kind == "CASE":
        obs = globals()["context"]()
        obs_root, _, _, _, _, obs_study = start(obs, "OBSERVATIONAL")
        actual_case = obs_root.capture_case(obs_study, 0, OUTCOMES[0])
    else:
        actual_case = root
    values = {
        "STUDY": study,
        "RCE": rce,
        "CASE": actual_case,
        "APPLICATION": receipts[0],
        "ISOLATION": receipts[1],
        "EXECUTION": receipts[2],
        "MEASUREMENT": receipts[3],
        "ORIGIN": origin_cap,
        "DOMAIN": root,
    }
    handle = values[kind]
    with pytest.raises(TypeError):
        type(handle)()
    for copier in (copy.copy, copy.deepcopy, pickle.dumps, canonical_identity_bytes):
        with pytest.raises((TypeError, ValueError)):
            copier(handle)
    forged = object.__new__(type(handle))
    if kind == "STUDY":
        with pytest.raises(IngressAbort):
            context[2].open_rce(authority, 0, ledger, forged)
    elif kind == "RCE":
        with pytest.raises(IngressAbort):
            root.controllers[0].receipt(forged, 0)
    elif kind == "DOMAIN":
        with pytest.raises(IngressAbort):
            _ = forged.environment
    else:
        altered = (forged,) + receipts[1:]
        with pytest.raises(IngressAbort):
            context[2].admit_bundle(authority, 0, ledger, study, rce, altered)


@pytest.mark.parametrize(
    "damage", ["partial", "duplicate", "wrong_role", "descriptor", "foreign"]
)
def test_bundle_complete_opaque_exact_rce(context, damage):
    root, plan, authority, ledger, cie, study = start(context, repetitions=2)
    rce = context[2].open_rce(authority, 0, ledger, study)
    receipts = execute_counter(root, plan, rce)
    if damage == "partial":
        bad = receipts[:-1]
    elif damage == "duplicate":
        bad = receipts[:-1] + (receipts[0],)
    elif damage == "wrong_role":
        bad = (root.controllers[0],) + receipts[1:]
    elif damage == "descriptor":
        bad = (d("CausalControllerReceipt", "APPLICATION"),) + receipts[1:]
    else:
        context[2].admit_bundle(authority, 0, ledger, study, rce, receipts)
        context[2].compare(authority, 0, ledger, cie, study, rce=rce)
        rce = context[2].open_rce(authority, 0, ledger, study, repeat=1)
        bad = receipts
    before = ledger.summary(authority)
    with pytest.raises(IngressAbort):
        context[2].admit_bundle(authority, 0, ledger, study, rce, bad)
    assert ledger.summary(authority) == before


@pytest.mark.parametrize(
    "damage", ["schedule", "origin", "steps", "target", "time", "blind", "outcome"]
)
def test_bound_physical_and_measurement_contract(context, damage):
    root, plan, authority, ledger, _cie, study = start(context)
    rce = context[2].open_rce(authority, 0, ledger, study)
    execution, measurement = root.controllers[3:]
    before = ledger.summary(authority)
    with pytest.raises((IngressAbort, ValueError, TypeError)):
        if damage in ("schedule", "origin", "steps"):
            execution.receipt(
                rce,
                0,
                actual_origin=d("OtherOrigin")
                if damage == "origin"
                else plan.origin.canonical_descriptor(),
                actual_schedule=((0, d("OtherSchedule")),)
                if damage == "schedule"
                else SCHEDULE,
                consumed_steps=3 if damage == "steps" else 2,
            )
        else:
            measurement.receipt(
                rce,
                0,
                d("UnboundOutcome") if damage == "outcome" else OUTCOMES[0],
                target=d("AdaptiveTarget")
                if damage == "target"
                else MEASUREMENT.target,
                logical_slot=0 if damage == "time" else 1,
                treatment_label_blind=damage != "blind",
            )
    assert ledger.summary(authority) == before


def test_environment_aba_invalidates_origin_study_rce(context):
    root, plan, authority, ledger, _cie, study = start(context)
    rce = context[2].open_rce(authority, 0, ledger, study)
    receipts = execute_counter(root, plan, rce)
    before = root.environment
    root.revise_environment(d("Environment", "B"))
    root.revise_environment(d("Environment", "A"))
    assert before.environment == root.environment.environment
    assert root.environment.revision == before.revision + 2
    with pytest.raises(IngressAbort):
        context[2].admit_bundle(authority, 0, ledger, study, rce, receipts)
    assert ledger.summary(authority).reserved == 0


def test_begin_close_aborts_studies_rces_and_retires(context):
    root, plan, authority, ledger, _cie, study = start(context)
    rce = context[2].open_rce(authority, 0, ledger, study)
    receipts = execute_counter(root, plan, rce)
    context[2].invocations.begin_close(authority, 0)
    assert context[2].registry_status().values[1] == 0
    assert ledger.summary(authority).reserved == 0
    for action in (
        lambda: root.controllers[0].receipt(rce, 0),
        lambda: context[2].admit_bundle(authority, 0, ledger, study, rce, receipts),
        lambda: context[2].open_rce(authority, 0, ledger, study),
    ):
        with pytest.raises(IngressAbort):
            action()
    ledger.retire_unused(authority, 1)
    assert context[2].invocations.finalize_close(authority, 1)


def test_study_survives_sequential_cies_only_active(context):
    root, plan, authority, ledger, cie, study = start(context, repetitions=2)
    for repeat in range(2):
        rce = context[2].open_rce(authority, 0, ledger, study, repeat=repeat)
        context[2].admit_bundle(
            authority, 0, ledger, study, rce, execute_counter(root, plan, rce)
        )
        context[2].compare(authority, 0, ledger, cie, study, rce=rce)
        context[2].cie.abort(cie)
        if repeat == 0:
            cie = context[2].cie.open(authority, 0)
    assert context[2].finish_study(authority, 0, ledger, study).status == "COMPLETE"


def test_open_reservation_failure_changes_nothing(context):
    ctx = globals()["context"](budget=5)
    root, plan, origin_cap = prospective(ctx)
    authority, ledger, _cie = invocation(ctx)
    before = ledger.summary(authority)
    with pytest.raises(IngressAbort):
        ctx[2].open_study(authority, 0, ledger, root, plan, origin_authority=origin_cap)
    assert ledger.summary(authority) == before
    assert ctx[2].registry_status().values[1:] == (0, 0)


def test_open_publication_fault_atomic(context, monkeypatch):
    root, plan, cap = prospective(context)
    authority, ledger, _cie = invocation(context)
    before = ledger.summary(authority)
    monkeypatch.setattr("dgca_lite.cognition.effects._before_effect_publish", fail_hook)
    with pytest.raises(RuntimeError):
        context[2].open_study(authority, 0, ledger, root, plan, origin_authority=cap)
    assert ledger.summary(authority) == before
    assert context[2].registry_status().values == (1, 0, 0)
    monkeypatch.undo()
    assert context[2].open_study(authority, 0, ledger, root, plan, origin_authority=cap)


def test_rce_registry_fault_rollback(context, monkeypatch):
    from dgca_lite.cognition.causality.runtime import _CausalSystem

    root, _, authority, ledger, _cie, study = start(context)
    original = _CausalSystem.register

    def faulty(system, token, role, record, domain):
        original(system, token, role, record, domain)
        if role == "RCE":
            raise RuntimeError("post-registration allocation fault")

    monkeypatch.setattr(_CausalSystem, "register", faulty)
    before = ledger.summary(authority)
    with pytest.raises(RuntimeError):
        context[2].open_rce(authority, 0, ledger, study)
    assert ledger.summary(authority) == before
    monkeypatch.undo()
    rce = context[2].open_rce(authority, 0, ledger, study)
    assert root.controllers[0].receipt(rce, 0)


def test_prepublication_failure_keeps_paid_work_no_refund(context, monkeypatch):
    root, plan, authority, ledger, cie, study = start(context)
    rce = context[2].open_rce(authority, 0, ledger, study)
    context[2].admit_bundle(
        authority, 0, ledger, study, rce, execute_counter(root, plan, rce)
    )
    original = __import__(
        "dgca_lite.cognition.effects", fromlist=["_before_effect_publish"]
    )._before_effect_publish
    count = 0

    def last_fault():
        nonlocal count
        count += 1
        if count == 2:
            fail_hook()
        original()

    before = ledger.summary(authority)
    monkeypatch.setattr(
        "dgca_lite.cognition.effects._before_effect_publish", last_fault
    )
    with pytest.raises(RuntimeError):
        context[2].compare(authority, 0, ledger, cie, study, rce=rce)
    after = ledger.summary(authority)
    assert after.consumed == before.consumed + 1
    assert context[2].registry_status().values[2] == 0
    monkeypatch.undo()
    result = context[2].compare(authority, 0, ledger, cie, study, rce=rce)
    assert result.result_class == "REPLAY_IDENTIFIED_TREATMENT_EFFECT"
    assert ledger.summary(authority).consumed == after.consumed + 1


def test_same_crci_disagreement_detected_not_new_evidence(context):
    root, plan, authority, ledger, cie, study = start(context, repetitions=2)
    for repeat in range(2):
        rce = context[2].open_rce(authority, 0, ledger, study, repeat=repeat)
        outcomes = None if repeat == 0 else (OUTCOMES[1], OUTCOMES[0])
        context[2].admit_bundle(
            authority,
            0,
            ledger,
            study,
            rce,
            execute_counter(root, plan, rce, outcomes=outcomes),
        )
        if repeat == 0:
            context[2].compare(authority, 0, ledger, cie, study, rce=rce)
        else:
            with pytest.raises(IngressAbort, match="DETERMINISM_CONTRACT_VIOLATION"):
                context[2].compare(authority, 0, ledger, cie, study, rce=rce)
    assert context[2].registry_status().values[2] == 1


def test_returned_origin_and_bundle_do_not_alias_private_state(context):
    root, plan, authority, ledger, cie, study = start(context)
    object.__setattr__(plan.origin.state, "values", (99,))
    rce = context[2].open_rce(authority, 0, ledger, study)
    clean_plan = replace(plan, origin=root.capture_origin(STATE)[0])
    # The genuine original source identity, not a replacement origin, is bound.
    clean_plan = replace(
        clean_plan, origin=replace(clean_plan.origin, occurrence_index=0)
    )
    receipts = execute_counter(root, clean_plan, rce)
    bundle = context[2].admit_bundle(authority, 0, ledger, study, rce, receipts)
    object.__setattr__(bundle.receipts[0], "values", ("tampered",))
    result = context[2].compare(authority, 0, ledger, cie, study, rce=rce)
    assert result.outcome_relation == "DIFFERENT"


def test_causal_adapter_is_modal_literal_not_formal_rule(context):
    report, _, _ = replay(context)
    view = causal_result_view(report.results[0])
    data = reasoning_view(view)
    ask = data.values[0]
    assert ask.basis is AssertionBasis.CAUSAL_RESULT_VIEW
    assert ask.dependencies == (view.causal_dependency_root,)
    assert ask.content.descriptor.kind == "CausalResultStatement"
    assert ask.scope == report.results[0].scope
    with pytest.raises((ValueError, TypeError)):
        replace(view, causal_dependency_root=None)
    assert b"CAUSES" not in canonical_identity_bytes(data)


def test_causal_result_reenters_reasoning_only_modal(context):
    report, _, _ = replay(context)
    authority, ledger, _cie = invocation(context)
    # Close the caller's empty CIE before the reasoning runtime opens its own.
    context[2].cie.abort(_cie)
    result = context[2].reasoning.run(
        authority, 0, ledger, (), causal_views=(causal_result_view(report.results[0]),)
    )
    assert result


def test_escrow_charge_is_causal_not_general(context):
    root, _, authority, ledger, _cie, study = start(context, "INTERVENTIONAL")
    value = context[2].request_case(authority, 0, ledger, study, 0)
    assert value.charge.source_kind is BudgetSourceKind.CAUSAL_STUDY_ESCROW
    with pytest.raises(IngressAbort):
        ledger.reserve(study, 0, 1, d("other-work"))
    before = ledger.summary(authority)
    context[2].abort(authority, 0, ledger, study)
    after = ledger.summary(authority)
    assert after.available == before.available and after.reserved == 0
    assert after.retired == before.reserved
    assert root.environment


def test_lifetime_study_capacity_and_no_semantic_history(context):
    policy = CausalityPolicy(max_studies=1)
    ctx = globals()["context"](policy=policy)
    root, plan, authority, ledger, _cie, study = start(ctx)
    ctx[2].abort(authority, 0, ledger, study)
    with pytest.raises(IngressAbort):
        ctx[2].open_study(
            authority,
            0,
            ledger,
            root,
            plan,
            origin_authority=root.capture_origin(STATE)[1],
        )
    assert ctx[2].registry_status().values == (1, 0, 0)


@pytest.mark.parametrize(
    "container", ["conflicts", "outcomes", "slots", "schedule", "treatments"]
)
def test_outer_bound_precedes_hostile_member(container):
    hostile = object()
    with pytest.raises(ValueError, match="outer bound"):
        if container == "conflicts":
            ExactOutcomeClassification(OUTCOMES[0], (hostile,) * 33)
        elif container == "outcomes":
            OutcomeSpec((hostile,) * 33)
        elif container == "slots":
            CausalStudyPlan(
                "OBSERVATIONAL",
                None,
                (),
                SPEC,
                (hostile,) * 17,
                (),
                (),
                CLASSIFIER,
                d("protocol"),
            )
        elif container == "schedule":
            replace(REPLAY_CONTRACT, exogenous_schedule=(hostile,) * 66)
        else:
            replace(REPLAY_CONTRACT, treatments=(hostile,) * 17)


@pytest.mark.parametrize("value", [True, False, -1, 1.0, float("nan"), float("inf")])
def test_numeric_identity_no_bool_nonfinite(value):
    with pytest.raises(ValueError):
        ReplayEnvironmentBinding(d("runtime"), d("environment"), value)


def test_hypothesis_data_only_and_no_live_nested_payload():
    value = CausalHypothesis(d("HypotheticalCause", "A", "B"))
    assert value.canonical_descriptor().kind == "CausalHypothesis"
    forged = object.__new__(CausalStudyAuthority)
    with pytest.raises(TypeError):
        CausalHypothesis(d("nested", forged))


def signature():
    report, _, budget = replay(context())
    return canonical_identity_bytes(
        d(
            "Unit9CausalitySignature",
            report.canonical_descriptor(),
            causal_result_view(report.results[0]).canonical_descriptor(),
            budget.canonical_descriptor(),
        )
    )


def test_supplied_pure_frame_cannot_forge_case_result(context):
    root, _, authority, ledger, cie, study = start(context, "OBSERVATIONAL")
    case = root.capture_case(study, 0, OUTCOMES[0])
    _, coordinate, genuine = context[2]._call(
        "case_input", authority, 0, ledger, study, case
    )
    rows = genuine.values[2]
    altered_row = rows[0][:3] + (OUTCOMES[1],) + rows[0][4:]
    forged = d("CausalCaseClassificationInput", *genuine.values[:2], (altered_row,))
    before = ledger.summary(authority)
    with pytest.raises(IngressAbort):
        context[2]._call(
            "prepare_compute",
            authority,
            0,
            ledger,
            cie,
            study,
            CausalOperation.CLASSIFY_CASE,
            0,
            forged,
            ("CASE", coordinate[1], coordinate[2]),
        )
    assert ledger.summary(authority) == before
    assert (
        context[2].admit_case(authority, 0, ledger, cie, study, case).classification
        == "MATCH"
    )


def test_classifier_mutation_after_open_not_active_plan_revision(context):
    root, plan, authority, ledger, cie, study = start(
        context, "OBSERVATIONAL", resolved=False
    )
    object.__setattr__(plan.matching, "explicit_conflict_outcomes", (OUTCOMES[2],))
    for slot, outcome in enumerate((OUTCOMES[0], OUTCOMES[2])):
        cap = root.capture_case(study, slot, outcome)
        context[2].admit_case(authority, 0, ledger, cie, study, cap)
    report = context[2].compare(authority, 0, ledger, cie, study)
    assert report.slots[1].classification == "UNRESOLVED"


@pytest.mark.parametrize("kind", ["case", "study", "receipt"])
def test_cross_runtime_and_core_reuse_rejected(context, kind):
    root, plan, authority, ledger, cie, study = start(context)
    rce = context[2].open_rce(authority, 0, ledger, study)
    receipts = execute_counter(root, plan, rce)
    other = globals()["context"]()
    foreign_root, _, foreign_authority, foreign_ledger, _foreign_cie, foreign_study = (
        start(other, "OBSERVATIONAL")
    )
    source = foreign_root.capture_case(foreign_study, 0, OUTCOMES[0])
    before = ledger.summary(authority)
    with pytest.raises(IngressAbort):
        if kind == "case":
            context[2].admit_case(authority, 0, ledger, cie, study, source)
        elif kind == "study":
            context[2].open_rce(authority, 0, ledger, foreign_study)
        else:
            other[2].admit_bundle(
                foreign_authority, 0, foreign_ledger, foreign_study, rce, receipts
            )
    assert ledger.summary(authority) == before


@pytest.mark.parametrize(
    "content",
    ["association", "prediction", "hypothesis", "formal", "derived", "copied-root"],
)
def test_internal_and_hypothetical_data_not_cases(context, content):
    root, _, authority, ledger, cie, study = start(context, "OBSERVATIONAL")
    value = d("CopiedContent", content)
    before = ledger.summary(authority)
    with pytest.raises(IngressAbort):
        context[2].admit_case(authority, 0, ledger, cie, study, value)
    assert ledger.summary(authority) == before
    assert root.environment


def test_new_origin_different_crci(context):
    root, plan, _, _, _, _ = start(context)
    other_origin, _ = root.capture_origin(STATE)
    basis = identification_basis(REPLAY_CONTRACT, root.environment)
    pair = treatment_pair(*TREATMENTS)
    a = contrast_identity(root.environment.domain_runtime, plan.origin, pair, basis)
    b = contrast_identity(root.environment.domain_runtime, other_origin, pair, basis)
    assert a != b and canonical_identity_bytes(a) != canonical_identity_bytes(b)


def test_hash_collision_never_conflates_origins_or_results(context, monkeypatch):
    class SameDigest:
        def hexdigest(self):
            return "0" * 64

        def digest(self):
            return bytes(32)

    monkeypatch.setattr(hashlib, "sha256", lambda *_args, **_kwargs: SameDigest())
    root, plan, authority, ledger, cie, study = start(context)
    identities = []
    for index in range(2):
        if index:
            origin, cap = root.capture_origin(STATE)
            plan = replace(plan, origin=origin)
            study = context[2].open_study(
                authority, 0, ledger, root, plan, origin_authority=cap
            )
        rce = context[2].open_rce(authority, 0, ledger, study)
        receipts = execute_counter(root, plan, rce)
        context[2].admit_bundle(authority, 0, ledger, study, rce, receipts)
        identities.append(
            context[2].compare(authority, 0, ledger, cie, study, rce=rce).identity
        )
        context[2].finish_study(authority, 0, ledger, study)
    assert identities[0] != identities[1]
    assert context[2].registry_status().values[2] == 2


def test_complete_group_multiple_comparisons_not_resolved_subset(context):
    root, plan, _cap = prospective(context, "OBSERVATIONAL")
    plan = replace(
        plan,
        condition_axis=(d("Condition", 0), d("Condition", 1), d("Condition", 2)),
        slots=plan.slots + (CaseSlot(d("Condition", 2)),),
        comparisons=(Comparison(0, 1), Comparison(0, 2)),
        execute_slots=(0, 1, 2),
    )
    authority, ledger, cie = invocation(context)
    study = context[2].open_study(authority, 0, ledger, root, plan)
    for slot in range(2):
        source = root.capture_case(study, slot, OUTCOMES[slot])
        context[2].admit_case(authority, 0, ledger, cie, study, source)
    report = context[2].compare(authority, 0, ledger, cie, study)
    assert report.status == "INCOMPLETE" and report.results == ()
    assert len(report.slots) == 3


@pytest.mark.parametrize("target", ["STUDY", "MEASUREMENT"])
def test_registry_insertion_failure_has_no_partial_owner(context, monkeypatch, target):
    from dgca_lite.cognition.causality.runtime import _CausalSystem

    original = _CausalSystem.register
    root, plan, origin_cap = prospective(context)
    authority, ledger, _cie = invocation(context)
    study = (
        None
        if target == "STUDY"
        else context[2].open_study(
            authority, 0, ledger, root, plan, origin_authority=origin_cap
        )
    )
    rce = None if study is None else context[2].open_rce(authority, 0, ledger, study)

    def faulty(system, token, role, record, domain):
        original(system, token, role, record, domain)
        if role == target:
            raise RuntimeError("post-insert fault")

    monkeypatch.setattr(_CausalSystem, "register", faulty)
    before = ledger.summary(authority)
    with pytest.raises(RuntimeError):
        if target == "STUDY":
            context[2].open_study(
                authority, 0, ledger, root, plan, origin_authority=origin_cap
            )
        else:
            root.controllers[-1].receipt(
                rce,
                0,
                OUTCOMES[0],
                target=MEASUREMENT.target,
                logical_slot=1,
                treatment_label_blind=True,
            )
    assert ledger.summary(authority) == before
    monkeypatch.undo()
    if target == "STUDY":
        assert context[2].open_study(
            authority, 0, ledger, root, plan, origin_authority=origin_cap
        )
    else:
        assert root.controllers[-1].receipt(
            rce,
            0,
            OUTCOMES[0],
            target=MEASUREMENT.target,
            logical_slot=1,
            treatment_label_blind=True,
        )


def test_close_wins_race_with_result_publication(context, monkeypatch):
    root, plan, authority, ledger, cie, study = start(context)
    rce = context[2].open_rce(authority, 0, ledger, study)
    context[2].admit_bundle(
        authority, 0, ledger, study, rce, execute_counter(root, plan, rce)
    )
    ready, proceed = Event(), Event()
    from dgca_lite.cognition.causality import results

    original = results.compute

    def blocked(operation, data):
        output = original(operation, data)
        if operation is CausalOperation.COMPARE_REPLAY:
            ready.set()
            assert proceed.wait(10)
        return output

    monkeypatch.setattr(results, "compute", blocked)
    failures = []

    def worker():
        try:
            context[2].compare(authority, 0, ledger, cie, study, rce=rce)
        except IngressAbort as failure:
            failures.append(failure)

    thread = Thread(target=worker)
    thread.start()
    assert ready.wait(10)
    context[2].invocations.begin_close(authority, 0)
    proceed.set()
    thread.join(10)
    assert not thread.is_alive() and len(failures) == 1
    assert context[2].registry_status().values[1:] == (0, 0)
    assert ledger.summary(authority).reserved == 0


def test_cie_closed_after_paid_work_prevents_publication(context):
    root, plan, authority, ledger, cie, study = start(context)
    rce = context[2].open_rce(authority, 0, ledger, study)
    context[2].admit_bundle(
        authority, 0, ledger, study, rce, execute_counter(root, plan, rce)
    )
    _, op, ordinal, data, key = context[2]._call(
        "comparison_input", authority, 0, ledger, study, rce
    )
    permit, frame, _, _ = context[2]._call(
        "prepare_compute", authority, 0, ledger, cie, study, op, ordinal, data, key
    )
    context[2].work.execute(permit, frame)
    context[2].cie.abort(cie)
    before = ledger.summary(authority)
    with pytest.raises(IngressAbort):
        context[2]._call("publish_comparison", authority, 0, ledger, study, rce)
    assert ledger.summary(authority) == before
    assert context[2].registry_status().values[2] == 0


def test_replay_measurement_missing_no_partial_result(context):
    root, plan, authority, ledger, cie, study = start(context)
    rce = context[2].open_rce(authority, 0, ledger, study)
    context[2].admit_bundle(
        authority,
        0,
        ledger,
        study,
        rce,
        execute_counter(root, plan, rce, status="FAILED"),
    )
    assert context[2].compare(authority, 0, ledger, cie, study, rce=rce) is None
    report = context[2].finish_study(authority, 0, ledger, study)
    assert report.status == "INCOMPLETE" and report.results == ()
    assert all(
        s.terminal_state == "FAILED" and s.classification == "UNRESOLVED"
        for s in report.slots
    )


def test_frontier_independent_of_outcome_and_remaining_budget(context):
    root, plan, authority, ledger, cie, study = start(
        context, "OBSERVATIONAL", attempts=2
    )
    frozen = work_frontier(plan)
    for slot, outcome in enumerate((OUTCOMES[2], OUTCOMES[0])):
        source = root.capture_case(study, slot, outcome)
        context[2].admit_case(authority, 0, ledger, cie, study, source)
    assert work_frontier(plan) == frozen
    report = context[2].compare(authority, 0, ledger, cie, study)
    assert report.status == "INCOMPLETE" and len(report.slots) == 2


@pytest.mark.parametrize(
    "issuer_kind", ["none", "descriptor", "read-adapter", "forged", "foreign"]
)
def test_cognition_holder_cannot_mint_trusted_domain_authority(context, issuer_kind):
    from dgca_lite.cognition.ingress import TrustedIngressIssuer

    actual = context[1]
    value = {
        "none": None,
        "descriptor": d("Issuer", "copied"),
        "read-adapter": actual.invocation_causes,
        "forged": object.__new__(TrustedIngressIssuer),
        "foreign": actual,
    }[issuer_kind]
    if issuer_kind == "foreign":
        value = globals()["context"]()[1]
    before = context[2].registry_status()
    with pytest.raises(IngressAbort):
        context[2].trusted_domain(value, DOMAIN, d("Environment", "A"), MEASUREMENT)
    assert context[2].registry_status() == before


def test_wep_issuance_fault_no_half_owner_or_charge(context, monkeypatch):
    from dgca_lite.cognition.invocation import _pinned_cie_parent

    root, _, authority, ledger, cie, study = start(context, "OBSERVATIONAL")
    case = root.capture_case(study, 0, OUTCOMES[0])
    before = ledger.summary(authority)
    with _pinned_cie_parent(context[2].invocations, authority) as (_, item, _):
        owner = item.work_owner
    monkeypatch.setattr("dgca_lite.cognition.effects._before_effect_publish", fail_hook)
    with pytest.raises(RuntimeError):
        context[2].admit_case(authority, 0, ledger, cie, study, case)
    assert ledger.summary(authority) == before
    with _pinned_cie_parent(context[2].invocations, authority) as (_, item, _):
        assert item.work_owner is owner
    monkeypatch.undo()
    assert (
        context[2].admit_case(authority, 0, ledger, cie, study, case).classification
        == "MATCH"
    )


def test_returned_case_not_private_live_record(context):
    root, _, authority, ledger, cie, study = start(context, "OBSERVATIONAL")
    source = root.capture_case(study, 0, OUTCOMES[0])
    report = context[2].admit_case(authority, 0, ledger, cie, study, source)
    object.__setattr__(report.outcome, "values", (99,))
    repeated = context[2].admit_case(authority, 0, ledger, cie, study, source)
    assert repeated.outcome == OUTCOMES[0]


def test_replay_receipt_cannot_rewrite_observed_outcome(context):
    root, plan, authority, ledger, _cie, study = start(context)
    rce = context[2].open_rce(authority, 0, ledger, study)
    execute_counter(root, plan, rce)
    with pytest.raises(IngressAbort):
        root.controllers[-1].receipt(
            rce,
            0,
            OUTCOMES[1],
            target=MEASUREMENT.target,
            logical_slot=1,
            treatment_label_blind=True,
        )


def test_controller_capabilities_cannot_be_substituted_for_each_other(context):
    root, plan, authority, ledger, cie, study = start(context, randomization=True)
    rce = context[2].open_rce(authority, 0, ledger, study)
    receipts = execute_counter(root, plan, rce)
    # Replace the isolation receipt with actual application authority. Similar
    # outcomes cannot make the physically distinct authority interchangeable.
    bad = (receipts[0], receipts[0]) + receipts[2:]
    with pytest.raises(IngressAbort):
        context[2].admit_bundle(authority, 0, ledger, study, rce, bad)
    context[2].admit_bundle(authority, 0, ledger, study, rce, tuple(reversed(receipts)))
    assert (
        context[2].compare(authority, 0, ledger, cie, study, rce=rce).outcome_relation
        == "DIFFERENT"
    )


def test_genuine_fda_cannot_open_study_or_pay_causal_work(context):
    from dgca_lite.cognition.causality.runtime import CausalityRuntime
    from dgca_lite.cognition.effects import _attach_causality

    # Use the existing genuine Core/L2 forecast harness, not a fabricated FDA.
    ns = __import__("runpy").run_path(
        str(Path(__file__).with_name("test_prediction.py"))
    )
    ctx = ns["context"]()
    prediction = ctx[2]
    policy = CausalityPolicy()
    _attach_causality(prediction.effects, prediction.work, policy)
    causal = CausalityRuntime(
        prediction.invocations,
        prediction.cie,
        prediction.work,
        prediction.effects,
        policy,
        prediction,
    )
    root, plan, cap = prospective((ctx[0], ctx[1], causal))
    authority, ledger, _cie, *_values, fda = ns["seal"](ctx, 1)
    before = ledger.summary(authority)
    with pytest.raises(IngressAbort):
        causal.open_study(fda, 0, ledger, root, plan, origin_authority=cap)
    assert ledger.summary(authority) == before
    study = causal.open_study(authority, 0, ledger, root, plan, origin_authority=cap)
    with pytest.raises(IngressAbort):
        causal.open_rce(fda, 0, ledger, study)
    causal.abort(authority, 0, ledger, study)


def test_public_policy_cannot_expand_private_authority_registry(context):
    object.__setattr__(context[2].policy, "max_domains", 16)
    for index in range(8):
        context[2].trusted_domain(
            context[1], d("Domain", index), d("Environment"), MEASUREMENT
        )
    before = context[2].registry_status()
    with pytest.raises(IngressAbort):
        context[2].trusted_domain(
            context[1], d("Domain", 8), d("Environment"), MEASUREMENT
        )
    assert context[2].registry_status() == before


def test_branch_and_receipt_completion_order_not_result_identity(context):
    root, plan, authority, ledger, cie, study = start(context, repetitions=2)
    results = []
    for repeat in range(2):
        rce = context[2].open_rce(authority, 0, ledger, study, repeat=repeat)
        receipts = execute_counter(root, plan, rce, reverse=bool(repeat))
        context[2].admit_bundle(
            authority, 0, ledger, study, rce, tuple(reversed(receipts))
        )
        results.append(context[2].compare(authority, 0, ledger, cie, study, rce=rce))
    assert canonical_identity_bytes(
        results[0].canonical_descriptor()
    ) == canonical_identity_bytes(results[1].canonical_descriptor())
    assert len(context[2].finish_study(authority, 0, ledger, study).results) == 1


def test_randomization_not_inferred_from_application(context):
    root, _, authority, ledger, cie, study = start(
        context, "INTERVENTIONAL", randomization=True
    )
    source = root.capture_case(study, 0, OUTCOMES[0])
    context[2].request_case(authority, 0, ledger, study, 0)
    application = root.controllers[0].receipt(study, 0)
    before = ledger.summary(authority)
    with pytest.raises(IngressAbort):
        context[2].admit_case(
            authority, 0, ledger, cie, study, source, application=application
        )
    assert ledger.summary(authority) == before


def test_learned_core_and_temporal_context_conserved(context):
    core, issuer, runtime = context
    issuer.process_core_event(SurfaceEvent.from_text("real external context"))
    before = engine_state(core)
    report, _, _ = replay(context)
    assert report.status == "COMPLETE"
    assert engine_state(core) == before
    assert runtime.registry_status().values[1:] == (0, 1)


def test_study_abort_invalidates_late_receipts_and_historical_views(context):
    root, plan, authority, ledger, _cie, study = start(context)
    rce = context[2].open_rce(authority, 0, ledger, study)
    receipts = execute_counter(root, plan, rce)
    report = context[2].abort(authority, 0, ledger, study)
    assert report.status == "ABORTED" and len(report.slots) == 2
    for value in (study, report.canonical_descriptor(), d("RCE", "copied")):
        with pytest.raises(IngressAbort):
            context[2].open_rce(authority, 0, ledger, value)
    with pytest.raises(IngressAbort):
        context[2].admit_bundle(authority, 0, ledger, study, rce, receipts)
    assert ledger.summary(authority).reserved == 0


def test_causal_dependency_union_survives_ordinary_derived_chain(context):
    from dgca_lite.cognition.reasoning.assertions import derived_key

    report, _, _ = replay(context)
    view = causal_result_view(report.results[0])
    source = reasoning_view(view).values[0]
    first = derived_key(
        ground("GroundAtom", "ordinary-conclusion"), (source,), source.scope
    )
    second = derived_key(
        ground("GroundAtom", "later-conclusion"), (first,), source.scope
    )
    assert first.basis is second.basis is AssertionBasis.DERIVED
    assert first.dependencies == second.dependencies == (view.causal_dependency_root,)
    assert first.scope == second.scope == source.scope


def test_rce_registry_rollback_revokes_reused_weak_handle_id(context, monkeypatch):
    from weakref import ref

    from dgca_lite.cognition.causality.replay import (
        ReplayComparisonEpoch,
        ReplayOriginAuthority,
    )
    from dgca_lite.cognition.causality.runtime import _CausalSystem

    _root, _plan, authority, ledger, _cie, study = start(context)
    publish = _CausalSystem.publish
    register = _CausalSystem.register
    captured = []
    dead = object.__new__(ReplayOriginAuthority)
    expired = ref(dead)
    del dead
    assert expired() is None

    def with_reused_index(
        system, current, item, core, operation, ordinal, payload, mutation, **kwargs
    ):
        if operation is CausalOperation.OPEN_RCE:
            # Deterministically model a freed handle address being reused by the
            # prospective RCE. No reliance on allocator luck or actual addresses.
            token = next(
                value
                for value in inspect.getclosurevars(mutation).nonlocals.values()
                if type(value) is ReplayComparisonEpoch
            )
            captured.append(token)
            current.domain.handle_ids.add(id(token))
            system.registry[id(token)] = (
                expired,
                system.runtime,
                "CAUSAL",
                "ORIGIN",
                None,
                current.domain,
            )
        return publish(
            system, current, item, core, operation, ordinal, payload, mutation, **kwargs
        )

    def fault(system, token, role, record, domain):
        register(system, token, role, record, domain)
        if role == "RCE":
            raise RuntimeError("registration fault after object-ID reuse")

    monkeypatch.setattr(_CausalSystem, "publish", with_reused_index)
    monkeypatch.setattr(_CausalSystem, "register", fault)
    before = ledger.summary(authority)
    with pytest.raises(RuntimeError):
        context[2].open_rce(authority, 0, ledger, study)
    assert ledger.summary(authority) == before
    with pytest.raises(IngressAbort):
        context[2]._call("comparison_input", authority, 0, ledger, study, captured[0])
    monkeypatch.undo()
    assert context[2].open_rce(authority, 0, ledger, study)


def test_operation_equality_spoof_cannot_promote_controller_role(context):
    from dgca_lite.cognition.causality.runtime import _root

    root, _, _authority, _ledger, _cie, _study = start(context)

    class Spoof(str):
        def __eq__(self, other):
            raise AssertionError("noncanonical operation equality executed")

    before = root.capture_origin(STATE)[0]
    with pytest.raises(IngressAbort):
        _root(root.controllers[0], Spoof("APPLICATION"), STATE)
    after = root.capture_origin(STATE)[0]
    assert after.occurrence_index == before.occurrence_index + 1


def test_domain_issuer_pinned_through_final_publication(context, monkeypatch):
    import gc
    from weakref import ref

    root, plan, authority, ledger, cie, study = start(context)
    rce = context[2].open_rce(authority, 0, ledger, study)
    context[2].admit_bundle(
        authority, 0, ledger, study, rce, execute_counter(root, plan, rce)
    )
    keeper, weak = [root], ref(root)
    del root
    calls = 0

    def drop_at_commit():
        nonlocal calls
        calls += 1
        if calls == 2:
            keeper.clear()
            gc.collect()
            assert weak() is not None

    monkeypatch.setattr(
        "dgca_lite.cognition.effects._before_effect_publish", drop_at_commit
    )
    result = context[2].compare(authority, 0, ledger, cie, study, rce=rce)
    assert result.result_class == "REPLAY_IDENTIFIED_TREATMENT_EFFECT"
    gc.collect()
    assert weak() is None
    assert result.canonical_descriptor()
    with pytest.raises(IngressAbort):
        context[2].finish_study(authority, 0, ledger, study)
    context[2].invocations.begin_close(authority, 0)
    assert ledger.summary(authority).reserved == 0


@pytest.mark.parametrize("seed", ["0", "1", "27", "123", "random"])
def test_causality_signature_independent_process(seed):
    script = f"import runpy; ns=runpy.run_path({str(Path(__file__).resolve())!r}); print(ns['signature']().hex())"
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"))

    def run(value):
        return subprocess.run(
            [sys.executable, "-B", "-c", script],
            env=dict(env, PYTHONHASHSEED=value),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    assert run(seed) == run("0")


def _isolated_test(function):
    @wraps(function)
    def isolated(**arguments):
        args = [f"{name}={value!r}" for name, value in arguments.items()]
        args.append("context=ns['context']()")
        if "monkeypatch" in inspect.signature(function).parameters:
            args.append("monkeypatch=patch")
        script = f"import runpy, pytest; ns=runpy.run_path({str(Path(__file__).resolve())!r}); patch=pytest.MonkeyPatch(); ns[{function.__name__!r}].__wrapped__({', '.join(args)}); patch.undo()"
        result = subprocess.run(
            [sys.executable, "-B", "-c", script],
            env=dict(
                os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src")
            ),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    isolated.__signature__ = inspect.signature(function).replace(
        parameters=tuple(
            p
            for n, p in inspect.signature(function).parameters.items()
            if n not in ("context", "monkeypatch")
        )
    )
    return isolated


for _name, _function in tuple(globals().items()):
    if (
        _name.startswith("test_")
        and "context" in inspect.signature(_function).parameters
    ):
        globals()[_name] = _isolated_test(_function)
