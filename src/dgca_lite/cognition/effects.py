"""Unit-6 logical effect infrastructure, NOT physical/semantic effect execution.

Production catalogue is EMPTY. A separate private, fixed mechanical harness
exercises the same transaction with passive audit records only. There is no
executor, plugin, transport callback, deferred child permit or child-mint API.
Future concrete contracts must stage any exact child inside this transaction;
a historical commit cannot be converted into new authority after parent close.
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
    _prepare_reasoning_publication,
)
from .effect import (
    CanonicalEffectDescriptor,
    EffectCommitID,
    EffectCommitView,
    EffectPolicy,
    PreparedEffect,
    clone_commit_view,
    freeze_effect,
)
from .effect_types import _MechanicalEffectOperation
from .identity import CanonicalDescriptor, CognitiveEnvironmentBinding, SnapshotBinding
from .ingress import _snapshot
from .invocation import (
    InvocationRuntime,
    _inspect_charge,
    _pinned_cie_parent,
    _pinned_effect_budget,
    _prepare_consumption,
    _prepare_reservation,
)
from .locks import RankedBarrier, _deferred_cleanup
from .operation import (
    AuthorityRequirement,
    BudgetClass,
    OperationContract,
    PublicationPolicy,
    ResourceEnvelope,
)
from .policy import ValueLimits
from .reasoning.fab import d
from .reasoning.schemas import ReasoningOperation, ReasoningPolicy
from .reasoning.schemas import catalogue as reasoning_catalogue
from .serialization import canonical_identity_bytes
from .types import BudgetSourceKind, FailureCode, InvocationState, WorkEffectClass
from .work import _completed_reasoning_result, _retire_reasoning_epoch

_OPERATIONS = tuple((member, member.value) for member in _MechanicalEffectOperation)


def _effect_contract(policy, operation, target, payload, scope):
    if not any(
        operation is member
        and type(operation.value) is str
        and operation.value == literal
        for member, literal in _OPERATIONS
    ):
        raise IngressAbort(FailureCode.UNKNOWN_OPERATION_TYPE)
    if (
        type(target) is not CanonicalDescriptor
        or target.kind != "MechanicalTarget"
        or len(target.values) != 1
        or type(target.values[0]) is not int
        or not 0 <= target.values[0] < 256
    ):
        raise IngressAbort(
            FailureCode.INVALID_INPUT, "no placeholder/mechanical target"
        )
    if (
        type(scope) is not CanonicalDescriptor
        or scope.kind != "MechanicalScope"
        or len(scope.values) != 1
        or type(scope.values[0]) is not str
        or not 1 <= len(scope.values[0]) <= 64
    ):
        raise IngressAbort(FailureCode.INVALID_SCOPE)
    data = canonical_identity_bytes(
        CanonicalDescriptor("MechanicalEffectInput", (target, payload, scope))
    )
    if len(data) > 32768:
        raise IngressAbort(FailureCode.CAPACITY_ABORT)
    needs_cie = operation is _MechanicalEffectOperation.CIE_AUDIT_ONLY
    requirements = (
        ((AuthorityRequirement.CIE_CURRENT,) if needs_cie else ())
        + (
            AuthorityRequirement.ENVIRONMENT_CURRENT,
            AuthorityRequirement.INVOCATION_CURRENT,
        )
        + ((AuthorityRequirement.SNAPSHOT_CURRENT,) if needs_cie else ())
    )
    return OperationContract(
        operation,
        BudgetClass.CHARGED_WORK,
        WorkEffectClass.OPERATIONAL_EFFECT,
        requirements,
        CanonicalDescriptor("Unit6EffectWorkClass", (operation.value,)),
        ResourceEnvelope(1, 256, len(data)),
        PublicationPolicy.SEPARATE_EFFECT_GATE_REQUIRED,
    )


def _before_effect_publish():
    """Last fixed prepublication boundary, for test fault injection only.

    No arguments/dispatch hooks. Production is a no-op; no caller callback can
    enter this path. All preparation and both returned/private views are built.
    """


def _reasoning_contract(policy, target, payload, scope):
    if type(policy) is not ReasoningPolicy:
        raise IngressAbort(FailureCode.UNKNOWN_OPERATION_TYPE)
    if type(target) is not CanonicalDescriptor or target.kind != "ReasoningArenaTarget":
        raise IngressAbort(FailureCode.INVALID_INPUT)
    if type(scope) is not CanonicalDescriptor or scope.kind != "ReasoningArenaScope":
        raise IngressAbort(FailureCode.INVALID_SCOPE)
    data = canonical_identity_bytes(payload, policy.value_limits)
    if len(data) > 262144:
        raise IngressAbort(FailureCode.CAPACITY_ABORT)
    return OperationContract(
        ReasoningOperation.PUBLISH,
        BudgetClass.CHARGED_WORK,
        WorkEffectClass.OPERATIONAL_EFFECT,
        (
            AuthorityRequirement.CIE_CURRENT,
            AuthorityRequirement.ENVIRONMENT_CURRENT,
            AuthorityRequirement.INVOCATION_CURRENT,
            AuthorityRequirement.SNAPSHOT_CURRENT,
        ),
        d("ReasoningPublishWorkClass"),
        ResourceEnvelope(1, policy.value_limits.max_nodes, len(data)),
        PublicationPolicy.SEPARATE_EFFECT_GATE_REQUIRED,
    )


def _build_effect_system():
    registry_lock = RankedBarrier(5)
    handles = {}

    @dataclass(slots=True)
    class _Runtime:
        parent: object
        cie: object
        policy: EffectPolicy
        mechanical: bool
        owner_ref: object = None
        owners: dict = field(default_factory=dict)
        retired: bool = False
        reasoning_policy: object = None

    @dataclass(slots=True)
    class _Owner:
        runtime: _Runtime
        lock: object = field(default_factory=lambda: RankedBarrier(4))
        index: dict = field(default_factory=dict)
        closed: bool = False

        def parent_close(self):
            with self.lock:
                # Preserve committed historical effects, NEVER new authority.
                self.closed = True

    @contextmanager
    def access(handle):
        with registry_lock:
            entry = handles.get(id(handle))
            if (
                entry is None
                or entry[0]() is not handle
                or type(handle) is not EffectRuntime
            ):
                raise IngressAbort(FailureCode.OPERATIONAL_EFFECT_AUTHORITY_STALE)
            runtime = entry[1]
            owner = runtime.owner_ref()
            if owner is None or runtime.retired:
                raise IngressAbort(FailureCode.OPERATIONAL_EFFECT_AUTHORITY_STALE)
        yield runtime
        del owner

    def operation_for(runtime, effect):
        if runtime.reasoning_policy is not None and effect.effect_type == d(
            "EffectType", ReasoningOperation.PUBLISH.value
        ):
            return ReasoningOperation.PUBLISH
        if not runtime.mechanical:
            raise IngressAbort(FailureCode.UNKNOWN_OPERATION_TYPE)
        kind = effect.effect_type
        if kind.kind == "EffectType" and len(kind.values) == 1:
            for member, literal in _OPERATIONS:
                if type(kind.values[0]) is str and kind.values[0] == literal:
                    return member
        raise IngressAbort(FailureCode.UNKNOWN_OPERATION_TYPE)

    def frozen_request(runtime, item, revision, effect, snapshot):
        try:
            reasoning = runtime.reasoning_policy is not None
            if not runtime.mechanical and not reasoning:
                raise IngressAbort(FailureCode.UNKNOWN_OPERATION_TYPE)
            if type(effect) is not CanonicalEffectDescriptor:
                raise TypeError("exact effect descriptor required")
            # The fixed harness knows these closed metadata envelopes. Check
            # their OUTER shapes before cloning/inspecting any members.
            for value, kind, count in (
                (effect.effect_type, "EffectType", 1),
                (
                    effect.target_identity,
                    "ReasoningArenaTarget" if reasoning else "MechanicalTarget",
                    1,
                ),
                (
                    effect.scope_binding,
                    "ReasoningArenaScope" if reasoning else "MechanicalScope",
                    1,
                ),
                (effect.owner_binding, "EffectOwnerBinding", 2),
                (effect.execution_contract, "OperationContract", 7),
            ):
                if (
                    type(value) is not CanonicalDescriptor
                    or type(value.kind) is not str
                    or value.kind != kind
                    or type(value.values) is not tuple
                    or len(value.values) != count
                ):
                    raise IngressAbort(
                        FailureCode.INVALID_INPUT, "effect metadata outer envelope"
                    )
            limits = runtime.reasoning_policy.value_limits if reasoning else None
            frozen = freeze_effect(runtime.policy, effect, payload_limits=limits)
            snapshot = _snapshot(snapshot)
            operation = operation_for(runtime, frozen)
            contract = (
                _reasoning_contract(
                    runtime.reasoning_policy,
                    frozen.target_identity,
                    frozen.canonical_payload,
                    frozen.scope_binding,
                )
                if reasoning
                else _effect_contract(
                    runtime.policy,
                    operation,
                    frozen.target_identity,
                    frozen.canonical_payload,
                    frozen.scope_binding,
                )
            )
            if type(revision) is not int or revision < 0:
                raise IngressAbort(FailureCode.INVALID_INPUT)
            expected_owner = CanonicalDescriptor(
                "EffectOwnerBinding", (item.identity, revision)
            )
            if canonical_identity_bytes(
                frozen.owner_binding
            ) != canonical_identity_bytes(expected_owner):
                raise IngressAbort(FailureCode.OPERATIONAL_EFFECT_AUTHORITY_STALE)
            if canonical_identity_bytes(
                frozen.execution_contract
            ) != canonical_identity_bytes(contract.canonical_descriptor()):
                raise IngressAbort(FailureCode.EFFECT_PAYLOAD_MISMATCH)
            if contract.effect_class is not WorkEffectClass.OPERATIONAL_EFFECT:
                raise IngressAbort(FailureCode.EXEMPTION_CONTRACT_VIOLATION)
            needs_cie = (
                reasoning or operation is _MechanicalEffectOperation.CIE_AUDIT_ONLY
            )
            if needs_cie and type(snapshot) is not SnapshotBinding:
                raise IngressAbort(FailureCode.CIE_STALE)
            if not needs_cie and snapshot is not None:
                raise IngressAbort(FailureCode.INVALID_SCOPE)
            if reasoning:
                from .reasoning.constraints import snapshot_ref

                if frozen.target_identity != d(
                    "ReasoningArenaTarget", snapshot_ref(snapshot)
                ) or frozen.scope_binding != d(
                    "ReasoningArenaScope", snapshot.cie.identity
                ):
                    raise IngressAbort(FailureCode.EFFECT_PAYLOAD_MISMATCH)
            context = CanonicalDescriptor(
                "EffectAuthorityContext",
                (frozen.owner_binding, frozen.environment_revision, snapshot),
            )
            identity = EffectCommitID(frozen, context)
            return frozen, snapshot, contract, identity
        except (TypeError, ValueError, AttributeError) as error:
            raise IngressAbort(FailureCode.INVALID_INPUT) from error

    def current(item, revision):
        if item.lifecycle != (InvocationState.ACTIVE, revision):
            raise IngressAbort(FailureCode.OPERATIONAL_EFFECT_AUTHORITY_STALE)

    def environment(runtime, core):
        with _pinned_effect_context(runtime.cie, runtime.parent) as context:
            return CognitiveEnvironmentBinding(
                core, context.l2_policy, context.l3_policy
            )

    def require_environment(runtime, frozen, core):
        if canonical_identity_bytes(
            environment(runtime, core)
        ) != canonical_identity_bytes(frozen.environment_revision):
            raise IngressAbort(FailureCode.ENVIRONMENT_STALE)

    def charge_from_data(data):
        if type(data) is not BudgetChargeView:
            raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE)
        try:
            image = _snapshot(data.canonical_descriptor())
            if (
                image.kind != "BudgetChargeBinding"
                or len(image.values) != 5
                or image.values[0] is not BudgetSourceKind.INVOCATION_GENERAL
            ):
                raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE)
            return BudgetChargeView(*image.values[1:])
        except (TypeError, ValueError, AttributeError) as error:
            raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE) from error

    def require_charge(item, reservation, ordinal, contract, supplied):
        charge = _inspect_charge(item, reservation, ordinal, contract.work_class)
        if canonical_identity_bytes(
            charge.canonical_descriptor()
        ) != canonical_identity_bytes(supplied.canonical_descriptor()):
            raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE)

    def owner_for(runtime, item):
        owner = item.effect_owner
        if owner is not None and owner.runtime is not runtime:
            raise IngressAbort(FailureCode.OPERATIONAL_EFFECT_AUTHORITY_STALE)
        return owner

    def duplicate(runtime, item, identity):
        owner = owner_for(runtime, item)
        if owner is None:
            return None
        with owner.lock, registry_lock:
            previous = owner.index.get(identity.canonical_bytes)
            if previous is not None:
                return clone_commit_view(
                    runtime.policy,
                    previous,
                    payload_limits=(
                        runtime.reasoning_policy.value_limits
                        if runtime.reasoning_policy
                        else None
                    ),
                )
        return None

    class EffectRuntime(_OpaqueHandle):
        __slots__ = ()

        def prepare_effect(
            self, authority, revision, target, payload, scope, *, operation=None
        ):
            with (
                access(self) as runtime,
                _pinned_cie_parent(runtime.parent, authority, revision, core=True) as (
                    _,
                    item,
                    core,
                ),
            ):
                if operation is None:
                    operation = _MechanicalEffectOperation.AUDIT_ONLY
                reasoning = runtime.reasoning_policy is not None
                if not runtime.mechanical and not reasoning:
                    raise IngressAbort(FailureCode.UNKNOWN_OPERATION_TYPE)
                try:
                    payload = _snapshot(
                        payload,
                        limits=(
                            runtime.reasoning_policy.value_limits
                            if reasoning
                            else runtime.policy.payload_limits
                        ),
                    )
                    small = (
                        ValueLimits(128, 48, runtime.policy.max_scalar_bytes)
                        if reasoning
                        else ValueLimits(32, 16, runtime.policy.max_scalar_bytes)
                    )
                    target = _snapshot(target, limits=small)
                    scope = _snapshot(scope, limits=small)
                    if reasoning and operation is not ReasoningOperation.PUBLISH:
                        raise IngressAbort(FailureCode.UNKNOWN_OPERATION_TYPE)
                    contract = (
                        _reasoning_contract(
                            runtime.reasoning_policy, target, payload, scope
                        )
                        if reasoning
                        else _effect_contract(
                            runtime.policy, operation, target, payload, scope
                        )
                    )
                    effect = CanonicalEffectDescriptor(
                        CanonicalDescriptor("EffectType", (operation.value,)),
                        target,
                        payload,
                        scope,
                        _snapshot(environment(runtime, core)),
                        _snapshot(
                            CanonicalDescriptor(
                                "EffectOwnerBinding", (item.identity, revision)
                            )
                        ),
                        contract.canonical_descriptor(),
                    )
                    return freeze_effect(
                        runtime.policy,
                        effect,
                        payload_limits=(
                            runtime.reasoning_policy.value_limits if reasoning else None
                        ),
                    )
                except (TypeError, ValueError, AttributeError) as error:
                    raise IngressAbort(FailureCode.INVALID_INPUT) from error

        def reserve(
            self, authority, revision, ledger, effect, *, cie=None, snapshot=None
        ):
            with (
                access(self) as runtime,
                _pinned_effect_budget(runtime.parent, authority, ledger, core=True) as (
                    _,
                    item,
                    core,
                ),
            ):
                current(item, revision)
                frozen, snapshot, contract, identity = frozen_request(
                    runtime, item, revision, effect, snapshot
                )
                require_environment(runtime, frozen, core)
                if snapshot is None and cie is not None:
                    raise IngressAbort(FailureCode.INVALID_SCOPE)
                guard = (
                    _pinned_cie_work(runtime.cie, cie, item, snapshot, core)
                    if snapshot is not None
                    else nullcontext()
                )
                with guard:
                    token, record, staged = _prepare_reservation(
                        item,
                        contract.resource_envelope.charge_units,
                        contract.work_class,
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
                        output = PreparedEffect(frozen, snapshot, charge, ordinal)
                        # Complete ID, history and independent return shell must
                        # fit BEFORE committing even the budget reservation.
                        clone_commit_view(
                            runtime.policy,
                            EffectCommitView(identity, frozen, charge),
                            payload_limits=(
                                runtime.reasoning_policy.value_limits
                                if runtime.reasoning_policy
                                else None
                            ),
                        )
                    except (TypeError, ValueError) as error:
                        raise IngressAbort(FailureCode.CAPACITY_ABORT) from error
                    item.budget.index = staged
                    return token, output

        def authorize_charge_and_commit(
            self,
            authority,
            revision,
            ledger,
            reservation,
            prepared,
            *,
            cie=None,
            work_runtime=None,
            work_permit=None,
        ):
            if type(prepared) is not PreparedEffect:
                raise IngressAbort(FailureCode.MISSING_BUDGET_CHARGE)
            try:
                source_effect, source_snapshot, source_charge, ordinal = (
                    prepared.effect,
                    prepared.snapshot_binding,
                    prepared.charge,
                    prepared.unit_ordinal,
                )
            except AttributeError as error:
                raise IngressAbort(FailureCode.INVALID_INPUT) from error
            with access(self) as runtime:
                # Historical lookup needs no current Core/CIE: it creates NO
                # effect/authority and requires genuine owner + charge records.
                try:
                    with _pinned_effect_budget(runtime.parent, authority, ledger) as (
                        _,
                        item,
                        _,
                    ):
                        frozen, snapshot, contract, identity = frozen_request(
                            runtime, item, revision, source_effect, source_snapshot
                        )
                        supplied = charge_from_data(source_charge)
                        require_charge(item, reservation, ordinal, contract, supplied)
                        previous = duplicate(runtime, item, identity)
                        if previous is not None:
                            return previous
                        current(item, revision)
                    with _pinned_effect_budget(
                        runtime.parent, authority, ledger, core=True
                    ) as (_, item, core):
                        # Race-safe second lookup, inside the final barriers.
                        previous = duplicate(runtime, item, identity)
                        if previous is not None:
                            return previous
                        current(item, revision)
                        require_environment(runtime, frozen, core)
                        if snapshot is None and cie is not None:
                            raise IngressAbort(FailureCode.INVALID_SCOPE)
                        guard = (
                            _pinned_cie_work(runtime.cie, cie, item, snapshot, core)
                            if snapshot is not None
                            else nullcontext()
                        )
                        with guard:
                            arena_plan = None
                            if runtime.reasoning_policy is not None:
                                from .reasoning.runtime import publication_from_output

                                proven = _completed_reasoning_result(
                                    work_runtime, work_permit, item, snapshot
                                )
                                publication = publication_from_output(proven)
                                if publication != frozen.canonical_payload:
                                    raise IngressAbort(
                                        FailureCode.EFFECT_PAYLOAD_MISMATCH
                                    )
                                _, additions_data, terminal = publication.values
                                from .arena import ArenaEntry

                                additions = tuple(
                                    ArenaEntry(*e.values) for e in additions_data
                                )
                                epoch, candidate = _prepare_reasoning_publication(
                                    runtime.cie,
                                    cie,
                                    item,
                                    snapshot,
                                    core,
                                    additions,
                                    terminal,
                                )
                                arena_plan = (
                                    epoch,
                                    candidate,
                                    terminal,
                                    (
                                        epoch.snapshot,
                                        epoch.terminal,
                                        epoch.last_binding,
                                        item.cie_child,
                                        item.nondelegated_children,
                                    ),
                                )
                            owner = owner_for(runtime, item) or _Owner(runtime)
                            retirement = (
                                _retire_reasoning_epoch(
                                    work_runtime, item, snapshot.cie, arena_plan[2]
                                )
                                if arena_plan is not None
                                else nullcontext()
                            )
                            with retirement, owner.lock, registry_lock:
                                if owner.closed:
                                    raise IngressAbort(
                                        FailureCode.OPERATIONAL_EFFECT_AUTHORITY_STALE
                                    )
                                if len(owner.index) >= min(
                                    runtime.policy.max_commits_per_owner,
                                    len(item.budget.index[0]),
                                ):
                                    raise IngressAbort(FailureCode.CAPACITY_ABORT)
                                charge, staged_budget = _prepare_consumption(
                                    item, reservation, ordinal, contract.work_class
                                )
                                if canonical_identity_bytes(
                                    charge.canonical_descriptor()
                                ) != canonical_identity_bytes(
                                    supplied.canonical_descriptor()
                                ):
                                    raise IngressAbort(
                                        FailureCode.MISSING_BUDGET_CHARGE
                                    )
                                stored = EffectCommitView(identity, frozen, charge)
                                output = clone_commit_view(
                                    runtime.policy,
                                    stored,
                                    payload_limits=(
                                        runtime.reasoning_policy.value_limits
                                        if runtime.reasoning_policy
                                        else None
                                    ),
                                )
                                index = dict(owner.index)
                                index[identity.canonical_bytes] = stored
                                owners = dict(runtime.owners)
                                owners[id(authority)] = owner
                                old = (
                                    item.budget.index,
                                    item.effect_owner,
                                    runtime.owners,
                                    owner.index,
                                )
                                _before_effect_publish()
                                try:
                                    # No callbacks/allocations/validators after
                                    # this point. Owner index swap is the exact
                                    # logical commit; every reader is excluded.
                                    item.budget.index = staged_budget
                                    runtime.owners = owners
                                    item.effect_owner = owner
                                    if arena_plan is not None:
                                        epoch, candidate, terminal, _ = arena_plan
                                        epoch.snapshot = None if terminal else candidate
                                        if terminal:
                                            epoch.terminal = "PUBLISHED"
                                            epoch.last_binding = candidate.binding
                                            item.cie_child = None
                                            item.nondelegated_children -= 1
                                    owner.index = index
                                except BaseException:
                                    # Covers injected/asynchronous interruption
                                    # between prebuilt pointer swaps, before any
                                    # observer can see the logical commit.
                                    (
                                        item.budget.index,
                                        item.effect_owner,
                                        runtime.owners,
                                        owner.index,
                                    ) = old
                                    if arena_plan is not None:
                                        epoch = arena_plan[0]
                                        (
                                            epoch.snapshot,
                                            epoch.terminal,
                                            epoch.last_binding,
                                            item.cie_child,
                                            item.nondelegated_children,
                                        ) = arena_plan[3]
                                    raise
                                return output
                except IngressAbort as error:
                    if error.code in (
                        FailureCode.OWNER_AUTHORITY_STALE,
                        FailureCode.INVOCATION_NOT_ACTIVE,
                        FailureCode.PARENT_AUTHORITY_STALE,
                    ):
                        raise IngressAbort(
                            FailureCode.OPERATIONAL_EFFECT_AUTHORITY_STALE
                        ) from error
                    raise

        def registry_status(self, authority):
            with (
                access(self) as runtime,
                _pinned_cie_parent(runtime.parent, authority) as (_, item, _),
            ):
                owner = owner_for(runtime, item)
                if owner is None:
                    return 0, runtime.policy.max_commits_per_owner
                with owner.lock, registry_lock:
                    return len(owner.index), runtime.policy.max_commits_per_owner

    def bootstrap(parent, cie, policy, mechanical, reasoning_policy=None):
        if policy is None:
            policy = EffectPolicy()
        if (
            type(parent) is not InvocationRuntime
            or type(cie) is not CIERuntime
            or type(policy) is not EffectPolicy
        ):
            raise IngressAbort(FailureCode.INVALID_INPUT)
        frozen = EffectPolicy(*policy.canonical_descriptor().values)
        if reasoning_policy is not None:
            if mechanical or type(reasoning_policy) is not ReasoningPolicy:
                raise IngressAbort(FailureCode.INVALID_POLICY_BINDING)
            reasoning_policy = ReasoningPolicy(
                *reasoning_policy.canonical_descriptor().values
            )
        catalogue = CanonicalDescriptor(
            "Unit6EffectCatalogue",
            (
                frozen.canonical_descriptor(),
                tuple(
                    _effect_contract(
                        frozen,
                        member,
                        CanonicalDescriptor("MechanicalTarget", (0,)),
                        (),
                        CanonicalDescriptor("MechanicalScope", ("test",)),
                    ).canonical_descriptor()
                    for member, _ in _OPERATIONS
                )
                if mechanical
                else (),
            ),
        )
        with (
            _pinned_cie_parent(parent) as (domain, _, _),
            _pinned_effect_context(cie, parent, bootstrap=True) as cie_state,
        ):
            if domain.effect_attached:
                raise IngressAbort(FailureCode.INVALID_POLICY_BINDING)
            if reasoning_policy is not None and (
                cie_state.reasoning_policy is None
                or reasoning_catalogue(reasoning_policy)
                != reasoning_catalogue(cie_state.reasoning_policy)
            ):
                raise IngressAbort(FailureCode.INVALID_POLICY_BINDING)
            l3 = _snapshot(
                CanonicalDescriptor(
                    "L3Unit6PolicyBinding", (cie_state.l3_policy, catalogue)
                )
            )
            if reasoning_policy is not None:
                l3 = _snapshot(
                    d(
                        "L3Unit7Effects",
                        l3,
                        d("ReasoningEffectCatalogue", ReasoningOperation.PUBLISH.value),
                    )
                )
            handle = object.__new__(EffectRuntime)
            runtime = _Runtime(
                parent, cie, frozen, mechanical, reasoning_policy=reasoning_policy
            )
            key = id(handle)

            @_deferred_cleanup
            def discard(reference):
                with _pinned_cie_parent(parent):
                    runtime.retired = True
                    for owner in runtime.owners.values():
                        with owner.lock:
                            owner.closed = True
                            owner.index = {}
                    with registry_lock:
                        handles.pop(key, None)
                    runtime.owners = {}

            owner_ref = ref(handle, discard)
            runtime.owner_ref = owner_ref
            registered = (owner_ref, runtime)
            with registry_lock:
                handles[key] = registered
                cie_state.l3_policy = l3
                cie_state.effect_attached = True
                domain.effect_attached = True
            return handle

    def create_effect_runtime(parent, cie, *, policy=None, reasoning_policy=None):
        """Production bootstrap: no concrete semantic effect catalogue yet."""
        return bootstrap(parent, cie, policy, False, reasoning_policy)

    def mechanical_harness(parent, cie, *, policy=None):
        """Private fixed test-only audit operations. No executor/handler argument."""
        return bootstrap(parent, cie, policy, True)

    return EffectRuntime, create_effect_runtime, mechanical_harness


EffectRuntime, create_effect_runtime, _create_mechanical_effect_harness = (
    _build_effect_system()
)
del _build_effect_system
