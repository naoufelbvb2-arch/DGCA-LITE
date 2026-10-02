"""Closed, bounded deterministic identity encoding; never a capability codec."""

from __future__ import annotations

import hashlib
import struct
from math import isfinite

from .contracts import ConstraintFamily, ControlPlaneOperation, InferenceFamily
from .identity import (
    _RECORD_SCHEMAS,
    ActiveEpistemicContextIdentity,
    AssertionSemanticKey,
    CanonicalDescriptor,
    ConstraintEnvironmentBinding,
    DependencyRootIdentity,
    _validated_record_fields,
)
from .policy import DEFAULT_VALUE_LIMITS, ValueLimits
from .types import (
    AssertionBasis,
    BudgetSourceKind,
    CaptureState,
    DependencyKind,
    FailureCode,
    ForecastStatus,
    InvocationState,
    WorkEffectClass,
)

_MAGIC = b"DGCA-LITE-L3-IDENTITY-1\x00"
_ENUM_TYPES = (
    AssertionBasis,
    BudgetSourceKind,
    CaptureState,
    DependencyKind,
    FailureCode,
    ForecastStatus,
    InvocationState,
    WorkEffectClass,
    ConstraintFamily,
    ControlPlaneOperation,
    InferenceFamily,
)
# Snapshot the closed vocabulary, not a caller-extensible encoding registry.
# A forged object with an allowed Enum class is not a canonical member.
_ENUM_MEMBERS = tuple(
    (enum_type, tuple((member, member.name, member.value) for member in enum_type))
    for enum_type in _ENUM_TYPES
)


def _set_member_type(record_type: type, field_name: str) -> type | None:
    if (
        record_type is AssertionSemanticKey
        or record_type is ActiveEpistemicContextIdentity
    ) and field_name == "dependencies":
        return DependencyRootIdentity
    if record_type is ConstraintEnvironmentBinding and field_name in (
        "schema_set",
        "active_constraint_set",
    ):
        return CanonicalDescriptor
    return None


def canonical_identity_bytes(
    value: object, limits: ValueLimits = DEFAULT_VALUE_LIMITS
) -> bytes:
    """Validate and encode a complete value inside the supplied finite envelope.

    No arbitrary dataclasses, containers, subclasses, hooks, or live handles are
    accepted. Binary64 values retain all bits, including signed zero.
    """
    if type(limits) is not ValueLimits:
        raise TypeError("unknown value-limits type")
    limits.__post_init__()
    nodes = 0
    ancestors: set[int] = set()

    def length(size: int) -> bytes:
        return size.to_bytes(8, "big")

    def scalar(tag: bytes, payload: bytes) -> bytes:
        if len(payload) > limits.max_scalar_bytes:
            raise ValueError("scalar exceeds byte bound")
        return tag + length(len(payload)) + payload

    def encode(item: object, depth: int, set_member_type: type | None = None) -> bytes:
        nonlocal nodes
        nodes += 1
        if nodes > limits.max_nodes or depth > limits.max_depth:
            raise ValueError("canonical value exceeds node/depth bound")
        item_type = type(item)
        if item is None:
            return b"N"
        if item_type is bool:
            return b"T" if item else b"F"
        if item_type is int:
            size = max(1, (item.bit_length() + 7) // 8)
            if size > limits.max_scalar_bytes:
                raise ValueError("integer exceeds byte bound")
            sign = b"-" if item < 0 else b"+"
            magnitude = -item if item < 0 else item
            return b"I" + sign + length(size) + magnitude.to_bytes(size, "big")
        if item_type is float:
            if not isfinite(item):
                raise ValueError("canonical values must be finite")
            return scalar(b"D", struct.pack(">d", item))
        if item_type is str:
            if len(item) > limits.max_scalar_bytes:
                raise ValueError("string exceeds byte bound")
            return scalar(b"S", item.encode("utf-8"))
        if item_type is bytes:
            return scalar(b"B", item)
        for enum_type, members in _ENUM_MEMBERS:
            if item_type is enum_type:
                for member, name, enum_value in members:
                    if item is member:
                        if (
                            type(item.name) is not str
                            or type(item.value) is not str
                            or item.name != name
                            or item.value != enum_value
                        ):
                            raise ValueError("mutated canonical enum member")
                        return (
                            b"E"
                            + encode(enum_type.__name__, depth + 1)
                            + encode(enum_value, depth + 1)
                        )
                raise TypeError("counterfeit canonical enum member")
        if item_type is not tuple and not any(
            item_type is record_type for record_type in _RECORD_SCHEMAS
        ):
            raise TypeError("unknown or authority-bearing canonical value type")
        identity = id(item)
        if identity in ancestors:
            raise ValueError("cyclic canonical value")
        ancestors.add(identity)
        try:
            if item_type is tuple:
                if len(item) > limits.max_nodes - nodes:
                    raise ValueError("tuple exceeds remaining node bound")
                # Inspect no member (not even its type) until the outer bound
                # has passed against the current shared traversal budget.
                encoded_members = []
                for child in item:
                    if (
                        set_member_type is not None
                        and type(child) is not set_member_type
                    ):
                        raise TypeError("invalid canonical set member type")
                    encoded_members.append(encode(child, depth + 1))
                if set_member_type is not None and encoded_members != sorted(
                    set(encoded_members)
                ):
                    raise ValueError("noncanonical dependency/constraint set")
                return b"A" + length(len(item)) + b"".join(encoded_members)
            record_fields = _validated_record_fields(item, limits.max_nodes - nodes)
            return (
                b"R"
                + encode(item_type.__name__, depth + 1)
                + length(len(record_fields))
                + b"".join(
                    encode(name, depth + 1)
                    + encode(field, depth + 1, _set_member_type(item_type, name))
                    for name, field in record_fields
                )
            )
        finally:
            ancestors.remove(identity)

    return _MAGIC + encode(value, 0)


def identity_digest(value: object, limits: ValueLimits = DEFAULT_VALUE_LIMITS) -> str:
    """Return a verification/index digest, never a replacement for identity."""
    return hashlib.sha256(canonical_identity_bytes(value, limits)).hexdigest()
