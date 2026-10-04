"""Unit-2 opaque handles and authority-free issuance descriptors (Sections 14/19).

No handle fields are credentials. Only the issuing boundary's private identity
registry can validate a handle, including one allocated with object.__new__.
"""

from __future__ import annotations

from dataclasses import dataclass

from .identity import CanonicalDescriptor, ScopeIdentity
from .serialization import canonical_identity_bytes
from .types import FailureCode


class IngressAbort(Exception):
    def __init__(self, code: FailureCode, detail: str = "") -> None:
        self.code = code
        super().__init__(code.value if not detail else f"{code.value}: {detail}")


class _OpaqueHandle:
    __slots__ = ("__weakref__",)

    def __new__(cls, *args: object, **kwargs: object):
        raise TypeError("live ingress handles are issued only by the trusted boundary")

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("live ingress handles expose no mutable credential fields")

    def __reduce__(self):
        raise TypeError("live ingress authority cannot be serialized")

    def __reduce_ex__(self, protocol: int):
        raise TypeError("live ingress authority cannot be serialized")

    def __copy__(self):
        raise TypeError("live ingress authority cannot be copied")

    def __deepcopy__(self, memo: dict[int, object]):
        raise TypeError("live ingress authority cannot be copied")


class ExternalOccurrenceCapability(_OpaqueHandle):
    __slots__ = ()


class FormalSourceOccurrenceCapability(_OpaqueHandle):
    __slots__ = ()


class AssumptionIssuanceCapability(_OpaqueHandle):
    __slots__ = ()


class FormalConstraintOccurrenceCapability(_OpaqueHandle):
    __slots__ = ()


@dataclass(frozen=True, slots=True)
class ExternalOccurrenceBinding:
    """Historical data, never a usable capability or caller-selected credential."""

    ingress_class: str
    occurrence: CanonicalDescriptor
    runtime: CanonicalDescriptor
    issuance_revision: int
    scope: ScopeIdentity

    def canonical_descriptor(self) -> CanonicalDescriptor:
        if type(self.ingress_class) is not str or self.ingress_class not in (
            "FORMAL_GIVEN",
            "FORMAL_ASSUMPTION",
            "FORMAL_CONSTRAINT_GIVEN",
            "FORMAL_CONSTRAINT_ASSUMPTION",
            "EXTERNAL_OBSERVATION",
        ):
            raise TypeError("unknown ingress class")
        if (
            type(self.occurrence) is not CanonicalDescriptor
            or type(self.runtime) is not CanonicalDescriptor
        ):
            raise TypeError("invalid occurrence/runtime descriptor")
        if type(self.issuance_revision) is not int or self.issuance_revision < 0:
            raise ValueError("invalid issuance revision")
        if type(self.scope) is not ScopeIdentity:
            raise TypeError("invalid authorized scope")
        return CanonicalDescriptor(
            "ExternalOccurrenceCapabilityBinding",
            (
                self.ingress_class,
                self.occurrence,
                self.runtime,
                self.issuance_revision,
                self.scope,
            ),
        )

    def __post_init__(self) -> None:
        canonical_identity_bytes(self.canonical_descriptor())
