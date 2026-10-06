"""Closed Unit-5 mechanical contracts and authority-free work descriptors.

The compiled catalogue contains no cognitive operator or callable registration.
Constructing/copying these data records NEVER authorizes execution.
"""

from dataclasses import dataclass
from enum import Enum

from .budget import BudgetChargeView
from .identity import CanonicalDescriptor, SnapshotBinding
from .ingress import _snapshot
from .policy import ValueLimits
from .serialization import canonical_identity_bytes
from .types import WorkEffectClass


class OperationType(Enum):
    CLONE_CLOSED_VALUE = "CLONE_CLOSED_VALUE"
    EFFECT_CLASSIFICATION_ONLY = "EFFECT_CLASSIFICATION_ONLY"


class BudgetClass(Enum):
    CHARGED_WORK = "CHARGED_WORK"


class AuthorityRequirement(Enum):
    INVOCATION_CURRENT = "INVOCATION_CURRENT"
    ENVIRONMENT_CURRENT = "ENVIRONMENT_CURRENT"
    CIE_CURRENT = "CIE_CURRENT"
    SNAPSHOT_CURRENT = "SNAPSHOT_CURRENT"


class PublicationPolicy(Enum):
    STAGED_IMMUTABLE_ONLY = "STAGED_IMMUTABLE_ONLY"
    SEPARATE_EFFECT_GATE_REQUIRED = "SEPARATE_EFFECT_GATE_REQUIRED"


_MEMBERS = tuple(
    (cls, tuple((item, item.value) for item in cls))
    for cls in (
        OperationType,
        BudgetClass,
        AuthorityRequirement,
        PublicationPolicy,
        WorkEffectClass,
    )
)


def _label(value, cls):
    for family, members in _MEMBERS:
        if family is cls and type(value) is cls:
            for member, literal in members:
                if (
                    value is member
                    and type(value.value) is str
                    and value.value == literal
                ):
                    return literal
    raise TypeError("unknown or mutated operation vocabulary")


@dataclass(frozen=True, slots=True)
class WorkPolicy:
    """Trusted mechanical bounds; no semantic priorities or per-call policy."""

    max_input_nodes: int = 128
    max_input_depth: int = 24
    max_scalar_bytes: int = 4096
    max_input_bytes: int = 16384

    def __post_init__(self):
        for value, ceiling in (
            (self.max_input_nodes, 256),
            (self.max_input_depth, 32),
            (self.max_scalar_bytes, 8192),
            (self.max_input_bytes, 32768),
        ):
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError("invalid work policy bound")

    def canonical_descriptor(self):
        self.__post_init__()
        return CanonicalDescriptor(
            "Unit5WorkPolicy",
            (
                self.max_input_nodes,
                self.max_input_depth,
                self.max_scalar_bytes,
                self.max_input_bytes,
            ),
        )

    @property
    def value_limits(self):
        self.__post_init__()
        return ValueLimits(
            self.max_input_nodes, self.max_input_depth, self.max_scalar_bytes
        )


@dataclass(frozen=True, slots=True)
class ResourceEnvelope:
    charge_units: int
    max_nodes: int
    encoded_input_bytes: int

    def canonical_descriptor(self):
        for value, ceiling in (
            (self.charge_units, 256),
            (self.max_nodes, 256),
            (self.encoded_input_bytes, 32768),
        ):
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError("invalid finite resource envelope")
        return CanonicalDescriptor(
            "ResourceEnvelope",
            (self.charge_units, self.max_nodes, self.encoded_input_bytes),
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


@dataclass(frozen=True, slots=True)
class OperationContract:
    operation_type: OperationType
    budget_class: BudgetClass
    effect_class: WorkEffectClass
    authority_requirements: tuple[AuthorityRequirement, ...]
    work_class: CanonicalDescriptor
    resource_envelope: ResourceEnvelope
    publication_policy: PublicationPolicy

    def canonical_descriptor(self):
        # Outer bound BEFORE any semantic member check or traversal.
        requirements = self.authority_requirements
        if type(requirements) is not tuple or len(requirements) > 4:
            raise ValueError("invalid authority requirements bound")
        labels = tuple(_label(item, AuthorityRequirement) for item in requirements)
        if len(set(labels)) != len(labels) or labels != tuple(sorted(labels)):
            raise ValueError("requirements must be a canonical unique set")
        if (
            type(self.work_class) is not CanonicalDescriptor
            or type(self.resource_envelope) is not ResourceEnvelope
        ):
            raise TypeError("closed work class/envelope required")
        return CanonicalDescriptor(
            "OperationContract",
            (
                _label(self.operation_type, OperationType),
                _label(self.budget_class, BudgetClass),
                _label(self.effect_class, WorkEffectClass),
                labels,
                self.work_class,
                self.resource_envelope.canonical_descriptor(),
                _label(self.publication_policy, PublicationPolicy),
            ),
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


def compiled_contract(policy, operation, frozen_input):
    """Only trusted built-in implementations. No plugins, callbacks or overrides."""
    if type(policy) is not WorkPolicy:
        raise TypeError("exact trusted policy required")
    literal = _label(operation, OperationType)
    data = canonical_identity_bytes(frozen_input, policy.value_limits)
    if len(data) > policy.max_input_bytes:
        raise ValueError("complete work input exceeds byte bound")
    pure = literal == "CLONE_CLOSED_VALUE"
    return OperationContract(
        operation,
        BudgetClass.CHARGED_WORK,
        WorkEffectClass.PURE_COMPUTE if pure else WorkEffectClass.OPERATIONAL_EFFECT,
        (
            AuthorityRequirement.CIE_CURRENT,
            AuthorityRequirement.ENVIRONMENT_CURRENT,
            AuthorityRequirement.INVOCATION_CURRENT,
            AuthorityRequirement.SNAPSHOT_CURRENT,
        ),
        CanonicalDescriptor("Unit5WorkClass", (literal,)),
        ResourceEnvelope(1, policy.max_input_nodes, len(data)),
        PublicationPolicy.STAGED_IMMUTABLE_ONLY
        if pure
        else PublicationPolicy.SEPARATE_EFFECT_GATE_REQUIRED,
    )


def compiled_policy_descriptor(policy):
    # Bind the complete frozen catalogue, not a caller's claimed contract.
    return CanonicalDescriptor(
        "Unit5OperationCatalogue",
        (
            policy.canonical_descriptor(),
            tuple(
                compiled_contract(policy, op, ()).canonical_descriptor()
                for op in OperationType
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class FrozenWork:
    contract: OperationContract
    frozen_input: object
    owner_identity: CanonicalDescriptor
    owner_revision: int
    snapshot_binding: SnapshotBinding

    def canonical_descriptor(self):
        if (
            type(self.contract) is not OperationContract
            or type(self.owner_identity) is not CanonicalDescriptor
            or type(self.owner_revision) is not int
            or self.owner_revision < 0
            or type(self.snapshot_binding) is not SnapshotBinding
        ):
            raise TypeError("invalid exact work descriptor")
        return CanonicalDescriptor(
            "ExactWorkIdentity",
            (
                self.contract.canonical_descriptor(),
                self.frozen_input,
                self.owner_identity,
                self.owner_revision,
                self.snapshot_binding,
            ),
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


@dataclass(frozen=True, slots=True)
class PreparedDispatch:
    work: FrozenWork
    charge: BudgetChargeView
    unit_ordinal: int

    def canonical_descriptor(self):
        if (
            type(self.work) is not FrozenWork
            or type(self.charge) is not BudgetChargeView
            or type(self.unit_ordinal) is not int
            or not 0 <= self.unit_ordinal < 256
        ):
            raise TypeError("invalid prepared dispatch")
        return CanonicalDescriptor(
            "PreparedDispatch",
            (
                self.work.canonical_descriptor(),
                self.charge.canonical_descriptor(),
                self.unit_ordinal,
            ),
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


@dataclass(frozen=True, slots=True)
class PureWorkResultView:
    permit_binding: CanonicalDescriptor
    output: object

    def canonical_descriptor(self):
        if type(self.permit_binding) is not CanonicalDescriptor:
            raise TypeError("authority-free binding required")
        return CanonicalDescriptor(
            "PureWorkResultView", (self.permit_binding, self.output)
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


def freeze_work(policy, work):
    if type(work) is not FrozenWork:
        raise TypeError("closed frozen work required")
    # The tighter work-input bound must precede even general descriptor encoding.
    # Otherwise its larger metadata bound could traverse an oversized input.
    source = work.frozen_input
    source_contract = work.contract
    source_owner, source_revision, source_snapshot = (
        work.owner_identity,
        work.owner_revision,
        work.snapshot_binding,
    )
    canonical_identity_bytes(source, policy.value_limits)
    frozen = _snapshot(source, limits=policy.value_limits)
    if type(source_contract) is not OperationContract:
        raise TypeError("closed contract required")
    supplied_contract = _snapshot(source_contract.canonical_descriptor())
    contract = compiled_contract(policy, source_contract.operation_type, frozen)
    if canonical_identity_bytes(
        contract.canonical_descriptor()
    ) != canonical_identity_bytes(supplied_contract):
        raise ValueError("caller contract differs from frozen trusted policy")
    fields = _snapshot(
        CanonicalDescriptor(
            "WorkOwnerFields",
            (source_owner, source_revision, source_snapshot),
        )
    )
    return FrozenWork(contract, frozen, *fields.values)
