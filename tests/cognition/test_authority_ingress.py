from __future__ import annotations

import copy
import gc
import os
import pickle
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, dataclass
from itertools import count
from pathlib import Path
from threading import Event

import pytest

from dgca_lite import CoreConfig, CoreEngine, SurfaceEvent
from dgca_lite.cognition import (
    AssertionBasis,
    AssertionSemanticKey,
    CanonicalDescriptor,
    ClaimContentID,
    DependencyKind,
    DependencyRootIdentity,
    ScopeIdentity,
    ValueLimits,
    canonical_identity_bytes,
)
from dgca_lite.cognition import assertions as assertions_module
from dgca_lite.cognition import ingress as ingress_module
from dgca_lite.cognition.assertions import (
    ActiveConstraintPremiseView,
    IngressAssertionView,
)
from dgca_lite.cognition.authority import (
    AssumptionIssuanceCapability,
    ExternalOccurrenceCapability,
    FormalConstraintOccurrenceCapability,
    FormalSourceOccurrenceCapability,
    IngressAbort,
)
from dgca_lite.cognition.ingress import (
    FormalConstraintIngress,
    FormalReasoningIngress,
    TrustedIngressIssuer,
    TrustedObservationAdapter,
    create_trusted_ingress_boundary,
)
from dgca_lite.cognition.types import FailureCode
from dgca_lite.memory.integration import TrustedCoreAdapter, TrustedRetrievalReceipt
from dgca_lite.memory.session import retrieve_after_core_event, retrieve_internal
from dgca_lite.memory.types import RetrievalResult
from dgca_lite.persistence import engine_state


def d(kind, *values):
    return CanonicalDescriptor(kind, values)


def claim(label="P"):
    return ClaimContentID(d("GroundAtom", label))


def formal_scope(label="main"):
    return ScopeIdentity("FORMAL", d("formal-source", "test"), d("scope", label))


runtime_names = count()


def boundary(capacity=128, core=None):
    core = CoreEngine(CoreConfig(receptor_fanout=1, K_R=32)) if core is None else core
    owner = create_trusted_ingress_boundary(
        core,
        d("test-runtime", next(runtime_names)),
        d("formal-source", "test"),
        capacity=capacity,
    )
    return core, owner


@dataclass(frozen=True)
class Context:
    core: CoreEngine
    owner: TrustedIngressIssuer
    given: FormalSourceOccurrenceCapability
    assumption: AssumptionIssuanceCapability
    constraint: FormalConstraintOccurrenceCapability
    observation: ExternalOccurrenceCapability


@pytest.fixture(scope="module")
def context():
    core, owner = boundary()
    given = owner.authorize_given(claim(), formal_scope(), d("formal-occurrence", 1))
    assumption = owner.authorize_assumption(
        claim("H"), formal_scope(), d("assumption-occurrence", 1)
    )
    constraint = owner.authorize_constraint_given(
        ClaimContentID(d("SingleValued", d("slot", "name"))),
        formal_scope(),
        d("constraint-occurrence", 1),
    )
    with owner.core_transition():
        trusted = TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("x"))
        observation = owner.authorize_core_observation(trusted.receipt, formal_scope())
    yield Context(core, owner, given, assumption, constraint, observation)
    owner.close()


CAPABILITY_TYPES = (
    ExternalOccurrenceCapability,
    FormalSourceOccurrenceCapability,
    AssumptionIssuanceCapability,
    FormalConstraintOccurrenceCapability,
)
HANDLE_TYPES = CAPABILITY_TYPES + (
    TrustedIngressIssuer,
    FormalReasoningIngress,
    FormalConstraintIngress,
    TrustedObservationAdapter,
)


@pytest.mark.parametrize("handle_type", HANDLE_TYPES)
def test_live_handles_are_not_publicly_constructible(handle_type):
    with pytest.raises(TypeError):
        handle_type()
    with pytest.raises(TypeError):
        handle_type(issuer_id="copied", issuance_revision=0)


@pytest.mark.parametrize("handle_type", CAPABILITY_TYPES)
def test_object_new_and_copied_fields_cannot_forge_capability(context, handle_type):
    forged = object.__new__(handle_type)
    description = context.owner.describe(context.given)
    for field in (
        "issuer_id",
        "runtime",
        "scope",
        "occurrence",
        "issuance_revision",
        "_seal",
    ):
        with pytest.raises(AttributeError):
            object.__setattr__(forged, field, getattr(description, field, object()))
    for ingress in (
        context.owner.formal_reasoning,
        context.owner.formal_constraints,
        context.owner.observations,
    ):
        with pytest.raises(IngressAbort):
            ingress.accept(forged)


@pytest.mark.parametrize(
    "handle_type",
    (
        TrustedIngressIssuer,
        FormalReasoningIngress,
        FormalConstraintIngress,
        TrustedObservationAdapter,
    ),
)
def test_object_new_cannot_forge_issuer_or_ingress(context, handle_type):
    forged = object.__new__(handle_type)
    with pytest.raises(IngressAbort):
        if handle_type is TrustedIngressIssuer:
            forged.authorize_given(claim(), formal_scope(), d("occurrence", "forged"))
        else:
            forged.accept(context.given)


@pytest.mark.parametrize(
    "token_name", ("given", "assumption", "constraint", "observation")
)
@pytest.mark.parametrize(
    "operation", (copy.copy, copy.deepcopy, pickle.dumps, canonical_identity_bytes)
)
def test_capability_copy_and_serialization_are_rejected(context, token_name, operation):
    with pytest.raises(TypeError):
        operation(getattr(context, token_name))


def test_issuer_and_adapters_cannot_be_copied_or_serialized(context):
    for handle in (
        context.owner,
        context.owner.formal_reasoning,
        context.owner.formal_constraints,
        context.owner.observations,
    ):
        for operation in (
            copy.copy,
            copy.deepcopy,
            pickle.dumps,
            canonical_identity_bytes,
        ):
            with pytest.raises(TypeError):
                operation(handle)


def test_nested_capabilities_and_live_lower_layer_handles_fail_closed(context):
    for value in (
        context.given,
        context.owner,
        context.owner.formal_reasoning,
        context.core,
    ):
        with pytest.raises(TypeError):
            d("nested", (d("safe"), (value,)))


def test_capability_subclasses_and_metaclass_hooks_cannot_forge_authority(context):
    class Meta(type):
        def __eq__(cls, other):
            raise AssertionError("metaclass equality executed")

        def __hash__(cls):
            raise AssertionError("metaclass hash executed")

    class Counterfeit(FormalSourceOccurrenceCapability, metaclass=Meta):
        pass

    forged = object.__new__(Counterfeit)
    object.__setattr__(forged, "issuer_id", "copied")
    with pytest.raises(IngressAbort):
        context.owner.formal_reasoning.accept(forged)


def test_descriptors_copied_views_and_basis_labels_are_not_capabilities(context):
    ingress = context.owner.formal_reasoning
    view = ingress.accept(context.given)
    descriptor = context.owner.describe(context.given)
    copied = pickle.loads(pickle.dumps(view))
    encoded = canonical_identity_bytes(descriptor.canonical_descriptor())
    for data in (
        descriptor,
        descriptor.canonical_descriptor(),
        encoded,
        copied,
        copied.semantic_key,
        copied.source_key,
        AssertionBasis.FORMAL_GIVEN,
        "FORMAL_GIVEN",
    ):
        with pytest.raises(IngressAbort):
            ingress.accept(data)
    assert copied == view
    assert copy.deepcopy(descriptor) == descriptor


def test_given_and_assumption_bases_have_exact_constructor_dependencies(context):
    given = context.owner.formal_reasoning.accept(context.given)
    assumed = context.owner.formal_reasoning.accept(context.assumption)
    assert given.semantic_key.basis is AssertionBasis.FORMAL_GIVEN
    assert given.semantic_key.dependencies == ()
    assert assumed.semantic_key.basis is AssertionBasis.FORMAL_ASSUMPTION
    assert len(assumed.semantic_key.dependencies) == 1
    assert assumed.semantic_key.dependencies[0].kind is DependencyKind.ASSUMPTION
    with pytest.raises(TypeError):
        context.owner.formal_reasoning.accept(
            context.assumption, basis=AssertionBasis.FORMAL_GIVEN
        )


def test_caller_constructed_basis_spoof_is_data_not_issued_authority(context):
    original = context.owner.formal_reasoning.accept(context.given)
    fake = IngressAssertionView(
        AssertionSemanticKey(
            claim("if P then Q"), AssertionBasis.FORMAL_GIVEN, formal_scope()
        ),
        original.source_key,
    )
    for adapter in (
        context.owner.formal_reasoning,
        context.owner.formal_constraints,
        context.owner.observations,
    ):
        with pytest.raises(IngressAbort):
            adapter.accept(fake)


def test_same_occurrence_replay_and_independent_equal_content_are_distinct():
    _, owner = boundary()
    try:
        content, scope, occurrence = claim(), formal_scope(), d("occurrence", 1)
        first = owner.authorize_given(content, scope, occurrence)
        status = owner.registry_status
        assert (
            owner.authorize_given(
                copy.deepcopy(content), copy.deepcopy(scope), copy.deepcopy(occurrence)
            )
            is first
        )
        assert owner.registry_status == status
        left, replay = (
            owner.formal_reasoning.accept(first),
            owner.formal_reasoning.accept(first),
        )
        assert left == replay
        assert left is not replay  # Fresh capability-free data, not a registry alias.
        second = owner.authorize_given(content, scope, d("occurrence", 2))
        right = owner.formal_reasoning.accept(second)
        assert left.semantic_key == right.semantic_key
        assert left.source_key != right.source_key
        assert len({left.source_key, replay.source_key, right.source_key}) == 2
    finally:
        owner.close()


@pytest.mark.parametrize("changed", ("content", "scope", "dependencies"))
def test_source_payload_and_scope_substitution_cannot_reuse_occurrence(changed):
    _, owner = boundary()
    try:
        content, scope, occurrence = claim(), formal_scope(), d("occurrence", 1)
        token = owner.authorize_given(content, scope, occurrence)
        status = owner.registry_status
        roots = ()
        if changed == "content":
            content = claim("Q")
        elif changed == "scope":
            scope = formal_scope("broader")
        else:
            roots = (
                DependencyRootIdentity(
                    DependencyKind.ASSUMPTION, d("issuer"), d("origin", 1)
                ),
            )
        with pytest.raises(IngressAbort) as caught:
            owner.authorize_given(content, scope, occurrence, dependencies=roots)
        assert caught.value.code is FailureCode.EFFECT_PAYLOAD_MISMATCH
        assert owner.registry_status == status
        assert owner.formal_reasoning.accept(token).semantic_key.content == claim()
    finally:
        owner.close()


def test_private_issuance_snapshots_do_not_alias_inputs_outputs_or_descriptors():
    _, owner = boundary()
    try:
        content, scope, occurrence = claim(), formal_scope(), d("occurrence", 1)
        token = owner.authorize_given(content, scope, occurrence)
        before = owner.formal_reasoning.accept(token).canonical_descriptor()
        object.__setattr__(content.descriptor, "values", ("mutated",))
        object.__setattr__(scope.descriptor, "values", ("broadened",))
        object.__setattr__(occurrence, "values", (999,))
        view = owner.formal_reasoning.accept(token)
        object.__setattr__(
            view.semantic_key, "basis", AssertionBasis.EXTERNAL_OBSERVATION
        )
        description = owner.describe(token)
        object.__setattr__(description.scope.descriptor, "values", ("tampered",))
        assert owner.formal_reasoning.accept(token).canonical_descriptor() == before
    finally:
        owner.close()


def test_revision_invalidation_is_monotonic_and_stale_replay_cannot_reissue():
    _, owner = boundary()
    try:
        first = owner.authorize_given(claim(), formal_scope(), d("occurrence", 1))
        assert owner.describe(first).issuance_revision == 0
        owner.invalidate()
        with pytest.raises(IngressAbort) as caught:
            owner.formal_reasoning.accept(first)
        assert caught.value.code is FailureCode.OWNER_AUTHORITY_STALE
        with pytest.raises(IngressAbort):
            owner.authorize_given(claim(), formal_scope(), d("occurrence", 1))
        second = owner.authorize_given(claim(), formal_scope(), d("occurrence", 2))
        assert owner.describe(second).issuance_revision == 1
        owner.invalidate()
        assert owner.registry_status == (2, 2, 128)
        with pytest.raises(IngressAbort):
            owner.describe(second)
    finally:
        owner.close()


def test_cross_runtime_core_and_equal_issuer_id_reuse_cannot_validate(context):
    core, other = boundary()
    try:
        for adapter in (
            other.formal_reasoning,
            other.formal_constraints,
            other.observations,
        ):
            for token in (
                context.given,
                context.assumption,
                context.constraint,
                context.observation,
            ):
                with pytest.raises(IngressAbort):
                    adapter.accept(token)
        duplicate_id = context.owner.describe(context.given).runtime
        with pytest.raises(IngressAbort):
            create_trusted_ingress_boundary(
                core, duplicate_id, d("formal-source", "test")
            )
        with pytest.raises(IngressAbort):
            create_trusted_ingress_boundary(
                context.core, d("new-domain"), d("formal-source", "test")
            )
    finally:
        other.close()


def test_terminal_owner_and_reused_runtime_identity_cannot_resurrect():
    core = CoreEngine()
    runtime = d("terminal-runtime", next(runtime_names))
    owner = create_trusted_ingress_boundary(core, runtime, d("formal-source", "test"))
    adapter = owner.formal_reasoning
    token = owner.authorize_given(claim(), formal_scope(), d("occurrence", 1))
    owner.close()
    for operation in (
        lambda: adapter.accept(token),
        lambda: owner.registry_status,
        lambda: create_trusted_ingress_boundary(
            core, runtime, d("formal-source", "test")
        ),
    ):
        with pytest.raises(IngressAbort):
            operation()
    replacement = create_trusted_ingress_boundary(
        core, d("replacement", next(runtime_names)), d("formal-source", "test")
    )
    try:
        with pytest.raises(IngressAbort):
            replacement.formal_reasoning.accept(token)
    finally:
        replacement.close()


def test_garbage_collected_issuer_does_not_leave_live_authority():
    _, owner = boundary()
    adapter = owner.formal_reasoning
    token = owner.authorize_given(claim(), formal_scope(), d("occurrence", 1))
    del owner
    gc.collect()
    with pytest.raises(IngressAbort):
        adapter.accept(token)


def test_fixed_occurrence_capacity_includes_invalidated_tombstones():
    _, owner = boundary(capacity=1)
    try:
        token = owner.authorize_given(claim(), formal_scope(), d("occurrence", 1))
        assert (
            owner.authorize_given(claim(), formal_scope(), d("occurrence", 1)) is token
        )
        with pytest.raises(IngressAbort) as caught:
            owner.authorize_given(claim(), formal_scope(), d("occurrence", 2))
        assert caught.value.code is FailureCode.CAPACITY_ABORT
        assert owner.registry_status == (0, 1, 1)
        owner.invalidate()
        with pytest.raises(IngressAbort):
            owner.authorize_given(claim(), formal_scope(), d("occurrence", 2))
        assert owner.registry_status == (1, 1, 1)
    finally:
        owner.close()


@pytest.mark.parametrize("capacity", (True, False, 0, -1, 1.0))
def test_capacity_requires_a_positive_exact_integer(capacity):
    with pytest.raises(ValueError):
        create_trusted_ingress_boundary(
            CoreEngine(), d("invalid-capacity"), d("source"), capacity=capacity
        )


def test_closed_data_validation_failure_publishes_no_issuance(monkeypatch):
    _, owner = boundary()
    try:
        before = owner.registry_status
        bad = claim()
        object.__setattr__(bad.descriptor, "values", ((object(),),))
        with pytest.raises(IngressAbort):
            owner.authorize_given(bad, formal_scope(), d("occurrence", 1))
        assert owner.registry_status == before

        def fail_snapshot(value):
            raise ValueError("injected snapshot failure")

        with monkeypatch.context() as patch:
            patch.setattr(ingress_module, "_snapshot", fail_snapshot)
            with pytest.raises(IngressAbort):
                owner.authorize_given(claim(), formal_scope(), d("occurrence", 1))
        assert owner.registry_status == before
        assert owner.authorize_given(claim(), formal_scope(), d("occurrence", 1))
    finally:
        owner.close()


@pytest.mark.parametrize("content", (claim("if P then Q"), claim("R is transitive")))
def test_formal_shape_or_retrieved_text_cannot_self_promote(context, content):
    for data in (content, content.descriptor, canonical_identity_bytes(content)):
        with pytest.raises(IngressAbort):
            context.owner.formal_reasoning.accept(data)
    # New external source authorization is the only lawful promotion path.
    token = context.owner.authorize_given(
        content, formal_scope(), d("independent-source", content)
    )
    assert (
        context.owner.formal_reasoning.accept(token).semantic_key.basis
        is AssertionBasis.FORMAL_GIVEN
    )


@pytest.mark.parametrize(
    "basis",
    (
        AssertionBasis.INTERNAL_RETRIEVAL,
        AssertionBasis.DERIVED,
        AssertionBasis.PREDICTION_VIEW,
        AssertionBasis.CAUSAL_RESULT_VIEW,
        AssertionBasis.HYPOTHETICAL,
        AssertionBasis.EXTERNAL_OBSERVATION,
    ),
)
def test_nonformal_data_cannot_activate_constraints(context, basis):
    data = AssertionSemanticKey(
        ClaimContentID(d("SingleValued", d("slot", 1))), basis, formal_scope()
    )
    with pytest.raises(IngressAbort):
        context.owner.formal_constraints.accept(data)
    with pytest.raises(TypeError):
        ActiveConstraintPremiseView(
            data.content, basis, data.scope, (), d("issuer"), d("occurrence")
        )


@pytest.mark.parametrize(
    "kind", ("FormalNegation", "MutuallyExclusive", "SingleValued")
)
def test_only_typed_authorized_constraint_premises_activate(kind):
    _, owner = boundary()
    try:
        if kind == "FormalNegation":
            content = ClaimContentID(d(kind, claim()))
        elif kind == "MutuallyExclusive":
            content = ClaimContentID(d(kind, d("state", "P"), d("state", "Q")))
        else:
            content = ClaimContentID(d(kind, d("slot", 1)))
        first = owner.authorize_constraint_given(
            content, formal_scope(), d("occurrence", 1)
        )
        assert (
            owner.authorize_constraint_given(
                content, formal_scope(), d("occurrence", 1)
            )
            is first
        )
        left = owner.formal_constraints.accept(first)
        second = owner.authorize_constraint_given(
            content, formal_scope(), d("occurrence", 2)
        )
        right = owner.formal_constraints.accept(second)
        assert left.semantic_key == right.semantic_key
        assert left.source_key != right.source_key
        assumed = owner.authorize_assumption(
            claim("H"), formal_scope(), d("assumption", 1)
        )
        conditional = owner.authorize_constraint_assumption(
            content, d("occurrence", 3), assumed
        )
        constraint = owner.formal_constraints.accept(conditional)
        parent = owner.formal_reasoning.accept(assumed)
        assert constraint.basis is AssertionBasis.FORMAL_ASSUMPTION
        assert constraint.dependencies == parent.semantic_key.dependencies
        assert constraint.scope == parent.semantic_key.scope
        assert constraint.semantic_key != left.semantic_key
        with pytest.raises(IngressAbort):
            owner.formal_reasoning.accept(first)
        with pytest.raises(IngressAbort):
            owner.formal_constraints.accept(assumed)
    finally:
        owner.close()


@pytest.mark.parametrize(
    "node",
    (
        d("text", "not P"),
        d("SingleValued", "slot"),
        d("FormalNegation", "P"),
        d("MutuallyExclusive", claim(), claim()),
        d("UnknownConstraint", claim()),
    ),
)
def test_ill_typed_lexical_and_self_exclusion_constraints_are_rejected(node):
    _, owner = boundary()
    try:
        with pytest.raises(IngressAbort):
            owner.authorize_constraint_given(
                ClaimContentID(node), formal_scope(), d("occurrence", 1)
            )
        assert owner.registry_status == (0, 0, 128)
    finally:
        owner.close()


def test_observation_requires_genuine_receipt_and_occurrence_is_not_content():
    core, owner = boundary()
    try:
        # Recruitment precedes activation in Core; warm up the one-receptor
        # structure before comparing two equal, independently accepted captures.
        with owner.core_transition():
            for _ in range(2):
                TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text(""))
        captures = []
        for _ in range(2):
            with owner.core_transition():
                trusted = TrustedCoreAdapter.process_event(
                    core, SurfaceEvent.from_text("")
                )
                token = owner.authorize_core_observation(
                    trusted.receipt, formal_scope()
                )
                assert (
                    owner.authorize_core_observation(trusted.receipt, formal_scope())
                    is token
                )
            captures.append(owner.observations.accept(token))
        assert captures[0].semantic_key == captures[1].semantic_key
        assert captures[0].source_key != captures[1].source_key
        assert captures[0].semantic_key.basis is AssertionBasis.EXTERNAL_OBSERVATION
        assert captures[0].semantic_key.dependencies == ()
        assert owner.registry_status == (0, 2, 128)
        with pytest.raises(IngressAbort):
            owner.observations.accept(trusted.receipt)
        with pytest.raises(IngressAbort):
            owner.authorize_core_observation(
                object.__new__(TrustedRetrievalReceipt), formal_scope()
            )
        with pytest.raises(TypeError):
            owner.authorize_core_observation(
                trusted.receipt, formal_scope(), content=claim("unrelated")
            )
    finally:
        owner.close()


def test_genuine_internal_and_trusted_l2_result_views_cannot_reenter_ingress():
    core, owner = boundary()
    try:
        with owner.core_transition():
            TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("x"))
            trusted = TrustedCoreAdapter.process_event(
                core, SurfaceEvent.from_text("x")
            )
            result = retrieve_after_core_event(core, trusted.receipt)
            internal = retrieve_internal(
                core, {cell_id: 1.0 for cell_id in trusted.receipt.learning_frontier}
            )
        assert type(result) is RetrievalResult and type(internal) is RetrievalResult
        copied_receipt = d(
            "receipt-fields",
            trusted.receipt.post_commit_version,
            trusted.receipt.post_commit_tick,
            trusted.receipt.root_id,
        )
        for data in (
            result,
            internal,
            result.root,
            copy.deepcopy(result.root),
            copied_receipt,
            trusted.tick_result,
        ):
            for adapter in (
                owner.observations,
                owner.formal_reasoning,
                owner.formal_constraints,
            ):
                with pytest.raises(IngressAbort):
                    adapter.accept(data)
            with pytest.raises(IngressAbort):
                owner.authorize_core_observation(data, formal_scope())
    finally:
        owner.close()


def test_stale_cross_core_and_torn_temporal_receipts_cannot_issue(monkeypatch):
    core, owner = boundary()
    other_core = CoreEngine()
    try:
        with owner.core_transition():
            other = TrustedCoreAdapter.process_event(
                other_core, SurfaceEvent.from_text("x")
            )
            with pytest.raises(IngressAbort):
                owner.authorize_core_observation(other.receipt, formal_scope())
            trusted = TrustedCoreAdapter.process_event(
                core, SurfaceEvent.from_text("x")
            )
            with monkeypatch.context() as patch:
                patch.setattr(core.temporal, "_next_root_id", 999)
                with pytest.raises(IngressAbort):
                    owner.authorize_core_observation(trusted.receipt, formal_scope())
            TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("y"))
            with pytest.raises(IngressAbort):
                owner.authorize_core_observation(trusted.receipt, formal_scope())
        assert owner.registry_status == (0, 0, 128)
    finally:
        owner.close()


def test_failed_core_event_cannot_create_observation_or_allocate_issuer_state(
    monkeypatch,
):
    core, owner = boundary()
    try:
        with owner.core_transition():
            TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("context"))
        before = engine_state(core)

        def fail_commit(transaction):
            raise ValueError("injected Core commit failure")

        monkeypatch.setattr(core.network, "commit", fail_commit)
        with owner.core_transition(), pytest.raises(ValueError, match="injected"):
            TrustedCoreAdapter.process_event(
                core, SurfaceEvent.from_text("failed"), boundary=True
            )
        assert engine_state(core) == before
        assert owner.registry_status == (0, 0, 128)
    finally:
        owner.close()


def test_ingress_and_authority_administration_preserve_complete_lower_layer_state(
    context,
):
    before = engine_state(context.core)
    for token, adapter in (
        (context.given, context.owner.formal_reasoning),
        (context.assumption, context.owner.formal_reasoning),
        (context.constraint, context.owner.formal_constraints),
        (context.observation, context.owner.observations),
    ):
        canonical_identity_bytes(adapter.accept(token).canonical_descriptor())
    assert engine_state(context.core) == before
    with pytest.raises(FrozenInstanceError):
        context.owner.formal_reasoning.accept(context.given).semantic_key = None


def test_concurrent_source_replay_has_one_linearized_registration():
    _, owner = boundary(capacity=1)
    try:

        def authorize(_):
            return owner.authorize_given(claim(), formal_scope(), d("occurrence", 1))

        with ThreadPoolExecutor(max_workers=4) as pool:
            tokens = list(pool.map(authorize, range(16)))
        assert all(token is tokens[0] for token in tokens)
        assert owner.registry_status == (0, 1, 1)
    finally:
        owner.close()


def test_currentness_validation_and_output_are_linearized_with_invalidation(
    monkeypatch,
):
    _, owner = boundary()
    token = owner.authorize_given(claim(), formal_scope(), d("occurrence", 1))
    entered, release, invalidating = Event(), Event(), Event()
    original = ingress_module._snapshot

    def paused(value):
        if value.kind == "IngressAssertionFields":
            entered.set()
            assert release.wait(5)
        return original(value)

    def invalidate():
        invalidating.set()
        owner.invalidate()

    try:
        with monkeypatch.context() as patch:
            patch.setattr(ingress_module, "_snapshot", paused)
            with ThreadPoolExecutor(max_workers=2) as pool:
                accepting = pool.submit(owner.formal_reasoning.accept, token)
                assert entered.wait(5)
                retiring = pool.submit(invalidate)
                assert invalidating.wait(5)
                assert not retiring.done()
                release.set()
                assert (
                    accepting.result(timeout=5).semantic_key.basis
                    is AssertionBasis.FORMAL_GIVEN
                )
                retiring.result(timeout=5)
        with pytest.raises(IngressAbort):
            owner.formal_reasoning.accept(token)
    finally:
        release.set()
        owner.close()


def test_runtime_audit_bound_and_nonrecycling_are_enforced_in_a_fresh_process():
    script = """
from dgca_lite import CoreEngine
from dgca_lite.cognition import CanonicalDescriptor
from dgca_lite.cognition.authority import IngressAbort
from dgca_lite.cognition.ingress import create_trusted_ingress_boundary
from dgca_lite.cognition.types import FailureCode
for index in range(64):
    owner = create_trusted_ingress_boundary(CoreEngine(), CanonicalDescriptor('runtime',(index,)), CanonicalDescriptor('source'))
    owner.close()
try:
    create_trusted_ingress_boundary(CoreEngine(), CanonicalDescriptor('runtime',(64,)), CanonicalDescriptor('source'))
except IngressAbort as error:
    assert error.code is FailureCode.CAPACITY_ABORT
else:
    raise AssertionError('runtime audit capacity not enforced')
print('64 domains bounded; terminal IDs do not recycle')
"""
    environment = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"),
    )
    output = subprocess.check_output(
        [sys.executable, "-B", "-c", script], env=environment, text=True
    )
    assert "64 domains bounded" in output


@pytest.mark.parametrize(
    "kind,arity", (("FormalNegation", 1), ("MutuallyExclusive", 2), ("SingleValued", 1))
)
def test_constraint_shape_outer_bound_precedes_member_validation(
    monkeypatch, kind, arity
):
    _, owner = boundary()
    marker = object()
    node = d(kind)
    object.__setattr__(node, "values", (marker,) * (arity + 1))
    # Bypass only the test input construction; the ingress must revalidate it.
    content = object.__new__(ClaimContentID)
    object.__setattr__(content, "descriptor", node)
    visits = []

    def guarded_type(value):
        if value is marker:
            visits.append(value)
            raise AssertionError("oversized constraint member inspected")
        return type(value)

    try:
        monkeypatch.setattr(assertions_module, "type", guarded_type, raising=False)
        with pytest.raises(IngressAbort):
            owner.authorize_constraint_given(
                content, formal_scope(), d("occurrence", 1)
            )
        assert visits == []
        assert owner.registry_status == (0, 0, 128)
    finally:
        owner.close()


def test_failed_bootstrap_publishes_no_handles_or_runtime_tombstone(monkeypatch):
    core = CoreEngine()
    runtime = d("bootstrap-retry", next(runtime_names))
    original = ingress_module.ref
    calls = 0

    def interrupted(value, *args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("injected registration failure")
        return original(value, *args)

    with monkeypatch.context() as patch:
        patch.setattr(ingress_module, "ref", interrupted)
        with pytest.raises(ValueError, match="injected"):
            create_trusted_ingress_boundary(core, runtime, d("formal-source", "test"))
    owner = create_trusted_ingress_boundary(core, runtime, d("formal-source", "test"))
    try:
        assert owner.registry_status == (0, 0, 128)
    finally:
        owner.close()


def test_dependent_formal_source_preserves_its_exact_authorized_dependencies():
    _, owner = boundary()
    try:
        assumed = owner.authorize_assumption(
            claim("H"), formal_scope(), d("assumption", 1)
        )
        roots = owner.formal_reasoning.accept(assumed).semantic_key.dependencies
        given = owner.authorize_given(
            claim("conditional"), formal_scope(), d("given", 1), dependencies=roots
        )
        constraint = owner.authorize_constraint_given(
            ClaimContentID(d("SingleValued", d("slot", 1))),
            formal_scope(),
            d("constraint", 1),
            dependencies=roots,
        )
        assert owner.formal_reasoning.accept(given).semantic_key.dependencies == roots
        assert owner.formal_constraints.accept(constraint).dependencies == roots
        descriptor = owner.describe(assumed)
        with pytest.raises(IngressAbort):
            owner.authorize_constraint_assumption(
                ClaimContentID(d("SingleValued", d("slot", 1))),
                d("constraint", 2),
                descriptor,
            )
    finally:
        owner.close()


def test_boolean_and_integer_occurrence_identity_do_not_alias():
    _, owner = boundary()
    try:
        first = owner.authorize_given(claim(), formal_scope(), d("occurrence", True))
        second = owner.authorize_given(claim(), formal_scope(), d("occurrence", 1))
        assert first is not second
        assert (
            owner.formal_reasoning.accept(first).source_key
            != owner.formal_reasoning.accept(second).source_key
        )
    finally:
        owner.close()


def test_snapshot_race_cannot_create_a_cycle_or_publish_partial_issuance(monkeypatch):
    _, owner = boundary()
    original = ingress_module.canonical_identity_bytes

    def mutate_after_validation(value):
        image = original(value)
        if type(value) is CanonicalDescriptor and value.kind == "IngressIssuance":
            object.__setattr__(value, "values", (value,))
        return image

    try:
        with monkeypatch.context() as patch:
            patch.setattr(
                ingress_module, "canonical_identity_bytes", mutate_after_validation
            )
            with pytest.raises(IngressAbort):
                owner.authorize_given(claim(), formal_scope(), d("occurrence", 1))
        assert owner.registry_status == (0, 0, 128)
    finally:
        owner.close()


def test_core_transition_barrier_covers_network_commit_and_temporal_publication(
    monkeypatch,
):
    core, owner = boundary()
    entered, release, capturing = Event(), Event(), Event()
    try:
        with owner.core_transition():
            previous = TrustedCoreAdapter.process_event(
                core, SurfaceEvent.from_text("context")
            )
        original = core.temporal.publish

        def paused(transaction):
            entered.set()
            assert release.wait(5)
            original(transaction)

        def transition():
            with owner.core_transition():
                return TrustedCoreAdapter.process_event(
                    core, SurfaceEvent.from_text("next")
                )

        def capture():
            capturing.set()
            return owner.authorize_core_observation(previous.receipt, formal_scope())

        with monkeypatch.context() as patch:
            patch.setattr(core.temporal, "publish", paused)
            with ThreadPoolExecutor(max_workers=2) as pool:
                updating = pool.submit(transition)
                assert entered.wait(5)
                accepting = pool.submit(capture)
                assert capturing.wait(5)
                assert not accepting.done()
                release.set()
                updating.result(timeout=5)
                with pytest.raises(IngressAbort):
                    accepting.result(timeout=5)
        assert owner.registry_status == (0, 0, 128)
    finally:
        release.set()
        owner.close()


def test_inflight_adapter_pins_issuer_until_gc_retirement_is_safe(monkeypatch):
    _, owner = boundary()
    adapter = owner.formal_reasoning
    token = owner.authorize_given(claim(), formal_scope(), d("occurrence", 1))
    entered, release = Event(), Event()
    original = ingress_module._snapshot

    def paused(value):
        if value.kind == "IngressAssertionFields":
            entered.set()
            assert release.wait(5)
        return original(value)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(ingress_module, "_snapshot", paused)
            with ThreadPoolExecutor(max_workers=1) as pool:
                accepting = pool.submit(adapter.accept, token)
                assert entered.wait(5)
                del owner
                gc.collect()
                release.set()
                assert (
                    accepting.result(timeout=5).semantic_key.basis
                    is AssertionBasis.FORMAL_GIVEN
                )
        gc.collect()
        with pytest.raises(IngressAbort):
            adapter.accept(token)
    finally:
        release.set()


UNIT2_DETERMINISTIC_SCRIPT = """
from dgca_lite import CoreEngine
from dgca_lite.cognition import *
from dgca_lite.cognition.ingress import create_trusted_ingress_boundary
def d(kind,*values): return CanonicalDescriptor(kind,values)
scope = ScopeIdentity('FORMAL',d('source',1),d('scope',1))
owner = create_trusted_ingress_boundary(CoreEngine(),d('runtime',1),d('source',1))
views = []
for name in {'alpha','beta','gamma'}:
    token = owner.authorize_given(ClaimContentID(d('GroundAtom','P')),scope,d('occurrence',name))
    views.append(owner.formal_reasoning.accept(token).canonical_descriptor())
views.sort(key=canonical_identity_bytes)
print(canonical_identity_bytes(tuple(views)).hex())
print(identity_digest(tuple(views)))
owner.close()
"""


def test_authorized_views_ignore_hash_seed_and_source_insertion_order():
    results = []
    for seed in ("0", "1", "27", "123", "random"):
        environment = dict(
            os.environ,
            PYTHONHASHSEED=seed,
            PYTHONDONTWRITEBYTECODE="1",
            PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"),
        )
        results.append(
            subprocess.check_output(
                [sys.executable, "-B", "-c", UNIT2_DETERMINISTIC_SCRIPT],
                env=environment,
                text=True,
            )
        )
    assert len(set(results)) == 1


@pytest.mark.parametrize(
    "target_type",
    (
        AssumptionIssuanceCapability,
        ExternalOccurrenceCapability,
        FormalConstraintOccurrenceCapability,
    ),
)
def test_genuine_handle_class_swap_cannot_change_its_issued_authority(
    context, target_type
):
    token = context.given
    original = context.owner.formal_reasoning.accept(token).canonical_descriptor()
    before = context.owner.registry_status
    with pytest.raises(AttributeError):
        token.__class__ = target_type
    try:
        object.__setattr__(token, "__class__", target_type)
        with pytest.raises(IngressAbort):
            context.owner.describe(token)
        for adapter in (
            context.owner.formal_reasoning,
            context.owner.formal_constraints,
            context.owner.observations,
        ):
            with pytest.raises(IngressAbort):
                adapter.accept(token)
        with pytest.raises(IngressAbort):
            context.owner.authorize_constraint_assumption(
                ClaimContentID(d("SingleValued", d("slot", 1))),
                d("class-swap", 1),
                token,
            )
    finally:
        object.__setattr__(token, "__class__", FormalSourceOccurrenceCapability)
    assert context.owner.registry_status == before
    assert (
        context.owner.formal_reasoning.accept(token).canonical_descriptor() == original
    )


def test_genuine_adapter_class_swap_does_not_create_an_issuer(context):
    adapter = context.owner.formal_reasoning
    try:
        object.__setattr__(adapter, "__class__", TrustedIngressIssuer)
        with pytest.raises(IngressAbort):
            adapter.authorize_given(
                claim("Q"), formal_scope(), d("adapter-as-issuer", 1)
            )
    finally:
        object.__setattr__(adapter, "__class__", FormalReasoningIngress)
    assert (
        adapter.accept(context.given).semantic_key.basis is AssertionBasis.FORMAL_GIVEN
    )


def test_even_authority_free_assumption_views_cannot_omit_mandatory_root(context):
    given = context.owner.formal_reasoning.accept(context.given)
    with pytest.raises(ValueError, match="assumption dependency"):
        IngressAssertionView(
            AssertionSemanticKey(
                claim("H"), AssertionBasis.FORMAL_ASSUMPTION, formal_scope()
            ),
            given.source_key,
        )
    with pytest.raises(ValueError, match="assumption dependency"):
        ActiveConstraintPremiseView(
            ClaimContentID(d("SingleValued", d("slot", 1))),
            AssertionBasis.FORMAL_ASSUMPTION,
            formal_scope(),
            (),
            d("source"),
            d("occurrence", 1),
        )


def test_issuance_invalidation_and_terminal_retirement_conserve_complete_core_state():
    core, owner = boundary()
    with owner.core_transition():
        TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("context"))
        trusted = TrustedCoreAdapter.process_event(
            core, SurfaceEvent.from_text("context")
        )
    before = engine_state(core)
    given = owner.authorize_given(claim(), formal_scope(), d("given", 1))
    assumption = owner.authorize_assumption(
        claim("H"), formal_scope(), d("assumption", 1)
    )
    constraint = owner.authorize_constraint_assumption(
        ClaimContentID(d("SingleValued", d("slot", 1))), d("constraint", 1), assumption
    )
    observation = owner.authorize_core_observation(trusted.receipt, formal_scope())
    adapters = (owner.formal_reasoning, owner.formal_constraints, owner.observations)
    views = (
        adapters[0].accept(given),
        adapters[1].accept(constraint),
        adapters[2].accept(observation),
    )
    serialized = tuple(
        canonical_identity_bytes(view.canonical_descriptor()) for view in views
    )
    owner.describe(given)
    owner.invalidate()
    owner.close()
    assert engine_state(core) == before
    assert (
        tuple(canonical_identity_bytes(view.canonical_descriptor()) for view in views)
        == serialized
    )
    for adapter, token in zip(adapters, (given, constraint, observation), strict=True):
        with pytest.raises(IngressAbort):
            adapter.accept(token)


def test_snapshot_shared_bound_includes_schema_metadata_before_member_inspection(
    monkeypatch,
):
    value = d("snapshot-bound")
    marker = object()
    original = ingress_module.canonical_identity_bytes
    inspected = []

    def replace_after_validation(item):
        encoded = original(item)
        if item is value:
            object.__setattr__(value, "values", (marker,) * 251)
        return encoded

    def guarded_type(item):
        if item is marker:
            inspected.append(item)
            raise AssertionError("over-bound snapshot member inspected")
        return type(item)

    monkeypatch.setattr(
        ingress_module, "DEFAULT_VALUE_LIMITS", ValueLimits(max_nodes=256)
    )
    monkeypatch.setattr(
        ingress_module, "canonical_identity_bytes", replace_after_validation
    )
    monkeypatch.setattr(ingress_module, "type", guarded_type, raising=False)
    with pytest.raises(ValueError, match="tuple exceeds"):
        ingress_module._snapshot(value)
    assert inspected == []


def test_replacement_runtime_cannot_reauthorize_same_core_occurrence_as_new_source():
    core, first = boundary()
    with first.core_transition():
        trusted = TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("x"))
        old_capability = first.authorize_core_observation(
            trusted.receipt, formal_scope()
        )
    old_view = first.observations.accept(old_capability)
    first.close()
    _, replacement = boundary(core=core)
    try:
        with pytest.raises(IngressAbort) as caught:
            replacement.authorize_core_observation(trusted.receipt, formal_scope())
        assert caught.value.code is FailureCode.OWNER_AUTHORITY_STALE
        assert replacement.registry_status == (0, 0, 128)
        with pytest.raises(IngressAbort):
            replacement.observations.accept(old_capability)
        with replacement.core_transition():
            new_event = TrustedCoreAdapter.process_event(
                core, SurfaceEvent.from_text("x")
            )
            new_capability = replacement.authorize_core_observation(
                new_event.receipt, formal_scope()
            )
        new_view = replacement.observations.accept(new_capability)
        assert new_view.source_key != old_view.source_key
        assert (
            replacement.authorize_core_observation(new_event.receipt, formal_scope())
            is new_capability
        )
    finally:
        replacement.close()


def test_failed_observation_issuance_does_not_publish_a_core_occurrence_watermark():
    core, first = boundary(capacity=1)
    first.authorize_given(claim(), formal_scope(), d("occupied", 1))
    with first.core_transition():
        trusted = TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("x"))
        with pytest.raises(IngressAbort) as caught:
            first.authorize_core_observation(trusted.receipt, formal_scope())
        assert caught.value.code is FailureCode.CAPACITY_ABORT
    first.close()
    _, replacement = boundary(core=core)
    try:
        # The receipt is genuine and was never authorized by the failed issuer.
        capability = replacement.authorize_core_observation(
            trusted.receipt, formal_scope()
        )
        assert (
            replacement.observations.accept(capability).semantic_key.basis
            is AssertionBasis.EXTERNAL_OBSERVATION
        )
    finally:
        replacement.close()


def test_issuer_class_tampering_invalidates_child_validation_until_restored(context):
    adapter = context.owner.formal_reasoning
    try:
        object.__setattr__(context.owner, "__class__", FormalReasoningIngress)
        with pytest.raises(IngressAbort):
            adapter.accept(context.given)
    finally:
        object.__setattr__(context.owner, "__class__", TrustedIngressIssuer)
    assert (
        adapter.accept(context.given).semantic_key.basis is AssertionBasis.FORMAL_GIVEN
    )
