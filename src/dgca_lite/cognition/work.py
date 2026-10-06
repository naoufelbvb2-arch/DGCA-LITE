"""Unit-5 atomic pure-work authorization. No effects or cognitive operators.

Operational state is bounded by the nonrenewable invocation budget. The only
worker is a compiled closed-value copy; no caller callable is ever dispatched.
Audit/result descriptors are data, not authority. No publication API exists.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
from weakref import ref

from .authority import IngressAbort, _OpaqueHandle
from .budget import BudgetChargeView
from .cie import CIERuntime, _pinned_cie_work, _pinned_work_policy
from .contracts import ControlPlaneOperation
from .identity import CanonicalDescriptor, SnapshotBinding
from .ingress import _snapshot
from .invocation import (
    InvocationRuntime,
    _pinned_cie_parent,
    _pinned_work_budget,
    _prepare_consumption,
    _prepare_reservation,
)
from .locks import RankedBarrier, _deferred_cleanup
from .operation import (
    FrozenWork,
    OperationType,
    PreparedDispatch,
    PureWorkResultView,
    WorkPolicy,
    compiled_contract,
    compiled_policy_descriptor,
    freeze_work,
)
from .serialization import canonical_identity_bytes
from .types import BudgetSourceKind, FailureCode, InvocationState, WorkEffectClass


class WorkExecutionPermit(_OpaqueHandle):
    __slots__ = ()


def _closed_value_worker(frozen_input, permit, context):
    """Fixed pure implementation. No registry/issuer/owner/callback is reachable
    through its arguments. The opaque permit itself exposes no authority API.
    This is mechanical data copying, not a new cognitive capability.
    """
    if (
        type(permit) is not WorkExecutionPermit
        or type(context) is not CanonicalDescriptor
    ):
        raise IngressAbort(FailureCode.INTERNAL_CONTRACT_VIOLATION)
    return _snapshot(frozen_input)


def _build_work_system():
    registry_lock = RankedBarrier(5)
    handles = {}
    controls = tuple((op, op.value) for op in ControlPlaneOperation)

    @dataclass(slots=True)
    class _Runtime:
        parent: object
        cie: object
        policy: WorkPolicy
        owner_ref: object = None
        owners: dict = field(default_factory=dict)
        retired: bool = False

    @dataclass(slots=True)
    class _Permit:
        token: object
        owner: object
        authority: object
        revision: int
        work: object
        image: bytes | None
        binding: object
        state: str = "ISSUED"
        output: object = None

    @dataclass(slots=True)
    class _Owner:
        runtime: _Runtime
        lock: object = field(default_factory=lambda: RankedBarrier(4))
        # One pointer swaps the next deterministic ordinal and local permit map.
        index: tuple = field(default_factory=lambda: (0, {}))
        closing: bool = False

        def parent_close(self):
            with self.lock:
                self.closing = True
                for record in self.index[1].values():
                    if record.state == "ISSUED":
                        record.state = "RETIRED"
                    # Running workers hold their already-frozen local input.
                    # Terminal registry never retains semantic work/audit data.
                    record.work = record.image = record.binding = record.output = None

    @contextmanager
    def access(handle, role):
        with registry_lock:
            entry = handles.get(id(handle))
            if (
                entry is None
                or entry[0]() is not handle
                or entry[2] != role
                or type(handle) is not entry[3]
            ):
                raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
            runtime, item = entry[1], entry[4]
            owner = runtime.owner_ref()
            if owner is None or runtime.retired:
                raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
        yield runtime, item
        del owner

    def check_runtime(handle, expected):
        with access(handle, "RUNTIME") as (actual, _):
            if actual is not expected:
                raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)

    def checked_work(runtime, work, item, revision):
        try:
            frozen = freeze_work(runtime.policy, work)
        except (TypeError, ValueError, AttributeError) as error:
            raise IngressAbort(FailureCode.INVALID_INPUT) from error
        if frozen.contract.effect_class is not WorkEffectClass.PURE_COMPUTE:
            raise IngressAbort(FailureCode.EXEMPTION_CONTRACT_VIOLATION)
        if (
            canonical_identity_bytes(frozen.owner_identity) != item.image
            or frozen.owner_revision != revision
        ):
            raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
        return frozen

    class WorkRuntime(_OpaqueHandle):
        __slots__ = ()

        def prepare_work(
            self,
            authority,
            revision,
            snapshot,
            frozen_input,
            *,
            operation=OperationType.CLONE_CLOSED_VALUE,
        ):
            with (
                access(self, "RUNTIME") as (runtime, _),
                _pinned_cie_parent(runtime.parent, authority, revision) as (_, item, _),
            ):
                if type(operation) is not OperationType or not any(
                    operation is op for op in OperationType
                ):
                    raise IngressAbort(FailureCode.UNKNOWN_OPERATION_TYPE)
                if type(snapshot) is not SnapshotBinding:
                    raise IngressAbort(FailureCode.INVALID_INPUT)
                try:
                    # The bounded representation check precedes cloning.
                    canonical_identity_bytes(frozen_input, runtime.policy.value_limits)
                    data = _snapshot(frozen_input, limits=runtime.policy.value_limits)
                    contract = compiled_contract(runtime.policy, operation, data)
                    fields = _snapshot(
                        CanonicalDescriptor(
                            "FrozenOwner", (item.identity, revision, snapshot)
                        )
                    )
                    return FrozenWork(contract, data, *fields.values)
                except (TypeError, ValueError, AttributeError) as error:
                    raise IngressAbort(FailureCode.INVALID_INPUT) from error

        def reserve(self, authority, revision, cie, ledger, work):
            """Preflight complete envelope AND returned charge plan before reserve."""
            with (
                access(self, "RUNTIME") as (runtime, _),
                _pinned_work_budget(runtime.parent, authority, revision, ledger) as (
                    _,
                    item,
                    core,
                ),
            ):
                frozen = checked_work(runtime, work, item, revision)
                with _pinned_cie_work(
                    runtime.cie, cie, item, frozen.snapshot_binding, core
                ):
                    token, record, staged = _prepare_reservation(
                        item,
                        frozen.contract.resource_envelope.charge_units,
                        frozen.contract.work_class,
                    )
                    ordinal = record.units[0]
                    charge = BudgetChargeView(
                        item.identity,
                        record.identity,
                        CanonicalDescriptor(
                            "InvocationChargeUnitIdentity", (record.identity, ordinal)
                        ),
                        record.work_class,
                    )
                    try:
                        output = PreparedDispatch(frozen, charge, ordinal)
                        # Complete eventual permit/result shell must fit too.
                        binding = CanonicalDescriptor(
                            "WorkExecutionPermitBinding",
                            (
                                frozen.canonical_descriptor(),
                                item.identity,
                                revision,
                                charge.canonical_descriptor(),
                                len(item.budget.index[0]),
                            ),
                        )
                        PureWorkResultView(binding, frozen.frozen_input)
                    except (TypeError, ValueError) as error:
                        raise IngressAbort(FailureCode.CAPACITY_ABORT) from error
                    item.budget.index = staged
                    return token, output

        def authorize_and_charge(
            self, authority, revision, cie, ledger, reservation, prepared
        ):
            """One linearizable Core/Life/Ledger/Arena/Owner/Registry transaction."""
            with (
                access(self, "RUNTIME") as (runtime, _),
                _pinned_work_budget(runtime.parent, authority, revision, ledger) as (
                    _,
                    item,
                    core,
                ),
            ):
                if type(prepared) is not PreparedDispatch:
                    raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE)
                try:
                    source_work, source_charge, ordinal = (
                        prepared.work,
                        prepared.charge,
                        prepared.unit_ordinal,
                    )
                    frozen = checked_work(runtime, source_work, item, revision)
                    if type(source_charge) is not BudgetChargeView:
                        raise TypeError("closed charge binding required")
                    image = _snapshot(source_charge.canonical_descriptor())
                    if (
                        image.kind != "BudgetChargeBinding"
                        or len(image.values) != 5
                        or image.values[0] is not BudgetSourceKind.INVOCATION_GENERAL
                    ):
                        raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE)
                    supplied_charge = BudgetChargeView(*image.values[1:])
                    PreparedDispatch(frozen, supplied_charge, ordinal)
                except (TypeError, ValueError, AttributeError) as error:
                    raise IngressAbort(FailureCode.INVALID_INPUT) from error
                with _pinned_cie_work(
                    runtime.cie, cie, item, frozen.snapshot_binding, core
                ):
                    owner = item.work_owner
                    if owner is None:
                        owner = _Owner(runtime)
                    if owner.runtime is not runtime:
                        raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
                    with owner.lock:
                        if owner.closing:
                            raise IngressAbort(FailureCode.INVOCATION_NOT_ACTIVE)
                        charge, staged_budget = _prepare_consumption(
                            item, reservation, ordinal, frozen.contract.work_class
                        )
                        if canonical_identity_bytes(
                            charge.canonical_descriptor()
                        ) != canonical_identity_bytes(
                            supplied_charge.canonical_descriptor()
                        ):
                            raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE)
                        epoch, records = owner.index
                        if epoch >= len(item.budget.index[0]):
                            raise IngressAbort(FailureCode.CAPACITY_ABORT)
                        binding = _snapshot(
                            CanonicalDescriptor(
                                "WorkExecutionPermitBinding",
                                (
                                    frozen.canonical_descriptor(),
                                    item.identity,
                                    revision,
                                    charge.canonical_descriptor(),
                                    epoch,
                                ),
                            )
                        )
                        # No allocations/validators remain after registry insertion.
                        PureWorkResultView(binding, frozen.frozen_input)
                        token = object.__new__(WorkExecutionPermit)
                        record = _Permit(
                            token,
                            owner,
                            authority,
                            revision,
                            frozen,
                            canonical_identity_bytes(frozen.canonical_descriptor()),
                            binding,
                        )
                        local_records = dict(records)
                        local_records[id(token)] = record
                        staged_owner = (epoch + 1, local_records)
                        staged_owners = dict(runtime.owners)
                        staged_owners[id(authority)] = owner
                        registered = (
                            ref(token),
                            runtime,
                            "PERMIT",
                            WorkExecutionPermit,
                            record,
                        )
                        with registry_lock:
                            handles[id(token)] = registered
                            # Linearization: all pointers published while every
                            # observer/closer is excluded by the same barriers.
                            item.budget.index = staged_budget
                            owner.index = staged_owner
                            runtime.owners = staged_owners
                            item.work_owner = owner
                        return token

        def permit_binding(self, permit):
            with access(permit, "PERMIT") as (runtime, record):
                check_runtime(self, runtime)
                with _pinned_cie_parent(runtime.parent), record.owner.lock:
                    if record.binding is None:
                        raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
                    return _snapshot(record.binding)

        def execute(self, permit, work):
            with access(permit, "PERMIT") as (runtime, record):
                check_runtime(self, runtime)
                with (
                    _pinned_cie_parent(
                        runtime.parent, record.authority, record.revision
                    ),
                    record.owner.lock,
                ):
                    if record.owner.closing or record.state != "ISSUED":
                        raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
                    try:
                        frozen = freeze_work(runtime.policy, work)
                    except (TypeError, ValueError, AttributeError) as error:
                        raise IngressAbort(FailureCode.INVALID_INPUT) from error
                    if (
                        canonical_identity_bytes(frozen.canonical_descriptor())
                        != record.image
                    ):
                        raise IngressAbort(FailureCode.INVALID_INPUT)
                    binding = _snapshot(record.binding)
                    context = CanonicalDescriptor("PureExecutionContext", (binding,))
                    # One-shot claim occurs BEFORE leaving owner barriers.
                    record.state = "RUNNING"
                try:
                    output = _closed_value_worker(frozen.frozen_input, permit, context)
                    result = PureWorkResultView(binding, _snapshot(output))
                    private_result = PureWorkResultView(
                        _snapshot(binding), _snapshot(output)
                    )
                except BaseException:
                    with _pinned_cie_parent(runtime.parent), record.owner.lock:
                        record.state = "RETIRED"
                        record.work = record.image = record.binding = record.output = (
                            None
                        )
                    raise
                with _pinned_cie_parent(runtime.parent), record.owner.lock:
                    record.state = "DONE"
                    if not record.owner.closing:
                        # Never retain the returned object's alias, including
                        # frozen-dataclass __setattr__ bypass on caller data.
                        record.output = private_result
                return result

        def control(self, operation, authority, revision, *, permit=None):
            # Closed enum by original identity, not strings/caller classifications.
            if type(operation) is not ControlPlaneOperation or not any(
                operation is member and operation.value == literal
                for member, literal in controls
            ):
                raise IngressAbort(FailureCode.UNKNOWN_OPERATION_TYPE)
            with access(self, "RUNTIME") as (runtime, _):
                if operation is ControlPlaneOperation.READ_IMMUTABLE_LIFECYCLE_FLAG:
                    if permit is not None:
                        raise IngressAbort(FailureCode.EXEMPTION_CONTRACT_VIOLATION)
                    view = InvocationRuntime.describe(runtime.parent, authority)
                    if type(revision) is not int or revision != view.revision:
                        raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
                    return view.state
                if (
                    operation
                    is ControlPlaneOperation.AUTHORITY_REDUCING_LIFECYCLE_BOOKKEEPING
                ):
                    if permit is not None:
                        raise IngressAbort(FailureCode.EXEMPTION_CONTRACT_VIOLATION)
                    return InvocationRuntime.begin_close(
                        runtime.parent, authority, revision
                    )
                if operation is ControlPlaneOperation.RETIRE_UNUSED_CHARGE_UNITS:
                    if permit is not None:
                        raise IngressAbort(FailureCode.EXEMPTION_CONTRACT_VIOLATION)
                    ledger = InvocationRuntime.ledger(runtime.parent, authority)
                    ledger.retire_unused(authority, revision)
                    return None
                with _pinned_cie_parent(runtime.parent, authority) as (_, item, _):
                    if type(revision) is not int or revision != item.lifecycle[1]:
                        raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
                    owner = item.work_owner
                    if owner is None or owner.runtime is not runtime:
                        raise IngressAbort(FailureCode.EXEMPTION_CONTRACT_VIOLATION)
                    with owner.lock:
                        if (
                            operation
                            is ControlPlaneOperation.RELEASE_TERMINAL_REGISTRY_CAPACITY
                        ):
                            if permit is not None or not owner.closing:
                                raise IngressAbort(
                                    FailureCode.EXEMPTION_CONTRACT_VIOLATION
                                )
                            removable = tuple(
                                key
                                for key, rec in owner.index[1].items()
                                if rec.state != "RUNNING"
                            )
                            remaining = {
                                key: rec
                                for key, rec in owner.index[1].items()
                                if rec.state == "RUNNING"
                            }
                            with registry_lock:
                                for key in removable:
                                    handles.pop(key, None)
                                owner.index = (owner.index[0], remaining)
                            return len(removable)
                        if (
                            item.lifecycle[0] is not InvocationState.ACTIVE
                            or owner.closing
                        ):
                            raise IngressAbort(FailureCode.INVOCATION_NOT_ACTIVE)
                        with access(permit, "PERMIT") as (own, record):
                            if (
                                own is not runtime
                                or record.owner is not owner
                                or record.state != "DONE"
                                or record.output is None
                            ):
                                raise IngressAbort(
                                    FailureCode.EXEMPTION_CONTRACT_VIOLATION
                                )
                            if (
                                operation
                                is ControlPlaneOperation.ATTACH_ALREADY_PRODUCED_DESCRIPTOR
                            ):
                                # Existing immutable data only; no arena attachment,
                                # semantic publication, callback or positive authority.
                                return _snapshot(record.output.canonical_descriptor())
                            if (
                                operation
                                is ControlPlaneOperation.CANONICAL_COMPARE_WITHIN_ALREADY_CHARGED_PARENT_WORK
                            ):
                                # Only the inputs/output of this already-charged
                                # bounded copy. No arbitrary frontier arguments.
                                return canonical_identity_bytes(
                                    record.work.frozen_input
                                ) == canonical_identity_bytes(record.output.output)
                            raise IngressAbort(FailureCode.EXEMPTION_CONTRACT_VIOLATION)

    def create_work_runtime(parent, cie, *, policy=None):
        """Trusted composition-root installation, once and before the first CIE."""
        if policy is None:
            policy = WorkPolicy()
        if (
            type(parent) is not InvocationRuntime
            or type(cie) is not CIERuntime
            or type(policy) is not WorkPolicy
        ):
            raise IngressAbort(FailureCode.INVALID_INPUT)
        data = policy.canonical_descriptor().values
        frozen_policy = WorkPolicy(*data)
        catalogue = compiled_policy_descriptor(frozen_policy)
        with (
            _pinned_cie_parent(parent) as (domain, _, _),
            _pinned_work_policy(cie, parent) as cie_state,
        ):
            if domain.work_attached:
                raise IngressAbort(FailureCode.INVALID_POLICY_BINDING)
            l3 = _snapshot(
                CanonicalDescriptor(
                    "L3Unit5PolicyBinding", (cie_state.l3_policy, catalogue)
                )
            )
            owner = object.__new__(WorkRuntime)
            runtime = _Runtime(parent, cie, frozen_policy)
            key = id(owner)

            @_deferred_cleanup
            def discard(reference):
                with _pinned_cie_parent(parent):
                    runtime.retired = True
                    for own in runtime.owners.values():
                        own.parent_close()
                        with registry_lock:
                            for token_id in own.index[1]:
                                handles.pop(token_id, None)
                        own.index = (own.index[0], {})
                    with registry_lock:
                        handles.pop(key, None)
                    runtime.owners = {}

            owner_ref = ref(owner, discard)
            runtime.owner_ref = owner_ref
            registered = (owner_ref, runtime, "RUNTIME", WorkRuntime, None)
            with registry_lock:
                handles[key] = registered
                cie_state.l3_policy = l3
                cie_state.work_attached = True
                domain.work_attached = True
            return owner

    return WorkRuntime, create_work_runtime


WorkRuntime, create_work_runtime = _build_work_system()
del _build_work_system
