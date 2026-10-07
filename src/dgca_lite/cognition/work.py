"""Shared atomic pure-work authorization and fixed capability-free operators.

Operational state is bounded by the nonrenewable invocation budget. The only
workers are closed-value copy and compiled Reasoning/Prediction functions;
no caller callable is dispatched. Results are data, never publication authority.
"""

from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from weakref import ref

from .authority import IngressAbort, _OpaqueHandle
from .budget import BudgetChargeView
from .cie import (
    CIERuntime,
    _pinned_cie_work,
    _pinned_effect_context,
    _pinned_work_policy,
)
from .contracts import ControlPlaneOperation
from .identity import CanonicalDescriptor, SnapshotBinding
from .ingress import _pinned_prediction_core, _reasoning_sources, _snapshot
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
    work_limits,
)
from .reasoning.schemas import ReasoningOperation, ReasoningPolicy
from .serialization import canonical_identity_bytes
from .types import (
    BudgetSourceKind,
    FailureCode,
    ForecastStatus,
    InvocationState,
    WorkEffectClass,
)


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


def _permit_identity(work):
    if type(work.contract.operation_type) is not ReasoningOperation:
        return work.canonical_descriptor()
    # The gate proves that the complete input arena is EXACTLY this immutable
    # snapshot. Discovery/evaluation are deterministic functions of it + branch.
    # Seed additionally binds every exact authorized source descriptor. This is
    # a complete local reference identity, never a hash or caller-chosen key.
    _, branch, extra = work.frozen_input.values
    return CanonicalDescriptor(
        "ExactReasoningWorkIdentity",
        (
            work.contract.canonical_descriptor(),
            work.snapshot_binding,
            branch,
            extra if work.contract.operation_type is ReasoningOperation.SEED else None,
        ),
    )


def _reasoning_source_bounds(
    policy, capabilities, internal_results, prediction_views=()
):
    if (
        type(capabilities) is not tuple
        or type(internal_results) is not tuple
        or type(prediction_views) is not tuple
    ):
        raise IngressAbort(FailureCode.INVALID_INPUT)
    # Bound the entire seed group before inspecting either container's members.
    if (
        len(capabilities) + len(internal_results) + len(prediction_views)
        > policy.max_sources
    ):
        raise IngressAbort(FailureCode.CAPACITY_ABORT)


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
        reasoning_policy: object = None
        prediction_policy: object = None

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
        prediction: bool = False
        origin: object = None
        audit_identity: object = None

    @dataclass(slots=True)
    class _Owner:
        runtime: _Runtime
        lock: object = field(default_factory=lambda: RankedBarrier(4))
        # One pointer swaps the next deterministic ordinal and local permit map.
        index: tuple = field(default_factory=lambda: (0, {}))
        closing: bool = False

        def prediction_epoch_close(self, binding):
            with self.lock:
                for record in self.index[1].values():
                    if (
                        record.prediction
                        and record.audit_identity is not None
                        and record.audit_identity.kind == "PredictionWorkPermitBinding"
                        and record.audit_identity.values[0].cie == binding
                    ):
                        record.state = "RETIRED"
                        record.work = record.image = record.binding = record.output = (
                            record.origin
                        ) = None

        def parent_close(self):
            with self.lock:
                self.closing = True
                for record in self.index[1].values():
                    if record.state == "ISSUED":
                        record.state = "RETIRED"
                    # Running workers hold their already-frozen local input.
                    # Terminal registry never retains semantic work/audit data.
                    record.work = record.image = record.binding = record.output = (
                        record.origin
                    ) = None

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
            frozen = freeze_work(runtime.policy, work, runtime.reasoning_policy)
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
                if type(operation) not in (
                    OperationType,
                    ReasoningOperation,
                ) or not any(
                    operation is op for op in (*OperationType, *ReasoningOperation)
                ):
                    raise IngressAbort(FailureCode.UNKNOWN_OPERATION_TYPE)
                if type(snapshot) is not SnapshotBinding:
                    raise IngressAbort(FailureCode.INVALID_INPUT)
                try:
                    # The bounded representation check precedes cloning.
                    limits = work_limits(
                        runtime.policy, operation, runtime.reasoning_policy
                    )
                    canonical_identity_bytes(frozen_input, limits)
                    data = _snapshot(frozen_input, limits=limits)
                    contract = compiled_contract(
                        runtime.policy, operation, data, runtime.reasoning_policy
                    )
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
                                _permit_identity(frozen),
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
            self,
            authority,
            revision,
            cie,
            ledger,
            reservation,
            prepared,
            *,
            source_capabilities=None,
            internal_results=(),
            prediction_views=(),
            discovery_permit=None,
        ):
            """One linearizable Core/Life/Ledger/Arena/Owner/Registry transaction."""
            with (
                access(self, "RUNTIME") as (runtime, _),
                _pinned_work_budget(runtime.parent, authority, revision, ledger) as (
                    domain,
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
                ) as epoch:
                    if type(frozen.contract.operation_type) is ReasoningOperation:
                        from .cie import _check_reasoning_capacity
                        from .reasoning.runtime import (
                            group_capacity,
                            validate_work_input,
                        )

                        expected_sources = None
                        if frozen.contract.operation_type is ReasoningOperation.SEED:
                            from .reasoning.assertions import internal_retrieval_view

                            _reasoning_source_bounds(
                                runtime.reasoning_policy,
                                source_capabilities,
                                internal_results,
                                prediction_views,
                            )
                            expected_sources = _reasoning_sources(
                                domain.ingress, source_capabilities
                            )
                            expected_sources += tuple(
                                internal_retrieval_view(v, frozen.snapshot_binding)
                                for v in internal_results
                            )
                            from .prediction.adapters import reasoning_view

                            expected_sources += tuple(
                                reasoning_view(v) for v in prediction_views
                            )
                        discovered = None
                        if (
                            frozen.contract.operation_type
                            is ReasoningOperation.EVALUATE
                        ):
                            discovered = completed_result(
                                self,
                                discovery_permit,
                                item,
                                frozen.snapshot_binding,
                                ReasoningOperation.DISCOVER,
                            )
                        validate_work_input(
                            frozen,
                            epoch.snapshot,
                            expected_sources,
                            discovered,
                            runtime.reasoning_policy,
                        )
                        _check_reasoning_capacity(
                            epoch, group_capacity(frozen, runtime.reasoning_policy)
                        )
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
                                    _permit_identity(frozen),
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
                if record.prediction:
                    return prediction_execute(self, runtime, record, work)
                with (
                    _pinned_cie_parent(
                        runtime.parent, record.authority, record.revision
                    ),
                    record.owner.lock,
                ):
                    if record.owner.closing or record.state != "ISSUED":
                        raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
                    try:
                        frozen = freeze_work(
                            runtime.policy, work, runtime.reasoning_policy
                        )
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
                    if type(frozen.contract.operation_type) is ReasoningOperation:
                        from .reasoning.runtime import compute

                        output = compute(
                            frozen.contract.operation_type,
                            frozen.frozen_input,
                            frozen.snapshot_binding,
                            runtime.reasoning_policy,
                        )
                    else:
                        output = _closed_value_worker(
                            frozen.frozen_input, permit, context
                        )
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
                    if record.state != "RETIRED":
                        record.state = "DONE"
                    if not record.owner.closing and record.state != "RETIRED":
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

    def create_work_runtime(
        parent, cie, *, policy=None, reasoning_policy=None, prediction_policy=None
    ):
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
        if reasoning_policy is not None:
            if type(reasoning_policy) is not ReasoningPolicy:
                raise IngressAbort(FailureCode.INVALID_POLICY_BINDING)
            reasoning_policy = ReasoningPolicy(
                *reasoning_policy.canonical_descriptor().values
            )
        catalogue = compiled_policy_descriptor(frozen_policy, reasoning_policy)
        if prediction_policy is not None:
            from .prediction.projection import PredictionPolicy

            if type(prediction_policy) is not PredictionPolicy:
                raise IngressAbort(FailureCode.INVALID_POLICY_BINDING)
            prediction_policy = PredictionPolicy(
                *prediction_policy.canonical_descriptor().values[:6]
            )
            catalogue = CanonicalDescriptor(
                "Unit8WorkCatalogue",
                (*catalogue.values, prediction_policy.canonical_descriptor()),
            )
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
            runtime = _Runtime(
                parent,
                cie,
                frozen_policy,
                reasoning_policy=reasoning_policy,
                prediction_policy=prediction_policy,
            )
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
                cie_state.reasoning_policy = reasoning_policy
                cie_state.prediction_policy = prediction_policy
                domain.work_attached = True
            return owner

    def completed_result(handle, permit, item, snapshot, operation=None):
        with (
            access(handle, "RUNTIME") as (runtime, _),
            access(permit, "PERMIT") as (own, record),
        ):
            if (
                own is not runtime
                or runtime.reasoning_policy is None
                or record.authority is not item.authority
            ):
                raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
            with record.owner.lock:
                if (
                    record.state != "DONE"
                    or record.output is None
                    or record.work is None
                ):
                    raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
                if type(record.work.contract.operation_type) is not ReasoningOperation:
                    raise IngressAbort(FailureCode.EXEMPTION_CONTRACT_VIOLATION)
                if record.work.snapshot_binding != snapshot or (
                    operation is not None
                    and record.work.contract.operation_type is not operation
                ):
                    raise IngressAbort(FailureCode.CIE_STALE)
                return _snapshot(record.output.output)

    def source_input(
        handle,
        authority,
        revision,
        cie,
        ledger,
        snapshot,
        capabilities,
        internal_results=(),
        prediction_views=(),
    ):
        with (
            access(handle, "RUNTIME") as (runtime, _),
            _pinned_work_budget(runtime.parent, authority, revision, ledger) as (
                domain,
                item,
                core,
            ),
        ):
            if runtime.reasoning_policy is None:
                raise IngressAbort(FailureCode.INVALID_POLICY_BINDING)
            with _pinned_cie_work(
                runtime.cie, cie, item, snapshot.binding, core
            ) as epoch:
                if snapshot.canonical_bytes != epoch.snapshot.canonical_bytes:
                    raise IngressAbort(FailureCode.CIE_STALE)
                _reasoning_source_bounds(
                    runtime.reasoning_policy,
                    capabilities,
                    internal_results,
                    prediction_views,
                )
                sources = _reasoning_sources(domain.ingress, capabilities)
                from .reasoning.assertions import internal_retrieval_view

                sources += tuple(
                    internal_retrieval_view(v, snapshot.binding)
                    for v in internal_results
                )
                from .prediction.adapters import reasoning_view

                sources += tuple(reasoning_view(v) for v in prediction_views)
                return CanonicalDescriptor(
                    "ReasoningInput",
                    (
                        tuple(e.canonical_descriptor() for e in epoch.snapshot.entries),
                        0,
                        sources,
                    ),
                )

    @contextmanager
    def retire_epoch(handle, item, binding, terminal=True):
        """Authority-reducing, rollback-safe cleanup under the parent Life gate.

        The existing per-invocation permit map is prospectively bounded by its
        budget. Peer owner barriers are never held together. A running worker
        can finish locally, but cannot reattach its output to a retired record.
        """
        if not terminal:
            yield
            return
        with access(handle, "RUNTIME") as (runtime, _):
            owner = item.work_owner
            if owner is None or owner.runtime is not runtime:
                raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
            with owner.lock:
                records = tuple(
                    (r, (r.state, r.work, r.image, r.binding, r.output, r.origin))
                    for r in owner.index[1].values()
                    if r.work is not None
                    and (
                        (
                            not r.prediction
                            and type(r.work.contract.operation_type)
                            is ReasoningOperation
                            and r.work.snapshot_binding.cie == binding
                        )
                        or (
                            r.prediction
                            and r.audit_identity is not None
                            and r.audit_identity.kind == "PredictionWorkPermitBinding"
                            and r.audit_identity.values[0].cie == binding
                        )
                    )
                )
                for r, _ in records:
                    r.state = "RETIRED"
                    r.work = r.image = r.binding = r.output = r.origin = None
            try:
                yield
            except BaseException:
                with owner.lock:
                    for r, old in records:
                        r.state, r.work, r.image, r.binding, r.output, r.origin = old
                raise

    def cleanup_epoch(handle, authority, binding):
        with (
            access(handle, "RUNTIME") as (runtime, _),
            _pinned_cie_parent(runtime.parent, authority) as (_, item, _),
        ):
            if item.work_owner is not None:
                with retire_epoch(handle, item, binding):
                    pass

    def prediction_record(
        runtime, owner, authority, revision, operation, data, binding, origin
    ):
        """One exact permit in the existing Work/WEP registry, no second runtime."""
        from .prediction.contracts import contract

        phase = "PROJECT" if operation.value == "PREDICTION_PROJECT" else "CAPTURE"
        offset = 0 if phase == "PROJECT" else binding.values[2]
        compiled = contract(operation, phase, offset)
        charge = binding.values[1] if phase == "PROJECT" else binding.values[3]
        if charge.values[4] != compiled.work_class:
            raise IngressAbort(FailureCode.BUDGET_WORKCLASS_MISMATCH)
        frame = CanonicalDescriptor(
            "PredictionPureWork",
            (compiled.canonical_descriptor(), data, binding),
        )
        image = canonical_identity_bytes(frame)
        if len(image) > 262144:
            raise IngressAbort(FailureCode.CAPACITY_ABORT)
        token = object.__new__(WorkExecutionPermit)
        record = _Permit(
            token,
            owner,
            authority,
            revision,
            frame,
            image,
            binding,
            prediction=True,
            origin=origin,
            audit_identity=binding,
        )
        sequence, records = owner.index
        staged = dict(records)
        staged[id(token)] = record
        registered = (ref(token), runtime, "PERMIT", WorkExecutionPermit, record)
        with registry_lock:
            old = owner.index
            try:
                handles[id(token)] = registered
                owner.index = (sequence + 1, staged)
            except BaseException:
                handles.pop(id(token), None)
                owner.index = old
                raise
        return token, frame

    def prediction_execute(handle, runtime, record, work, *, already_pinned=False):
        from .prediction.contracts import PredictionOperation, compute

        guard = (
            nullcontext
            if already_pinned
            else lambda: _pinned_cie_parent(runtime.parent)
        )
        with guard(), record.owner.lock:
            if record.owner.closing or record.state != "ISSUED":
                raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
            if (
                type(work) is not CanonicalDescriptor
                or canonical_identity_bytes(work) != record.image
            ):
                raise IngressAbort(FailureCode.INVALID_INPUT)
            frozen = _snapshot(work)
            record.state = "RUNNING"
        operation = PredictionOperation(frozen.values[0].values[0])
        try:
            output = compute(operation, frozen.values[1])
            returned = PureWorkResultView(_snapshot(record.binding), _snapshot(output))
            private = PureWorkResultView(_snapshot(record.binding), _snapshot(output))
        except BaseException:
            with guard(), record.owner.lock:
                record.state = "RETIRED"
                record.work = record.image = record.binding = record.output = (
                    record.origin
                ) = None
            raise
        with guard(), record.owner.lock:
            if record.owner.closing or record.state == "RETIRED":
                raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
            record.state = "DONE"
            record.output = private
        return returned

    def prediction_project(
        handle, authority, revision, cie, ledger, snapshot, receipt, cue, claims
    ):
        from dgca_lite.memory.config import MemoryConfig
        from dgca_lite.memory.types import FailureCode as L2Failure
        from dgca_lite.memory.types import RetrievalFailure

        from .identity import AssertionSemanticKey
        from .prediction.contracts import (
            PredictionOperation,
            compact_retrieval,
            contract,
        )
        from .types import AssertionBasis

        if (
            type(cue) is not tuple
            or type(claims) is not tuple
            or len(cue) > 256
            or len(claims) > 64
        ):
            raise IngressAbort(FailureCode.CAPACITY_ABORT)
        # The actual frozen L2 cue and reasoning source bounds precede even
        # pair/member inspection; no larger generic bound may hide traversal.
        with access(handle, "RUNTIME") as (bounded_runtime, _):
            if bounded_runtime.prediction_policy is None:
                raise IngressAbort(FailureCode.UNKNOWN_OPERATION_TYPE)
            with _pinned_cie_parent(bounded_runtime.parent):
                with _pinned_effect_context(
                    bounded_runtime.cie, bounded_runtime.parent
                ) as cie_state:
                    cue_bound = dict(cie_state.l2_policy.values)["K_C"]
                if (
                    len(cue) > cue_bound
                    or len(claims) > bounded_runtime.reasoning_policy.max_sources
                ):
                    raise IngressAbort(FailureCode.CAPACITY_ABORT)
        # Bound all nested pair containers before any member validation.
        if any(type(pair) is not tuple or len(pair) != 2 for pair in cue):
            raise IngressAbort(FailureCode.INVALID_INPUT)
        canonical_identity_bytes((cue, claims))
        if any(
            type(claim) is not AssertionSemanticKey
            or claim.basis not in (AssertionBasis.DERIVED, AssertionBasis.HYPOTHETICAL)
            for claim in claims
        ):
            raise IngressAbort(FailureCode.CROSS_CAPABILITY_ADAPTER_TYPE_VIOLATION)
        if tuple(cid for cid, _ in cue) != tuple(sorted({cid for cid, _ in cue})):
            raise IngressAbort(FailureCode.INVALID_INPUT)
        if any(
            type(cid) is not int
            or cid < 0
            or type(drive) not in (int, float)
            or not 0 < drive <= 1
            for cid, drive in cue
        ):
            raise IngressAbort(FailureCode.INVALID_INPUT)
        cue = tuple((cid, float(drive)) for cid, drive in cue)
        with access(handle, "RUNTIME") as (runtime, _):
            if runtime.prediction_policy is None:
                raise IngressAbort(FailureCode.UNKNOWN_OPERATION_TYPE)
            with _pinned_cie_parent(runtime.parent) as (domain, _, _):
                ingress = domain.ingress
            with _pinned_prediction_core(ingress, receipt) as reader:  # noqa: SIM117 -- explicit Core -> Life/ledger boundary
                with (
                    _pinned_cie_parent(runtime.parent, authority, revision) as (
                        _,
                        item,
                        _,
                    ),
                    item.budget.lock,
                ):
                    with _pinned_cie_work(
                        runtime.cie, cie, item, snapshot, reader.binding
                    ) as epoch:
                        available = tuple(
                            e.payload.values[0]
                            for e in epoch.snapshot.entries
                            if e.category == "ASSERTION"
                            and e.payload.kind == "AssertionRecord"
                        )
                        if any(claim not in available for claim in claims):
                            raise IngressAbort(
                                FailureCode.INVALID_FORMAL_AUTHORITY,
                                "reasoning/hypothesis input must be admitted in this exact CIE",
                            )
                        from .types import DependencyKind

                        if any(
                            claim.basis is AssertionBasis.HYPOTHETICAL
                            and not any(
                                r.kind is DependencyKind.HYPOTHESIS
                                for r in claim.dependencies
                            )
                            for claim in claims
                        ):
                            raise IngressAbort(FailureCode.INVALID_DEPENDENCY)
                        owner = item.work_owner or _Owner(runtime)
                        if owner.runtime is not runtime:
                            raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
                        with owner.lock:
                            operation = PredictionOperation.PROJECT
                            wc = contract(operation, "PROJECT").work_class
                            token, reservation, staged = _prepare_reservation(
                                item, 1, wc
                            )
                            old = item.budget.index
                            try:
                                item.budget.index = staged
                                charge, consumed = _prepare_consumption(
                                    item, token, reservation.units[0], wc
                                )
                            finally:
                                item.budget.index = old
                            # Charge before any retrieval/discovery; failures consume it.
                            item.budget.index = consumed
                            item.work_owner = owner
                            runtime.owners[id(authority)] = owner
                        config = MemoryConfig(
                            **dict(epoch.binding.environment.l2_policy.values)
                        )
                        result = reader.retrieve(config, cue)
                        if type(result) is RetrievalFailure:
                            if result.code is not L2Failure.EMPTY_CUE:
                                raise IngressAbort(FailureCode.CAPACITY_ABORT)
                            capture = CanonicalDescriptor(
                                "PredictionRetrievalCapture", ((), (), ())
                            )
                        else:
                            capture = compact_retrieval(
                                result, runtime.prediction_policy, targets=True
                            )
                        origin_class = (
                            "INTERNAL_ONLY"
                            if receipt is None
                            else ("MIXED" if cue or claims else "TRUSTED_ONLY")
                        )
                        provenance = CanonicalDescriptor(
                            "PredictionSessionProvenance",
                            (
                                reader.runtime,
                                reader.occurrence,
                                reader.revision,
                                reader.continuity,
                                cue,
                                claims,
                                epoch.binding.environment.l2_policy,
                            ),
                        )
                        data = CanonicalDescriptor(
                            "PredictionProjectionInput",
                            (origin_class, snapshot, capture, provenance),
                        )
                        binding = CanonicalDescriptor(
                            "PredictionWorkPermitBinding",
                            (snapshot, charge.canonical_descriptor(), owner.index[0]),
                        )
                        origin = (reader.binding, provenance, capture.values[0])
                        with owner.lock:
                            return prediction_record(
                                runtime,
                                owner,
                                authority,
                                revision,
                                operation,
                                data,
                                binding,
                                origin,
                            )

    def prediction_completed(handle, permit, item, snapshot):
        with (
            access(handle, "RUNTIME") as (runtime, _),
            access(permit, "PERMIT") as (own, record),
        ):
            if (
                own is not runtime
                or not record.prediction
                or record.authority is not item.authority
                or record.revision != item.lifecycle[1]
            ):
                raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
            with record.owner.lock:
                if (
                    record.state != "DONE"
                    or record.output is None
                    or record.owner.closing
                    or record.origin is None
                ):
                    raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
                if record.work.values[1].values[1] != snapshot:
                    raise IngressAbort(FailureCode.CIE_STALE)
                return _snapshot(record.output.output), tuple(
                    _snapshot(v) for v in record.origin
                )

    def prediction_audit(handle, permit, item):
        with (
            access(handle, "RUNTIME") as (runtime, _),
            access(permit, "PERMIT") as (own, record),
        ):
            if (
                own is not runtime
                or not record.prediction
                or record.authority is not item.authority
                or record.audit_identity is None
                or record.audit_identity.kind != "PredictionWorkPermitBinding"
            ):
                raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
            with record.owner.lock:
                return _snapshot(record.audit_identity)

    def forecast_capture(handle, forecast, reader, config, offset, charge):
        """Escrow already charged by the shared effect owner; no general fallback.

        Only a privately validated FRR can reach this fixed producer. Receipts
        and the read facet remain in acquisition infrastructure, never workers.
        """
        from .effects import _validate_forecast_record
        from .ingress import _validate_prediction_reader
        from .prediction.contracts import PredictionOperation, compact_retrieval

        _validate_forecast_record(forecast, handle)
        _validate_prediction_reader(reader)
        if forecast.status is not ForecastStatus.PENDING:
            raise IngressAbort(FailureCode.OPERATIONAL_EFFECT_AUTHORITY_STALE)
        from .invocation import _validate_forecast_charge

        _validate_forecast_charge(forecast.pool, offset, "CAPTURE", charge)

        with access(handle, "RUNTIME") as (runtime, _):
            if (
                runtime.prediction_policy is None
                or charge.source_kind is not BudgetSourceKind.FORECAST_ESCROW
            ):
                raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE)
            owner = forecast.work_owner or _Owner(runtime)
            if owner.runtime is not runtime or owner.closing:
                raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
            if reader.explicitly_empty:
                data = CanonicalDescriptor("PredictionRetrievalCapture", ((), (), ()))
            else:
                data = compact_retrieval(
                    reader.retrieve(config, ()),
                    runtime.prediction_policy,
                    targets=False,
                )
            binding = CanonicalDescriptor(
                "ForecastCapturePermitBinding",
                (
                    forecast.commitment.identity,
                    reader.occurrence,
                    offset,
                    charge.canonical_descriptor(),
                ),
            )
            with owner.lock:
                permit, frame = prediction_record(
                    runtime,
                    owner,
                    forecast.fda,
                    forecast.revision,
                    PredictionOperation.CAPTURE,
                    data,
                    binding,
                    None,
                )
                forecast.work_owner = owner
            # Run the same one-shot WEP machinery. Existing lifecycle is already
            # held; work owner is released before the effect owner is acquired.
            prediction_execute(
                handle, runtime, owner.index[1][id(permit)], frame, already_pinned=True
            )
            with owner.lock, registry_lock:
                record = owner.index[1][id(permit)]
                proven = _snapshot(record.output.output)
                record.state = "RETIRED"
                record.work = record.image = record.binding = record.output = None
                handles.pop(id(permit), None)
                owner.index = (owner.index[0], {})
            return proven

    def retire_forecast_work(handle, forecast, *, terminal=True):
        from .effects import _validate_forecast_record

        _validate_forecast_record(forecast, handle)
        with access(handle, "RUNTIME") as (runtime, _):
            owner = forecast.work_owner
            if owner is None:
                return
            if owner.runtime is not runtime:
                raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
            with owner.lock, registry_lock:
                for key, record in owner.index[1].items():
                    record.state = "RETIRED"
                    record.work = record.image = record.binding = record.output = (
                        record.origin
                    ) = None
                    handles.pop(key, None)
                owner.index = (owner.index[0], {})
                owner.closing = terminal

    def validate_prediction_attachment(handle, parent, cie, policy):
        with access(handle, "RUNTIME") as (runtime, _):
            if (
                runtime.parent is not parent
                or runtime.cie is not cie
                or runtime.prediction_policy != policy
            ):
                raise IngressAbort(FailureCode.INVALID_POLICY_BINDING)

    return (
        WorkRuntime,
        create_work_runtime,
        completed_result,
        source_input,
        retire_epoch,
        cleanup_epoch,
        prediction_project,
        prediction_completed,
        forecast_capture,
        prediction_audit,
        retire_forecast_work,
        validate_prediction_attachment,
    )


(
    WorkRuntime,
    create_work_runtime,
    _completed_reasoning_result,
    _reasoning_source_input,
    _retire_reasoning_epoch,
    _cleanup_reasoning_epoch,
    _prediction_project,
    _completed_prediction_result,
    _forecast_capture,
    _prediction_audit_binding,
    _retire_forecast_work,
    _validate_prediction_attachment,
) = _build_work_system()
del _build_work_system
