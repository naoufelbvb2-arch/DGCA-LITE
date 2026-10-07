"""Unit-3 invocation, budget and two-phase lifecycle infrastructure.

Trusted bootstrap freezes mechanical limits; admission accepts ONLY a genuine
Unit-2 occurrence through the narrow currentness bridge. No issuer, writable
Core, callback, or authorize_* method is exposed to Invocation/CIE consumers.

Reservation requests come from a trusted future dispatcher after it freezes
the complete work envelope. This module neither discovers a cognitive frontier
nor executes work: consume records accounting, but issues NO execution permit.
It asserts no new charge exemption. Future charged dispatch must atomically
combine these ledger transitions with its canonical execution/effect contract.

Lookups briefly acquire/release the registry before waiting on any barrier.
Authority-sensitive operations acquire Core (admission only), then lifecycle,
then ledger, then registry. Future arena/owner locks belong after the ledger.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import RLock, local
from weakref import ReferenceType, ref

from .authority import IngressAbort, _OpaqueHandle
from .budget import BudgetChargeView, BudgetLedgerView, BudgetReservation
from .identity import CanonicalDescriptor, InvocationCauseID
from .ingress import (
    InvocationCauseIngress,
    _pinned_core_binding,
    _pinned_invocation_cause,
    _snapshot,
)
from .locks import RankedBarrier, _deferred_cleanup
from .serialization import canonical_identity_bytes
from .types import BudgetSourceKind, FailureCode, InvocationState


@dataclass(frozen=True, slots=True)
class InvocationLimits:
    """Mechanical trusted policy, not a caller's per-admission budget source.

    Fixed caps bound administrative accounting, including terminal tombstones.
    No calibration here represents confidence, importance, or semantic priority.
    """

    initial_budget: int
    cause_capacity: int = 128

    def __post_init__(self) -> None:
        if type(self.initial_budget) is not int or not 0 <= self.initial_budget <= 256:
            raise ValueError("initial budget must be an exact integer in [0, 256]")
        if type(self.cause_capacity) is not int or not 1 <= self.cause_capacity <= 4096:
            raise ValueError("cause capacity must be an exact integer in [1, 4096]")

    def canonical_descriptor(self) -> CanonicalDescriptor:
        self.__post_init__()
        return CanonicalDescriptor(
            "InvocationLimits", (self.initial_budget, self.cause_capacity)
        )


class InvocationAuthority(_OpaqueHandle):
    __slots__ = ()


@dataclass(frozen=True, slots=True)
class InvocationView:
    identity: CanonicalDescriptor
    cause: InvocationCauseID
    runtime: CanonicalDescriptor
    revision: int
    state: InvocationState

    def canonical_descriptor(self) -> CanonicalDescriptor:
        if (
            type(self.identity) is not CanonicalDescriptor
            or type(self.cause) is not InvocationCauseID
            or type(self.runtime) is not CanonicalDescriptor
            or type(self.revision) is not int
            or self.revision < 0
            or type(self.state) is not InvocationState
        ):
            raise TypeError("invalid invocation binding")
        if self.identity != CanonicalDescriptor(
            "InvocationIdentity", (self.runtime, self.cause)
        ):
            raise ValueError("noncanonical invocation identity")
        return CanonicalDescriptor(
            "InvocationBinding",
            (self.identity, self.cause, self.runtime, self.revision, self.state),
        )

    def __post_init__(self) -> None:
        canonical_identity_bytes(self.canonical_descriptor())


def _build_invocation_system():
    registry_lock = RLock()
    held_lifecycle = local()
    # Includes retired runtime identities. Rebootstrap cannot reset a cause's
    # non-renewable authority/budget; there is no LRU or slot recycling.
    max_runtimes = 64
    used_runtimes: set[bytes] = set()
    handles: dict[int, tuple[ReferenceType, object, str, object, type]] = {}

    class _LifecycleBarrier:
        def __init__(self):
            self.lock = RankedBarrier(1)

        def __enter__(self):
            self.lock.acquire()
            try:
                held_lifecycle.depth = getattr(held_lifecycle, "depth", 0) + 1
            except BaseException:
                self.lock.release()
                raise

        def __exit__(self, *exception):
            held_lifecycle.depth -= 1
            self.lock.release()

    def before_core_guard() -> None:
        if getattr(held_lifecycle, "depth", 0):
            raise IngressAbort(
                FailureCode.INTERNAL_CONTRACT_VIOLATION,
                "Core admission below lifecycle barrier",
            )

    @dataclass(frozen=True, slots=True)
    class _Unit:
        state: str = "AVAILABLE"
        reservation: CanonicalDescriptor | None = None

    @dataclass(frozen=True, slots=True)
    class _Reservation:
        token: BudgetReservation
        identity: CanonicalDescriptor
        units: tuple[int, ...]
        work_class: CanonicalDescriptor
        image: bytes

    @dataclass(slots=True)
    class _Budget:
        lock: object = field(default_factory=lambda: RankedBarrier(2))
        # One publication swaps units, reservation records and the next sequence.
        index: tuple = field(default_factory=lambda: ((), {}, 0))

    @dataclass(slots=True)
    class _ForecastPool:
        identity: CanonicalDescriptor
        budget: _Budget
        tokens: tuple
        forecast: bool = True

    @dataclass(slots=True)
    class _Invocation:
        authority: InvocationAuthority
        ledger: object
        identity: CanonicalDescriptor
        cause: InvocationCauseID
        image: bytes
        budget: _Budget
        lifecycle: tuple = (InvocationState.ACTIVE, 0)
        # Future nondelegated owners must register within active_guard. Unit 3
        # creates none. Finalization already requires their count to be zero.
        nondelegated_children: int = 0
        cie_child: object = None
        cie_sequence: int = 0
        work_owner: object = None
        effect_owner: object = None

    @dataclass(slots=True)
    class _Domain:
        ingress: InvocationCauseIngress
        runtime: CanonicalDescriptor
        initial_budget: int
        capacity: int
        lifecycle: object = field(default_factory=_LifecycleBarrier)
        causes: dict[bytes, _Invocation] = field(default_factory=dict)
        owner_ref: object = None
        owner_id: int = 0
        retired: bool = False
        cie_attached: bool = False
        work_attached: bool = False
        effect_attached: bool = False

    @contextmanager
    def access(handle: object, role: str):
        with registry_lock:
            entry = handles.get(id(handle))
            if (
                entry is None
                or entry[0]() is not handle
                or entry[2] != role
                or type(handle) is not entry[4]
            ):
                raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
            domain, item = entry[1], entry[3]
            owner = domain.owner_ref()
            if owner is None or type(owner) is not InvocationRuntime:
                raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
        # Pin the genuine runtime until the entire operation/guard has quiesced.
        yield domain, item
        del owner

    def live(domain: _Domain) -> None:
        if domain.retired:
            raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)

    def invocation_for(domain: _Domain, authority: object) -> _Invocation:
        live(domain)
        if type(authority) is not InvocationAuthority:
            raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
        # The bounded exact-object index is attached at successful admission.
        entry = handles.get(id(authority))
        if (
            entry is None
            or entry[0]() is not authority
            or entry[1] is not domain
            or entry[2] != "AUTHORITY"
            or entry[4] is not InvocationAuthority
        ):
            raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
        item = entry[3]
        if (
            item.authority is not authority
            or canonical_identity_bytes(item.identity) != item.image
        ):
            raise IngressAbort(FailureCode.INTERNAL_CONTRACT_VIOLATION)
        return item

    def current(item: _Invocation, revision: int, *, active: bool) -> None:
        if type(revision) is not int or revision < 0:
            raise IngressAbort(FailureCode.INVALID_INPUT)
        state, actual = item.lifecycle
        if revision != actual:
            raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
        if state is InvocationState.CLOSED or (
            active and state is not InvocationState.ACTIVE
        ):
            raise IngressAbort(FailureCode.INVOCATION_NOT_ACTIVE)

    def view(domain: _Domain, item: _Invocation) -> InvocationView:
        image = _snapshot(
            CanonicalDescriptor(
                "InvocationViewFields",
                (
                    item.identity,
                    item.cause,
                    domain.runtime,
                    item.lifecycle[1],
                    item.lifecycle[0],
                ),
            )
        )
        return InvocationView(*image.values)

    @contextmanager
    def ledger_access(
        ledger: object, authority: object, revision: int, *, active: bool
    ):
        with access(ledger, "LEDGER") as (domain, registered), domain.lifecycle:
            with registry_lock:
                item = invocation_for(domain, authority)
            if item is not registered or item.ledger is not ledger:
                raise IngressAbort(FailureCode.AMBIGUOUS_BUDGET_OWNER)
            current(item, revision, active=active)
            with item.budget.lock:
                yield domain, item

    def reservation_for(item: _Invocation, token: object) -> _Reservation:
        if type(token) is not BudgetReservation:
            raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE)
        record = item.budget.index[1].get(id(token))
        if record is None or record.token is not token:
            raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE)
        payload = CanonicalDescriptor(
            "ReservationFields", (record.identity, record.units, record.work_class)
        )
        if canonical_identity_bytes(payload) != record.image:
            raise IngressAbort(FailureCode.INTERNAL_CONTRACT_VIOLATION)
        return record

    def unit_ordinal(value: object, limit: int) -> int:
        if type(value) is not int or not 0 <= value < limit:
            raise IngressAbort(FailureCode.INVALID_INPUT)
        return value

    def prepare_reservation(item, required_units, work_class):
        """Build a prospective index only. Caller owns lifecycle and ledger."""
        if type(required_units) is not int or required_units <= 0:
            raise IngressAbort(FailureCode.INVALID_INPUT)
        if type(work_class) is not CanonicalDescriptor:
            raise IngressAbort(FailureCode.INVALID_INPUT)
        units, records, sequence = item.budget.index
        if required_units > len(units):
            raise IngressAbort(FailureCode.BUDGET_ABORT)
        available = tuple(
            i for i, unit in enumerate(units) if unit.state == "AVAILABLE"
        )
        if required_units > len(available):
            raise IngressAbort(FailureCode.BUDGET_ABORT)
        chosen = available[:required_units]
        try:
            work = _snapshot(work_class)
            identity = CanonicalDescriptor(
                "InvocationReservationIdentity", (item.identity, sequence, work)
            )
            image = canonical_identity_bytes(
                CanonicalDescriptor("ReservationFields", (identity, chosen, work))
            )
        except (TypeError, ValueError) as error:
            raise IngressAbort(FailureCode.INVALID_INPUT) from error
        try:
            BudgetChargeView(
                item.identity,
                identity,
                CanonicalDescriptor(
                    "InvocationChargeUnitIdentity", (identity, chosen[-1])
                ),
                work,
            )
        except ValueError as error:
            raise IngressAbort(FailureCode.CAPACITY_ABORT) from error
        token = object.__new__(BudgetReservation)
        record = _Reservation(token, identity, chosen, work, image)
        staged_units = list(units)
        for index in chosen:
            staged_units[index] = _Unit("RESERVED", identity)
        staged_records = dict(records)
        staged_records[id(token)] = record
        return token, record, (tuple(staged_units), staged_records, sequence + 1)

    def prepare_consumption(item, reservation, unit_index, work_class):
        """No mutation: exact charge plus prospective consumed ledger index."""
        record = reservation_for(item, reservation)
        index = unit_ordinal(unit_index, len(item.budget.index[0]))
        if type(work_class) is not CanonicalDescriptor:
            raise IngressAbort(FailureCode.BUDGET_WORKCLASS_MISMATCH)
        try:
            work_bytes = canonical_identity_bytes(work_class)
        except (TypeError, ValueError) as error:
            raise IngressAbort(FailureCode.BUDGET_WORKCLASS_MISMATCH) from error
        if work_bytes != canonical_identity_bytes(record.work_class):
            raise IngressAbort(FailureCode.BUDGET_WORKCLASS_MISMATCH)
        units, records, sequence = item.budget.index
        if index not in record.units or units[index].state != "RESERVED":
            raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE)
        if units[index].reservation != record.identity:
            raise IngressAbort(FailureCode.INTERNAL_CONTRACT_VIOLATION)
        image = _snapshot(
            CanonicalDescriptor(
                "ChargeFields",
                (
                    item.identity,
                    record.identity,
                    CanonicalDescriptor(
                        "InvocationChargeUnitIdentity", (record.identity, index)
                    ),
                    record.work_class,
                ),
            )
        )
        output = BudgetChargeView(
            *image.values,
            source_kind=(
                BudgetSourceKind.FORECAST_ESCROW
                if getattr(item, "forecast", False)
                else BudgetSourceKind.INVOCATION_GENERAL
            ),
        )
        staged = list(units)
        staged[index] = _Unit("CONSUMED", units[index].reservation)
        return output, (tuple(staged), records, sequence)

    def inspect_charge(item, reservation, unit_index, work_class):
        """Genuine historical accounting binding, never a usable charge/permit.

        Used by exact effect retry lookup under lifecycle + ledger. State is
        deliberately not promoted to RESERVED; consumed/retired stays terminal.
        """
        record = reservation_for(item, reservation)
        index = unit_ordinal(unit_index, len(item.budget.index[0]))
        if index not in record.units:
            raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE)
        if type(work_class) is not CanonicalDescriptor or canonical_identity_bytes(
            work_class
        ) != canonical_identity_bytes(record.work_class):
            raise IngressAbort(FailureCode.BUDGET_WORKCLASS_MISMATCH)
        if item.budget.index[0][index].reservation != record.identity:
            raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE)
        data = _snapshot(
            CanonicalDescriptor(
                "ChargeFields",
                (
                    item.identity,
                    record.identity,
                    CanonicalDescriptor(
                        "InvocationChargeUnitIdentity", (record.identity, index)
                    ),
                    record.work_class,
                ),
            )
        )
        return BudgetChargeView(
            *data.values,
            source_kind=(
                BudgetSourceKind.FORECAST_ESCROW
                if getattr(item, "forecast", False)
                else BudgetSourceKind.INVOCATION_GENERAL
            ),
        )

    def retire_unused(item: _Invocation) -> None:
        units, records, sequence = item.budget.index
        retirement = CanonicalDescriptor(
            "InvocationRetirementReservation", (item.identity, item.lifecycle[1])
        )
        staged = []
        for unit in units:
            if unit.state == "AVAILABLE":
                # Administrative AVAILABLE -> RESERVED -> RETIRED, published
                # atomically. No positive authority or executable charge issued.
                unit = _Unit("RESERVED", retirement)
            if unit.state == "RESERVED":
                unit = _Unit("RETIRED", unit.reservation)
            staged.append(unit)
        item.budget.index = (tuple(staged), records, sequence)

    class InvocationBudgetLedger(_OpaqueHandle):
        __slots__ = ()

        def reserve(
            self,
            authority: object,
            revision: int,
            required_units: int,
            work_class: CanonicalDescriptor,
        ) -> BudgetReservation:
            """Reserve the exact complete frozen envelope or change nothing."""
            if type(required_units) is not int or required_units <= 0:
                raise IngressAbort(FailureCode.INVALID_INPUT)
            if type(work_class) is not CanonicalDescriptor:
                raise IngressAbort(FailureCode.INVALID_INPUT)
            with ledger_access(self, authority, revision, active=True) as (_, item):
                token, _, staged = prepare_reservation(item, required_units, work_class)
                item.budget.index = staged
                return token

        def reservation_view(
            self, authority: object, revision: int, reservation: object
        ) -> CanonicalDescriptor:
            with ledger_access(self, authority, revision, active=False) as (_, item):
                record = reservation_for(item, reservation)
                return _snapshot(
                    CanonicalDescriptor(
                        "ReservationFields",
                        (record.identity, record.units, record.work_class),
                    )
                )

        def consume(
            self,
            authority: object,
            revision: int,
            reservation: object,
            unit_index: int,
            work_class: CanonicalDescriptor,
        ) -> BudgetChargeView:
            """Accounting transition only: no permit, dispatch or semantic effect."""
            with ledger_access(self, authority, revision, active=True) as (_, item):
                output, staged = prepare_consumption(
                    item, reservation, unit_index, work_class
                )
                item.budget.index = staged
                return output

        def retire(self, authority: object, revision: int, reservation: object) -> None:
            with ledger_access(self, authority, revision, active=False) as (_, item):
                record = reservation_for(item, reservation)
                units, records, sequence = item.budget.index
                if not any(units[index].state == "RESERVED" for index in record.units):
                    raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE)
                staged = list(units)
                for index in record.units:
                    if units[index].state == "RESERVED":
                        staged[index] = _Unit("RETIRED", units[index].reservation)
                item.budget.index = (tuple(staged), records, sequence)

        def retire_unused(self, authority: object, revision: int) -> None:
            with ledger_access(self, authority, revision, active=False) as (_, item):
                retire_unused(item)

        def summary(self, authority: object) -> BudgetLedgerView:
            with access(self, "LEDGER") as (domain, registered), domain.lifecycle:
                with registry_lock:
                    item = invocation_for(domain, authority)
                if item is not registered:
                    raise IngressAbort(FailureCode.AMBIGUOUS_BUDGET_OWNER)
                with item.budget.lock:
                    units = item.budget.index[0]
                    counts = tuple(
                        sum(unit.state == status for unit in units)
                        for status in (
                            "AVAILABLE",
                            "RESERVED",
                            "CONSUMED",
                            "RETIRED",
                        )
                    )
                    return BudgetLedgerView(
                        _snapshot(item.identity),
                        len(units),
                        *counts,
                        delegated=sum(
                            u.state == "DELEGATED_FORECAST_POOL" for u in units
                        ),
                    )

        def unit_state(self, authority: object, index: int) -> str:
            with access(self, "LEDGER") as (domain, registered), domain.lifecycle:
                with registry_lock:
                    item = invocation_for(domain, authority)
                if item is not registered:
                    raise IngressAbort(FailureCode.AMBIGUOUS_BUDGET_OWNER)
                with item.budget.lock:
                    index = unit_ordinal(index, len(item.budget.index[0]))
                    return item.budget.index[0][index].state

    class InvocationRuntime(_OpaqueHandle):
        __slots__ = ()

        def admit(self, capability: object) -> InvocationAuthority:
            """No caller-selected cause, identity, budget, source or mint callback."""
            nonlocal handles
            before_core_guard()
            if capability is None:
                raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
            with (
                access(self, "RUNTIME") as (domain, _),
                _pinned_invocation_cause(domain.ingress, capability) as (
                    runtime,
                    cause,
                ),
                domain.lifecycle,
            ):
                if runtime != domain.runtime or type(cause) is not InvocationCauseID:
                    raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
                live(domain)
                key = canonical_identity_bytes(cause)
                previous = domain.causes.get(key)
                if previous is not None:
                    with registry_lock:
                        invocation_for(domain, previous.authority)
                    # Even terminal retry returns ONLY the original handle;
                    # no lifecycle reset or replacement ledger can occur.
                    return previous.authority
                if len(domain.causes) >= domain.capacity:
                    raise IngressAbort(FailureCode.CAPACITY_ABORT)
                try:
                    identity = _snapshot(
                        CanonicalDescriptor(
                            "InvocationIdentity", (domain.runtime, cause)
                        )
                    )
                    image = canonical_identity_bytes(identity)
                except (TypeError, ValueError) as error:
                    raise IngressAbort(FailureCode.INVALID_INPUT) from error
                # An admitted invocation must be representable throughout its
                # complete known lifecycle, including authority-reducing close.
                # Never accept a cause that would strand an unclosable owner.
                try:
                    for revision, status in enumerate(
                        (
                            InvocationState.ACTIVE,
                            InvocationState.CLOSING,
                            InvocationState.CLOSED,
                        )
                    ):
                        InvocationView(
                            identity, cause, domain.runtime, revision, status
                        )
                    CanonicalDescriptor(
                        "InvocationRetirementReservation", (identity, 1)
                    )
                except ValueError as error:
                    raise IngressAbort(FailureCode.CAPACITY_ABORT) from error
                authority = object.__new__(InvocationAuthority)
                ledger = object.__new__(InvocationBudgetLedger)
                budget = _Budget(
                    index=(tuple(_Unit() for _ in range(domain.initial_budget)), {}, 0)
                )
                item = _Invocation(authority, ledger, identity, cause, image, budget)
                # Stage all weakrefs/index allocation before one locked
                # admission publication. No root allocator or Core write.
                causes = dict(domain.causes)
                causes[key] = item
                with registry_lock:
                    staged_handles = dict(handles)
                    staged_handles[id(authority)] = (
                        ref(authority),
                        domain,
                        "AUTHORITY",
                        item,
                        InvocationAuthority,
                    )
                    staged_handles[id(ledger)] = (
                        ref(ledger),
                        domain,
                        "LEDGER",
                        item,
                        InvocationBudgetLedger,
                    )
                    domain.causes, handles = causes, staged_handles
                return authority

        def ledger(self, authority: object) -> InvocationBudgetLedger:
            with (
                access(self, "RUNTIME") as (domain, _),
                domain.lifecycle,
                registry_lock,
            ):
                return invocation_for(domain, authority).ledger

        def describe(self, authority: object) -> InvocationView:
            with access(self, "RUNTIME") as (domain, _), domain.lifecycle:
                with registry_lock:
                    item = invocation_for(domain, authority)
                return view(domain, item)

        @property
        def registry_status(self) -> tuple[int, int]:
            with access(self, "RUNTIME") as (domain, _), domain.lifecycle:
                live(domain)
                return len(domain.causes), domain.capacity

        @contextmanager
        def active_guard(self, authority: object, revision: int):
            """Future child creation/publication must linearize inside this gate.

            No child is issued here. Do not wait for child completion inside it.
            A caller needing the Core barrier must acquire it BEFORE this gate.
            """
            with access(self, "RUNTIME") as (domain, _), domain.lifecycle:
                with registry_lock:
                    item = invocation_for(domain, authority)
                current(item, revision, active=True)
                yield

        def validate(self, authority: object, revision: int) -> None:
            with self.active_guard(authority, revision):
                pass

        def begin_close(self, authority: object, revision: int) -> InvocationView:
            with access(self, "RUNTIME") as (domain, _), domain.lifecycle:
                with registry_lock:
                    item = invocation_for(domain, authority)
                current(item, revision, active=False)
                if item.lifecycle[0] is InvocationState.ACTIVE:
                    # Build the exact immutable returned view first.
                    output = view(domain, item)
                    output = InvocationView(
                        output.identity,
                        output.cause,
                        output.runtime,
                        revision + 1,
                        InvocationState.CLOSING,
                    )
                    item.lifecycle = (InvocationState.CLOSING, revision + 1)
                    if item.cie_child is not None:
                        # Fixed private Unit-4 child, not a caller callback. No
                        # asynchronous drain/wait occurs under this barrier.
                        item.cie_child.parent_close()
                    if item.work_owner is not None:
                        item.work_owner.parent_close()
                    if item.effect_owner is not None:
                        item.effect_owner.parent_close()
                    return output
                return view(domain, item)

        def finalize_close(self, authority: object, revision: int) -> bool:
            """Nonblocking readiness check: caller drains outside the barrier."""
            with access(self, "RUNTIME") as (domain, _), domain.lifecycle:
                with registry_lock:
                    item = invocation_for(domain, authority)
                current(item, revision, active=False)
                if item.lifecycle[0] is not InvocationState.CLOSING:
                    raise IngressAbort(FailureCode.INVOCATION_NOT_ACTIVE)
                with item.budget.lock:
                    if item.nondelegated_children or any(
                        unit.state in ("AVAILABLE", "RESERVED")
                        for unit in item.budget.index[0]
                    ):
                        return False
                    item.lifecycle = (InvocationState.CLOSED, revision + 1)
                    return True

    def create_invocation_runtime(
        ingress: object, limits: InvocationLimits
    ) -> InvocationRuntime:
        """Trusted composition-root bootstrap; never callable by operators.

        Exactly one runtime per Unit-2 runtime identity, including after GC.
        The frozen policy is copied to private scalars, not retained by alias.
        """
        nonlocal handles, used_runtimes
        before_core_guard()
        if (
            type(ingress) is not InvocationCauseIngress
            or type(limits) is not InvocationLimits
        ):
            raise IngressAbort(FailureCode.INVALID_INPUT)
        limits.__post_init__()
        initial_budget, capacity = limits.initial_budget, limits.cause_capacity
        # Revalidate the captured scalars, including frozen-field bypass races.
        InvocationLimits(initial_budget, capacity)
        with _pinned_invocation_cause(ingress) as (runtime, cause):
            if cause is not None:
                raise IngressAbort(FailureCode.INTERNAL_CONTRACT_VIOLATION)
            key = canonical_identity_bytes(runtime)
            with registry_lock:
                if key in used_runtimes:
                    raise IngressAbort(
                        FailureCode.INVALID_FORMAL_AUTHORITY,
                        "invocation runtime identity cannot recycle",
                    )
                if len(used_runtimes) >= max_runtimes:
                    raise IngressAbort(FailureCode.CAPACITY_ABORT)
                owner = object.__new__(InvocationRuntime)
                domain = _Domain(ingress, runtime, initial_budget, capacity)
                domain.owner_id = id(owner)

                @_deferred_cleanup
                def discard(reference: ReferenceType) -> None:
                    # Every runtime/ledger operation pins its owner. No use is
                    # in flight here; no lifecycle wait or reverse acquisition.
                    domain.retired = True
                    for item in domain.causes.values():
                        if item.lifecycle[0] is InvocationState.ACTIVE:
                            item.lifecycle = (
                                InvocationState.CLOSING,
                                item.lifecycle[1] + 1,
                            )
                        if item.lifecycle[0] is InvocationState.CLOSING:
                            if item.cie_child is not None:
                                item.cie_child.parent_close()
                            if item.work_owner is not None:
                                item.work_owner.parent_close()
                            if item.effect_owner is not None:
                                item.effect_owner.parent_close()
                            retire_unused(item)
                            item.lifecycle = (
                                InvocationState.CLOSED,
                                item.lifecycle[1] + 1,
                            )
                    with registry_lock:
                        # Local bounded cleanup only; never scan other runtimes.
                        own_ids = [domain.owner_id]
                        for item in domain.causes.values():
                            own_ids.extend((id(item.authority), id(item.ledger)))
                        for handle_id in own_ids:
                            entry = handles.get(handle_id)
                            if entry is not None and entry[1] is domain:
                                handles.pop(handle_id)
                    domain.causes = {}

                owner_ref = ref(owner, discard)
                domain.owner_ref = owner_ref
                staged_handles = dict(handles)
                staged_used = set(used_runtimes)
                staged_handles[id(owner)] = (
                    owner_ref,
                    domain,
                    "RUNTIME",
                    None,
                    InvocationRuntime,
                )
                staged_used.add(key)
                handles, used_runtimes = staged_handles, staged_used
                return owner

    @contextmanager
    def pinned_cie_parent(
        runtime: object,
        authority: object = None,
        revision: int | None = None,
        *,
        core: bool = False,
    ):
        """Private Unit-4 integration; never accepts caller validation callbacks.

        Holds existing barriers in Core -> lifecycle order, pins the genuine
        invocation runtime and exposes private owner state only to CIE runtime.
        """
        if core:
            before_core_guard()
        with access(runtime, "RUNTIME") as (domain, _):

            @contextmanager
            def binding_guard():
                if core:
                    with _pinned_core_binding(domain.ingress) as binding:
                        yield binding
                else:
                    yield None

            with binding_guard() as binding, domain.lifecycle:
                live(domain)
                item = None
                if authority is not None:
                    with registry_lock:
                        item = invocation_for(domain, authority)
                    if revision is not None:
                        current(item, revision, active=True)
                yield domain, item, binding

    @contextmanager
    def pinned_work_budget(runtime, authority, revision, ledger):
        # Never call this from beneath Arena: Core -> lifecycle -> ledger.
        with (
            pinned_cie_parent(runtime, authority, revision, core=True) as (
                domain,
                item,
                binding,
            ),
            access(ledger, "LEDGER") as (budget_domain, registered),
        ):
            if (
                budget_domain is not domain
                or registered is not item
                or item.ledger is not ledger
            ):
                raise IngressAbort(FailureCode.AMBIGUOUS_BUDGET_OWNER)
            with item.budget.lock:
                yield domain, item, binding

    @contextmanager
    def pinned_effect_budget(runtime, authority, ledger, *, core=False):
        # Allows historical lookup after close, never reactivates an owner.
        with (
            pinned_cie_parent(runtime, authority, core=core) as (domain, item, binding),
            access(ledger, "LEDGER") as (own, registered),
        ):
            if own is not domain or registered is not item or item.ledger is not ledger:
                raise IngressAbort(FailureCode.AMBIGUOUS_BUDGET_OWNER)
            with item.budget.lock:
                yield domain, item, binding

    def prepare_forecast_delegation(item, horizon, binding):
        """Prospective one-way issuance. Caller holds Core/Life/parent ledger.

        All units/reservations use the existing accounting structures. Nothing
        is published here; the Unit-6 seal publishes parent and pool together.
        """
        if type(horizon) is not int or not 1 <= horizon <= 64:
            raise IngressAbort(FailureCode.INVALID_INPUT)
        work = CanonicalDescriptor("ForecastEscrowReservation", (binding, horizon))
        _, reservation, staged_parent = prepare_reservation(item, 2 * horizon, work)
        identity = CanonicalDescriptor(
            "ForecastEscrowIdentity", (reservation.identity,)
        )
        units, records, sequence = staged_parent
        delegated = list(units)
        for index in reservation.units:
            delegated[index] = _Unit("DELEGATED_FORECAST_POOL", reservation.identity)
        staged_parent = (tuple(delegated), records, sequence)
        pool_units, pool_records, tokens = [], {}, []
        for ordinal in range(2 * horizon):
            phase = "CAPTURE" if ordinal % 2 == 0 else "EVALUATION"
            work_class = CanonicalDescriptor(
                "PredictionWorkClass", (phase, ordinal // 2 + 1)
            )
            rid = CanonicalDescriptor(
                "ForecastReservationIdentity", (identity, ordinal, work_class)
            )
            token = object.__new__(BudgetReservation)
            record = _Reservation(
                token,
                rid,
                (ordinal,),
                work_class,
                canonical_identity_bytes(
                    CanonicalDescriptor(
                        "ReservationFields", (rid, (ordinal,), work_class)
                    )
                ),
            )
            pool_units.append(_Unit("RESERVED", rid))
            pool_records[id(token)] = record
            tokens.append(token)
        budget = _Budget(index=(tuple(pool_units), pool_records, 0))
        return _ForecastPool(identity, budget, tuple(tokens)), staged_parent

    def prepare_forecast_consumption(pool, offset, phase):
        if type(pool) is not _ForecastPool or type(offset) is not int:
            raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE)
        if type(phase) is not str or phase not in ("CAPTURE", "EVALUATION"):
            raise IngressAbort(FailureCode.BUDGET_WORKCLASS_MISMATCH)
        ordinal = 2 * (offset - 1) + (phase == "EVALUATION")
        if not 0 <= ordinal < len(pool.tokens):
            raise IngressAbort(FailureCode.BUDGET_ABORT)
        return prepare_consumption(
            pool,
            pool.tokens[ordinal],
            ordinal,
            CanonicalDescriptor("PredictionWorkClass", (phase, offset)),
        )

    def forecast_retirement(pool, index=None):
        if type(pool) is not _ForecastPool:
            raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE)
        units, records, sequence = pool.budget.index if index is None else index
        return (
            tuple(
                _Unit("RETIRED", u.reservation) if u.state == "RESERVED" else u
                for u in units
            ),
            records,
            sequence,
        )

    def validate_forecast_charge(pool, offset, phase, charge):
        if (
            type(pool) is not _ForecastPool
            or type(offset) is not int
            or type(charge) is not BudgetChargeView
        ):
            raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE)
        if phase not in ("CAPTURE", "EVALUATION"):
            raise IngressAbort(FailureCode.BUDGET_WORKCLASS_MISMATCH)
        ordinal = 2 * (offset - 1) + (phase == "EVALUATION")
        if (
            not 0 <= ordinal < len(pool.tokens)
            or pool.budget.index[0][ordinal].state != "CONSUMED"
        ):
            raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE)
        actual = inspect_charge(
            pool,
            pool.tokens[ordinal],
            ordinal,
            CanonicalDescriptor("PredictionWorkClass", (phase, offset)),
        )
        if canonical_identity_bytes(
            actual.canonical_descriptor()
        ) != canonical_identity_bytes(charge.canonical_descriptor()):
            raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE)

    return (
        InvocationRuntime,
        InvocationBudgetLedger,
        create_invocation_runtime,
        pinned_cie_parent,
        pinned_work_budget,
        prepare_reservation,
        prepare_consumption,
        pinned_effect_budget,
        inspect_charge,
        prepare_forecast_delegation,
        prepare_forecast_consumption,
        forecast_retirement,
        validate_forecast_charge,
    )


(
    InvocationRuntime,
    InvocationBudgetLedger,
    create_invocation_runtime,
    _pinned_cie_parent,
    _pinned_work_budget,
    _prepare_reservation,
    _prepare_consumption,
    _pinned_effect_budget,
    _inspect_charge,
    _prepare_forecast_delegation,
    _prepare_forecast_consumption,
    _forecast_retirement,
    _validate_forecast_charge,
) = _build_invocation_system()
del _build_invocation_system
