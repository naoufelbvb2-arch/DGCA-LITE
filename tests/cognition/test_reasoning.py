"""Unit 7: complete reasoning, authority firewalls and adversarial contracts."""

import hashlib
import inspect
import os
import subprocess
import sys
from dataclasses import replace
from functools import wraps
from itertools import count
from pathlib import Path

import pytest

from dgca_lite import CoreConfig, CoreEngine
from dgca_lite.cognition.arena import ArenaEntry
from dgca_lite.cognition.authority import IngressAbort
from dgca_lite.cognition.contracts import ConstraintFamily, InferenceFamily
from dgca_lite.cognition.identity import (
    ScopeIdentity,
    SnapshotBinding,
)
from dgca_lite.cognition.ingress import create_trusted_ingress_boundary
from dgca_lite.cognition.invocation import InvocationLimits, _pinned_cie_parent
from dgca_lite.cognition.reasoning.assertions import key
from dgca_lite.cognition.reasoning.constraints import (
    gate_witness,
    interaction_envelope,
    no_interaction_certificate,
    participant_binding,
    preflight,
    state_identity_of,
    validate_profile,
)
from dgca_lite.cognition.reasoning.fab import d, ground, referent, validate
from dgca_lite.cognition.reasoning.inference import active_context, candidates
from dgca_lite.cognition.reasoning.lineage import parent_witness
from dgca_lite.cognition.reasoning.runtime import (
    create_reasoning_runtime,
    entries_from_data,
)
from dgca_lite.cognition.reasoning.schemas import (
    ReasoningOperation,
    ReasoningPolicy,
    require_schema,
    schema,
)
from dgca_lite.cognition.types import AssertionBasis
from dgca_lite.cognition.work import _completed_reasoning_result
from dgca_lite.persistence import engine_state

P, Q, Z = (ground("GroundAtom", v) for v in ("P", "Q", "Z"))
SCOPE = ScopeIdentity("FORMAL", d("source"), d("scope"))
NAMES = count()


@pytest.fixture(scope="module")
def context():
    core = CoreEngine(CoreConfig(receptor_fanout=1))
    issuer = create_trusted_ingress_boundary(
        core, d("unit7"), d("source"), capacity=2048
    )
    root = create_reasoning_runtime(
        issuer.invocation_causes, invocation_limits=InvocationLimits(64, 1024)
    )
    return core, issuer, root


def admit(
    context, contents, *, assumptions=(), constraints=(), constraint_assumptions=()
):
    _, issuer, root = context
    caps = tuple(
        issuer.authorize_given(v, SCOPE, d("occurrence", next(NAMES))) for v in contents
    )
    caps += tuple(
        issuer.authorize_assumption(v, SCOPE, d("occurrence", next(NAMES)))
        for v in assumptions
    )
    caps += tuple(
        issuer.authorize_constraint_given(v, SCOPE, d("occurrence", next(NAMES)))
        for v in constraints
    )
    caps += tuple(
        issuer.authorize_constraint_assumption(
            v, d("occurrence", next(NAMES)), caps[len(contents)]
        )
        for v in constraint_assumptions
    )
    auth = root.parent.admit(caps[0])
    return root, auth, root.parent.ledger(auth), caps


def run(context, contents, **kwargs):
    branch = kwargs.pop("branch", 0)
    mode = kwargs.pop("mode", "EXISTS_INCOMPATIBILITY")
    root, auth, ledger, caps = admit(context, contents, **kwargs)
    try:
        result = root.run(auth, 0, ledger, caps, branch=branch, query_mode=mode)
        return result
    finally:
        root.parent.begin_close(auth, 0)
        ledger.retire_unused(auth, 1)
        assert root.parent.finalize_close(auth, 1)


def seed(context, contents):
    root, auth, ledger, caps = admit(context, contents)
    cie = root.cie.open(auth, 0)
    snapshot = root.cie.snapshot(cie)
    from dgca_lite.cognition.work import _reasoning_source_input

    data = _reasoning_source_input(root.work, auth, 0, cie, ledger, snapshot, caps)
    permit, output, charge = root._work(
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
    snapshot, commit = root._publish(
        auth, 0, cie, ledger, snapshot, permit, output, charge
    )
    return root, auth, ledger, cie, snapshot, commit


def close(root, auth, ledger, cie=None):
    if cie is not None and root.cie.status(cie) == "OPEN":
        root.cie.abort(cie)
    root.parent.begin_close(auth, 0)
    ledger.retire_unused(auth, 1)
    assert root.parent.finalize_close(auth, 1)


def derived(result):
    return tuple(v for v in result.assertions if v.basis is AssertionBasis.DERIVED)


@pytest.mark.parametrize(
    "kind,values",
    [
        ("GroundAtom", ("A",)),
        ("GroundConditional", (P, Q)),
        (
            "GroundRelation",
            (
                referent("relation", "R"),
                referent("entity", "A"),
                referent("entity", "B"),
            ),
        ),
        ("Transitive", (referent("relation", "R"),)),
        ("FormalNegation", (P,)),
        ("GroundState", (referent("participant", "X"), referent("state", "P"))),
        ("MutuallyExclusive", (referent("state", "P"), referent("state", "Q"))),
        ("SingleValued", (referent("slot", "S"),)),
        (
            "Assign",
            (referent("entity", "A"), referent("slot", "S"), referent("value", "V")),
        ),
    ],
)
def test_closed_ground_nodes(kind, values):
    assert validate(ground(kind, *values)) is not None


@pytest.mark.parametrize(
    "kind", ["Universal", "Exists", "Unknown", "Callback", "LearnedRule", "GroundAtom"]
)
def test_unknown_node_or_bad_arity(kind):
    with pytest.raises((ValueError, TypeError)):
        ground(kind, P, Q)


@pytest.mark.parametrize(
    "value", [True, False, -1, 2**63, 1.0, float("inf"), float("nan"), object(), [], {}]
)
def test_referent_identity_is_exact_bounded(value):
    with pytest.raises((ValueError, TypeError)):
        referent("entity", value)


def test_deep_closure_and_cycles_and_opaque_metadata():
    claim = ground(
        "GroundRelation",
        referent("relation", "R"),
        referent("entity", "A"),
        referent("entity", "B"),
    )
    with pytest.raises(ValueError, match="invented"):
        validate(claim, allowed_referents=frozenset())
    with pytest.raises(ValueError):
        ground("MutuallyExclusive", referent("state", "P"), referent("state", "P"))
    with pytest.raises((TypeError, ValueError)):
        ground("GroundAtom", d("Opaque", d("hidden")))
    cyclic = ground("FormalNegation", P)
    object.__setattr__(cyclic.descriptor, "values", (cyclic,))
    with pytest.raises(ValueError, match="cyclic"):
        validate(cyclic)


def test_outer_bounds_before_member_validation():
    class Poison:
        def __getattribute__(self, name):
            raise AssertionError("member inspected")

    with pytest.raises(ValueError, match="outer"):
        entries_from_data((Poison(),) * 129)
    with pytest.raises(ValueError, match="outer"):
        validate_profile((Poison(),) * 4)
    claim = ground("GroundAtom", "ok")
    object.__setattr__(claim.descriptor, "values", (Poison(),) * 2)
    with pytest.raises(ValueError, match="arity"):
        validate(claim)


@pytest.mark.parametrize("family", list(InferenceFamily))
def test_schema_is_closed_not_caller_selected(family):
    assert require_schema(schema(family)) is family
    altered = d("InferenceSchema", *schema(family).values, "extra")
    with pytest.raises(ValueError):
        require_schema(altered)


def test_ground_mp_no_implicit_execution(context):
    lonely = run(context, (ground("GroundConditional", P, Q),))
    assert lonely.status == "FIXED_POINT" and not derived(lonely)
    result = run(context, (P, ground("GroundConditional", P, Q)))
    assert result.status == "FIXED_POINT"
    assert tuple(a.content for a in derived(result)) == (Q,)
    assert all(not a.dependencies for a in derived(result))


def test_derived_ordinary_later_round_not_same_round(context):
    result = run(
        context,
        (P, ground("GroundConditional", P, Q), ground("GroundConditional", Q, Z)),
    )
    assert result.status == "FIXED_POINT"
    assert {v.content for v in derived(result)} == {Q, Z}
    records = [
        e.payload for e in result.snapshot.entries if e.category == "DERIVATION_WITNESS"
    ]
    assert len(records) == 2
    # Witness snapshot round increases: no recursive same-round consumption.
    rounds = {v.values[4][0].values[1].values[2] for v in records}
    assert len(rounds) == 2


def test_derived_conditional_cannot_be_rule(context):
    conditional = ground("GroundConditional", Q, Z)
    result = run(context, (P, Q, ground("GroundConditional", P, conditional)))
    assert result.status == "FIXED_POINT"
    assert {v.content for v in derived(result)} == {conditional}


@pytest.mark.parametrize(
    "basis",
    [
        b
        for b in AssertionBasis
        if b not in (AssertionBasis.FORMAL_GIVEN, AssertionBasis.FORMAL_ASSUMPTION)
    ],
)
@pytest.mark.parametrize("family", list(InferenceFamily))
def test_nonformal_rule_role_rejected_before_support_matching(context, basis, family):
    if family is InferenceFamily.GROUND_MODUS_PONENS:
        claims = (ground("GroundConditional", P, Q), P)
    else:
        r, a, b, c = (
            referent("relation", "R"),
            *(referent("entity", v) for v in ("A", "B", "C")),
        )
        claims = (
            ground("Transitive", r),
            ground("GroundRelation", r, a, b),
            ground("GroundRelation", r, b, c),
        )
    root, auth, ledger, cie, snapshot, _ = seed(context, claims)
    try:
        entries = []
        for e in snapshot.entries:
            if e.category == "ASSERTION" and e.payload.values[0].content == claims[0]:
                old = e.payload.values[0]
                # Forged missing-root data for modal bases is rejected by Unit1
                # too; for permitted empty EDS bases the role check rejects it.
                try:
                    ask = replace(old, basis=basis)
                except ValueError:
                    continue
                e = ArenaEntry("ASSERTION", d("ASK", ask), d("AssertionRecord", ask))
            entries.append(e)
        assert not candidates(tuple(entries), snapshot.binding, 0, ReasoningPolicy())
    finally:
        close(root, auth, ledger, cie)


def test_assumption_dependencies_never_discharge(context):
    result = run(
        context, (P,), assumptions=(ground("GroundConditional", P, Q),), branch=1
    )
    assert result.status == "FIXED_POINT"
    conclusion = derived(result)[0]
    assumption = next(
        a for a in result.assertions if a.basis is AssertionBasis.FORMAL_ASSUMPTION
    )
    assert (
        conclusion.dependencies == assumption.dependencies and conclusion.dependencies
    )
    excluded = run(
        context, (P,), assumptions=(ground("GroundConditional", P, Q),), branch=0
    )
    assert not derived(excluded)


def test_transitive_composition_needs_explicit_exact_property(context):
    r, a, b, c = (
        referent("relation", "R"),
        *(referent("entity", v) for v in ("A", "B", "C")),
    )
    left, right = ground("GroundRelation", r, a, b), ground("GroundRelation", r, b, c)
    absent = run(context, (left, right))
    assert not derived(absent)
    exact = run(context, (left, right, ground("Transitive", r)))
    assert exact.status == "FIXED_POINT"
    assert {v.content for v in derived(exact)} == {ground("GroundRelation", r, a, c)}
    wrong = run(context, (left, right, ground("Transitive", referent("relation", "r"))))
    assert not derived(wrong)


def test_content_cycle_has_independent_support_but_no_circular_justification(context):
    result = run(
        context,
        (P, ground("GroundConditional", P, Q), ground("GroundConditional", Q, P)),
    )
    assert result.status == "FIXED_POINT"
    records = [
        e.payload for e in result.snapshot.entries if e.category == "DERIVATION_WITNESS"
    ]
    assert len(records) == 2
    for record in records:
        assert key(record.values[0]) not in record.values[3]


def test_duplicate_source_occurrences_do_not_multiply_work(context):
    root, auth, ledger, caps = admit(context, (P, P, ground("GroundConditional", P, Q)))
    result = root.run(auth, 0, ledger, caps + (caps[0],))
    try:
        assert result.status == "FIXED_POINT" and len(derived(result)) == 1
        assert (
            len(
                [
                    e
                    for e in result.snapshot.entries
                    if e.category == "DERIVATION_WITNESS"
                ]
            )
            == 1
        )
        assert (
            len([e for e in result.snapshot.entries if e.category == "SOURCE_SUPPORT"])
            == 3
        )
    finally:
        close(root, auth, ledger)


def test_scope_identity_never_broadens(context):
    _, issuer, root = context
    other = ScopeIdentity("FORMAL", d("source"), d("other_scope"))
    cap1 = issuer.authorize_given(P, SCOPE, d("occurrence", next(NAMES)))
    cap2 = issuer.authorize_given(
        ground("GroundConditional", P, Q), other, d("occurrence", next(NAMES))
    )
    auth = root.parent.admit(cap1)
    ledger = root.parent.ledger(auth)
    try:
        result = root.run(auth, 0, ledger, (cap1, cap2))
        assert result.status == "FIXED_POINT" and not derived(result)
    finally:
        close(root, auth, ledger)


@pytest.mark.parametrize("missing", list(ConstraintFamily))
def test_profile_cannot_omit_relevant_family(missing):
    with pytest.raises(ValueError):
        validate_profile(tuple(f for f in ConstraintFamily if f is not missing))
    with pytest.raises(ValueError):
        no_interaction_certificate(schema(InferenceFamily.GROUND_MODUS_PONENS))


def test_negation_blocks_exact_use_no_ex_falso(context):
    result = run(
        context,
        (P, ground("GroundConditional", P, Q)),
        constraints=(ground("FormalNegation", P),),
    )
    assert result.status == "FIXED_POINT" and not derived(result)
    assert len(result.assertions) == 2
    assert any(e.category == "CONSTRAINT_FINDING" for e in result.snapshot.entries)
    nonmatching = run(
        context,
        (P, ground("GroundConditional", P, Q)),
        constraints=(ground("FormalNegation", Z),),
    )
    assert {v.content for v in derived(nonmatching)} == {Q}


def test_all_three_constraint_families_and_exact_assignments(context):
    entity, slot = referent("entity", "X"), referent("slot", "S")
    left, right = (ground("Assign", entity, slot, referent("value", v)) for v in (1, 2))
    participant = referent("participant", "X")
    states = tuple(referent("state", v) for v in (1, 2))
    for assertions, constraint in (
        (
            tuple(ground("GroundState", participant, state) for state in states),
            ground("MutuallyExclusive", *states),
        ),
        ((left, right), ground("SingleValued", slot)),
    ):
        result = run(
            context,
            assertions,
            constraints=(constraint,),
            mode="ENUMERATE_ALL_INCOMPATIBILITIES",
        )
        assert result.status == "FIXED_POINT"
        assert any(e.category == "CONSTRAINT_FINDING" for e in result.snapshot.entries)
        assert not derived(result)
    absent = run(context, (left,), constraints=(ground("SingleValued", slot),))
    assert not any(e.category == "CONSTRAINT_FINDING" for e in absent.snapshot.entries)
    different = ground("Assign", referent("entity", "Y"), slot, referent("value", 2))
    result = run(
        context, (left, different), constraints=(ground("SingleValued", slot),)
    )
    assert not any(e.category == "CONSTRAINT_FINDING" for e in result.snapshot.entries)


def test_derived_constraint_shape_cannot_self_activate(context):
    negative = ground("FormalNegation", P)
    result = run(context, (P, ground("GroundConditional", P, negative)))
    assert result.status == "FIXED_POINT"
    assert {v.content for v in derived(result)} == {negative}
    assert not any(e.category == "CONSTRAINT_FINDING" for e in result.snapshot.entries)


def test_natural_language_negation_is_not_formal(context):
    result = run(context, (P, ground("GroundAtom", "not P")))
    assert not any(e.category == "CONSTRAINT_FINDING" for e in result.snapshot.entries)


@pytest.mark.parametrize("kind", ["CONSTRAINT_BLOCKED", "CONSTRAINT_CHECK_INCOMPLETE"])
def test_incomplete_or_positive_is_not_clearance(kind):
    with pytest.raises(ValueError):
        gate_witness(d(kind))


def test_historical_clearance_and_stale_snapshot_cannot_publish(context):
    root, auth, ledger, cie, snapshot, commit = seed(
        context, (P, ground("GroundConditional", P, Q))
    )
    try:
        old = SnapshotBinding(snapshot.binding.cie, 0, 0)
        work = root.work.prepare_work(
            auth,
            0,
            old,
            d("ReasoningInput", (), 0, "EXISTS_INCOMPATIBILITY"),
            operation=ReasoningOperation.DISCOVER,
        )
        with pytest.raises(IngressAbort):
            root.work.reserve(auth, 0, cie, ledger, work)
        root.cie.abort(cie)
        with pytest.raises(IngressAbort):
            root.run(auth, 0, ledger, (commit,))
    finally:
        close(root, auth, ledger, cie)


def test_terminal_cleanup_preserves_data_not_work_authority(context):
    root, auth, ledger, caps = admit(context, (P, ground("GroundConditional", P, Q)))
    result = root.run(auth, 0, ledger, caps)
    with _pinned_cie_parent(root.parent, auth) as (_, item, _):
        assert item.cie_child is None and item.nondelegated_children == 0
        assert all(
            r.work is None and r.output is None
            for r in item.work_owner.index[1].values()
        )
    before = result.snapshot.canonical_bytes
    close(root, auth, ledger)
    assert result.snapshot.canonical_bytes == before


def test_core_and_layer2_never_mutate(context):
    core, _, _ = context
    before = engine_state(core)
    run(context, (P, ground("GroundConditional", P, Q)))
    assert engine_state(core) == before


@pytest.mark.parametrize("reserved", [59, 60, 61, 62, 63, 64])
def test_complete_group_budget(context, reserved):
    root, auth, ledger, caps = admit(context, (P, ground("GroundConditional", P, Q)))
    ledger.reserve(auth, 0, reserved, d("OtherGroup"))
    try:
        result = root.run(auth, 0, ledger, caps)
        assert result.status == "PARTIAL_BUDGET"
        assert (len(derived(result)) == 1) == (reserved == 59)
    finally:
        close(root, auth, ledger)


def test_constraint_assumption_branches(context):
    kwargs = {
        "assumptions": (ground("GroundAtom", "H"),),
        "constraint_assumptions": (ground("FormalNegation", P),),
    }
    base = run(context, (P, ground("GroundConditional", P, Q)), branch=0, **kwargs)
    assert {a.content for a in derived(base)} == {Q}
    child = run(context, (P, ground("GroundConditional", P, Q)), branch=1, **kwargs)
    assert not derived(child)
    a = next(a for a in child.assertions if a.basis is AssertionBasis.FORMAL_ASSUMPTION)
    views = [
        e.payload for e in child.snapshot.entries if e.category == "CONSTRAINT_FINDING"
    ]
    assert views and all(v.values[5] == a.dependencies for v in views)


def test_duplicate_constraint_sources(context):
    result = run(
        context,
        (P,),
        constraints=(ground("FormalNegation", P), ground("FormalNegation", P)),
    )
    assert (
        len(
            [
                e
                for e in result.snapshot.entries
                if e.payload.kind == "ActiveConstraintRecord"
            ]
        )
        == 1
    )
    assert (
        len(
            [
                e
                for e in result.snapshot.entries
                if e.payload.kind == "ConstraintSourceSupport"
            ]
        )
        == 2
    )
    views = [
        e.payload for e in result.snapshot.entries if e.category == "CONSTRAINT_FINDING"
    ]
    assert len(views) == 1 and len(views[0].values[7].values[2]) == 1


def test_query_order_and_incomplete_coverage(context):
    root, auth, ledger, cie, snapshot, _ = seed(context, (P, Q))
    try:
        aec = active_context(snapshot.entries, snapshot.binding, 0).identity
        cs = {}
        for p in (P, Q):
            semantic = d(
                "ConstraintSemanticKey",
                ground("FormalNegation", p),
                AssertionBasis.FORMAL_GIVEN,
                SCOPE,
                (),
            )
            cs[key(semantic)] = d("ActiveConstraintRecord", semantic)
        asks = tuple(
            e.payload.values[0] for e in snapshot.entries if e.category == "ASSERTION"
        )
        roles = tuple((str(i), a) for i, a in enumerate(asks))
        query = d("ConstraintQuerySchema")
        exists = preflight(query, roles, aec, snapshot.binding, cs, ReasoningPolicy())
        enumeration = preflight(
            query,
            roles,
            aec,
            snapshot.binding,
            dict(reversed(tuple(cs.items()))),
            ReasoningPolicy(),
            mode="ENUMERATE_ALL_INCOMPATIBILITIES",
        )
        assert exists.kind == enumeration.kind == "CONSTRAINT_BLOCKED"
        assert (
            len(enumeration.values[2]) == 2
            and exists.values[2][0] == enumeration.values[2][0]
        )
        incomplete = preflight(
            query,
            roles,
            aec,
            snapshot.binding,
            cs,
            ReasoningPolicy(max_checks=1),
            mode="ENUMERATE_ALL_INCOMPATIBILITIES",
        )
        assert incomplete.kind == "CONSTRAINT_CHECK_INCOMPLETE"
        with pytest.raises(ValueError):
            gate_witness(incomplete)
    finally:
        close(root, auth, ledger, cie)


def test_support_context_and_cycle(context):
    result = run(context, (P, ground("GroundConditional", P, Q)))
    ask = derived(result)[0]
    records = [
        e.payload for e in result.snapshot.entries if e.category == "DERIVATION_WITNESS"
    ]
    record = records[0]
    wrong = d("DerivationContextReference", "different")
    assert (
        parent_witness(
            ask,
            result.snapshot.binding,
            {},
            {key(ask): records},
            wrong,
            replace(ask, content=Z),
            ReasoningPolicy(),
        )
        is None
    )
    assert (
        parent_witness(
            ask,
            result.snapshot.binding,
            {},
            {key(ask): records},
            record.values[2],
            ask,
            ReasoningPolicy(),
        )
        is None
    )


def test_copied_work_output_not_authority(context):
    root, auth, ledger, cie, snapshot, _ = seed(
        context, (P, ground("GroundConditional", P, Q))
    )
    try:
        data = d(
            "ReasoningInput",
            tuple(e.canonical_descriptor() for e in snapshot.entries),
            0,
            "EXISTS_INCOMPATIBILITY",
        )
        permit, output, _ = root._work(
            auth, 0, cie, ledger, snapshot, ReasoningOperation.DISCOVER, data
        )
        original = key(output)
        object.__setattr__(output, "values", (0, (), "EXISTS_INCOMPATIBILITY"))
        with _pinned_cie_parent(root.parent, auth) as (_, item, _):
            assert (
                key(
                    _completed_reasoning_result(
                        root.work, permit, item, snapshot.binding
                    )
                )
                == original
            )
    finally:
        close(root, auth, ledger, cie)


def empty_round(context):
    root, auth, ledger, cie, snapshot, _ = seed(context, (P,))
    data = d(
        "ReasoningInput",
        tuple(e.canonical_descriptor() for e in snapshot.entries),
        0,
        "EXISTS_INCOMPATIBILITY",
    )
    discovery, frontier, _ = root._work(
        auth, 0, cie, ledger, snapshot, ReasoningOperation.DISCOVER, data
    )
    data = d(
        "ReasoningInput",
        tuple(e.canonical_descriptor() for e in snapshot.entries),
        0,
        frontier,
    )
    permit, output, charge = root._work(
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
    return root, auth, ledger, cie, snapshot, permit, output, charge


def test_publication_rollback_including_retirement(context, monkeypatch):
    from dgca_lite.cognition import effects as effect_module

    root, auth, ledger, cie, snapshot, permit, output, charge = empty_round(context)
    try:
        before = ledger.summary(auth)

        def fail():
            raise MemoryError("before publication")

        with monkeypatch.context() as patch:
            patch.setattr(effect_module, "_before_effect_publish", fail)
            with pytest.raises(MemoryError):
                root._publish(auth, 0, cie, ledger, snapshot, permit, output, charge)
        assert root.cie.snapshot(cie).canonical_bytes == snapshot.canonical_bytes
        assert ledger.summary(auth) == before
        with _pinned_cie_parent(root.parent, auth) as (_, item, _):
            assert (
                _completed_reasoning_result(root.work, permit, item, snapshot.binding)
                == output
            )
        final, _ = root._publish(auth, 0, cie, ledger, snapshot, permit, output, charge)
        assert (
            root.cie.status(cie) == "PUBLISHED"
            and final.binding.arena_version == snapshot.binding.arena_version + 1
        )
    finally:
        close(root, auth, ledger, cie)


def test_closure_wins_before_effect(context):
    root, auth, ledger, cie, snapshot, permit, output, charge = empty_round(context)
    root.parent.begin_close(auth, 0)
    before = ledger.summary(auth)
    with pytest.raises(IngressAbort):
        root._publish(auth, 0, cie, ledger, snapshot, permit, output, charge)
    assert ledger.summary(auth) == before
    ledger.retire_unused(auth, 1)
    assert root.parent.finalize_close(auth, 1)


def test_internal_adapter_literal_and_modal(context):
    from dgca_lite.cognition.reasoning.assertions import internal_retrieval_view
    from dgca_lite.memory.session import retrieve_internal

    core, issuer, _ = context
    from dgca_lite import SurfaceEvent
    from dgca_lite.memory.integration import TrustedCoreAdapter

    with issuer.core_transition():
        TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("x"))
        receipt = TrustedCoreAdapter.process_event(
            core, SurfaceEvent.from_text("x")
        ).receipt
    cell = receipt.learning_frontier[0]
    root, auth, ledger, cie, snapshot, _ = seed(context, (P,))
    try:
        l2 = retrieve_internal(core, {cell: 1.0})
        view = internal_retrieval_view(l2, snapshot.binding)
        ask, _ = view.values
        assert ask.basis is AssertionBasis.INTERNAL_RETRIEVAL and ask.dependencies
        assert ask.content.descriptor.kind == "InternalRetrievalStatement"
        with pytest.raises(IngressAbort):
            issuer.formal_reasoning.accept(view)
        with pytest.raises(TypeError):
            internal_retrieval_view(l2.root, snapshot.binding)
        with pytest.raises(ValueError):
            internal_retrieval_view(
                replace(l2, root=replace(l2.root, trusted_root_id=1)), snapshot.binding
            )
        with pytest.raises(TypeError):
            internal_retrieval_view(replace(l2, sources=(auth,)), snapshot.binding)
    finally:
        close(root, auth, ledger, cie)


def test_real_unit2_observation_is_consumable_without_basis_promotion(context):
    from dgca_lite import SurfaceEvent
    from dgca_lite.memory.integration import TrustedCoreAdapter

    core, issuer, root = context
    with issuer.core_transition():
        event = TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("y"))
        observation = issuer.authorize_core_observation(event.receipt, SCOPE)
    observed = issuer.observations.accept(observation).canonical_descriptor().values[0]
    conditional = issuer.authorize_given(
        ground("GroundConditional", observed.content, Q),
        SCOPE,
        d("occurrence", next(NAMES)),
    )
    auth = root.parent.admit(observation)
    ledger = root.parent.ledger(auth)
    before = engine_state(core)
    try:
        result = root.run(auth, 0, ledger, (observation, conditional))
        assert result.status == "FIXED_POINT"
        assert {a.content for a in derived(result)} == {Q}
        assert any(
            a.basis is AssertionBasis.EXTERNAL_OBSERVATION for a in result.assertions
        )
        assert engine_state(core) == before
    finally:
        close(root, auth, ledger)


def test_u7_b02_malformed_relation_constraint_rejected_transitivity_remains(context):
    r, a, b, c = (
        referent("relation", "R"),
        *(referent("entity", v) for v in ("A", "B", "C")),
    )
    left, right = ground("GroundRelation", r, a, b), ground("GroundRelation", r, b, c)
    from dgca_lite.cognition.identity import ClaimContentID

    malformed = ClaimContentID(d("MutuallyExclusive", left, right))
    before = engine_state(context[0])
    with pytest.raises((TypeError, IngressAbort)):
        context[1].authorize_constraint_given(malformed, SCOPE, d("bad_constraint"))
    result = run(context, (left, right, ground("Transitive", r)))
    assert {a.content for a in derived(result)} == {ground("GroundRelation", r, a, c)}
    assert engine_state(context[0]) == before


@pytest.mark.parametrize("form", ["relation", "assignment", "atom", "conditional"])
def test_b02_ineligible_forms_have_no_participant_or_state(form):
    if form == "relation":
        content = ground(
            "GroundRelation",
            referent("relation", "R"),
            referent("entity", "X"),
            referent("entity", "Y"),
        )
    elif form == "assignment":
        content = ground(
            "Assign",
            referent("entity", "X"),
            referent("slot", "S"),
            referent("value", "V"),
        )
    elif form == "atom":
        content = ground("GroundAtom", "state X first participant")
    else:
        content = ground("GroundConditional", P, Q)
    assert participant_binding(content) is None
    assert state_identity_of(content) is None


def test_b02_ground_state_deep_closure_and_typed_identity():
    x, state = referent("participant", 1), referent("state", 1)
    claim = ground("GroundState", x, state)
    assert participant_binding(claim) == x
    assert state_identity_of(claim) == state
    assert validate(claim) == {key(x), key(state)}
    with pytest.raises(ValueError, match="invented"):
        validate(claim, allowed_referents={key(x)})
    with pytest.raises(ValueError, match="invented"):
        validate(claim, allowed_referents={key(state)})
    assert state != referent("state", "1")
    assert x != referent("participant", "1")
    with pytest.raises(TypeError):
        ground("GroundState", referent("entity", 1), state)
    with pytest.raises(TypeError):
        ground("GroundState", x, referent("value", 1))


@pytest.mark.parametrize("kind", ["GroundState", "MutuallyExclusive"])
def test_b02_outer_arity_precedes_nested_member_inspection(kind):
    from dgca_lite.cognition.assertions import validate_constraint_content
    from dgca_lite.cognition.identity import ClaimContentID

    class Poison:
        def __getattribute__(self, name):
            raise AssertionError("unbounded nested member inspected")

    content = ClaimContentID(d("GroundAtom", "valid_before_forging"))
    object.__setattr__(content.descriptor, "kind", kind)
    object.__setattr__(content.descriptor, "values", (Poison(),) * 3)
    with pytest.raises(ValueError, match="arity"):
        validate(content)
    if kind == "MutuallyExclusive":
        with pytest.raises(ValueError, match="arity"):
            validate_constraint_content(content)


@pytest.mark.parametrize("field", ["participant", "state"])
@pytest.mark.parametrize("invalid", [True, False, -1, 2**63, "", "x" * 257])
def test_b02_referents_reject_noncanonical_values(field, invalid):
    with pytest.raises((TypeError, ValueError)):
        referent(field, invalid)


@pytest.mark.parametrize("bad", ["proposition", "relation", "value", "opaque", "self"])
def test_b02_formal_constraint_shape_rejects_before_issuance(context, bad):
    from dgca_lite.cognition.identity import ClaimContentID

    _, issuer, _ = context
    state = referent("state", "S")
    if bad == "proposition":
        other = P
    elif bad == "relation":
        other = ground(
            "GroundRelation",
            referent("relation", "R"),
            referent("entity", "A"),
            referent("entity", "B"),
        )
    elif bad == "value":
        other = referent("value", "T")
    elif bad == "opaque":
        other = d("state", d("hidden", "T"))
    else:
        other = state
    before = issuer.registry_status
    with pytest.raises(IngressAbort):
        issuer.authorize_constraint_given(
            ClaimContentID(d("MutuallyExclusive", state, other)),
            SCOPE,
            d("bad_constraint", bad),
        )
    assert issuer.registry_status == before


@pytest.mark.parametrize("reverse", [0, 1])
def test_b02_exact_state_conflict_symmetry_preserves_assertions(context, reverse):
    x = referent("participant", "X")
    states = (referent("state", 1), referent("state", "1"))
    assertions = tuple(ground("GroundState", x, s) for s in states)
    constraint = ground("MutuallyExclusive", *(states[::-1] if reverse else states))
    result = run(context, assertions, constraints=(constraint,))
    findings = [
        e.payload for e in result.snapshot.entries if e.category == "CONSTRAINT_FINDING"
    ]
    assert result.status == "FIXED_POINT" and len(findings) == 1
    assert len(result.assertions) == 2 and not derived(result)
    assert findings[0].values[5] == ()
    assert len(findings[0].values[7].values[2]) == 1


@pytest.mark.parametrize(
    "case",
    [
        "other_participant",
        "typed_participant",
        "other_state",
        "missing",
        "assign",
        "relations",
    ],
)
def test_b02_no_heuristic_conflict_or_interaction(context, case):
    x, s, t = referent("participant", 1), referent("state", "S"), referent("state", "T")
    left = ground("GroundState", x, s)
    right = ground("GroundState", x, t)
    if case == "other_participant":
        right = ground("GroundState", referent("participant", 2), t)
    elif case == "typed_participant":
        right = ground("GroundState", referent("participant", "1"), t)
    elif case == "other_state":
        right = ground("GroundState", x, referent("state", "U"))
    elif case == "assign":
        left, right = tuple(
            ground(
                "Assign",
                referent("entity", 1),
                referent("slot", "slot"),
                referent("value", v),
            )
            for v in ("S", "T")
        )
    elif case == "relations":
        r = referent("relation", "MutuallyExclusive")
        a, b, c = tuple(referent("entity", v) for v in ("A", "B", "C"))
        left, right = (
            ground("GroundRelation", r, a, b),
            ground("GroundRelation", r, b, c),
        )
    result = run(
        context,
        (left,) if case == "missing" else (left, right),
        constraints=(ground("MutuallyExclusive", s, t),),
    )
    assert result.status == "FIXED_POINT"
    assert not any(e.category == "CONSTRAINT_FINDING" for e in result.snapshot.entries)
    assert (
        "EXPLICIT_GROUND_STATE_ONLY"
        in interaction_envelope(ConstraintFamily.EXPLICIT_MUTUAL_EXCLUSION).values
    )


def test_b02_constraint_assumption_and_participant_eds_exact(context):
    x, s, t = (
        referent("participant", "X"),
        referent("state", "S"),
        referent("state", "T"),
    )
    left, right = ground("GroundState", x, s), ground("GroundState", x, t)
    result = run(
        context,
        (left,),
        assumptions=(right,),
        constraint_assumptions=(ground("MutuallyExclusive", s, t),),
        branch=1,
    )
    findings = [
        e.payload for e in result.snapshot.entries if e.category == "CONSTRAINT_FINDING"
    ]
    assumption = next(
        a for a in result.assertions if a.basis is AssertionBasis.FORMAL_ASSUMPTION
    )
    assert len(findings) == 1 and findings[0].values[5] == assumption.dependencies
    base = run(
        context,
        (left,),
        assumptions=(right,),
        constraint_assumptions=(ground("MutuallyExclusive", s, t),),
        branch=0,
    )
    assert not any(e.category == "CONSTRAINT_FINDING" for e in base.snapshot.entries)


def test_b02_derived_state_is_ordinary_data_and_constraint_does_not_activate(context):
    x, s, t = (
        referent("participant", "X"),
        referent("state", "S"),
        referent("state", "T"),
    )
    left, right = ground("GroundState", x, s), ground("GroundState", x, t)
    mutex = ground("MutuallyExclusive", s, t)
    result = run(context, (left, right, P, ground("GroundConditional", P, mutex)))
    assert {a.content for a in derived(result)} == {mutex}
    assert not any(e.category == "CONSTRAINT_FINDING" for e in result.snapshot.entries)
    active = run(
        context, (left, P, ground("GroundConditional", P, right)), constraints=(mutex,)
    )
    assert {a.content for a in derived(active)} == {right}
    assert any(e.category == "CONSTRAINT_FINDING" for e in active.snapshot.entries)


def test_b02_relation_overlap_has_empty_mutual_exclusion_check_frontier(context):
    r = referent("relation", "R")
    a, b, c = tuple(referent("entity", v) for v in ("A", "B", "C"))
    claims = (ground("GroundRelation", r, a, b), ground("GroundRelation", r, b, c))
    root, auth, ledger, cie, snapshot, _ = seed(context, claims)
    try:
        aec = active_context(snapshot.entries, snapshot.binding, 0).identity
        semantic = d(
            "ConstraintSemanticKey",
            ground("MutuallyExclusive", referent("state", "S"), referent("state", "T")),
            AssertionBasis.FORMAL_GIVEN,
            SCOPE,
            (),
        )
        constraints = {key(semantic): d("ActiveConstraintRecord", semantic)}
        roles = tuple(
            (str(i), a)
            for i, a in enumerate(
                snapshot_entry.payload.values[0]
                for snapshot_entry in snapshot.entries
                if snapshot_entry.category == "ASSERTION"
            )
        )
        check = preflight(
            d("ConstraintQuerySchema"),
            roles,
            aec,
            snapshot.binding,
            constraints,
            ReasoningPolicy(max_checks=1),
        )
        assert check.kind == "CONSTRAINT_CLEARED"
        assert check.values[0].values[5].values == ((), (), True)
    finally:
        close(root, auth, ledger, cie)


def test_ancestry_bound_is_incompleteness_not_fixed_point(context):
    core = CoreEngine(CoreConfig(receptor_fanout=1))
    issuer = create_trusted_ingress_boundary(core, d("small_ancestry"), d("source"))
    root = create_reasoning_runtime(
        issuer.invocation_causes, policy=ReasoningPolicy(max_ancestry=1)
    )
    local = (core, issuer, root)
    result = run(local, (P, ground("GroundConditional", P, Q)))
    assert result.status == "CAPACITY_ABORT" and not derived(result)
    assert len(result.assertions) == 2


def test_transitive_longer_chain_consumes_only_committed_rounds(context):
    r = referent("relation", "R")
    a, b, c, e = tuple(referent("entity", v) for v in ("A", "B", "C", "D"))
    result = run(
        context,
        (
            ground("Transitive", r),
            ground("GroundRelation", r, a, b),
            ground("GroundRelation", r, b, c),
            ground("GroundRelation", r, c, e),
        ),
    )
    # The full second round derives the three-edge conclusion. Its complete
    # historical arena then exceeds the next work-input representation bound:
    # no falsely claimed fixed point and no partially published frontier.
    assert result.status == "CAPACITY_ABORT"
    assert ground("GroundRelation", r, a, e) in {v.content for v in derived(result)}
    records = [
        e.payload for e in result.snapshot.entries if e.category == "DERIVATION_WITNESS"
    ]
    last = [
        v for v in records if v.values[0].content == ground("GroundRelation", r, a, e)
    ]
    earlier = [
        v for v in records if v.values[0].content != ground("GroundRelation", r, a, e)
    ]
    assert min(v.values[4][0].values[1].values[2] for v in last) > min(
        v.values[4][0].values[1].values[2] for v in earlier
    )


def test_terminal_effect_transport_retry_is_exact_read_only(context):
    root, auth, ledger, cie, snapshot, permit, output, charge = empty_round(context)
    try:
        final, first = root._publish(
            auth, 0, cie, ledger, snapshot, permit, output, charge
        )
        before = ledger.summary(auth)
        retry, second = root._publish(
            auth, 0, cie, ledger, snapshot, permit, output, charge
        )
        assert final.canonical_bytes == retry.canonical_bytes
        assert first.canonical_descriptor() == second.canonical_descriptor()
        assert ledger.summary(auth) == before
    finally:
        close(root, auth, ledger, cie)


@pytest.mark.parametrize("reserved", [59, 60])
def test_multi_candidate_budget_group_never_publishes_first_n(context, reserved):
    root, auth, ledger, caps = admit(
        context,
        (P, ground("GroundConditional", P, Q), ground("GroundConditional", P, Z)),
    )
    ledger.reserve(auth, 0, reserved, d("OtherGroup"))
    try:
        result = root.run(auth, 0, ledger, caps)
        assert result.status == "PARTIAL_BUDGET"
        assert len(derived(result)) == (2 if reserved == 59 else 0)
    finally:
        close(root, auth, ledger)


def test_reasoning_commit_wins_threaded_invocation_close(context, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from dgca_lite.cognition import effects as effect_module

    root, auth, ledger, cie, snapshot, permit, output, charge = empty_round(context)
    inside, release, closing_started = Event(), Event(), Event()
    before = ledger.summary(auth).consumed

    def pause():
        inside.set()
        assert release.wait(10)

    def closing():
        closing_started.set()
        return root.parent.begin_close(auth, 0)

    with monkeypatch.context() as patch:
        patch.setattr(effect_module, "_before_effect_publish", pause)
        with ThreadPoolExecutor(max_workers=2) as pool:
            committing = pool.submit(
                root._publish, auth, 0, cie, ledger, snapshot, permit, output, charge
            )
            assert inside.wait(10)
            close_future = pool.submit(closing)
            assert closing_started.wait(10) and not close_future.done()
            release.set()
            final, _ = committing.result(10)
            close_future.result(10)
    assert root.cie.status(cie) == "PUBLISHED"
    assert ledger.summary(auth).consumed == before + 1
    assert final.binding.arena_version == snapshot.binding.arena_version + 1
    ledger.retire_unused(auth, 1)
    assert root.parent.finalize_close(auth, 1)


@pytest.mark.parametrize("container", ["capabilities", "internal_results"])
def test_seed_combined_outer_bound_precedes_member_inspection(context, container):
    class Poison:
        def __getattribute__(self, name):
            raise AssertionError("oversized source member inspected")

    root, auth, ledger, caps = admit(context, (P,))
    try:
        oversize = (Poison(),) * 33
        result = root.run(
            auth,
            0,
            ledger,
            oversize if container == "capabilities" else caps,
            internal_results=oversize if container == "internal_results" else (),
        )
        assert result.status == "CAPACITY_ABORT" and not result.assertions
        assert ledger.summary(auth).consumed == 0
    finally:
        close(root, auth, ledger)


@pytest.mark.parametrize("pointer", ["terminal", "last_binding", "final_effect_index"])
def test_reasoning_publication_pointer_interruption_rolls_back_all_state(
    context, monkeypatch, pointer
):
    from dgca_lite.cognition import effects as effect_module

    root, auth, ledger, cie, snapshot, permit, output, charge = empty_round(context)
    with _pinned_cie_parent(root.parent, auth) as (_, item, _):
        owner = item.effect_owner
        child, count = item.cie_child, item.nondelegated_children
    before = ledger.summary(auth), root.effects.registry_status(auth)
    fired = []
    original_prepare = effect_module._prepare_reasoning_publication

    def prepare(*args):
        result = original_prepare(*args)
        target = owner if pointer == "final_effect_index" else result[0]
        name_to_fail = "index" if pointer == "final_effect_index" else pointer
        original_setattr = type(target).__setattr__

        def fail_once(self, name, value):
            if self is target and name == name_to_fail and not fired:
                fired.append(True)
                raise MemoryError("reasoning group pointer interruption")
            return original_setattr(self, name, value)

        monkeypatch.setattr(type(target), "__setattr__", fail_once)
        return result

    try:
        with monkeypatch.context() as patch:
            patch.setattr(effect_module, "_prepare_reasoning_publication", prepare)
            with pytest.raises(MemoryError):
                root._publish(auth, 0, cie, ledger, snapshot, permit, output, charge)
        assert fired == [True]
        assert (ledger.summary(auth), root.effects.registry_status(auth)) == before
        assert root.cie.snapshot(cie).canonical_bytes == snapshot.canonical_bytes
        with _pinned_cie_parent(root.parent, auth) as (_, item, _):
            assert item.cie_child is child and item.nondelegated_children == count
            assert (
                _completed_reasoning_result(root.work, permit, item, snapshot.binding)
                == output
            )
        final, _ = root._publish(auth, 0, cie, ledger, snapshot, permit, output, charge)
        assert final.binding.arena_version == snapshot.binding.arena_version + 1
    finally:
        close(root, auth, ledger, cie)


def test_derived_transitivity_property_cannot_activate_composition(context):
    r = referent("relation", "R")
    a, b, c = tuple(referent("entity", v) for v in ("A", "B", "C"))
    property_claim = ground("Transitive", r)
    result = run(
        context,
        (
            P,
            ground("GroundConditional", P, property_claim),
            ground("GroundRelation", r, a, b),
            ground("GroundRelation", r, b, c),
        ),
    )
    assert result.status == "FIXED_POINT"
    assert {v.content for v in derived(result)} == {property_claim}


def test_b02_exact_constraint_scope_does_not_broaden(context):
    _, issuer, root = context
    x, s, t = (
        referent("participant", "X"),
        referent("state", "S"),
        referent("state", "T"),
    )
    cap1 = issuer.authorize_given(ground("GroundState", x, s), SCOPE, d("left"))
    cap2 = issuer.authorize_given(ground("GroundState", x, t), SCOPE, d("right"))
    other = ScopeIdentity("FORMAL", d("source"), d("other_scope"))
    constraint = issuer.authorize_constraint_given(
        ground("MutuallyExclusive", s, t), other, d("constraint")
    )
    auth = root.parent.admit(cap1)
    ledger = root.parent.ledger(auth)
    try:
        result = root.run(auth, 0, ledger, (cap1, cap2, constraint))
        assert result.status == "FIXED_POINT"
        assert not any(
            e.category == "CONSTRAINT_FINDING" for e in result.snapshot.entries
        )
    finally:
        close(root, auth, ledger)


def test_independent_support_survives_circular_alternative(context):
    result = run(context, (P, ground("GroundConditional", P, Q)))
    ask = derived(result)[0]
    record = next(
        e.payload for e in result.snapshot.entries if e.category == "DERIVATION_WITNESS"
    )
    conclusion = replace(ask, content=Z)
    circular = d(
        record.kind,
        *record.values[:3],
        tuple(sorted((*record.values[3], key(conclusion)))),
        *record.values[4:],
    )
    paths = {key(ask): (circular, record)}
    witness = parent_witness(
        ask,
        result.snapshot.binding,
        {},
        paths,
        record.values[2],
        conclusion,
        ReasoningPolicy(),
    )
    assert witness is not None and key(conclusion) not in witness[1]
    assert (
        parent_witness(
            ask,
            result.snapshot.binding,
            {},
            {key(ask): (circular,)},
            record.values[2],
            conclusion,
            ReasoningPolicy(),
        )
        is None
    )


@pytest.mark.parametrize("limit", ["frontier", "checks"])
def test_incomplete_semantic_group_has_no_partial_publication(context, limit):
    core = CoreEngine(CoreConfig(receptor_fanout=1))
    issuer = create_trusted_ingress_boundary(core, d("small_group", limit), d("source"))
    policy = (
        ReasoningPolicy(max_frontier=1)
        if limit == "frontier"
        else ReasoningPolicy(max_checks=1)
    )
    root = create_reasoning_runtime(issuer.invocation_causes, policy=policy)
    local = (core, issuer, root)
    kwargs = (
        {}
        if limit == "frontier"
        else {
            "constraints": (ground("FormalNegation", ground("GroundAtom", "Absent")),)
        }
    )
    result = run(
        local,
        (P, ground("GroundConditional", P, Q), ground("GroundConditional", P, Z)),
        **kwargs,
    )
    assert result.status == (
        "CAPACITY_ABORT" if limit == "frontier" else "CONSTRAINT_CHECK_INCOMPLETE"
    )
    assert not derived(result)
    assert len(result.assertions) == 3
    assert not any(
        e.category in ("CONSTRAINT_FINDING", "CLEARANCE_RECORD", "DERIVATION_WITNESS")
        for e in result.snapshot.entries
    )


@pytest.mark.parametrize("bound", [1, 2])
def test_assertion_capacity_is_prospective_not_postpublication(context, bound):
    core = CoreEngine(CoreConfig(receptor_fanout=1))
    issuer = create_trusted_ingress_boundary(
        core, d("assertion_cap", bound), d("source")
    )
    root = create_reasoning_runtime(
        issuer.invocation_causes, policy=ReasoningPolicy(max_assertions=bound)
    )
    result = run((core, issuer, root), (P, ground("GroundConditional", P, Q)))
    assert result.status == "CAPACITY_ABORT"
    assert len(result.assertions) == (0 if bound == 1 else 2)
    assert not derived(result)
    assert not any(
        e.category in ("DERIVATION_WITNESS", "CLEARANCE_RECORD")
        for e in result.snapshot.entries
    )


def test_real_internal_l2_result_enters_reasoning_without_strengthening(context):
    from dgca_lite import SurfaceEvent
    from dgca_lite.memory.integration import TrustedCoreAdapter
    from dgca_lite.memory.session import retrieve_internal

    core, issuer, root = context
    with issuer.core_transition():
        TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("internal"))
        receipt = TrustedCoreAdapter.process_event(
            core, SurfaceEvent.from_text("internal")
        ).receipt
    result_l2 = retrieve_internal(core, {receipt.learning_frontier[0]: 1.0})
    _, auth, ledger, caps = admit(context, (P,))
    before = engine_state(core)
    try:
        result = root.run(
            auth, 0, ledger, caps, internal_results=(result_l2,), branch=1
        )
        assert result.status == "FIXED_POINT"
        internal = [
            a for a in result.assertions if a.basis is AssertionBasis.INTERNAL_RETRIEVAL
        ]
        assert len(internal) == 1 and internal[0].dependencies
        assert internal[0].content.descriptor.kind == "InternalRetrievalStatement"
        assert not derived(result)
        assert engine_state(core) == before
        with pytest.raises(IngressAbort):
            issuer.formal_reasoning.accept(internal[0])
        with pytest.raises(IngressAbort):
            issuer.observations.accept(internal[0])
    finally:
        close(root, auth, ledger)


UNIT7_DETERMINISTIC_SCRIPT = """
import hashlib, sys
sys.path.insert(0,"src")
from dgca_lite import CoreEngine
from dgca_lite.cognition.identity import ScopeIdentity
from dgca_lite.cognition.ingress import create_trusted_ingress_boundary
from dgca_lite.cognition.reasoning.fab import d, ground
from dgca_lite.cognition.reasoning.runtime import create_reasoning_runtime
from dgca_lite.cognition.serialization import canonical_identity_bytes
p,q,z=(ground("GroundAtom",x) for x in ("P","Q","Z"))
issuer=create_trusted_ingress_boundary(CoreEngine(),d("seed_test"),d("source"))
scope=ScopeIdentity("FORMAL",d("source"),d("scope"))
claims=(p,ground("GroundConditional",p,q),ground("GroundConditional",q,z))
caps=tuple(issuer.authorize_given(v,scope,d("occurrence",i)) for i,v in enumerate(claims))
root=create_reasoning_runtime(issuer.invocation_causes)
auth=root.parent.admit(caps[0]);ledger=root.parent.ledger(auth)
result=root.run(auth,0,ledger,caps)
assert result.status=="FIXED_POINT"
print(canonical_identity_bytes(result.canonical_descriptor()).hex())
"""


UNIT7_MUTEX_DETERMINISTIC_SCRIPT = (
    UNIT7_DETERMINISTIC_SCRIPT.replace(
        "from dgca_lite.cognition.reasoning.fab import d, ground",
        "from dgca_lite.cognition.reasoning.fab import d, ground, referent",
    )
    .replace(
        'claims=(p,ground("GroundConditional",p,q),ground("GroundConditional",q,z))',
        'x=referent("participant",1); s,t=referent("state",1),referent("state","1"); '
        'claims=(ground("GroundState",x,s),ground("GroundState",x,t),ground("MutuallyExclusive",s,t))',
    )
    .replace(
        'caps=tuple(issuer.authorize_given(v,scope,d("occurrence",i)) for i,v in enumerate(claims))',
        "caps=tuple((issuer.authorize_constraint_given if i==2 else issuer.authorize_given)"
        '(v,scope,d("occurrence",i)) for i,v in enumerate(claims))',
    )
)


@pytest.mark.parametrize("seed", ["0", "1", "27", "123", "random"])
@pytest.mark.parametrize("case", ["inference", "mutual_exclusion"])
def test_independent_process_signature(seed, case):
    script = (
        UNIT7_DETERMINISTIC_SCRIPT
        if case == "inference"
        else UNIT7_MUTEX_DETERMINISTIC_SCRIPT
    )
    env = dict(
        os.environ,
        PYTHONHASHSEED=seed,
        PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"),
    )
    output = subprocess.run(
        [sys.executable, "-B", "-c", script],
        env=env,
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


def _isolated_context_test(function):
    """Do not consume the frozen whole-suite lifetime issuer-domain allowance.

    Parametrization stays in pytest; genuine runtime fixtures and fault injection
    run in an independent interpreter, without weakening any authority bound.
    """

    @wraps(function)
    def independent_process(**arguments):
        expressions = {}
        for name, value in arguments.items():
            if type(value) in (str, int):
                expressions[name] = repr(value)
            elif type(value) in (AssertionBasis, InferenceFamily):
                expressions[name] = f"ns[{type(value).__name__!r}][{value.name!r}]"
            else:
                raise TypeError("closed subprocess test parameter required")
        args = ", ".join(f"{name}={value}" for name, value in expressions.items())
        if args:
            args += ", "
        args += "context=ns['context'].__wrapped__()"
        if "monkeypatch" in inspect.signature(function).parameters:
            args += ", monkeypatch=patch"
        script = (
            "import runpy, pytest; "
            f"ns=runpy.run_path({str(Path(__file__).resolve())!r}); "
            "patch=pytest.MonkeyPatch(); "
            f"ns[{function.__name__!r}].__wrapped__({args}); patch.undo()"
        )
        output = subprocess.run(
            [sys.executable, "-B", "-c", script],
            env=dict(
                os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src")
            ),
            capture_output=True,
            text=True,
            check=False,
        )
        assert output.returncode == 0, output.stdout + output.stderr

    signature = inspect.signature(function)
    independent_process.__signature__ = signature.replace(
        parameters=tuple(
            p
            for name, p in signature.parameters.items()
            if name not in ("context", "monkeypatch")
        )
    )
    return independent_process


for _name, _function in tuple(globals().items()):
    if (
        _name.startswith("test_")
        and "context" in inspect.signature(_function).parameters
    ):
        globals()[_name] = _isolated_context_test(_function)
