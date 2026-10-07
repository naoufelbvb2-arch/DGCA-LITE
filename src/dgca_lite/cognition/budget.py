"""Unit-3 closed budget data and opaque reservation handles, not work permits.

These views describe accounting only. Constructing/copying them grants no
authority, execution, publication, owner selection, or replacement reservation.
"""

from dataclasses import dataclass

from .authority import _OpaqueHandle
from .identity import CanonicalDescriptor
from .serialization import canonical_identity_bytes
from .types import BudgetSourceKind


class BudgetReservation(_OpaqueHandle):
    __slots__ = ()


@dataclass(frozen=True, slots=True)
class BudgetLedgerView:
    owner_identity: CanonicalDescriptor
    initial: int
    available: int
    reserved: int
    consumed: int
    retired: int
    delegated: int = 0

    def canonical_descriptor(self) -> CanonicalDescriptor:
        counts = (
            self.initial,
            self.available,
            self.reserved,
            self.consumed,
            self.retired,
        )
        if type(self.owner_identity) is not CanonicalDescriptor:
            raise TypeError("invalid budget owner")
        if any(type(value) is not int or value < 0 for value in counts):
            raise ValueError("budget counts must be exact nonnegative integers")
        if type(self.delegated) is not int or self.delegated < 0:
            raise ValueError("invalid delegated count")
        if self.initial != sum(counts[1:]) + self.delegated:
            raise ValueError("budget conservation violated")
        if self.delegated:
            return CanonicalDescriptor(
                "DelegatedInvocationBudgetLedgerView",
                (self.owner_identity,) + counts + (self.delegated,),
            )
        return CanonicalDescriptor(
            "InvocationBudgetLedgerView", (self.owner_identity,) + counts
        )

    def __post_init__(self) -> None:
        canonical_identity_bytes(self.canonical_descriptor())


@dataclass(frozen=True, slots=True)
class BudgetChargeView:
    """Section-94 data only; not an authorization or executable-work permit."""

    owner_identity: CanonicalDescriptor
    reservation_identity: CanonicalDescriptor
    unit_identity: CanonicalDescriptor
    work_class: CanonicalDescriptor
    source_kind: BudgetSourceKind = BudgetSourceKind.INVOCATION_GENERAL

    def canonical_descriptor(self) -> CanonicalDescriptor:
        fields = (
            self.owner_identity,
            self.reservation_identity,
            self.unit_identity,
            self.work_class,
        )
        if any(type(value) is not CanonicalDescriptor for value in fields):
            raise TypeError("invalid charge identity")
        if type(self.source_kind) is not BudgetSourceKind:
            raise TypeError("exact charge source required")
        return CanonicalDescriptor(
            "BudgetChargeBinding",
            (self.source_kind,) + fields,
        )

    def __post_init__(self) -> None:
        canonical_identity_bytes(self.canonical_descriptor())
