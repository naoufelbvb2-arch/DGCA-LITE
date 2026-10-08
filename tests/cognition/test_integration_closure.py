"""Unit-10 normative same-runtime modal-composition regression probes.

These tests intentionally require actual charged/publication-path derivations,
not truthiness of a returned CAPACITY_ABORT result or pure derived_key helpers.
No resource envelope is enlarged and no modal provenance is truncated.
"""

import copy
import hashlib
import inspect
import json
import os
import runpy
import subprocess
import sys
from dataclasses import replace
from functools import wraps
from pathlib import Path

import pytest

from dgca_lite import CoreConfig, CoreEngine, SurfaceEvent
from dgca_lite.cognition.authority import IngressAbort
from dgca_lite.cognition.causality.adapters import (
    causal_result_view,
)
from dgca_lite.cognition.causality.adapters import (
    reasoning_view as causal_assertion,
)
from dgca_lite.cognition.causality.runtime import create_causality_runtime
from dgca_lite.cognition.identity import ScopeIdentity
from dgca_lite.cognition.ingress import create_trusted_ingress_boundary
from dgca_lite.cognition.invocation import InvocationLimits
from dgca_lite.cognition.prediction.adapters import (
    prediction_outcome_view,
)
from dgca_lite.cognition.prediction.adapters import (
    reasoning_view as prediction_assertion,
)
from dgca_lite.cognition.reasoning.fab import d, ground
from dgca_lite.cognition.reasoning.runtime import ReasoningRuntime
from dgca_lite.cognition.reasoning.schemas import ReasoningPolicy
from dgca_lite.cognition.serialization import canonical_identity_bytes
from dgca_lite.cognition.types import AssertionBasis, ForecastStatus
from dgca_lite.model import Cell, Synapse, SynapseScope, SynapseState, Territory
from dgca_lite.persistence import engine_state


def integrated_context(name, *, cie_policy=None):
    """One actual highest-level runtime; two Cells and one associative edge."""
    core = CoreEngine(
        CoreConfig(
            logical_capacity=300,
            receptor_fanout=1,
            E_max=1.0,
            associative_radius=6.0,
            default_synaptic_budget=32,
        )
    )
    origin = SurfaceEvent.from_text("a")

    def receptor(event):
        return next(iter(dict(core.surface.receptor_drive(core.surface.encode(event)))))

    source = receptor(origin)
    future = next(
        SurfaceEvent.from_text(str(i))
        for i in range(100)
        if 2
        < core.network.topology.distance(
            source, receptor(SurfaceEvent.from_text(str(i)))
        )
        <= 6
    )
    target = receptor(future)
    for cid in (source, target):
        core.network.seed_cell(Cell(cid, Territory.LANGUAGE, True, 0.0, 32))
    core.network.seed_synapse(
        source,
        Synapse(target, 1.0, 1.0, SynapseState.CONSOLIDATED, SynapseScope.ASSOCIATIVE),
    )
    issuer = create_trusted_ingress_boundary(core, d(name), d("source"), capacity=256)
    runtime = create_causality_runtime(
        issuer.invocation_causes,
        invocation_limits=InvocationLimits(256),
        cie_policy=cie_policy,
    )
    assert runtime.invocations is runtime.prediction.invocations
    assert runtime.cie is runtime.reasoning.cie is runtime.prediction.cie
    assert runtime.work is runtime.reasoning.work is runtime.prediction.work
    assert runtime.effects is runtime.reasoning.effects is runtime.prediction.effects
    scope = ScopeIdentity("FORMAL", d("source"), d("scope"))
    given = issuer.authorize_given(ground("GroundAtom", "P"), scope, d("occ", 0))
    authority = runtime.invocations.admit(given)
    ledger = runtime.invocations.ledger(authority)
    return (core, issuer, runtime), authority, ledger, origin, future


def require_actual_modal_derivation(
    ctx,
    authority,
    ledger,
    view,
    adapter,
    monkeypatch,
    *,
    rule_occurrence=None,
    follow_on=False,
):
    core, issuer, runtime = ctx
    modal = adapter(view).values[0]
    conclusion = ground("GroundAtom", "Q")
    rule = issuer.authorize_given(
        ground("GroundConditional", modal.content, conclusion),
        modal.scope,
        d("occ", 1) if rule_occurrence is None else rule_occurrence,
    )
    rules = (rule,)
    if follow_on:
        rules += (
            issuer.authorize_given(
                ground("GroundConditional", conclusion, ground("GroundAtom", "R")),
                modal.scope,
                d("occ", "modal-follow-on"),
            ),
        )
    measured = {
        "view_bytes": len(canonical_identity_bytes(view.canonical_descriptor())),
        "publications": {},
    }
    original = ReasoningRuntime._publish

    def inspect_complete_stage(self, *args, **kwargs):
        # args[6] is the genuine paid worker output passed to the effect gate.
        output = args[6]
        from dgca_lite.cognition.reasoning.runtime import publication_from_output

        measured["publications"][output.values[0]] = len(
            canonical_identity_bytes(
                publication_from_output(output), ReasoningPolicy().value_limits
            )
        )
        assert measured["publications"][output.values[0]] <= 262144
        published = original(self, *args, **kwargs)
        assert len(published[0].canonical_bytes) <= 262144
        return published

    monkeypatch.setattr(ReasoningRuntime, "_publish", inspect_complete_stage)
    before = engine_state(core)
    basis = modal.basis
    options = {
        "prediction_views"
        if basis is AssertionBasis.PREDICTION_VIEW
        else "causal_views": (view,)
    }
    result = runtime.reasoning.run(authority, 0, ledger, rules, branch=1, **options)
    assert engine_state(core) == before
    assert result.status == "FIXED_POINT", (result.status, measured)
    derived = tuple(a for a in result.assertions if a.basis is AssertionBasis.DERIVED)
    assert any(
        a.content == conclusion and a.dependencies == modal.dependencies
        for a in derived
    )
    if follow_on:
        assert any(
            a.content == ground("GroundAtom", "R")
            and a.dependencies == modal.dependencies
            for a in derived
        )
    category = basis.value
    modal_entries = tuple(e for e in result.snapshot.entries if e.category == category)
    assert len(modal_entries) == 1
    assert modal_entries[0].payload == view.canonical_descriptor()
    from dgca_lite.cognition.reasoning.modal import (
        assertion,
        source_input,
        validate_supports,
    )

    assert assertion(category, modal_entries[0].payload)[0] == modal
    assert len(validate_supports(result.snapshot.entries, result.snapshot.binding)) == 1
    assert modal_entries[0].identity.kind == "ModalArenaRef"
    assert (
        sum(e.payload.kind == "ModalSourceSupport" for e in result.snapshot.entries)
        == 1
    )
    measured["snapshot_bytes"] = len(result.snapshot.canonical_bytes)
    measured["signature"] = hashlib.sha256(
        canonical_identity_bytes(result.canonical_descriptor())
    ).hexdigest()  # Verification only; never a cognitive/source identity.
    print(json.dumps(measured, sort_keys=True))
    # Same occurrence replay is local, deterministic, and adds no source/root.
    from dgca_lite.cognition.reasoning.runtime import _seed

    replay = _seed(
        result.snapshot.entries,
        (source_input(view),),
        result.snapshot.binding,
        ReasoningPolicy(),
    )
    assert replay == ()
    check_reference_attacks(result.snapshot, view)
    for data in (
        modal_entries[0].identity,
        copy.deepcopy(modal_entries[0]),
        view.canonical_descriptor(),
        modal,
        result.canonical_descriptor(),
    ):
        before_budget = ledger.summary(authority)
        for consumer in (
            runtime.invocations.admit,
            issuer.formal_reasoning.accept,
            issuer.observations.accept,
            issuer.formal_constraints.accept,
        ):
            with pytest.raises((IngressAbort, TypeError, ValueError)):
                consumer(data)
        with pytest.raises(IngressAbort):
            runtime.cie.open(data, 0)
        for consumer in (
            lambda data=data: runtime.work.execute(data, data),
            lambda data=data: runtime.prediction.outcome(data),
            lambda data=data: runtime.prediction.seal(
                data, 0, ledger, data, data, data, 1
            ),
            lambda data=data: runtime.open_study(
                data, 0, ledger, data, data, origin_authority=data
            ),
            lambda data=data: runtime.open_rce(authority, 0, ledger, data),
            lambda data=data: runtime.effects.authorize_charge_and_commit(
                authority, 0, ledger, data, data, cie=data, work_permit=data
            ),
        ):
            with pytest.raises((IngressAbort, TypeError, ValueError)):
                consumer()
        assert ledger.summary(authority) == before_budget
    return result


def check_reference_attacks(snapshot, view):
    from dgca_lite.cognition.reasoning.modal import validate_supports

    entries = snapshot.entries
    modal = next(
        e for e in entries if e.category in ("PREDICTION_VIEW", "CAUSAL_RESULT_VIEW")
    )
    support = next(e for e in entries if e.payload.kind == "ModalSourceSupport")
    assertion = next(e for e in entries if e.identity.kind == "AssertionArenaRef")
    from dgca_lite.cognition.reasoning.assertions import semantic_records

    proofs = [e for e in entries if e.identity.kind == "ReasoningProofArenaRef"]
    for proof in proofs:
        for identity in (
            d(
                "ReasoningProofArenaRef",
                b"foreign",
                proof.category,
                proof.identity.values[2],
            ),
            d("ReasoningProofArenaRef", proof.identity.values[0], proof.category, True),
            d(
                "ReasoningProofArenaRef",
                proof.identity.values[0],
                "ASSERTION",
                proof.identity.values[2],
            ),
        ):
            with pytest.raises((ValueError, TypeError)):
                semantic_records(
                    tuple(
                        replace(e, identity=identity) if e is proof else e
                        for e in entries
                    ),
                    ReasoningPolicy(),
                    snapshot.binding,
                )
    ref = modal.identity
    for invalid in (
        d("ModalArenaRef", b"foreign CIE", ref.values[1], ref.values[2]),
        d("ModalArenaRef", ref.values[0], ref.values[1], True),
        d("ModalArenaRef", ref.values[0], ref.values[1], 127),
        d("ModalArenaRef", ref.values[0], "ASSERTION", ref.values[2]),
    ):
        with pytest.raises((ValueError, TypeError)):
            validate_supports(
                tuple(
                    replace(e, identity=invalid) if e is modal else e for e in entries
                ),
                snapshot.binding,
            )
    for removed in (modal, support, assertion):
        with pytest.raises((ValueError, TypeError)):
            validate_supports(
                tuple(e for e in entries if e is not removed), snapshot.binding
            )
    for changed in (
        replace(
            modal,
            category="CAUSAL_RESULT_VIEW"
            if modal.category == "PREDICTION_VIEW"
            else "PREDICTION_VIEW",
        ),
        replace(modal, payload=d("WrongView")),
        replace(
            support,
            payload=d(
                "ModalSourceSupport", assertion.identity, ref, d("ForgedOccurrence")
            ),
        ),
    ):
        with pytest.raises((ValueError, TypeError)):
            validate_supports(
                tuple(
                    changed
                    if e is (modal if changed.category != "SOURCE_SUPPORT" else support)
                    else e
                    for e in entries
                ),
                snapshot.binding,
            )
    if modal.category == "PREDICTION_VIEW":
        other = replace(
            view, outcome_status=ForecastStatus.WINDOW_ELAPSED_WITHOUT_MATCH
        )
    else:
        other = replace(
            view,
            result_descriptor=replace(
                view.result, domain=d("OtherDomain")
            ).canonical_descriptor(),
            causal_dependency_root=__import__(
                "dgca_lite.cognition.causality.adapters", fromlist=["dependency"]
            ).dependency(replace(view.result, domain=d("OtherDomain"))),
        )
    with pytest.raises((ValueError, TypeError)):
        validate_supports(
            tuple(
                replace(e, payload=other.canonical_descriptor()) if e is modal else e
                for e in entries
            ),
            snapshot.binding,
        )
    # Copies are historical DATA, requiring the same exact complete snapshot.
    assert copy.deepcopy(modal) == modal
    with pytest.raises(ValueError):
        validate_supports((copy.copy(modal),), snapshot.binding)
    for form in (ref, d("ReasoningAssertionReference", "AssertionArenaRef", 0)):
        with pytest.raises((ValueError, TypeError)):
            ground("GroundConditional", form, ground("GroundAtom", "Forged"))
    # A copied source-identity marker cannot collide with its factored role.
    if modal.category == "CAUSAL_RESULT_VIEW":
        from dgca_lite.cognition.causality.adapters import semantic_identity

        assert semantic_identity(view.result) != semantic_identity(
            replace(view.result, domain=d("CRCIDomain"))
        )


def test_minimal_atomic_prediction_actual_modal_derivation(monkeypatch):
    ctx, authority, ledger, origin, future = integrated_context("u10-prediction")
    _core, issuer, runtime = ctx
    trusted, _ = issuer.process_core_event(origin)
    cie = runtime.cie.open(authority, 0)
    projection, permit = runtime.prediction.project(
        authority, 0, ledger, cie, receipt=trusted.receipt
    )
    assert len(projection.targets) == 1
    assert projection.targets[0].kind == "AtomicCarrier"
    _commitment, _fda = runtime.prediction.seal(
        authority, 0, ledger, cie, permit, projection.targets[0], 1
    )
    _future_event, outcomes = issuer.process_core_event(future)
    assert len(outcomes) == 1 and outcomes[0].status is ForecastStatus.MATCHED
    runtime.cie.abort(cie)
    view = prediction_outcome_view(outcomes[0])
    require_actual_modal_derivation(
        ctx, authority, ledger, view, prediction_assertion, monkeypatch
    )


def test_genuine_rict_e_actual_modal_derivation(monkeypatch):
    ctx, authority, ledger, _origin, _future = integrated_context("u10-causality")
    runtime = ctx[2]
    # Reuse the frozen Unit-9 TEST-ONLY complete counter/fork harness.
    harness = runpy.run_path(str(Path(__file__).with_name("test_causality.py")))
    root, plan, origin_capability = harness["prospective"](ctx)
    cie = runtime.cie.open(authority, 0)
    study = runtime.open_study(
        authority, 0, ledger, root, plan, origin_authority=origin_capability
    )
    rce = runtime.open_rce(authority, 0, ledger, study)
    receipts = harness["execute_counter"](root, plan, rce)
    runtime.admit_bundle(authority, 0, ledger, study, rce, receipts)
    result = runtime.compare(authority, 0, ledger, cie, study, rce=rce)
    assert result.result_class == "REPLAY_IDENTIFIED_TREATMENT_EFFECT"
    assert runtime.finish_study(authority, 0, ledger, study).status == "COMPLETE"
    runtime.cie.abort(cie)
    require_actual_modal_derivation(
        ctx,
        authority,
        ledger,
        causal_result_view(result),
        causal_assertion,
        monkeypatch,
    )


def test_complete_import_capacity_abort_has_no_partial_modal_group(monkeypatch):
    from dgca_lite.cognition.arena import CIEPolicy

    ctx, authority, ledger, origin, future = integrated_context(
        "u10-small", cie_policy=CIEPolicy(max_snapshot_bytes=32768)
    )
    core, issuer, runtime = ctx
    trusted, _ = issuer.process_core_event(origin)
    cie = runtime.cie.open(authority, 0)
    projection, permit = runtime.prediction.project(
        authority, 0, ledger, cie, receipt=trusted.receipt
    )
    runtime.prediction.seal(authority, 0, ledger, cie, permit, projection.targets[0], 1)
    _, outcomes = issuer.process_core_event(future)
    runtime.cie.abort(cie)
    view = prediction_outcome_view(outcomes[0])
    before = engine_state(core)
    result = runtime.reasoning.run(authority, 0, ledger, (), prediction_views=(view,))
    assert result.status == "CAPACITY_ABORT"
    assert not result.snapshot.entries
    assert engine_state(core) == before


def test_canonical_modal_group_allocation_independent_of_completion(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    from dgca_lite.cognition.reasoning.modal import source_input, validate_supports
    from dgca_lite.cognition.reasoning.runtime import _seed

    ctx, authority, ledger, origin, future = integrated_context("u10-order")
    _, issuer, runtime = ctx
    trusted, _ = issuer.process_core_event(origin)
    forecasts = []
    for _ in range(2):
        cie = runtime.cie.open(authority, 0)
        projection, permit = runtime.prediction.project(
            authority, 0, ledger, cie, receipt=trusted.receipt
        )
        _, fda = runtime.prediction.seal(
            authority, 0, ledger, cie, permit, projection.targets[0], 1
        )
        forecasts.append(fda)
        runtime.cie.abort(cie)
    _, outcomes = issuer.process_core_event(future)
    views = tuple(prediction_outcome_view(outcome) for outcome in outcomes)
    assert len(views) == 2
    assert views[0].commitment_identity != views[1].commitment_identity
    cie = runtime.cie.open(authority, 0)
    snapshot = runtime.cie.snapshot(cie)
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = [pool.submit(source_input, view) for view in views]
        forward = tuple(t.result() for t in tasks)
        reverse = tuple(t.result() for t in reversed(tasks))
    a = _seed((), forward, snapshot.binding, ReasoningPolicy())
    b = _seed((), reverse, snapshot.binding, ReasoningPolicy())
    assert a == b
    assert len(validate_supports(a, snapshot.binding)) == 2
    assert _seed(a, forward, snapshot.binding, ReasoningPolicy()) == ()
    assert sum(e.category == "PREDICTION_VIEW" for e in a) == 2
    runtime.cie.abort(cie)


def test_shared_three_capability_chain_budget_and_conservation(monkeypatch):
    ctx, authority, ledger, origin, future = integrated_context("u10-shared")
    core, issuer, runtime = ctx
    scope = ScopeIdentity("FORMAL", d("source"), d("scope"))
    p, q = (ground("GroundAtom", x) for x in ("P", "Q"))
    given = issuer.authorize_given(p, scope, d("occ", 0))
    rule = issuer.authorize_given(ground("GroundConditional", p, q), scope, d("occ", 2))
    before = engine_state(core)
    cie = runtime.cie.open(authority, 0)
    from dgca_lite.cognition.reasoning.schemas import ReasoningOperation
    from dgca_lite.cognition.work import _reasoning_source_input

    snapshot = runtime.cie.snapshot(cie)
    data = _reasoning_source_input(
        runtime.work, authority, 0, cie, ledger, snapshot, (given, rule)
    )
    permit, output, charge = runtime.reasoning._work(
        authority,
        0,
        cie,
        ledger,
        snapshot,
        ReasoningOperation.SEED,
        data,
        sources=(given, rule),
        publication_charge=True,
    )
    snapshot, _ = runtime.reasoning._publish(
        authority, 0, cie, ledger, snapshot, permit, output, charge
    )
    data = d(
        "ReasoningInput",
        tuple(e.canonical_descriptor() for e in snapshot.entries),
        0,
        "EXISTS_INCOMPATIBILITY",
    )
    discovered, frontier, _ = runtime.reasoning._work(
        authority, 0, cie, ledger, snapshot, ReasoningOperation.DISCOVER, data
    )
    data = d(
        "ReasoningInput",
        tuple(e.canonical_descriptor() for e in snapshot.entries),
        0,
        frontier,
    )
    permit, output, charge = runtime.reasoning._work(
        authority,
        0,
        cie,
        ledger,
        snapshot,
        ReasoningOperation.EVALUATE,
        data,
        discovery=discovered,
        publication_charge=True,
    )
    snapshot, _ = runtime.reasoning._publish(
        authority, 0, cie, ledger, snapshot, permit, output, charge
    )
    derived = next(
        e.payload.values[0]
        for e in snapshot.entries
        if e.category == "ASSERTION"
        and e.payload.values[0].basis is AssertionBasis.DERIVED
    )
    assert derived.content == q and engine_state(core) == before
    # Only an assertion admitted in THIS OPEN CIE can feed projection.
    conditional, _ = runtime.prediction.project(
        authority, 0, ledger, cie, reasoning_claims=(derived,)
    )
    assert conditional.origin_class == "INTERNAL_ONLY"
    runtime.cie.abort(cie)
    trusted, _ = issuer.process_core_event(origin)
    before = engine_state(core)
    cie = runtime.cie.open(authority, 0)
    projection, permit = runtime.prediction.project(
        authority, 0, ledger, cie, receipt=trusted.receipt
    )
    _, fda = runtime.prediction.seal(
        authority, 0, ledger, cie, permit, projection.targets[0], 1
    )
    sealed = ledger.summary(authority)
    assert sealed.delegated == 2
    harness = runpy.run_path(str(Path(__file__).with_name("test_causality.py")))
    root, plan, origin_cap = harness["prospective"](ctx)
    study = runtime.open_study(
        authority, 0, ledger, root, plan, origin_authority=origin_cap
    )
    rce = runtime.open_rce(authority, 0, ledger, study)
    escrowed = ledger.summary(authority)
    assert (
        escrowed.reserved > sealed.reserved and escrowed.delegated == sealed.delegated
    )
    available = escrowed.available
    receipts = harness["execute_counter"](root, plan, rce)
    runtime.admit_bundle(authority, 0, ledger, study, rce, receipts)
    result = runtime.compare(authority, 0, ledger, cie, study, rce=rce)
    assert result.result_class == "REPLAY_IDENTIFIED_TREATMENT_EFFECT"
    assert runtime.finish_study(authority, 0, ledger, study).status == "COMPLETE"
    finished = ledger.summary(authority)
    assert finished.available == available and finished.reserved == 0
    assert finished.delegated == 2 and finished.consumed > escrowed.consumed
    assert engine_state(core) == before
    for token in (fda, study, rce, permit, root):
        for consumer in (
            runtime.invocations.admit,
            issuer.formal_reasoning.accept,
            issuer.observations.accept,
        ):
            with pytest.raises(IngressAbort):
                consumer(token)
    with pytest.raises(IngressAbort):
        runtime.open_study(fda, 0, ledger, root, plan, origin_authority=origin_cap)
    assert ledger.summary(authority) == finished
    runtime.cie.abort(cie)
    _, outcomes = issuer.process_core_event(future)
    assert len(outcomes) == 1 and outcomes[0].status is ForecastStatus.MATCHED
    assert ledger.summary(authority) == finished  # FDA spent its pool, not parent.
    pred_view, causal_view = (
        prediction_outcome_view(outcomes[0]),
        causal_result_view(result),
    )
    require_actual_modal_derivation(
        ctx, authority, ledger, pred_view, prediction_assertion, monkeypatch
    )
    monkeypatch.undo()
    require_actual_modal_derivation(
        ctx,
        authority,
        ledger,
        causal_view,
        causal_assertion,
        monkeypatch,
        rule_occurrence=d("occ", "causal-modal-rule"),
    )
    runtime.invocations.begin_close(authority, 0)
    ledger.retire_unused(authority, 1)
    closed = ledger.summary(authority)
    assert closed.available == closed.reserved == 0
    assert closed.initial == closed.consumed + closed.retired + closed.delegated
    assert runtime.invocations.finalize_close(authority, 1)


@pytest.mark.parametrize(
    "probe",
    [
        "test_minimal_atomic_prediction_actual_modal_derivation",
        "test_genuine_rict_e_actual_modal_derivation",
    ],
)
def test_modal_roots_survive_actual_later_synchronous_round(probe, monkeypatch):
    original = require_actual_modal_derivation
    results = []

    def chain(*args, **kwargs):
        result = original(*args, follow_on=True, **kwargs)
        results.append(result)
        return result

    monkeypatch.setitem(globals(), "require_actual_modal_derivation", chain)
    globals()[probe].__wrapped__(monkeypatch)
    assert len(results) == 1 and results[0].status == "FIXED_POINT"


def test_modal_blocked_use_reaches_complete_fixed_point(monkeypatch):
    def blocked(ctx, authority, ledger, view, adapter, _patch):
        core, issuer, runtime = ctx
        modal = adapter(view).values[0]
        premise = ground("GroundAtom", "P")
        given = issuer.authorize_given(
            premise, modal.scope, d("occ", "blocked-premise")
        )
        rule = issuer.authorize_given(
            ground("GroundConditional", premise, ground("GroundAtom", "Q")),
            modal.scope,
            d("occ", "blocked-rule"),
        )
        negative = issuer.authorize_constraint_given(
            ground("FormalNegation", premise),
            modal.scope,
            d("occ", "negative-modal"),
        )
        before = engine_state(core)
        result = runtime.reasoning.run(
            authority,
            0,
            ledger,
            (given, rule, negative),
            branch=0,
            prediction_views=(view,),
        )
        assert result.status == "FIXED_POINT", result.status
        assert not any(a.basis is AssertionBasis.DERIVED for a in result.assertions)
        from dgca_lite.cognition.reasoning.modal import resolve_payload

        payloads = tuple(
            resolve_payload(e, result.snapshot.entries, result.snapshot.binding)
            for e in result.snapshot.entries
        )
        assert sum(p.kind == "CompletedInferenceUse" for p in payloads) == 1
        assert any(p.kind == "IncompatibilityView" for p in payloads)
        assert engine_state(core) == before

    monkeypatch.setitem(globals(), "require_actual_modal_derivation", blocked)
    test_minimal_atomic_prediction_actual_modal_derivation.__wrapped__(monkeypatch)


def test_paid_modal_publication_rejects_partial_and_rebased_groups(monkeypatch):
    original = ReasoningRuntime._publish
    attacks = []

    def attacked(self, *args, **kwargs):
        output = args[6]
        if output.values[0] == "SEED":
            from dgca_lite.cognition.reasoning.runtime import entries_from_data

            entries = entries_from_data(output.values[1])
            ref_entry = next(e for e in entries if e.category == "PREDICTION_VIEW")
            groups = [
                tuple(e for e in entries if e.category != category)
                for category in ("PREDICTION_VIEW", "ASSERTION", "SOURCE_SUPPORT")
            ]
            groups.append(
                tuple(
                    replace(
                        e,
                        identity=d(
                            "ModalArenaRef",
                            ref_entry.identity.values[0],
                            "PREDICTION_VIEW",
                            7,
                        ),
                    )
                    if e is ref_entry
                    else e
                    for e in entries
                )
            )
            before = self.cie.snapshot(args[2]).canonical_bytes
            budget = args[3].summary(args[0])
            for group in groups:
                data = d(
                    "ReasoningStage",
                    "SEED",
                    tuple(e.canonical_descriptor() for e in group),
                    False,
                )
                tampered = (*args[:6], data, *args[7:])
                with pytest.raises(IngressAbort):
                    original(self, *tampered, **kwargs)
                assert self.cie.snapshot(args[2]).canonical_bytes == before
                assert args[3].summary(args[0]) == budget
                attacks.append(data)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ReasoningRuntime, "_publish", attacked)
    test_minimal_atomic_prediction_actual_modal_derivation.__wrapped__(monkeypatch)
    assert len(attacks) == 4


def integrated_signature():
    """Complete fixture bytes, never digest-as-identity; no authority decoder."""
    results = []
    original = require_actual_modal_derivation

    def capture(*args, **kwargs):
        result = original(*args, **kwargs)
        results.append(canonical_identity_bytes(result.canonical_descriptor()))
        return result

    for probe in (
        test_minimal_atomic_prediction_actual_modal_derivation,
        test_genuine_rict_e_actual_modal_derivation,
    ):
        with pytest.MonkeyPatch.context() as patch:
            patch.setitem(globals(), "require_actual_modal_derivation", capture)
            probe.__wrapped__(patch)
    return tuple(results)


def test_integrated_canonical_bytes_independent_hash_seeds():
    script = (
        "import runpy,json; "
        f"ns=runpy.run_path({str(Path(__file__).resolve())!r}); "
        "print(json.dumps([b.hex() for b in ns['integrated_signature']()]))"
    )
    reference = None
    for seed in ("0", "1", "27", "123", "random"):
        completed = subprocess.run(
            [sys.executable, "-B", "-c", script],
            env=dict(
                os.environ,
                PYTHONHASHSEED=seed,
                PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"),
            ),
            capture_output=True,
            text=True,
            check=True,
            timeout=180,
        )
        actual = tuple(
            bytes.fromhex(b) for b in json.loads(completed.stdout.splitlines()[-1])
        )
        assert len(actual) == 2 and all(actual)
        assert reference is None or actual == reference
        reference = actual


@pytest.mark.parametrize("size", [1, 129])
def test_modal_effect_outer_bound_and_closed_members_before_attribute_reads(size):
    from dgca_lite.cognition.budget import BudgetChargeView
    from dgca_lite.cognition.effect import CanonicalEffectDescriptor, PreparedEffect
    from dgca_lite.cognition.identity import CanonicalDescriptor

    class Hostile:
        def __getattr__(self, _name):
            raise AssertionError("member inspected before closed/outer validation")

    payload = object.__new__(CanonicalDescriptor)
    object.__setattr__(payload, "kind", "ReasoningPublication")
    object.__setattr__(payload, "values", ("SEED", (Hostile(),) * size, False))
    effect = object.__new__(CanonicalEffectDescriptor)
    object.__setattr__(effect, "canonical_payload", payload)
    charge = BudgetChargeView(
        *(d(label) for label in ("owner", "reservation", "unit", "class"))
    )
    with pytest.raises((TypeError, ValueError)):
        PreparedEffect(effect, None, charge, 0)


@pytest.mark.parametrize("field", ["kind", "values"])
def test_semantic_descriptor_shell_rejects_hostile_fields_without_hooks(field):
    from dgca_lite.cognition.causality.adapters import (
        validate_semantic_identity as causality,
    )
    from dgca_lite.cognition.identity import CanonicalDescriptor
    from dgca_lite.cognition.prediction.adapters import (
        validate_semantic_identity as prediction,
    )
    from dgca_lite.cognition.reasoning.modal import fields

    class Hostile:
        def __eq__(self, _other):
            raise AssertionError("comparison hook ran")

        def __len__(self):
            raise AssertionError("length hook ran")

    for kind, validator in (
        ("PredictionOutcomeSemanticIdentity", prediction),
        ("CausalReplaySemanticIdentity", causality),
        ("ModalArenaRef", lambda value: fields(value, "ModalArenaRef", 3)),
    ):
        data = object.__new__(CanonicalDescriptor)
        object.__setattr__(data, "kind", kind)
        object.__setattr__(data, "values", ())
        object.__setattr__(data, field, Hostile())
        with pytest.raises((TypeError, ValueError)):
            validator(data)

    # Forged exact-type shells cannot defer closed nested validation until
    # outcome equality, where an opaque member could run a comparison hook.
    nested = object.__new__(CanonicalDescriptor)
    object.__setattr__(nested, "kind", "CausalReplaySemanticIdentity")
    object.__setattr__(
        nested,
        "values",
        (
            "NO_PRESPECIFIED_OUTCOME_DISCRIMINATION",
            d("ExactReplayContrastIdentity", b"not-an-authority"),
            (Hostile(), Hostile()),
            "SAME",
            *(
                d(role)
                for role in ("CRCIDomain", "CRCIScope", "CRCIMeasurement", "CRCIPair")
            ),
        ),
    )
    with pytest.raises((TypeError, ValueError)):
        causality(nested)

    from dgca_lite.cognition.budget import BudgetChargeView
    from dgca_lite.cognition.effect import CanonicalEffectDescriptor, PreparedEffect

    payload = object.__new__(CanonicalDescriptor)
    object.__setattr__(payload, "kind", "ReasoningPublication")
    object.__setattr__(payload, "values", Hostile())
    effect = object.__new__(CanonicalEffectDescriptor)
    object.__setattr__(effect, "canonical_payload", payload)
    charge = BudgetChargeView(
        *(d(v) for v in ("owner", "reservation", "unit", "class"))
    )
    with pytest.raises(ValueError, match="outer shape"):
        PreparedEffect(effect, None, charge, 0)


def test_full_stack_close_vs_replay_publication_fda_survives(monkeypatch):
    from threading import Event, Thread

    from dgca_lite.cognition.causality import results
    from dgca_lite.cognition.causality.contracts import CausalOperation

    ctx, authority, ledger, origin, future = integrated_context("u10-closing")
    _, issuer, runtime = ctx
    trusted, _ = issuer.process_core_event(origin)
    cie = runtime.cie.open(authority, 0)
    projection, permit = runtime.prediction.project(
        authority, 0, ledger, cie, receipt=trusted.receipt
    )
    runtime.prediction.seal(authority, 0, ledger, cie, permit, projection.targets[0], 1)
    harness = runpy.run_path(str(Path(__file__).with_name("test_causality.py")))
    root, plan, cap = harness["prospective"](ctx)
    study = runtime.open_study(authority, 0, ledger, root, plan, origin_authority=cap)
    rce = runtime.open_rce(authority, 0, ledger, study)
    runtime.admit_bundle(
        authority, 0, ledger, study, rce, harness["execute_counter"](root, plan, rce)
    )
    ready, proceed = Event(), Event()
    original = results.compute

    def paused(op, data):
        output = original(op, data)
        if op is CausalOperation.COMPARE_REPLAY:
            ready.set()
            assert proceed.wait(10)
        return output

    monkeypatch.setattr(results, "compute", paused)
    failures = []

    def worker():
        try:
            runtime.compare(authority, 0, ledger, cie, study, rce=rce)
        except IngressAbort as error:
            failures.append(error)

    thread = Thread(target=worker)
    thread.start()
    assert ready.wait(10)
    paid = ledger.summary(authority)
    runtime.invocations.begin_close(authority, 0)  # MUST NOT wait for child.
    proceed.set()
    thread.join(10)
    assert not thread.is_alive() and len(failures) == 1
    assert runtime.registry_status().values[1:] == (0, 0)
    after = ledger.summary(authority)
    assert after.consumed == paid.consumed and after.delegated == 2
    _, outcomes = issuer.process_core_event(future)
    assert len(outcomes) == 1 and outcomes[0].status is ForecastStatus.MATCHED
    assert ledger.summary(authority) == after
    ledger.retire_unused(authority, 1)
    assert runtime.invocations.finalize_close(authority, 1)


def _isolated(function):
    """One shared stack per child, not a second runtime within a scenario.

    Like Units 7-9, do not consume the parent test process's nonrenewable,
    bounded ingress-domain lifetime audit with additional unrelated fixtures.
    No production registry reset or capacity change is performed.
    """

    @wraps(function)
    def invoke(**arguments):
        parameters = [f"{name}={value!r}" for name, value in arguments.items()]
        parameters.append("monkeypatch=patch")
        script = (
            "import runpy,pytest; "
            f"ns=runpy.run_path({str(Path(__file__).resolve())!r}); "
            "patch=pytest.MonkeyPatch(); "
            f"ns[{function.__name__!r}].__wrapped__({', '.join(parameters)})"
        )
        environment = dict(
            os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src")
        )
        child = subprocess.run(
            [sys.executable, "-B", "-c", script],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
        assert child.returncode == 0, child.stdout + child.stderr

    invoke.__signature__ = inspect.signature(function).replace(
        parameters=tuple(
            p
            for name, p in inspect.signature(function).parameters.items()
            if name != "monkeypatch"
        )
    )
    return invoke


test_minimal_atomic_prediction_actual_modal_derivation = _isolated(
    test_minimal_atomic_prediction_actual_modal_derivation
)
test_genuine_rict_e_actual_modal_derivation = _isolated(
    test_genuine_rict_e_actual_modal_derivation
)
test_complete_import_capacity_abort_has_no_partial_modal_group = _isolated(
    test_complete_import_capacity_abort_has_no_partial_modal_group
)
test_canonical_modal_group_allocation_independent_of_completion = _isolated(
    test_canonical_modal_group_allocation_independent_of_completion
)
test_shared_three_capability_chain_budget_and_conservation = _isolated(
    test_shared_three_capability_chain_budget_and_conservation
)
test_full_stack_close_vs_replay_publication_fda_survives = _isolated(
    test_full_stack_close_vs_replay_publication_fda_survives
)
test_modal_roots_survive_actual_later_synchronous_round = _isolated(
    test_modal_roots_survive_actual_later_synchronous_round
)
test_modal_blocked_use_reaches_complete_fixed_point = _isolated(
    test_modal_blocked_use_reaches_complete_fixed_point
)
test_paid_modal_publication_rejects_partial_and_rebased_groups = _isolated(
    test_paid_modal_publication_rejects_partial_and_rebased_groups
)
