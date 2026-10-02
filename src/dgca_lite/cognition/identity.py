"""Canonical authority-free identity records from Sections 13--18.1.

Equality compares complete typed descriptors, never digest-only identity.
Operational issuers must validate their private records separately: possession
or construction of any value in this module creates no live capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from .policy import DEFAULT_VALUE_LIMITS, ValueLimits
from .types import AssertionBasis, DependencyKind


class _CanonicalData:
    __slots__ = ()

    def __post_init__(self) -> None:
        from .serialization import canonical_identity_bytes

        if (
            type(self) is AssertionSemanticKey
            or type(self) is ActiveEpistemicContextIdentity
        ):
            object.__setattr__(
                self, "dependencies", canonical_dependencies(self.dependencies)
            )
        if type(self) is ConstraintEnvironmentBinding:
            for name in ("schema_set", "active_constraint_set"):
                object.__setattr__(
                    self, name, canonical_descriptor_set(getattr(self, name))
                )
        canonical_identity_bytes(self)

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return False
        from .serialization import canonical_identity_bytes

        return canonical_identity_bytes(self) == canonical_identity_bytes(other)

    def __hash__(self) -> int:
        from .serialization import canonical_identity_bytes

        # A process-local index only; it never enters canonical serialization.
        return hash(canonical_identity_bytes(self))


@dataclass(frozen=True, slots=True, eq=False)
class CanonicalDescriptor(_CanonicalData):
    kind: str
    values: tuple[object, ...] = ()


@dataclass(frozen=True, slots=True, eq=False)
class ClaimContentID(_CanonicalData):
    descriptor: CanonicalDescriptor


@dataclass(frozen=True, slots=True, eq=False)
class ScopeIdentity(_CanonicalData):
    kind: str
    authority_binding: CanonicalDescriptor
    descriptor: CanonicalDescriptor


@dataclass(frozen=True, slots=True, eq=False)
class DependencyRootIdentity(_CanonicalData):
    kind: DependencyKind
    origin_authority_binding: CanonicalDescriptor
    origin_descriptor: CanonicalDescriptor


@dataclass(frozen=True, slots=True, eq=False)
class AssertionSemanticKey(_CanonicalData):
    content: ClaimContentID
    basis: AssertionBasis
    scope: ScopeIdentity
    dependencies: tuple[DependencyRootIdentity, ...] = ()


@dataclass(frozen=True, slots=True, eq=False)
class SourceAssertionKey(_CanonicalData):
    source_kind: str
    origin_authority_binding: CanonicalDescriptor
    occurrence_descriptor: CanonicalDescriptor


@dataclass(frozen=True, slots=True, eq=False)
class InvocationCauseID(_CanonicalData):
    origin_authority_binding: CanonicalDescriptor
    occurrence_descriptor: CanonicalDescriptor


@dataclass(frozen=True, slots=True, eq=False)
class CoreStateBinding(_CanonicalData):
    core_identity: CanonicalDescriptor
    version: int
    tick: int
    next_root_id: int
    core_policy: CanonicalDescriptor


@dataclass(frozen=True, slots=True, eq=False)
class CognitiveEnvironmentBinding(_CanonicalData):
    core_state: CoreStateBinding
    l2_policy: CanonicalDescriptor
    l3_policy: CanonicalDescriptor


@dataclass(frozen=True, slots=True, eq=False)
class CIEIdentity(_CanonicalData):
    invocation_cause: InvocationCauseID
    sequence_index: int


@dataclass(frozen=True, slots=True, eq=False)
class CIEBinding(_CanonicalData):
    identity: CIEIdentity
    invocation_revision: int
    environment: CognitiveEnvironmentBinding


@dataclass(frozen=True, slots=True, eq=False)
class SnapshotBinding(_CanonicalData):
    cie: CIEBinding
    arena_version: int
    round_identity: int


@dataclass(frozen=True, slots=True, eq=False)
class ActiveEpistemicContextIdentity(_CanonicalData):
    branch_identity: CanonicalDescriptor
    dependencies: tuple[DependencyRootIdentity, ...]
    cie: CIEBinding


@dataclass(frozen=True, slots=True, eq=False)
class ConstraintEnvironmentBinding(_CanonicalData):
    cie: CIEBinding
    schema_set: tuple[CanonicalDescriptor, ...]
    active_constraint_set: tuple[CanonicalDescriptor, ...]
    l3_policy: CanonicalDescriptor


@dataclass(frozen=True, slots=True, eq=False)
class DerivationContextBinding(_CanonicalData):
    aec: ActiveEpistemicContextIdentity
    constraint_environment: ConstraintEnvironmentBinding
    consumer_schema: CanonicalDescriptor


def canonical_dependencies(
    roots: tuple[DependencyRootIdentity, ...],
    limits: ValueLimits = DEFAULT_VALUE_LIMITS,
) -> tuple[DependencyRootIdentity, ...]:
    """Canonicalize a complete bounded set; never consume an arbitrary iterator."""
    from .serialization import canonical_identity_bytes

    if type(roots) is not tuple:
        raise TypeError("dependency roots must be an immutable tuple")
    if type(limits) is not ValueLimits:
        raise TypeError("unknown value-limits type")
    limits.__post_init__()
    # The outer tuple itself consumes one node. Check before even inspecting
    # member types, including when a caller supplies malformed members.
    if len(roots) > limits.max_nodes - 1:
        raise ValueError("dependency set exceeds node bound")
    if any(type(root) is not DependencyRootIdentity for root in roots):
        raise TypeError("unknown dependency-root type")
    canonical_identity_bytes(roots, limits)
    by_descriptor = {canonical_identity_bytes(root, limits): root for root in roots}
    return tuple(by_descriptor[key] for key in sorted(by_descriptor))


def canonical_descriptor_set(
    values: tuple[CanonicalDescriptor, ...],
    limits: ValueLimits = DEFAULT_VALUE_LIMITS,
) -> tuple[CanonicalDescriptor, ...]:
    """Canonical ordered set for the two Section 74 set-identity fields."""
    from .serialization import canonical_identity_bytes

    if type(values) is not tuple:
        raise TypeError("descriptor set must be an immutable tuple")
    if type(limits) is not ValueLimits:
        raise TypeError("unknown value-limits type")
    limits.__post_init__()
    if len(values) > limits.max_nodes - 1:
        raise ValueError("descriptor set exceeds node bound")
    if any(type(value) is not CanonicalDescriptor for value in values):
        raise TypeError("unknown set-descriptor type")
    canonical_identity_bytes(values, limits)
    by_descriptor = {canonical_identity_bytes(value, limits): value for value in values}
    return tuple(by_descriptor[key] for key in sorted(by_descriptor))


# A closed field schema, not a caller-extensible serializer registry.
_RECORD_SCHEMAS = MappingProxyType(
    {
        CanonicalDescriptor: (("kind", str), ("values", tuple)),
        ClaimContentID: (("descriptor", CanonicalDescriptor),),
        ScopeIdentity: (
            ("kind", str),
            ("authority_binding", CanonicalDescriptor),
            ("descriptor", CanonicalDescriptor),
        ),
        DependencyRootIdentity: (
            ("kind", DependencyKind),
            ("origin_authority_binding", CanonicalDescriptor),
            ("origin_descriptor", CanonicalDescriptor),
        ),
        AssertionSemanticKey: (
            ("content", ClaimContentID),
            ("basis", AssertionBasis),
            ("scope", ScopeIdentity),
            ("dependencies", tuple),
        ),
        SourceAssertionKey: (
            ("source_kind", str),
            ("origin_authority_binding", CanonicalDescriptor),
            ("occurrence_descriptor", CanonicalDescriptor),
        ),
        InvocationCauseID: (
            ("origin_authority_binding", CanonicalDescriptor),
            ("occurrence_descriptor", CanonicalDescriptor),
        ),
        CoreStateBinding: (
            ("core_identity", CanonicalDescriptor),
            ("version", int),
            ("tick", int),
            ("next_root_id", int),
            ("core_policy", CanonicalDescriptor),
        ),
        CognitiveEnvironmentBinding: (
            ("core_state", CoreStateBinding),
            ("l2_policy", CanonicalDescriptor),
            ("l3_policy", CanonicalDescriptor),
        ),
        CIEIdentity: (("invocation_cause", InvocationCauseID), ("sequence_index", int)),
        CIEBinding: (
            ("identity", CIEIdentity),
            ("invocation_revision", int),
            ("environment", CognitiveEnvironmentBinding),
        ),
        SnapshotBinding: (
            ("cie", CIEBinding),
            ("arena_version", int),
            ("round_identity", int),
        ),
        ActiveEpistemicContextIdentity: (
            ("branch_identity", CanonicalDescriptor),
            ("dependencies", tuple),
            ("cie", CIEBinding),
        ),
        ConstraintEnvironmentBinding: (
            ("cie", CIEBinding),
            ("schema_set", tuple),
            ("active_constraint_set", tuple),
            ("l3_policy", CanonicalDescriptor),
        ),
        DerivationContextBinding: (
            ("aec", ActiveEpistemicContextIdentity),
            ("constraint_environment", ConstraintEnvironmentBinding),
            ("consumer_schema", CanonicalDescriptor),
        ),
    }
)


def _validated_record_fields(
    value: _CanonicalData, remaining_nodes: int
) -> tuple[tuple[str, object], ...]:
    """Revalidate records even if construction/frozen fields were bypassed."""
    schema = _RECORD_SCHEMAS[type(value)]
    result = []
    for name, expected_type in schema:
        try:
            field = getattr(value, name)
        except AttributeError as error:
            raise ValueError("incomplete canonical record") from error
        if type(field) is not expected_type:
            raise TypeError(f"invalid canonical field type: {name}")
        if expected_type is int and field < 0:
            raise ValueError(f"negative canonical index: {name}")
        if expected_type is str and not field:
            raise ValueError(f"empty canonical kind: {name}")
        if expected_type is tuple and len(field) > remaining_nodes - 1:
            raise ValueError("tuple identity exceeds remaining node bound")
        result.append((name, field))
    # Member validation belongs to the encoder's tuple traversal, after its
    # current shared-budget outer-bound check (not this preliminary budget).
    return tuple(result)
