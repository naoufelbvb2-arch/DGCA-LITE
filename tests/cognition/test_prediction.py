"""Unit 8: genuine Core/L2 Prediction and authority/budget adversarial review."""

import copy
import hashlib
import inspect
import os
import pickle
import subprocess
import sys
from dataclasses import replace
from functools import wraps
from itertools import combinations
from pathlib import Path
from threading import Event, Thread

import pytest

from dgca_lite import CoreConfig, CoreEngine, SurfaceEvent
from dgca_lite.cognition.authority import IngressAbort
from dgca_lite.cognition.identity import AssertionSemanticKey, ScopeIdentity
from dgca_lite.cognition.ingress import create_trusted_ingress_boundary
from dgca_lite.cognition.invocation import InvocationLimits
from dgca_lite.cognition.prediction.adapters import (
    prediction_outcome_view,
    reasoning_view,
)
from dgca_lite.cognition.prediction.contracts import (
    PredictionOperation,
    contract,
    projection_targets,
)
from dgca_lite.cognition.prediction.evaluation import match, status_after
from dgca_lite.cognition.prediction.fda import ForecastDelegatedAuthority
from dgca_lite.cognition.prediction.projection import PredictionPolicy
from dgca_lite.cognition.prediction.runtime import create_prediction_runtime
from dgca_lite.cognition.prediction.targets import AtomicCarrier, BranchPattern, d
from dgca_lite.cognition.reasoning.fab import ground
from dgca_lite.cognition.serialization import canonical_identity_bytes
from dgca_lite.cognition.types import (
    AssertionBasis,
    BudgetSourceKind,
    CaptureState,
    DependencyKind,
    FailureCode,
    ForecastStatus,
    WorkEffectClass,
)
from dgca_lite.memory.session import retrieve_after_core_event, retrieve_internal
from dgca_lite.memory.types import SourceID
from dgca_lite.model import (
    Assembly,
    Cell,
    Synapse,
    SynapseScope,
    SynapseState,
    Territory,
)
from dgca_lite.persistence import engine_state

SCOPE = ScopeIdentity("FORMAL", d("source"), d("scope"))


def context(
    *,
    policy=None,
    budget=128,
    name="unit8",
    memory_config=None,
    effect_policy=None,
    theta_active=0.1,
    gamma_A=0.75,
    delta_A=0.25,
):
    config = CoreConfig(
        logical_capacity=300,
        E_max=1.0,
        local_radius=2.0,
        associative_radius=6.0,
        assembly_radius=2.0,
        K_min=3,
        K_max=6,
        default_synaptic_budget=32,
        theta_active=theta_active,
        theta_emit=max(0.2, theta_active),
        gamma_A=gamma_A,
        delta_A=delta_A,
    )
    core = CoreEngine(config)
    a, b = (SurfaceEvent.from_text(v) for v in ("a", "b"))
    origin = dict(core.surface.receptor_drive(core.surface.encode(a)))
    future = dict(core.surface.receptor_drive(core.surface.encode(b)))
    unused = sorted(set(range(100)) - set(origin) - set(future))
    choice = None
    for anchor in sorted(set(future) - set(origin)):
        for left, right in combinations(unused, 2):
            members = (anchor, left, right)
            if core.network.topology.diameter(members) > 2:
                continue
            for source in sorted(set(origin) & set(future)):
                if all(
                    2 < core.network.topology.distance(source, t) <= 6 for t in members
                ):
                    choice = source, members
                    break
            if choice:
                break
        if choice:
            break
    assert choice is not None
    source, members = choice
    for cid in sorted(set(origin) | set(future) | set(members)):
        core.network.seed_cell(Cell(cid, Territory.LANGUAGE, True, 0.0, 32))
    for left, right in combinations(members, 2):
        for start, end in ((left, right), (right, left)):
            core.network.seed_synapse(
                start,
                Synapse(end, 0.4, 1.0, SynapseState.CONSOLIDATED, SynapseScope.LOCAL),
            )
    for target in members[:2]:
        core.network.seed_synapse(
            source,
            Synapse(
                target, 1.0, 1.0, SynapseState.CONSOLIDATED, SynapseScope.ASSOCIATIVE
            ),
        )
    core.network.seed_assembly(Assembly(7, Territory.LANGUAGE, frozenset(members)))
    issuer = create_trusted_ingress_boundary(core, d(name), d("source"), capacity=256)
    runtime = create_prediction_runtime(
        issuer.invocation_causes,
        policy=PredictionPolicy(max_capture_synapses=2048)
        if policy is None
        else policy,
        invocation_limits=InvocationLimits(budget),
        l2_config=memory_config,
        effect_policy=effect_policy,
    )
    return core, issuer, runtime


def origin(context, *, cue=(), claims=()):
    _, issuer, runtime = context
    capability = issuer.authorize_given(
        ground("GroundAtom", "p"), SCOPE, d("occurrence", issuer.registry_status[1])
    )
    authority = runtime.invocations.admit(capability)
    ledger = runtime.invocations.ledger(authority)
    event, _ = issuer.process_core_event(SurfaceEvent.from_text("a"))
    cie = runtime.cie.open(authority, 0)
    projection, permit = runtime.project(
        authority,
        0,
        ledger,
        cie,
        receipt=event.receipt,
        internal_cue=cue,
        reasoning_claims=claims,
    )
    return authority, ledger, cie, projection, permit, event


def seal(context, horizon=2):
    _, _, runtime = context
    authority, ledger, cie, projection, permit, event = origin(context)
    target = next(t for t in projection.targets if t.kind == "BranchPattern")
    commitment, fda = runtime.seal(authority, 0, ledger, cie, permit, target, horizon)
    return authority, ledger, cie, projection, permit, event, target, commitment, fda


def step(context, text="b", *, boundary=False):
    return context[1].process_core_event(
        SurfaceEvent.from_text(text), boundary=boundary
    )


def test_genuine_root_source_not_exact_origin_branch(context):
    core, _, runtime = context
    *_, event, target, commitment, _fda = seal(context, 1)
    origin_result = retrieve_after_core_event(core, event.receipt)
    branch = next(
        b for b in origin_result.branches if b.branch_id.target_assembly_id == 7
    )
    future, outcomes = step(context)
    result = retrieve_after_core_event(core, future.receipt)
    source = next(s for s in result.sources if s.source_id == SourceID.assembly(7))
    reconstructed = next(b for b in result.branches if b.branch_id == branch.branch_id)
    assert set(target.values[1]) & set(source.root_authorized_witnesses)
    assert not set(target.values[2]) <= set(source.reconstructed_cells)
    assert set(target.values[2]) <= set(reconstructed.reconstructed_target_cells)
    assert outcomes[0].status is ForecastStatus.WINDOW_ELAPSED_WITHOUT_MATCH
    assert outcomes[0].coverage[0].values[2] is CaptureState.CAPTURED
    assert outcomes[0].commitment.identity == commitment.identity
    assert runtime.forecast_registry_status()[0] == 0


@pytest.mark.parametrize(
    "sources,witnesses,expected",
    [
        (((("ASM", 7), (3,), (3, 4, 9)),), (3,), True),
        (((("ASM", 7), (), (3, 4, 9)),), (), False),
        (((("ASM", 7), (3, 9), (3, 9)),), (3, 9), False),
        (((("ASM", 8), (3,), (3, 4, 9)),), (3,), False),
        (((("ATOM", 5), (3,), (3, 4, 9)),), (3,), False),
        ((), (3, 4, 9), False),
        (((("ASM", 7), (3,), (3, 4)), (("ASM", 8), (9,), (9,))), (3, 9), False),
    ],
)
def test_exact_source_lane_no_unions(sources, witnesses, expected):
    target = BranchPattern(
        7, (3, 9), (3, 4, 9), d("PredictionSourceIdentity", "ATOM", 5)
    )
    assert match(target.canonical_descriptor(), sources, witnesses) is expected


@pytest.mark.parametrize(
    "witnesses,expected", [((), False), ((3,), True), ((4, 9), False)]
)
def test_atomic_only_root_witness(witnesses, expected):
    target = AtomicCarrier(
        3, d("PredictionSourceIdentity", "ATOM", 5)
    ).canonical_descriptor()
    assert match(target, ((("ASM", 7), (), (3, 4, 9)),), witnesses) is expected


@pytest.mark.parametrize(
    "states,matched,expected",
    [
        ((CaptureState.CAPTURED,), False, ForecastStatus.PENDING),
        ((CaptureState.OBSERVATION_GAP,), False, ForecastStatus.PENDING),
        (
            (CaptureState.CAPTURED, CaptureState.PROVEN_EMPTY),
            False,
            ForecastStatus.WINDOW_ELAPSED_WITHOUT_MATCH,
        ),
        (
            (CaptureState.CAPTURED, CaptureState.OBSERVATION_GAP),
            False,
            ForecastStatus.INCONCLUSIVE_OBSERVATION_GAP,
        ),
        (
            (CaptureState.OBSERVATION_GAP, CaptureState.CAPTURED),
            True,
            ForecastStatus.MATCHED,
        ),
        ((CaptureState.CAPTURED,), True, ForecastStatus.MATCHED),
    ],
)
def test_status_algebra(states, matched, expected):
    assert status_after(2, states, matched) is expected


def test_nonmatch_advances_and_final_closes(context):
    _, _, runtime = context
    *_, fda = seal(context, 2)
    _, first = step(context)
    assert first[0].status is ForecastStatus.PENDING
    assert len(first[0].coverage) == 1
    _, second = step(context, "a")
    assert second[0].status is ForecastStatus.MATCHED
    assert len(second[0].coverage) == 2
    assert first[0].coverage == second[0].coverage[:1]
    with pytest.raises(IngressAbort):
        runtime.outcome(fda)


def test_gap_advances_not_empty(context, monkeypatch):
    from dgca_lite.cognition import effects

    _, _, runtime = context
    *_, fda = seal(context, 2)
    monkeypatch.setattr(
        effects,
        "_before_forecast_capture",
        lambda: (_ for _ in ()).throw(RuntimeError("capture fault")),
    )
    _, first = step(context)
    assert first[0].status is ForecastStatus.PENDING
    assert first[0].coverage[0].values[2] is CaptureState.OBSERVATION_GAP
    _, second = step(context)
    assert second[0].status is ForecastStatus.INCONCLUSIVE_OBSERVATION_GAP
    assert second[0].coverage[:1] == first[0].coverage
    assert runtime.forecast_registry_status()[0] == 0
    with pytest.raises(IngressAbort):
        runtime.cancel(fda)


def test_last_offset_match_wins_after_gap(context, monkeypatch):
    from dgca_lite.cognition import effects

    core, _, _runtime = context
    *_, target, commitment, _fda = seal(context, 2)
    monkeypatch.setattr(
        effects,
        "_before_forecast_capture",
        lambda: (_ for _ in ()).throw(RuntimeError("capture fault")),
    )
    _, first = step(context)
    assert first[0].coverage[0].values[2] is CaptureState.OBSERVATION_GAP
    monkeypatch.undo()
    # Ordinary trusted surface input directly witnesses every sealed Cell.
    text = next(
        v
        for v in ("ab", "abc", "hello", "abcdefghijklmnopqrstuvwxyz")
        if set(target.values[2])
        <= set(
            dict(
                core.surface.receptor_drive(
                    core.surface.encode(SurfaceEvent.from_text(v))
                )
            )
        )
    )
    _, outcomes = step(context, text)
    assert outcomes[0].status is ForecastStatus.MATCHED
    assert len(outcomes[0].coverage) == 2
    assert outcomes[0].commitment == commitment


def test_supported_target_missing_source_is_not_stale(context):
    _, _, _runtime = context
    seal(context, 1)
    _, outcomes = step(context, "a")
    assert outcomes[0].status is ForecastStatus.WINDOW_ELAPSED_WITHOUT_MATCH


def test_seal_idempotent_and_parent_closed_cannot_recover_authority(context):
    _, _, runtime = context
    auth, ledger, cie, _, permit, _, target, commitment, fda = seal(context)
    before = ledger.summary(auth)
    second, token = runtime.seal(auth, 0, ledger, cie, permit, target, 2)
    assert second == commitment and token is fda
    assert ledger.summary(auth) == before
    runtime.invocations.begin_close(auth, 0)
    ledger.retire_unused(auth, 1)
    assert runtime.invocations.finalize_close(auth, 1)
    historical, recovered = runtime.seal(auth, 0, ledger, cie, permit, target, 2)
    assert historical == commitment and recovered is None
    _, outcomes = step(context)
    assert outcomes[0].status is ForecastStatus.PENDING


def test_seal_publication_failure_rolls_back_every_positive_component(
    context, monkeypatch
):
    from dgca_lite.cognition import effects

    core, _, runtime = context
    auth, ledger, cie, projection, permit, _ = origin(context)
    target = next(t for t in projection.targets if t.kind == "BranchPattern")
    before = (
        ledger.summary(auth),
        runtime.forecast_registry_status(),
        runtime.effects.registry_status(auth),
        engine_state(core),
    )
    monkeypatch.setattr(
        effects,
        "_before_effect_publish",
        lambda: (_ for _ in ()).throw(RuntimeError("seal fault")),
    )
    with pytest.raises(RuntimeError, match="seal fault"):
        runtime.seal(auth, 0, ledger, cie, permit, target, 2)
    assert before == (
        ledger.summary(auth),
        runtime.forecast_registry_status(),
        runtime.effects.registry_status(auth),
        engine_state(core),
    )
    monkeypatch.undo()
    runtime.seal(auth, 0, ledger, cie, permit, target, 2)
    assert runtime.forecast_registry_status()[0] == 1


@pytest.mark.parametrize("horizon", [True, False, 0, -1, 9, 1.0])
def test_horizon_fail_closed_without_charge(context, horizon):
    _, _, runtime = context
    auth, ledger, cie, projection, permit, _ = origin(context)
    before = ledger.summary(auth)
    with pytest.raises(IngressAbort):
        runtime.seal(auth, 0, ledger, cie, permit, projection.targets[0], horizon)
    assert ledger.summary(auth) == before
    assert runtime.forecast_registry_status()[0] == 0


@pytest.mark.parametrize("mixed", ["cue"])
def test_whole_mixed_origin_never_purifies(context, mixed):
    core, _, runtime = context
    cue = ((5, 1.0),) if mixed == "cue" else ()
    claims = (
        ()
        if mixed == "cue"
        else (
            AssertionSemanticKey(
                ground("GroundAtom", "p"),
                AssertionBasis.DERIVED
                if mixed == "derived"
                else AssertionBasis.HYPOTHETICAL,
                SCOPE,
            ),
        )
    )
    auth, ledger, cie, projection, permit, _ = origin(context, cue=cue, claims=claims)
    assert projection.origin_class == "MIXED"
    before = ledger.summary(auth), engine_state(core)
    with pytest.raises(IngressAbort):
        runtime.seal(auth, 0, ledger, cie, permit, projection.targets[0], 1)
    assert before == (ledger.summary(auth), engine_state(core))


@pytest.mark.parametrize("basis", ["DERIVED", "HYPOTHETICAL"])
def test_copied_basis_claim_is_not_current_cie_reasoning_input(context, basis):
    _, _, runtime = context
    auth, ledger, cie, _, _, event = origin(context)
    claim = AssertionSemanticKey(
        ground("GroundAtom", "Q"), AssertionBasis[basis], SCOPE
    )
    before = ledger.summary(auth)
    with pytest.raises(IngressAbort) as error:
        runtime.project(
            auth, 0, ledger, cie, receipt=event.receipt, reasoning_claims=(claim,)
        )
    assert error.value.code is FailureCode.INVALID_FORMAL_AUTHORITY
    assert ledger.summary(auth) == before


def test_genuine_derived_arena_input_remains_mixed_not_sealable(context):
    from dgca_lite.cognition.reasoning.schemas import ReasoningOperation
    from dgca_lite.cognition.work import _reasoning_source_input

    _, issuer, runtime = context
    auth, ledger, cie, _, _, event = origin(context)
    p, q = (ground("GroundAtom", v) for v in ("P", "Q"))
    caps = tuple(
        issuer.authorize_given(c, SCOPE, d("occurrence", i))
        for i, c in enumerate((p, ground("GroundConditional", p, q)), 100)
    )
    reasoning = runtime.reasoning
    snapshot = runtime.cie.snapshot(cie)
    data = _reasoning_source_input(runtime.work, auth, 0, cie, ledger, snapshot, caps)
    permit, output, charge = reasoning._work(
        auth,
        0,
        cie,
        ledger,
        snapshot,
        ReasoningOperation.SEED,
        data,
        sources=caps,
        publication_charge=True,
    )
    snapshot, _ = reasoning._publish(
        auth, 0, cie, ledger, snapshot, permit, output, charge
    )
    data = d(
        "ReasoningInput",
        tuple(e.canonical_descriptor() for e in snapshot.entries),
        0,
        "EXISTS_INCOMPATIBILITY",
    )
    discovery, frontier, _ = reasoning._work(
        auth, 0, cie, ledger, snapshot, ReasoningOperation.DISCOVER, data
    )
    data = d(
        "ReasoningInput",
        tuple(e.canonical_descriptor() for e in snapshot.entries),
        0,
        frontier,
    )
    permit, output, charge = reasoning._work(
        auth,
        0,
        cie,
        ledger,
        snapshot,
        ReasoningOperation.EVALUATE,
        data,
        discovery=discovery,
        publication_charge=True,
    )
    snapshot, _ = reasoning._publish(
        auth, 0, cie, ledger, snapshot, permit, output, charge
    )
    derived = next(
        e.payload.values[0]
        for e in snapshot.entries
        if e.category == "ASSERTION"
        and e.payload.values[0].basis is AssertionBasis.DERIVED
    )
    projection, permit = runtime.project(
        auth, 0, ledger, cie, receipt=event.receipt, reasoning_claims=(derived,)
    )
    assert projection.origin_class == "MIXED"
    assert derived in projection.input_provenance.values[5]
    with pytest.raises(IngressAbort):
        runtime.seal(auth, 0, ledger, cie, permit, projection.targets[0], 1)


def test_fda_cannot_open_cie_admit_invocation_or_use_general_budget(context):
    _, issuer, runtime = context
    auth, ledger, _, _, _, _, _, _, fda = seal(context)
    before = ledger.summary(auth)
    for call in (
        lambda: runtime.cie.open(fda, 0),
        lambda: runtime.invocations.admit(fda),
        lambda: ledger.reserve(fda, 0, 1, d("fake")),
        lambda: issuer.authorize_core_observation(fda, SCOPE),
    ):
        with pytest.raises(IngressAbort):
            call()
    assert ledger.summary(auth) == before
    assert not hasattr(fda, "process_core_event")
    assert not hasattr(fda, "seal_forecast")
    assert not hasattr(fda, "start_causal_study")


def test_internal_projection_remains_internal(context):
    _, _, runtime = context
    auth, ledger, cie, _, _, _ = origin(context)
    projection, permit = runtime.project(auth, 0, ledger, cie, internal_cue=((5, 1.0),))
    assert projection.origin_class == "INTERNAL_ONLY"
    with pytest.raises(IngressAbort):
        runtime.seal(auth, 0, ledger, cie, permit, projection.targets[0], 1)


@pytest.mark.parametrize(
    "form", ["direct", "new", "copy", "deepcopy", "pickle", "descriptor", "commitment"]
)
def test_fda_unforgeable_and_no_serialization(context, form):
    _, _, runtime = context
    *_, commitment, fda = seal(context)
    before = runtime.forecast_registry_status()
    if form == "direct":
        with pytest.raises(TypeError):
            ForecastDelegatedAuthority()
    elif form in ("copy", "deepcopy", "pickle"):
        function = {
            "copy": copy.copy,
            "deepcopy": copy.deepcopy,
            "pickle": pickle.dumps,
        }[form]
        with pytest.raises(TypeError):
            function(fda)
    else:
        fake = (
            object.__new__(ForecastDelegatedAuthority)
            if form == "new"
            else (commitment if form == "commitment" else commitment.identity)
        )
        with pytest.raises(IngressAbort):
            runtime.outcome(fake)
    with pytest.raises(TypeError):
        canonical_identity_bytes(d("leak", fda))
    assert runtime.forecast_registry_status() == before


def test_cross_runtime_fda_rejected(context):
    *_, fda = seal(context)
    other = globals()["context"](name="other")
    with pytest.raises(IngressAbort):
        other[2].outcome(fda)
    with pytest.raises(IngressAbort):
        other[2].cancel(fda)
    assert context[2].forecast_registry_status()[0] == 1
    assert other[2].forecast_registry_status()[0] == 0


def test_cancel_terminal_and_capacity_released(context):
    _, _, runtime = context
    *_, fda = seal(context)
    result = runtime.cancel(fda)
    assert result.status is ForecastStatus.CANCELLED
    assert runtime.forecast_registry_status()[0] == 0
    assert step(context)[1] == ()
    with pytest.raises(IngressAbort):
        runtime.cancel(fda)


def test_boundary_first_prevents_window_admission(context):
    _, _, runtime = context
    *_, fda = seal(context)
    _, result = step(context, boundary=True)
    assert result[0].status is ForecastStatus.BOUNDARY_TERMINATED
    assert result[0].coverage == ()
    assert runtime.forecast_registry_status()[0] == 0
    with pytest.raises(IngressAbort):
        runtime.outcome(fda)


def test_issuer_invalidation_retires_and_cannot_aba(context):
    _, issuer, runtime = context
    *_, fda = seal(context)
    issuer.invalidate()
    assert runtime.forecast_registry_status()[0] == 0
    with pytest.raises(IngressAbort):
        runtime.outcome(fda)
    issuer.invalidate()
    assert issuer.registry_status[0] == 2


def test_target_guard_removed_assembly_does_not_capture(context, monkeypatch):
    from dgca_lite.cognition import effects

    core, _, runtime = context
    seal(context)
    from dgca_lite.model import TickTransaction

    transaction = TickTransaction(base_version=core.network.version)
    transaction.assembly_deletes.add(7)
    core.network.commit(transaction)
    charges = []
    original = effects._prepare_forecast_consumption
    monkeypatch.setattr(
        effects,
        "_prepare_forecast_consumption",
        lambda *a: charges.append(a[1:]) or original(*a),
    )
    _, results = step(context)
    assert results[0].status is ForecastStatus.TARGET_STALE
    assert charges == []
    assert runtime.forecast_registry_status()[0] == 0


@pytest.mark.parametrize("boundary", [False, True])
def test_failed_core_tick_is_not_an_occurrence(context, monkeypatch, boundary):
    core, _, runtime = context
    *_, fda = seal(context)
    before = engine_state(core), runtime.outcome(fda)
    assert core.temporal.events
    monkeypatch.setattr(
        type(core.network),
        "commit",
        lambda *a: (_ for _ in ()).throw(RuntimeError("Core fault")),
    )
    with pytest.raises(RuntimeError):
        step(context, boundary=boundary)
    assert before == (engine_state(core), runtime.outcome(fda))


def test_capture_eval_use_exact_escrow_only_and_no_general_fallback(
    context, monkeypatch
):
    from dgca_lite.cognition import effects

    _, _, _runtime = context
    auth, ledger, _, _, _, _, _, _, _fda = seal(context, 2)
    before = ledger.summary(auth)
    charges = []
    original = effects._prepare_forecast_consumption

    def record(*args):
        charge, index = original(*args)
        charges.append(charge)
        return charge, index

    monkeypatch.setattr(effects, "_prepare_forecast_consumption", record)
    step(context)
    step(context)
    assert ledger.summary(auth) == before
    assert len(charges) == 4
    assert all(c.source_kind is BudgetSourceKind.FORECAST_ESCROW for c in charges)
    assert len({canonical_identity_bytes(c.unit_identity) for c in charges}) == 4
    assert [c.work_class.values for c in charges] == [
        ("CAPTURE", 1),
        ("EVALUATION", 1),
        ("CAPTURE", 2),
        ("EVALUATION", 2),
    ]


def test_eval_publication_fault_no_partial_result_no_free_recomputation(
    context, monkeypatch
):
    from dgca_lite.cognition import effects
    from dgca_lite.cognition.prediction import evaluation

    _, _, runtime = context
    *_, fda = seal(context, 2)
    before = runtime.outcome(fda)
    matches = []
    original = evaluation.match
    monkeypatch.setattr(
        evaluation, "match", lambda *a: matches.append(True) or original(*a)
    )
    monkeypatch.setattr(
        effects,
        "_before_effect_publish",
        lambda: (_ for _ in ()).throw(RuntimeError("publication fault")),
    )
    _, results = step(context)
    assert results[0].kind == "ForecastProcessingFailure"
    assert runtime.outcome(fda) == before
    assert len(matches) == 1
    monkeypatch.setattr(effects, "_before_effect_publish", lambda: None)
    attached = runtime.effects.retry_forecast_publication(fda)
    assert len(attached.coverage) == 1
    assert len(matches) == 1
    assert runtime.effects.retry_forecast_publication(fda) == attached


def test_cie_abort_retires_unsealed_projection_authority(context):
    _, _, runtime = context
    auth, ledger, cie, projection, permit, _ = origin(context)
    runtime.cie.abort(cie)
    with pytest.raises(IngressAbort):
        runtime.seal(auth, 0, ledger, cie, permit, projection.targets[0], 1)
    assert runtime.forecast_registry_status()[0] == 0


@pytest.mark.parametrize(
    "kind",
    ["root_descriptor", "receipt_descriptor", "internal_result", "commitment", "fda"],
)
def test_no_internal_or_descriptor_observation_ingress(context, kind):
    core, issuer, runtime = context
    *_, event, _target, commitment, fda = seal(context)
    result = retrieve_after_core_event(core, event.receipt)
    fake = {
        "root_descriptor": result.root,
        "receipt_descriptor": d("Receipt", event.receipt.root_id),
        "internal_result": retrieve_internal(core, {5: 1.0}),
        "commitment": commitment,
        "fda": fda,
    }[kind]
    with pytest.raises(IngressAbort):
        issuer.authorize_core_observation(fake, SCOPE)
    assert runtime.forecast_registry_status()[0] == 1


def test_copied_project_fields_never_seal(context):
    _, _, runtime = context
    auth, ledger, cie, projection, _permit, _ = origin(context)
    before = ledger.summary(auth)
    for fake in (
        projection,
        projection.canonical_descriptor(),
        object.__new__(
            __import__(
                "dgca_lite.cognition.work", fromlist=["WorkExecutionPermit"]
            ).WorkExecutionPermit
        ),
    ):
        with pytest.raises(IngressAbort):
            runtime.seal(auth, 0, ledger, cie, fake, projection.targets[0], 1)
    assert ledger.summary(auth) == before


def test_genuine_receipt_cannot_call_private_future_delivery_outside_trusted_event(
    context,
):
    from dgca_lite.cognition.effects import _deliver_prediction_event

    _, _, runtime = context
    *_, event, _target, _commitment, fda = seal(context)
    with pytest.raises(IngressAbort):
        _deliver_prediction_event(runtime.effects, runtime.work, event.receipt, False)
    assert runtime.outcome(fda).coverage == ()


def test_prediction_adapter_retains_modal_root_and_never_negative_assertion(context):
    _, _, _runtime = context
    seal(context, 1)
    _, results = step(context)
    view = prediction_outcome_view(results[0])
    source = reasoning_view(view)
    ask = source.values[0]
    assert ask.basis is AssertionBasis.PREDICTION_VIEW
    assert ask.content.descriptor.kind == "PredictionOutcomeStatement"
    assert ask.dependencies[0].kind is DependencyKind.PREDICTION
    assert ask.scope == results[0].commitment.scope
    from dgca_lite.cognition.prediction.adapters import semantic_identity

    assert semantic_identity(view) == ask.content.descriptor.values[0]
    for wrong in ("EXTERNAL_OBSERVATION", "FORMAL_GIVEN", "CAUSES"):
        with pytest.raises(ValueError):
            replace(view, prediction_class=wrong)


def test_global_capacity_across_invocations_no_eviction(context):
    ctx = globals()["context"](
        name="capacity",
        policy=PredictionPolicy(max_live_forecasts=1, max_capture_synapses=2048),
    )
    _, issuer, runtime = ctx
    *_, event, _target, _commitment, fda = seal(ctx)
    cap = issuer.authorize_given(
        ground("GroundAtom", "Q"), SCOPE, d("occurrence", "other")
    )
    auth = runtime.invocations.admit(cap)
    ledger = runtime.invocations.ledger(auth)
    cie = runtime.cie.open(auth, 0)
    view, permit = runtime.project(auth, 0, ledger, cie, receipt=event.receipt)
    before = ledger.summary(auth), runtime.outcome(fda)
    with pytest.raises(IngressAbort) as error:
        runtime.seal(auth, 0, ledger, cie, permit, view.targets[0], 2)
    assert error.value.code is FailureCode.CAPACITY_ABORT
    assert before == (ledger.summary(auth), runtime.outcome(fda))
    assert runtime.forecast_registry_status() == (1, 1)


def test_insufficient_complete_escrow_no_partial_seal(context):
    ctx = globals()["context"](name="insufficient", budget=3)
    _, _, runtime = ctx
    auth, ledger, cie, view, permit, _ = origin(ctx)
    before = ledger.summary(auth)
    with pytest.raises(IngressAbort) as error:
        runtime.seal(auth, 0, ledger, cie, permit, view.targets[0], 2)
    assert error.value.code is FailureCode.BUDGET_ABORT
    assert before == ledger.summary(auth)
    assert runtime.forecast_registry_status()[0] == 0


def test_prospective_effect_history_capacity_aborts_whole_seal(context):
    from dgca_lite.cognition.effect import EffectPolicy

    ctx = globals()["context"](
        name="history_bound",
        effect_policy=EffectPolicy(
            max_commits_per_owner=1, max_descriptor_bytes=262144
        ),
    )
    _, _, runtime = ctx
    auth, ledger, cie, projection, permit, _ = origin(ctx)
    before = ledger.summary(auth)
    with pytest.raises(IngressAbort) as error:
        runtime.seal(auth, 0, ledger, cie, permit, projection.targets[0], 2)
    assert error.value.code is FailureCode.CAPACITY_ABORT
    assert ledger.summary(auth) == before
    assert runtime.forecast_registry_status()[0] == 0
    _, fda = runtime.seal(auth, 0, ledger, cie, permit, projection.targets[0], 1)
    assert step(ctx)[1][0].status is ForecastStatus.WINDOW_ELAPSED_WITHOUT_MATCH
    with pytest.raises(IngressAbort):
        runtime.outcome(fda)


def test_duplicate_delivery_zero_new_units_and_gap_never_rewritten(
    context, monkeypatch
):
    from dgca_lite.cognition import effects

    _, _, runtime = context
    seal(context, 2)
    original = effects._deliver_prediction_event
    charges = []
    consume = effects._prepare_forecast_consumption
    # Count the actual future allocations, not the prospective sealing proof.
    monkeypatch.setattr(
        effects,
        "_prepare_forecast_consumption",
        lambda *a: charges.append(a[1:]) or consume(*a),
    )
    monkeypatch.setattr(
        effects,
        "_before_forecast_capture",
        lambda: (_ for _ in ()).throw(RuntimeError("gap")),
    )

    def duplicate(*args):
        first = original(*args)
        monkeypatch.setattr(effects, "_before_forecast_capture", lambda: None)
        second = original(*args)
        assert first == second
        return second

    monkeypatch.setattr(effects, "_deliver_prediction_event", duplicate)
    _, outcomes = step(context)
    assert outcomes[0].coverage[0].values[2] is CaptureState.OBSERVATION_GAP
    assert len(outcomes[0].coverage) == 1
    assert charges == [(1, "CAPTURE"), (1, "EVALUATION")]
    assert runtime.forecast_registry_status()[0] == 1


def test_same_surface_new_genuine_occurrences_not_deduplicated(context, monkeypatch):
    from dgca_lite.cognition import effects

    seal(context, 2)
    monkeypatch.setattr(
        effects,
        "_before_forecast_capture",
        lambda: (_ for _ in ()).throw(RuntimeError("gap")),
    )
    first = step(context, "b")[1][0]
    last = step(context, "b")[1][0]
    assert first.coverage[0].values[1] != last.coverage[1].values[1]
    assert last.status is ForecastStatus.INCONCLUSIVE_OBSERVATION_GAP


def test_same_core_second_trusted_issuer_cannot_skip_forecast_window(context):
    core, _, runtime = context
    seal(context, 1)
    # The existing Unit-2 boundary already forbids another active domain for
    # this exact Core. Unit 8 must preserve, not weaken, that firewall.
    with pytest.raises(IngressAbort):
        create_trusted_ingress_boundary(core, d("other-issuer"), d("source"))
    _, outcomes = step(context)
    assert len(outcomes) == 1
    assert len(outcomes[0].coverage) == 1
    assert runtime.forecast_registry_status()[0] == 0
    with pytest.raises(IngressAbort), context[1].core_transition():
        pass


def test_same_core_second_forecast_registry_cannot_bypass_global_bound(context):
    _, issuer, runtime = context
    seal(context)
    with pytest.raises(IngressAbort):
        create_prediction_runtime(issuer.invocation_causes)
    assert runtime.forecast_registry_status()[0] == 1


def test_capability_free_private_read_facet_copy_expiry_rejected(context):
    from dgca_lite.cognition.ingress import (
        _pinned_prediction_core,
        _validate_prediction_reader,
    )

    _, issuer, _ = context
    with _pinned_prediction_core(issuer.invocation_causes) as reader:
        forged = copy.copy(reader)
        with pytest.raises(IngressAbort):
            _validate_prediction_reader(forged)
    with pytest.raises(IngressAbort):
        _validate_prediction_reader(reader)


def test_seal_linearizes_before_begin_close_and_fda_continues(context, monkeypatch):
    from dgca_lite.cognition import effects

    _, _, runtime = context
    auth, ledger, cie, view, permit, _ = origin(context)
    started = Event()
    closed = Event()
    threads = []

    def close():
        started.set()
        runtime.invocations.begin_close(auth, 0)
        closed.set()

    def hook():
        thread = Thread(target=close)
        threads.append(thread)
        thread.start()
        assert started.wait(5)
        assert not closed.is_set()

    monkeypatch.setattr(effects, "_before_effect_publish", hook)
    commitment, fda = runtime.seal(auth, 0, ledger, cie, permit, view.targets[0], 2)
    threads[0].join(5)
    assert closed.is_set()
    monkeypatch.undo()
    assert runtime.outcome(fda).commitment == commitment
    assert step(context)[1][0].status is ForecastStatus.PENDING


def test_begin_close_first_prevents_seal(context):
    _, _, runtime = context
    auth, ledger, cie, view, permit, _ = origin(context)
    runtime.invocations.begin_close(auth, 0)
    before = ledger.summary(auth)
    with pytest.raises(IngressAbort):
        runtime.seal(auth, 0, ledger, cie, permit, view.targets[0], 2)
    assert before == ledger.summary(auth)
    assert runtime.forecast_registry_status()[0] == 0


def test_evaluation_then_cancel_is_linearizable(context, monkeypatch):
    from dgca_lite.cognition import effects

    _, _, runtime = context
    *_, fda = seal(context, 2)
    started = Event()
    result = []
    threads = []

    def cancel():
        started.set()
        result.append(runtime.cancel(fda))

    def hook():
        thread = Thread(target=cancel)
        threads.append(thread)
        thread.start()
        assert started.wait(5)
        assert not result

    monkeypatch.setattr(effects, "_before_effect_publish", hook)
    _, evaluations = step(context)
    threads[0].join(5)
    assert evaluations[0].status is ForecastStatus.PENDING
    assert result[0].status is ForecastStatus.CANCELLED
    assert result[0].coverage == evaluations[0].coverage


@pytest.mark.parametrize("boundary", [True, False])
def test_core_event_order_not_thread_completion_orders_offsets(
    context, monkeypatch, boundary
):
    from dgca_lite.cognition import effects

    seal(context, 2)
    started = Event()
    second = []
    errors = []
    threads = []

    def concurrent():
        started.set()
        try:
            second.append(step(context, boundary=boundary))
        except BaseException as error:  # noqa: BLE001 -- forward worker failures to main test
            errors.append(error)

    def hook():
        # Only the first capture starts another Core event. The second thread
        # cannot commit a root or admit its offset while this Core gate is held.
        monkeypatch.setattr(effects, "_before_forecast_capture", lambda: None)
        thread = Thread(target=concurrent)
        threads.append(thread)
        thread.start()
        assert started.wait(5)
        assert not second

    monkeypatch.setattr(effects, "_before_forecast_capture", hook)
    _, first = step(context)
    threads[0].join(5)
    assert not threads[0].is_alive() and not errors
    assert first[0].status is ForecastStatus.PENDING
    final = second[0][1][0]
    assert final.coverage[:1] == first[0].coverage
    if boundary:
        assert final.status is ForecastStatus.BOUNDARY_TERMINATED
        assert len(final.coverage) == 1
    else:
        assert len(final.coverage) == 2
        assert (
            final.coverage[1].values[1].values[1].values[2]
            > final.coverage[0].values[1].values[1].values[2]
        )


@pytest.mark.parametrize("status", ["miss", "match", "gap"])
def test_no_prediction_learning_feedback_complete_core_equality(
    context, monkeypatch, status
):
    from dgca_lite.cognition import effects

    control = globals()["context"](name="control")
    seal(context, 1)
    step(control, "a")
    assert engine_state(control[0]) == engine_state(context[0])
    if status == "gap":
        monkeypatch.setattr(
            effects,
            "_before_forecast_capture",
            lambda: (_ for _ in ()).throw(RuntimeError("gap")),
        )
    text = "abcdefghijklmnopqrstuvwxyz" if status == "match" else "b"
    _, result = step(context, text)
    step(control, text)
    assert (
        result[0].status
        is {
            "miss": ForecastStatus.WINDOW_ELAPSED_WITHOUT_MATCH,
            "match": ForecastStatus.MATCHED,
            "gap": ForecastStatus.INCONCLUSIVE_OBSERVATION_GAP,
        }[status]
    )
    assert engine_state(control[0]) == engine_state(context[0])


def test_terminal_state_clears_private_cognition_and_retires_only_unused(
    context, monkeypatch
):
    from dgca_lite.cognition import effects

    _, _, runtime = context
    records = []

    def inspect_seal():
        record = inspect.currentframe().f_back.f_locals.get("record")
        if record is not None:
            records.append(record)

    monkeypatch.setattr(effects, "_before_effect_publish", inspect_seal)
    auth, ledger, _, _, _, _, _, _, fda = seal(context, 4)
    record = records[0]
    pool = record.pool
    monkeypatch.undo()
    step(context)
    before = ledger.summary(auth)
    runtime.cancel(fda)
    assert ledger.summary(auth) == before
    states = [u.state for u in pool.budget.index[0]]
    assert states.count("CONSUMED") == 2
    assert states.count("RETIRED") == 6
    assert not any(s in ("AVAILABLE", "RESERVED") for s in states)
    assert (
        record.commitment
        is record.coverage
        is record.pending
        is record.pool
        is record.fda
        is record.work_owner
        is None
    )
    assert record.evaluation_owner.index == {}


def test_colliding_effect_digests_never_merge_forecasts(context, monkeypatch):
    from dgca_lite.cognition import effects
    from dgca_lite.cognition.effect import EffectCommitID

    _, _, runtime = context
    auth, ledger, cie, projection, permit, _ = origin(context)
    records = []

    def inspect_seal():
        records.append(inspect.currentframe().f_back.f_locals["record"])

    monkeypatch.setattr(
        EffectCommitID, "index_digest", property(lambda self: "collision")
    )
    monkeypatch.setattr(effects, "_before_effect_publish", inspect_seal)
    first, first_fda = runtime.seal(
        auth, 0, ledger, cie, permit, projection.targets[0], 1
    )
    second, second_fda = runtime.seal(
        auth, 0, ledger, cie, permit, projection.targets[0], 2
    )
    assert first.identity != second.identity and first_fda is not second_fda
    assert len(records[0].owner.index) == 2
    views = tuple(records[0].owner.index.values())
    assert views[0].commit_id.index_digest == views[1].commit_id.index_digest
    assert views[0].commit_id.canonical_bytes != views[1].commit_id.canonical_bytes
    monkeypatch.setattr(effects, "_before_effect_publish", lambda: None)
    results = step(context)[1]
    assert {r.status for r in results} == {
        ForecastStatus.PENDING,
        ForecastStatus.WINDOW_ELAPSED_WITHOUT_MATCH,
    }
    assert len({canonical_identity_bytes(r.commitment.identity) for r in results}) == 2


def test_terminal_cleanup_fault_cannot_revive_authority_or_allocate(
    context, monkeypatch
):
    from dgca_lite.cognition import effects, work

    _, _, runtime = context
    records = []

    def inspect_seal():
        records.append(inspect.currentframe().f_back.f_locals["record"])

    monkeypatch.setattr(effects, "_before_effect_publish", inspect_seal)
    *_, fda = seal(context, 4)
    record = records[0]
    pool = record.pool
    monkeypatch.setattr(effects, "_before_effect_publish", lambda: None)
    cleanup = work._retire_forecast_work
    calls = []

    def fail_once(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise MemoryError("negative cleanup fault")
        return cleanup(*args, **kwargs)

    monkeypatch.setattr(work, "_retire_forecast_work", fail_once)
    result = step(context, "abcdefghijklmnopqrstuvwxyz")[1][0]
    assert result.kind == "ForecastProcessingFailure"
    assert record.status is ForecastStatus.MATCHED
    before = pool.budget.index
    for action in (
        runtime.outcome,
        runtime.cancel,
        runtime.effects.retry_forecast_publication,
    ):
        with pytest.raises(IngressAbort) as error:
            action(fda)
        assert error.value.code is FailureCode.OPERATIONAL_EFFECT_AUTHORITY_STALE
    final = step(context, boundary=True)[1][0]
    assert final.status is ForecastStatus.MATCHED and len(final.coverage) == 1
    assert sum(u.state == "CONSUMED" for u in before[0]) == 2
    assert sum(u.state == "CONSUMED" for u in pool.budget.index[0]) == 2
    assert runtime.forecast_registry_status()[0] == 0


def test_explicit_empty_trusted_capture_not_missing(context):
    ctx = globals()["context"](
        name="empty", theta_active=0.8, gamma_A=0.01, delta_A=0.1
    )
    core, _, runtime = ctx
    core.network.cells[5] = replace(core.network.cells[5], activation=1.0)
    seal(ctx, 4)
    outcomes = []
    for _ in range(4):
        outcomes.extend(step(ctx, "b")[1])
        if runtime.forecast_registry_status()[0] == 0:
            break
    assert any(
        e.values[2] is CaptureState.PROVEN_EMPTY for o in outcomes for e in o.coverage
    )
    assert outcomes[-1].status is ForecastStatus.WINDOW_ELAPSED_WITHOUT_MATCH


@pytest.mark.parametrize(
    "field",
    [
        "max_live_forecasts",
        "max_horizon",
        "max_targets",
        "max_capture_cells",
        "max_capture_assemblies",
        "max_capture_synapses",
    ],
)
def test_policy_bounds_reject_bool_and_nonfinite(field):
    for invalid in (True, 0, -1, float("inf"), float("nan")):
        with pytest.raises(ValueError):
            PredictionPolicy(**{field: invalid})


def test_projection_duplicate_or_noncanonical_target_order_rejected(context):
    *_, view, _permit, _event = origin(context)
    with pytest.raises(ValueError, match="unique canonical"):
        replace(view, targets=(view.targets[0], view.targets[0]))


def test_oversized_cue_rejected_before_poison_member(context):
    _, _, runtime = context
    auth, ledger, cie, _, _, _ = origin(context)
    before = ledger.summary(auth)
    with pytest.raises(IngressAbort) as error:
        runtime.project(auth, 0, ledger, cie, internal_cue=(object(),) * 65)
    assert error.value.code is FailureCode.CAPACITY_ABORT
    assert ledger.summary(auth) == before


def test_prediction_view_consumed_by_genuine_reasoning_without_promotion(context):
    _, issuer, runtime = context
    seal(context, 1)
    _, results = step(context)
    view = prediction_outcome_view(results[0])
    cap = issuer.authorize_given(
        ground("GroundAtom", "Q"), SCOPE, d("occurrence", "next")
    )
    auth = runtime.invocations.admit(cap)
    result = runtime.reasoning.run(
        auth, 0, runtime.invocations.ledger(auth), (cap,), prediction_views=(view,)
    )
    assert result.status == "FIXED_POINT"
    asks = result.assertions
    assert any(
        a.basis is AssertionBasis.PREDICTION_VIEW
        and a.dependencies[0].kind is DependencyKind.PREDICTION
        for a in asks
    )
    assert not any(a.content.descriptor.kind == "FormalNegation" for a in asks)


def test_prediction_dependency_union_and_complete_reasoning_capacity(context):
    from dgca_lite.cognition.reasoning.assertions import derived_key

    _, issuer, runtime = context
    seal(context, 1)
    view = prediction_outcome_view(step(context)[1][0])
    modal = reasoning_view(view).values[0]
    conclusion = ground("GroundAtom", "modal_conclusion")
    conditional = issuer.authorize_given(
        ground("GroundConditional", modal.content, conclusion),
        modal.scope,
        d("occurrence", "modal_rule"),
    )
    auth = runtime.invocations.admit(conditional)
    result = runtime.reasoning.run(
        auth,
        0,
        runtime.invocations.ledger(auth),
        (conditional,),
        branch=1,
        prediction_views=(view,),
    )
    # Unit-10 normalization retains the entire view once and exact local proof
    # references, admitting this lawful chain without changing any bound.
    assert result.status == "FIXED_POINT"
    assert any(
        a.basis is AssertionBasis.DERIVED
        and a.content == conclusion
        and a.dependencies == modal.dependencies
        for a in result.assertions
    )
    formal = issuer.formal_reasoning.accept(conditional).semantic_key
    derived = derived_key(conclusion, (formal, modal), modal.scope)
    assert derived.basis is AssertionBasis.DERIVED
    assert derived.dependencies == (view.prediction_dependency_root,)
    assumption = issuer.authorize_assumption(
        formal.content, modal.scope, d("occurrence", "modal_assumption")
    )
    assumption_key = issuer.formal_reasoning.accept(assumption).semantic_key
    with_assumption = derived_key(conclusion, (assumption_key, modal), modal.scope)
    assert set(with_assumption.dependencies) == {
        view.prediction_dependency_root,
        *assumption_key.dependencies,
    }


@pytest.mark.parametrize(
    "field", ["max_snapshot_cells", "max_snapshot_assemblies", "max_snapshot_synapses"]
)
def test_unbounded_forecast_acquisition_rejected_before_runtime_attach(context, field):
    from dgca_lite.memory.config import MemoryConfig

    _, issuer, _ = context
    values = {
        "max_snapshot_cells": 128,
        "max_snapshot_assemblies": 32,
        "max_snapshot_synapses": 512,
    }
    values[field] = None
    with pytest.raises(ValueError, match="finite prospective"):
        create_prediction_runtime(
            issuer.invocation_causes,
            invocation_limits=InvocationLimits(128),
            l2_config=MemoryConfig(**values),
        )


def test_wrong_l2_policy_rejected_before_field_inspection(context):
    class Poison:
        def __getattribute__(self, name):
            raise AssertionError("policy fields inspected before exact type")

    with pytest.raises(TypeError, match="exact frozen L2"):
        create_prediction_runtime(
            context[1].invocation_causes,
            invocation_limits=InvocationLimits(128),
            l2_config=Poison(),
        )


def test_full_default_horizon_gap_coverage_completes(context, monkeypatch):
    from dgca_lite.cognition import effects

    stable = globals()["context"](name="full_horizon", gamma_A=1.0)
    core, _, runtime = stable
    for cid, cell in tuple(core.network.cells.items()):
        core.network.cells[cid] = replace(cell, activation=1.0)
    atom = next(
        c
        for c in range(100)
        if c not in core.network.cells and 2 < core.network.topology.distance(5, c) <= 6
    )
    core.network.seed_cell(Cell(atom, Territory.LANGUAGE, True, 1.0, 32))
    core.network.seed_synapse(
        5, Synapse(atom, 1.0, 1.0, SynapseState.CONSOLIDATED, SynapseScope.ASSOCIATIVE)
    )
    auth, ledger, cie, projection, permit, _ = origin(stable)
    target = next(
        t
        for t in projection.targets
        if t.kind == "AtomicCarrier" and t.values[0] == atom
    )
    commitment, fda = runtime.seal(
        auth, 0, ledger, cie, permit, target, runtime.policy.max_horizon
    )
    monkeypatch.setattr(
        effects,
        "_before_forecast_capture",
        lambda: (_ for _ in ()).throw(RuntimeError("missing")),
    )
    for offset in range(1, commitment.horizon + 1):
        outcome = step(stable)[1][0]
        assert len(outcome.coverage) == offset
    assert outcome.status is ForecastStatus.INCONCLUSIVE_OBSERVATION_GAP
    assert runtime.forecast_registry_status() == (0, runtime.policy.max_live_forecasts)
    with pytest.raises(IngressAbort):
        runtime.outcome(fda)


@pytest.mark.parametrize("field", ["anchor_carriers", "pattern_cells"])
def test_seal_target_outer_bound_before_poison_or_charge(context, field):
    _, _, runtime = context
    auth, ledger, cie, _, permit, _ = origin(context)
    target = d("BranchPattern", 7, (3,), (3,), d("PredictionSourceIdentity", "ATOM", 5))
    args = list(target.values)
    args[1 if field == "anchor_carriers" else 2] = (object(),) * 257
    object.__setattr__(target, "values", tuple(args))
    before = ledger.summary(auth)
    with pytest.raises(IngressAbort) as error:
        runtime.seal(auth, 0, ledger, cie, permit, target, 1)
    assert error.value.code is FailureCode.INVALID_INPUT
    assert "outer bound" in str(error.value.__cause__)
    assert ledger.summary(auth) == before


def test_closed_future_lane_rejects_duplicate_identity_and_oversized_outer():
    target = BranchPattern(
        7, (3,), (3, 4), d("PredictionSourceIdentity", "ATOM", 5)
    ).canonical_descriptor()
    with pytest.raises(ValueError, match="duplicate future"):
        match(target, ((("ASM", 7), (3,), (3, 4)),) * 2, (3,))
    with pytest.raises(ValueError, match="outer bound"):
        match(target, (object(),) * 641, ())
    with pytest.raises(ValueError, match="outer bound"):
        match(target, ((("ASM", 7), (object(),) * 513, ()),), ())


@pytest.mark.parametrize(
    "raw",
    [
        (("UNKNOWN", 3, ("ATOM", 5)),),
        (("ATOM", 3, ("ATOM", 5), (3,), (3,)),),
        (("BRANCH", 7, ("ATOM", 5), (object(),) * 257, (3,)),),
    ],
)
def test_closed_projection_target_rows_reject_unknown_or_oversized(raw):
    with pytest.raises(ValueError):
        projection_targets(raw)


@pytest.mark.parametrize("field", ["anchor_carriers", "pattern_cells"])
def test_target_outer_bound_before_poison(field):
    args = {
        "target_assembly_id": 7,
        "anchor_carriers": (3,),
        "pattern_cells": (3,),
        "source_identity": d("PredictionSourceIdentity", "ATOM", 5),
    }
    args[field] = (object(),) * 257
    with pytest.raises(ValueError, match="outer bound"):
        BranchPattern(**args)


@pytest.mark.parametrize("value", [True, -1, 1.0, "3"])
def test_cell_identity_exact_type(value):
    with pytest.raises(ValueError):
        AtomicCarrier(value, d("PredictionSourceIdentity", "ATOM", 5))


@pytest.mark.parametrize(
    "cells", [(3, 3), (9, 3), (3, True), (float("nan"),), (float("inf"),)]
)
def test_target_unique_typed_ordering(cells):
    with pytest.raises(ValueError):
        BranchPattern(7, (3,), cells, d("PredictionSourceIdentity", "ATOM", 5))


def test_target_discovery_preserves_source_specificity():
    rows = (
        ("BRANCH", 7, ("ATOM", 5), (3, 9), (3, 4, 9)),
        ("BRANCH", 7, ("ATOM", 6), (3, 9), (3, 4, 9)),
        ("ATOM", 3, ("ATOM", 5)),
        ("ATOM", 20, ("ATOM", 5)),
    )
    targets = projection_targets(rows)
    assert len(targets) == 3
    assert sum(t.kind == "BranchPattern" for t in targets) == 2
    assert targets == projection_targets(tuple(reversed(rows)))
    assert len({canonical_identity_bytes(t) for t in targets}) == 3


@pytest.mark.parametrize("operation", list(PredictionOperation))
def test_compiled_operation_budget_effect_contract(operation):
    value = contract(
        operation,
        "CAPTURE" if operation is PredictionOperation.CAPTURE else "EVALUATION",
    )
    assert value.resource_envelope.charge_units == 1
    assert value.effect_class is (
        WorkEffectClass.PURE_COMPUTE
        if operation in (PredictionOperation.PROJECT, PredictionOperation.CAPTURE)
        else WorkEffectClass.OPERATIONAL_EFFECT
    )


def signature():
    ctx = context()
    *_, commitment, _fda = seal(ctx, 2)
    first = step(ctx)[1][0]
    last = step(ctx)[1][0]
    image = canonical_identity_bytes(
        d(
            "Unit8PredictionSignature",
            commitment.canonical_descriptor(),
            first.canonical_descriptor(),
            last.canonical_descriptor(),
            prediction_outcome_view(last).canonical_descriptor(),
        )
    )
    return image


@pytest.mark.parametrize("seed", ["0", "1", "27", "123", "random"])
def test_prediction_signature_independent_process(seed):
    script = f"import runpy; ns=runpy.run_path({str(Path(__file__).resolve())!r}); print(ns['signature']().hex())"
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"))
    output = subprocess.run(
        [sys.executable, "-B", "-c", script],
        env=dict(env, PYTHONHASHSEED=seed),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    expected = subprocess.run(
        [sys.executable, "-B", "-c", script],
        env=dict(env, PYTHONHASHSEED="0"),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert (
        hashlib.sha256(bytes.fromhex(output)).digest()
        == hashlib.sha256(bytes.fromhex(expected)).digest()
    )


def _isolated_test(function):
    @wraps(function)
    def isolated(**arguments):
        args = []
        for name, value in arguments.items():
            if type(value) in (str, int, bool, float):
                args.append(f"{name}={value!r}")
            else:
                raise TypeError("closed subprocess parameter")
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
