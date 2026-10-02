from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import FrozenInstanceError, dataclass
from datetime import UTC, datetime
from enum import Enum
from itertools import permutations
from pathlib import Path
from threading import Lock
from uuid import UUID

import pytest

from dgca_lite.cognition import (
    AssertionBasis,
    AssertionSemanticKey,
    CanonicalDescriptor,
    ClaimContentID,
    DependencyKind,
    DependencyRootIdentity,
    ScopeIdentity,
    SourceAssertionKey,
    ValueLimits,
    canonical_identity_bytes,
    identity_digest,
)
from dgca_lite.cognition import identity as identity_module
from dgca_lite.cognition import serialization as serialization_module
from dgca_lite.cognition.contracts import (
    CONTROL_PLANE_ALLOWLIST,
    ConstraintFamily,
    InferenceFamily,
)
from dgca_lite.cognition.identity import (
    _RECORD_SCHEMAS,
    ActiveEpistemicContextIdentity,
    CIEBinding,
    CIEIdentity,
    CognitiveEnvironmentBinding,
    ConstraintEnvironmentBinding,
    CoreStateBinding,
    DerivationContextBinding,
    InvocationCauseID,
    SnapshotBinding,
    _CanonicalData,
    canonical_dependencies,
    canonical_descriptor_set,
)
from dgca_lite.cognition.types import (
    BudgetSourceKind,
    CaptureState,
    ForecastStatus,
    InvocationState,
    WorkEffectClass,
)
from dgca_lite.engine import CoreEngine
from dgca_lite.memory.integration import TrustedCoreAdapter
from dgca_lite.model import SurfaceEvent
from dgca_lite.persistence import engine_state


def descriptor(kind: str, *values: object) -> CanonicalDescriptor:
    return CanonicalDescriptor(kind, values)


def scope(kind: str = "FORMAL") -> ScopeIdentity:
    return ScopeIdentity(kind, descriptor("source", 1), descriptor("scope", 1))


def dependency(kind: DependencyKind = DependencyKind.PREDICTION, occurrence=1):
    return DependencyRootIdentity(
        kind, descriptor("origin", 1), descriptor("occurrence", occurrence)
    )


def cie_binding(sequence=0, revision=0, version=1) -> CIEBinding:
    core = CoreStateBinding(
        descriptor("core", 1), version, 1, 2, descriptor("core-policy", "v0.4")
    )
    environment = CognitiveEnvironmentBinding(
        core, descriptor("memory-policy", "v0.4"), descriptor("cognition-policy", 1)
    )
    cause = InvocationCauseID(descriptor("issuer", 1), descriptor("occurrence", 1))
    return CIEBinding(CIEIdentity(cause, sequence), revision, environment)


def test_closed_canonical_families_and_allowlist() -> None:
    assert len(AssertionBasis) == 8
    assert len(InferenceFamily) == 2
    assert len(ConstraintFamily) == 3
    assert {item.value for item in CONTROL_PLANE_ALLOWLIST} == {
        "READ_IMMUTABLE_LIFECYCLE_FLAG",
        "RETIRE_UNUSED_CHARGE_UNITS",
        "RELEASE_TERMINAL_REGISTRY_CAPACITY",
        "ATTACH_ALREADY_PRODUCED_DESCRIPTOR",
        "CANONICAL_COMPARE_WITHIN_ALREADY_CHARGED_PARENT_WORK",
        "AUTHORITY_REDUCING_LIFECYCLE_BOOKKEEPING",
    }
    assert {item.value for item in CaptureState} == {
        "CAPTURED",
        "PROVEN_EMPTY",
        "OBSERVATION_GAP",
    }
    assert len(ForecastStatus) == 8
    assert tuple(item.value for item in InvocationState) == (
        "ACTIVE",
        "CLOSING",
        "CLOSED",
    )
    assert len(BudgetSourceKind) == 3
    assert len(WorkEffectClass) == 2


@pytest.mark.parametrize("basis", tuple(AssertionBasis))
def test_basis_changes_assertion_identity_not_content(basis) -> None:
    content = ClaimContentID(descriptor("ground-content", "P"))
    assertion = AssertionSemanticKey(content, basis, scope())
    assert assertion.content == content
    assert assertion != AssertionSemanticKey(
        content,
        AssertionBasis.DERIVED
        if basis is not AssertionBasis.DERIVED
        else AssertionBasis.FORMAL_GIVEN,
        scope(),
    )


def test_scope_kind_and_source_occurrence_remain_distinct() -> None:
    assert scope("FORMAL") != scope("REPLAY")
    issuer = descriptor("issuer", 1)
    first = SourceAssertionKey("FORMAL", issuer, descriptor("occurrence", 1))
    assert first == SourceAssertionKey("FORMAL", issuer, descriptor("occurrence", 1))
    assert first != SourceAssertionKey("FORMAL", issuer, descriptor("occurrence", 2))
    assert first != SourceAssertionKey(
        "OBSERVATION", issuer, descriptor("occurrence", 1)
    )


def test_dependency_set_is_canonical_and_idempotent() -> None:
    first, second = dependency(occurrence=1), dependency(occurrence=2)
    left = AssertionSemanticKey(
        ClaimContentID(descriptor("content", "P")),
        AssertionBasis.PREDICTION_VIEW,
        scope(),
        (second, first, first),
    )
    right = AssertionSemanticKey(left.content, left.basis, left.scope, (first, second))
    assert left == right
    assert len(left.dependencies) == 2
    assert left != AssertionSemanticKey(left.content, left.basis, left.scope, ())


def test_dependency_kind_is_part_of_exact_identity() -> None:
    assert dependency(DependencyKind.PREDICTION) != dependency(
        DependencyKind.CAUSAL_RESULT
    )


@pytest.mark.parametrize("changed", ["sequence", "revision", "version"])
def test_cie_binding_includes_each_currentness_dimension(changed) -> None:
    baseline = cie_binding()
    values = {"sequence": 0, "revision": 0, "version": 1}
    values[changed] += 1
    assert baseline != cie_binding(**values)


def test_snapshot_and_derivation_context_bind_exact_schema_and_aec() -> None:
    cie = cie_binding()
    assert SnapshotBinding(cie, 0, 0) != SnapshotBinding(cie, 0, 1)
    aec = ActiveEpistemicContextIdentity(descriptor("branch", 0), (dependency(),), cie)
    environment = ConstraintEnvironmentBinding(
        cie, (descriptor("schema", "ground-negation"),), (), descriptor("policy", 1)
    )
    first = DerivationContextBinding(aec, environment, descriptor("schema", "MP"))
    assert first != DerivationContextBinding(
        aec, environment, descriptor("schema", "TRANSITIVE")
    )
    other_aec = ActiveEpistemicContextIdentity(
        descriptor("branch", 1), aec.dependencies, cie
    )
    assert first != DerivationContextBinding(
        other_aec, environment, first.consumer_schema
    )


def test_constraint_environment_set_identity_is_order_independent_and_idempotent() -> (
    None
):
    cie, policy = cie_binding(), descriptor("policy", 1)
    first, second = descriptor("schema", 1), descriptor("schema", 2)
    left = ConstraintEnvironmentBinding(
        cie, (second, first, first), (second, first), policy
    )
    right = ConstraintEnvironmentBinding(cie, (first, second), (first, second), policy)
    assert left == right
    assert len(left.schema_set) == 2


def test_constraint_set_mutation_cannot_bypass_canonical_ordering() -> None:
    environment = ConstraintEnvironmentBinding(
        cie_binding(), (), (), descriptor("policy")
    )
    member = descriptor("constraint", 1)
    object.__setattr__(environment, "active_constraint_set", (member, member))
    with pytest.raises(ValueError, match="noncanonical"):
        canonical_identity_bytes(environment)


@pytest.mark.parametrize("value", [None, True, 0, -1, 1.5, "λ", b"\x00", (1, "x")])
def test_scalar_and_tuple_serialization_is_deterministic(value) -> None:
    assert canonical_identity_bytes(value) == canonical_identity_bytes(value)
    assert len(identity_digest(value)) == 64


@pytest.mark.parametrize("left,right", [(True, 1), (1, 1.0), ("x", b"x"), (0.0, -0.0)])
def test_exact_type_and_binary64_bits_cannot_alias(left, right) -> None:
    assert descriptor("value", left) != descriptor("value", right)
    assert canonical_identity_bytes(left) != canonical_identity_bytes(right)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_values_fail_closed(value) -> None:
    with pytest.raises(ValueError):
        descriptor("value", value)


@pytest.mark.parametrize("value", [[], {}, set(), bytearray(b"x"), object()])
def test_unknown_or_mutable_nested_values_fail_closed(value) -> None:
    with pytest.raises(TypeError):
        descriptor("outer", (("nested", value),))


def test_arbitrary_dataclasses_enums_and_primitive_subclasses_are_rejected() -> None:
    @dataclass(frozen=True)
    class CounterfeitCapability:
        identity: int = 1

    class UnknownEnum(Enum):
        VALUE = "FORMAL_GIVEN"

    class StringSubclass(str):
        pass

    for value in (CounterfeitCapability(), UnknownEnum.VALUE, StringSubclass("x")):
        with pytest.raises(TypeError):
            canonical_identity_bytes(value)


def test_unknown_objects_are_not_interpreted_through_hooks() -> None:
    class Trap:
        def __str__(self):
            raise AssertionError("string hook executed")

        def __iter__(self):
            raise AssertionError("iterator executed")

    with pytest.raises(TypeError):
        descriptor("nested", Trap())
    with pytest.raises(TypeError):
        canonical_dependencies(Trap())


def test_type_allowlist_does_not_execute_custom_metaclass_equality_or_hash() -> None:
    class TrapMeta(type):
        def __eq__(cls, other):
            raise AssertionError("metaclass comparison executed")

        def __hash__(cls):
            raise AssertionError("metaclass hash executed")

    class CounterfeitCapability(metaclass=TrapMeta):
        pass

    with pytest.raises(TypeError):
        canonical_identity_bytes(CounterfeitCapability())


def test_frozen_and_constructor_bypass_does_not_skip_validation() -> None:
    value = descriptor("frozen", 1)
    with pytest.raises(FrozenInstanceError):
        value.values = ()  # type: ignore[misc]
    object.__setattr__(value, "values", (object(),))
    with pytest.raises(TypeError):
        canonical_identity_bytes(value)
    incomplete = object.__new__(CanonicalDescriptor)
    with pytest.raises(ValueError):
        canonical_identity_bytes(incomplete)
    binding = cie_binding().environment.core_state
    object.__setattr__(binding, "tick", True)
    with pytest.raises(TypeError):
        canonical_identity_bytes(binding)


def test_cycle_and_noncanonical_dependency_mutation_are_rejected() -> None:
    value = descriptor("cycle")
    object.__setattr__(value, "values", (value,))
    with pytest.raises(ValueError, match="cyclic"):
        canonical_identity_bytes(value)
    assertion = AssertionSemanticKey(
        ClaimContentID(descriptor("content", "P")), AssertionBasis.DERIVED, scope()
    )
    root = dependency()
    object.__setattr__(assertion, "dependencies", (root, root))
    with pytest.raises(ValueError, match="noncanonical"):
        canonical_identity_bytes(assertion)


@pytest.mark.parametrize("field", ["max_nodes", "max_depth", "max_scalar_bytes"])
@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_value_limits_reject_invalid_mechanical_bounds(field, value) -> None:
    with pytest.raises(ValueError):
        ValueLimits(**{field: value})


def test_complete_node_depth_and_byte_bounds_never_truncate() -> None:
    assert canonical_identity_bytes((1, 2), ValueLimits(max_nodes=3))
    with pytest.raises(ValueError):
        canonical_identity_bytes((1, 2), ValueLimits(max_nodes=2))
    assert canonical_identity_bytes(((1,),), ValueLimits(max_depth=2))
    with pytest.raises(ValueError):
        canonical_identity_bytes(((1,),), ValueLimits(max_depth=1))
    assert canonical_identity_bytes("λ", ValueLimits(max_scalar_bytes=2))
    with pytest.raises(ValueError):
        canonical_identity_bytes("λ", ValueLimits(max_scalar_bytes=1))
    with pytest.raises(ValueError):
        canonical_identity_bytes(1 << 1_000_000)


def test_dependency_validation_uses_a_complete_aggregate_bound() -> None:
    roots = (dependency(occurrence=1), dependency(occurrence=2))
    with pytest.raises(ValueError):
        canonical_dependencies(roots, ValueLimits(max_nodes=15))
    with pytest.raises(TypeError):
        canonical_dependencies(iter(roots))
    with pytest.raises(TypeError):
        canonical_dependencies((descriptor("counterfeit-root"),))


def test_serialization_rejects_oversized_dependency_tuple_before_traversal() -> None:
    assertion = AssertionSemanticKey(
        ClaimContentID(descriptor("content", "P")), AssertionBasis.DERIVED, scope()
    )
    object.__setattr__(assertion, "dependencies", (dependency(),) * 30)
    with pytest.raises(ValueError, match="tuple identity exceeds"):
        canonical_identity_bytes(assertion, ValueLimits(max_nodes=20))


def test_serialization_rejects_oversized_constraint_tuple_before_traversal() -> None:
    environment = ConstraintEnvironmentBinding(
        cie_binding(), (), (), descriptor("policy", 1)
    )
    object.__setattr__(
        environment, "active_constraint_set", (descriptor("constraint"),) * 30
    )
    with pytest.raises(ValueError, match="tuple identity exceeds"):
        canonical_identity_bytes(environment, ValueLimits(max_nodes=20))


def test_canonical_record_schema_has_no_registration_or_mutation_path() -> None:
    with pytest.raises(TypeError):
        _RECORD_SCHEMAS[object] = ()  # type: ignore[index]


def test_index_hash_collision_cannot_collapse_distinct_descriptors(monkeypatch) -> None:
    monkeypatch.setattr(_CanonicalData, "__hash__", lambda self: 0)
    first, second = descriptor("identity", 1), descriptor("identity", 2)
    lookup = {first: "first", second: "second"}
    assert len(lookup) == 2
    assert lookup[first] == "first"
    assert lookup[second] == "second"


def test_hash_seed_does_not_change_canonical_serialization() -> None:
    script = (
        "from dgca_lite.cognition import CanonicalDescriptor, identity_digest;"
        "print(identity_digest(CanonicalDescriptor('sample', (True, 1, -0.0, 'λ'))))"
    )
    results = []
    for seed in ("1", "27", "random"):
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = seed
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
        results.append(
            subprocess.check_output(
                [sys.executable, "-B", "-c", script], env=environment
            )
        )
    assert len(set(results)) == 1


def test_foundation_conserves_complete_lower_layer_state() -> None:
    core = CoreEngine()
    core.process_event(SurfaceEvent.from_text("foundation"))
    before = engine_state(core)
    roots = (dependency(DependencyKind.INTERNAL_RETRIEVAL),)
    assertion = AssertionSemanticKey(
        ClaimContentID(descriptor("content", "P")),
        AssertionBasis.INTERNAL_RETRIEVAL,
        scope(),
        roots,
    )
    canonical_identity_bytes(assertion)
    identity_digest(assertion)
    with pytest.raises(TypeError):
        descriptor("forbidden-core", core)
    assert engine_state(core) == before


def test_genuine_lower_layer_receipt_cannot_hide_in_a_cognitive_descriptor() -> None:
    core = CoreEngine()
    event = TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("receipt"))
    before = engine_state(core)
    with pytest.raises(TypeError):
        descriptor("nested-provenance", (descriptor("safe"), (event.receipt,)))
    assert engine_state(core) == before


def guard_member_inspection(monkeypatch, member) -> list[object]:
    """Instrument even type inspection: unknown objects have no traversal hooks."""
    inspections = []

    def guarded_type(value):
        if value is member:
            inspections.append(value)
            raise AssertionError("oversized container member inspected")
        return type(value)

    monkeypatch.setattr(identity_module, "type", guarded_type, raising=False)
    monkeypatch.setattr(serialization_module, "type", guarded_type, raising=False)
    return inspections


@pytest.mark.parametrize(
    "canonicalizer", [canonical_dependencies, canonical_descriptor_set]
)
def test_set_outer_node_is_charged_before_semantic_member_validation(
    monkeypatch, canonicalizer
) -> None:
    marker = object()
    inspections = guard_member_inspection(monkeypatch, marker)
    with pytest.raises(ValueError, match="set exceeds node bound"):
        canonicalizer((marker,) * 4, ValueLimits(max_nodes=4))
    assert inspections == []
    # Rejecting an oversized set must not weaken its under-bound member schema.
    monkeypatch.undo()
    with pytest.raises(TypeError):
        canonicalizer((marker,), ValueLimits(max_nodes=4))


@pytest.mark.parametrize("nested", [False, True])
def test_plain_tuple_bound_precedes_any_member_inspection(monkeypatch, nested) -> None:
    marker = object()
    value = ((marker,) * 4,) if nested else (marker,) * 4
    inspections = guard_member_inspection(monkeypatch, marker)
    with pytest.raises(ValueError, match="tuple exceeds"):
        canonical_identity_bytes(value, ValueLimits(max_nodes=4))
    assert inspections == []


def container_record(field: str):
    if field == "values":
        return descriptor("record"), "values"
    if field == "assertion_dependencies":
        return (
            AssertionSemanticKey(
                ClaimContentID(descriptor("content", "P")),
                AssertionBasis.DERIVED,
                scope(),
            ),
            "dependencies",
        )
    if field == "aec_dependencies":
        return (
            ActiveEpistemicContextIdentity(descriptor("branch"), (), cie_binding()),
            "dependencies",
        )
    return (
        ConstraintEnvironmentBinding(cie_binding(), (), (), descriptor("policy")),
        field,
    )


CONTAINER_FIELDS = (
    "values",
    "assertion_dependencies",
    "aec_dependencies",
    "schema_set",
    "active_constraint_set",
)


@pytest.mark.parametrize("field", CONTAINER_FIELDS)
@pytest.mark.parametrize("size", [255, 251])
def test_record_container_bounds_precede_type_inspection_even_after_prior_work(
    monkeypatch, field, size
) -> None:
    record, field_name = container_record(field)
    marker = object()
    object.__setattr__(record, field_name, (marker,) * size)
    inspections = guard_member_inspection(monkeypatch, marker)
    # 255 is rejected by the preliminary record bound; 251 is initially
    # admissible, but exceeds the remaining budget after earlier fields.
    with pytest.raises(ValueError, match="tuple.*exceeds"):
        canonical_identity_bytes(record, ValueLimits(max_nodes=256))
    assert inspections == []
    monkeypatch.undo()
    object.__setattr__(record, field_name, (marker,))
    with pytest.raises(TypeError):
        canonical_identity_bytes(record)


@pytest.mark.parametrize("field", CONTAINER_FIELDS)
def test_constructor_rejects_outer_oversize_before_members(monkeypatch, field) -> None:
    record, field_name = container_record(field)
    marker = object()
    parameters = {
        name: getattr(record, name) for name, _ in _RECORD_SCHEMAS[type(record)]
    }
    parameters[field_name] = (marker,) * 4096
    inspections = guard_member_inspection(monkeypatch, marker)
    with pytest.raises(ValueError, match="exceeds.*bound"):
        type(record)(**parameters)
    assert inspections == []


@pytest.mark.parametrize("field", ["version", "tick", "next_root_id"])
@pytest.mark.parametrize("value", [True, False, -1, 1.0, "1"])
def test_core_binding_identifiers_use_nonnegative_exact_integers(field, value) -> None:
    binding = cie_binding().environment.core_state
    parameters = {
        name: getattr(binding, name) for name, _ in _RECORD_SCHEMAS[type(binding)]
    }
    parameters[field] = value
    with pytest.raises((TypeError, ValueError)):
        CoreStateBinding(**parameters)


@pytest.mark.parametrize(
    "record_field",
    ["sequence_index", "invocation_revision", "arena_version", "round_identity"],
)
@pytest.mark.parametrize("value", [True, -1])
def test_operational_identity_numbers_cannot_alias_boolean_or_negative(
    record_field, value
) -> None:
    cie = cie_binding()
    if record_field == "sequence_index":
        record = cie.identity
    elif record_field == "invocation_revision":
        record = cie
    else:
        record = SnapshotBinding(cie, 0, 0)
    parameters = {
        name: getattr(record, name) for name, _ in _RECORD_SCHEMAS[type(record)]
    }
    parameters[record_field] = value
    with pytest.raises((TypeError, ValueError)):
        type(record)(**parameters)


def test_heterogeneous_identifier_sets_use_full_typed_byte_order() -> None:
    values = (None, False, 1, -1, 1.5, "1", b"1", (1,), AssertionBasis.DERIVED)
    roots = tuple(dependency(occurrence=value) for value in values)
    canonical = canonical_dependencies(roots)
    assert canonical == canonical_dependencies(tuple(reversed(roots)))
    assert len(canonical) == len(values)
    encoded = tuple(canonical_identity_bytes(root) for root in canonical)
    assert encoded == tuple(sorted(encoded))


def test_all_set_identity_fields_are_permutation_invariant() -> None:
    roots = (
        dependency(occurrence=True),
        dependency(occurrence=1),
        dependency(occurrence="1"),
    )
    members = tuple(descriptor("constraint", value) for value in (True, 1, "1"))
    content, cie = ClaimContentID(descriptor("content", "P")), cie_binding()
    identities = []
    for ordered_roots, ordered_members in zip(
        permutations(roots), permutations(members), strict=True
    ):
        assertion = AssertionSemanticKey(
            content, AssertionBasis.DERIVED, scope(), ordered_roots + ordered_roots
        )
        aec = ActiveEpistemicContextIdentity(
            descriptor("branch"), ordered_roots + ordered_roots, cie
        )
        constraints = ConstraintEnvironmentBinding(
            cie,
            ordered_members + ordered_members,
            ordered_members,
            descriptor("policy"),
        )
        identities.append(canonical_identity_bytes((assertion, aec, constraints)))
    assert len(set(identities)) == 1
    # Sequence-valued data is not silently treated as a set.
    assert descriptor("ordered", 1, 2) != descriptor("ordered", 2, 1)
    assert descriptor("ordered", 1, 1) != descriptor("ordered", 1)


@pytest.mark.parametrize(
    "enum_type", [AssertionBasis, DependencyKind, ConstraintFamily]
)
def test_allowed_enum_class_does_not_admit_counterfeit_members(enum_type) -> None:
    original = next(iter(enum_type))
    counterfeit = object.__new__(enum_type)
    object.__setattr__(counterfeit, "_name_", original.name)
    object.__setattr__(counterfeit, "_value_", original.value)
    with pytest.raises(TypeError, match="counterfeit"):
        descriptor("counterfeit-enum", counterfeit)


@pytest.mark.parametrize("field", ["_name_", "_value_"])
def test_mutated_enum_member_is_not_silently_recoded(monkeypatch, field) -> None:
    member = AssertionBasis.FORMAL_GIVEN
    before = canonical_identity_bytes(member)
    with monkeypatch.context() as patch:
        patch.setattr(member, field, "COUNTERFEIT")
        with pytest.raises(ValueError, match="mutated"):
            canonical_identity_bytes(member)
    assert canonical_identity_bytes(member) == before


@pytest.mark.parametrize(
    "value", [UUID(int=1), datetime(2020, 1, 1, tzinfo=UTC), Lock()]
)
def test_runtime_metadata_objects_cannot_enter_canonical_payloads(value) -> None:
    with pytest.raises(TypeError):
        descriptor("runtime-metadata", (value,))


def test_caller_labels_and_serialized_descriptors_do_not_issue_authority() -> None:
    fake = SourceAssertionKey(
        "EXTERNAL_OBSERVATION",
        descriptor("issuer", "caller-selected"),
        descriptor("occurrence", "caller-selected"),
    )
    encoded = canonical_identity_bytes(fake)
    assert type(encoded) is bytes
    assert not hasattr(fake, "validate")
    assert not hasattr(fake, "issue")
    assert not hasattr(fake, "dispatch")
    with pytest.raises(TypeError):
        ScopeIdentity("FORMAL", "caller-selected", descriptor("scope"))
    # A byte string remains data; it does not deserialize into a capability.
    assert canonical_identity_bytes(encoded) != encoded
    assert not hasattr(serialization_module, "deserialize")


def test_digest_collision_is_an_index_collision_not_identity(monkeypatch) -> None:
    class ConstantDigest:
        def hexdigest(self):
            return "0" * 64

    monkeypatch.setattr(
        serialization_module.hashlib, "sha256", lambda value: ConstantDigest()
    )
    first, second = descriptor("identity", 1), descriptor("identity", True)
    assert identity_digest(first) == identity_digest(second)
    assert first != second
    assert canonical_identity_bytes(first) != canonical_identity_bytes(second)


def test_serialized_format_has_explicit_tags_lengths_and_schema_order() -> None:
    magic = b"DGCA-LITE-L3-IDENTITY-1\x00"
    assert canonical_identity_bytes(None) == magic + b"N"
    assert canonical_identity_bytes(True) == magic + b"T"
    assert canonical_identity_bytes(False) == magic + b"F"
    assert (
        canonical_identity_bytes(1) == magic + b"I+" + (1).to_bytes(8, "big") + b"\x01"
    )
    assert (
        canonical_identity_bytes("\u03bb")
        == magic + b"S" + (2).to_bytes(8, "big") + b"\xce\xbb"
    )
    assert (
        canonical_identity_bytes((True, False))
        == magic + b"A" + (2).to_bytes(8, "big") + b"TF"
    )
    first = CanonicalDescriptor(values=(1,), kind="payload")
    second = CanonicalDescriptor("payload", (1,))
    assert canonical_identity_bytes(first) == canonical_identity_bytes(second)


DETERMINISTIC_GRAPH_SCRIPT = """
from dgca_lite.cognition import *
from dgca_lite.cognition.identity import *

def d(kind, *values):
    return CanonicalDescriptor(kind, values)

# Deliberately enumerate a salted-hash set before canonical normalization.
roots = tuple(DependencyRootIdentity(DependencyKind.PREDICTION, d('issuer', 1),
    d('occurrence', item)) for item in {'alpha', 'beta', 'gamma'})
schemas = tuple(d('schema', item) for item in {'MP', 'NEGATION', 'TRANSITIVE'})
core = CoreStateBinding(d('core', 1), 1, 1, 2, d('core-policy', 'v0.4'))
environment = CognitiveEnvironmentBinding(core, d('l2-policy', 'v0.4'), d('l3-policy', 1))
cause = InvocationCauseID(d('issuer', 1), d('occurrence', 1))
cie = CIEBinding(CIEIdentity(cause, 0), 0, environment)
aec = ActiveEpistemicContextIdentity(d('branch', 0), roots + roots, cie)
constraints = ConstraintEnvironmentBinding(cie, schemas + schemas, schemas, d('policy', 1))
assertion = AssertionSemanticKey(ClaimContentID(d('content', 'P')),
    AssertionBasis.DERIVED, ScopeIdentity('FORMAL', d('issuer', 1), d('scope', 1)), roots)
graph = (DerivationContextBinding(aec, constraints, d('consumer-schema', 'MP')),
    SnapshotBinding(cie, 0, 0), assertion,
    SourceAssertionKey('FORMAL', d('issuer', 1), d('occurrence', 1)),
    d('scalars', None, True, 1, -1, -0.0, 1.5, '\\u03bb', b'bytes'))
print(canonical_identity_bytes(graph).hex())
print(identity_digest(graph))
"""


def test_complex_graph_bytes_and_signature_match_across_independent_hash_seeds() -> (
    None
):
    results = []
    for seed in ("0", "1", "27", "123", "random"):
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = seed
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
        result = subprocess.check_output(
            [sys.executable, "-B", "-c", DETERMINISTIC_GRAPH_SCRIPT],
            env=environment,
            text=True,
        )
        serialized, signature = result.splitlines()
        assert len(bytes.fromhex(serialized)) > 1000
        assert len(signature) == 64
        results.append((serialized, signature))
    assert len(set(results)) == 1
