"""Shared logical effect gate with fixed Reasoning/Prediction production handlers.

Unconfigured Unit-6 runtimes still have an empty production catalogue. No
executor/plugin/caller callback exists. Forecast delegation stages its exact
child inside the seal transaction; historical audit is never child issuance.
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
from .identity import (
    CanonicalDescriptor,
    CognitiveEnvironmentBinding,
    ScopeIdentity,
    SnapshotBinding,
)
from .ingress import _pinned_prediction_core, _snapshot
from .invocation import (
    InvocationRuntime,
    _forecast_retirement,
    _inspect_charge,
    _pinned_cie_parent,
    _pinned_effect_budget,
    _prepare_consumption,
    _prepare_forecast_consumption,
    _prepare_forecast_delegation,
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
from .types import (
    BudgetSourceKind,
    CaptureState,
    FailureCode,
    ForecastStatus,
    InvocationState,
    WorkEffectClass,
)
from .work import (
    _completed_prediction_result,
    _completed_reasoning_result,
    _forecast_capture,
    _prediction_audit_binding,
    _retire_reasoning_epoch,
)

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


def _before_forecast_capture():
    """Fixed test fault boundary; never a configurable callback."""


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
    # These entries belong to the existing effect registry and share its lock.
    # Descriptors, Python class membership and copied fields are not admission.
    forecast_handles = {}

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
        prediction_policy: object = None
        forecasts: dict = field(default_factory=dict)

    @dataclass(slots=True)
    class _Owner:
        runtime: _Runtime
        lock: object = field(default_factory=lambda: RankedBarrier(4))
        index: dict = field(default_factory=dict)
        closed: bool = False
        seal_index: dict = field(default_factory=dict)

        def parent_close(self):
            with self.lock:
                # Preserve committed historical effects, NEVER new authority.
                self.closed = True

    @dataclass(slots=True)
    class _Forecast:
        fda: object
        commitment: object
        pool: object
        owner: object
        work: object
        origin_root: int
        seal_key: bytes
        seal_effect_key: bytes
        revision: int = 0
        coverage: tuple = ()
        status: object = ForecastStatus.PENDING
        work_owner: object = None
        pending: object = None
        evaluation_owner: object = None

    def forecast_for(runtime, token):
        from .prediction.fda import ForecastDelegatedAuthority

        with registry_lock:
            entry = forecast_handles.get(id(token))
            if (
                type(token) is not ForecastDelegatedAuthority
                or entry is None
                or entry[0]() is not token
                or entry[1] is not runtime
            ):
                raise IngressAbort(FailureCode.OPERATIONAL_EFFECT_AUTHORITY_STALE)
            record = entry[2]
            if (
                type(record) is not _Forecast
                or record.fda is not token
                or record.status is not ForecastStatus.PENDING
                or runtime.forecasts.get(
                    canonical_identity_bytes(record.commitment.identity)
                )
                is not record
            ):
                raise IngressAbort(FailureCode.OPERATIONAL_EFFECT_AUTHORITY_STALE)
            return record

    def outcome(record):
        from .prediction.commitment import ForecastCommitmentView
        from .prediction.observation import ForecastOutcomeView

        commitment = ForecastCommitmentView(
            *_snapshot(record.commitment.canonical_descriptor()).values
        )
        return ForecastOutcomeView(
            commitment, record.status, _snapshot(record.coverage)
        )

    def retire(runtime, record, status):
        """Bounded negative lifecycle transition. No new cognitive evaluation."""
        from .work import _retire_forecast_work

        with record.pool.budget.lock:
            # Terminal authority is already revoked even if a prior negative
            # cleanup failed. Cleanup cannot replace its published result.
            if record.status is not ForecastStatus.PENDING:
                status = record.status
            returned = outcome_with_status(record, status)
            staged_budget = _forecast_retirement(record.pool)
            _retire_forecast_work(record.work, record)
            with record.owner.lock, registry_lock:
                record.pool.budget.index = staged_budget
                runtime.forecasts.pop(
                    canonical_identity_bytes(record.commitment.identity), None
                )
                forecast_handles.pop(id(record.fda), None)
                # Retain only already-committed identity/charge accounting, not
                # a private prediction/result payload usable as cognitive memory.
                record.owner.index.pop(record.seal_effect_key, None)
                record.owner.seal_index[record.seal_key] = None
                record.status = status
                record.revision += 1
                if record.evaluation_owner is not None:
                    record.evaluation_owner.index = {}
                    record.evaluation_owner.closed = True
                record.commitment = record.coverage = record.work_owner = (
                    record.pending
                ) = None
                record.fda = record.work = record.pool = None
            return returned

    def outcome_with_status(record, status):
        from .prediction.observation import ForecastOutcomeView

        old = outcome(record)
        return ForecastOutcomeView(old.commitment, status, old.coverage)

    def seal_request(runtime, binding, target, horizon):
        from .prediction.targets import target_from_data

        if (
            type(horizon) is not int
            or not 1 <= horizon <= runtime.prediction_policy.max_horizon
        ):
            raise IngressAbort(FailureCode.INVALID_INPUT)
        try:
            target_from_data(target)
            target = _snapshot(target)
            key = canonical_identity_bytes(
                d(
                    "ForecastSealRequest",
                    binding,
                    target,
                    horizon,
                    runtime.prediction_policy.canonical_descriptor(),
                )
            )
        except (ValueError, TypeError, AttributeError) as error:
            raise IngressAbort(FailureCode.INVALID_INPUT) from error
        return target, key

    def seal_duplicate(runtime, item, key):
        owner = owner_for(runtime, item)
        if owner is None:
            return None
        with owner.lock:
            if key not in owner.seal_index:
                return None
            identity = owner.seal_index[key]
            if identity is None:
                raise IngressAbort(FailureCode.OPERATIONAL_EFFECT_AUTHORITY_STALE)
            record = runtime.forecasts.get(identity)
            if record is None or record.status is not ForecastStatus.PENDING:
                raise IngressAbort(FailureCode.OPERATIONAL_EFFECT_AUTHORITY_STALE)
            view = outcome(record).commitment
            # A historical lookup is never child-authority recovery.
            return view, record.fda if item.lifecycle[
                0
            ] is InvocationState.ACTIVE else None

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

        def seal_forecast(
            self,
            authority,
            revision,
            ledger,
            cie,
            work_runtime,
            projection_permit,
            target,
            horizon,
        ):
            nonlocal forecast_handles
            from .prediction.commitment import ForecastCommitmentView
            from .prediction.contracts import PredictionOperation, contract
            from .prediction.fda import ForecastDelegatedAuthority
            from .prediction.targets import TargetGuard

            with access(self) as runtime:
                if runtime.prediction_policy is None:
                    raise IngressAbort(FailureCode.UNKNOWN_OPERATION_TYPE)
                with _pinned_effect_budget(runtime.parent, authority, ledger) as (
                    domain,
                    item,
                    _,
                ):
                    audit = _prediction_audit_binding(
                        work_runtime, projection_permit, item
                    )
                    target, key = seal_request(runtime, audit, target, horizon)
                    previous = seal_duplicate(runtime, item, key)
                    if previous is not None:
                        return previous
                    current(item, revision)
                    ingress = domain.ingress
                with _pinned_prediction_core(ingress) as reader:  # noqa: SIM117 -- explicit Core -> Life/ledger boundary
                    with _pinned_effect_budget(runtime.parent, authority, ledger) as (
                        _,
                        item,
                        _,
                    ):
                        previous = seal_duplicate(runtime, item, key)
                        if previous is not None:
                            return previous
                        current(item, revision)
                        snapshot = audit.values[0]
                        with _pinned_cie_work(
                            runtime.cie, cie, item, snapshot, reader.binding
                        ):
                            proven, origin = _completed_prediction_result(
                                work_runtime, projection_permit, item, snapshot
                            )
                            origin_core, provenance, witnesses = origin
                            if (
                                proven.values[0] != "TRUSTED_ONLY"
                                or not witnesses
                                or target not in proven.values[2]
                                or origin_core != reader.binding
                                or provenance.values[2] != reader.revision
                                or provenance.values[3] != reader.continuity
                                or provenance.values[4]
                                or provenance.values[5]
                            ):
                                raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
                            if not reader.target_valid(target):
                                raise IngressAbort(FailureCode.ENVIRONMENT_STALE)
                            if (
                                len(runtime.forecasts)
                                >= runtime.prediction_policy.max_live_forecasts
                            ):
                                raise IngressAbort(FailureCode.CAPACITY_ABORT)
                            owner = owner_for(runtime, item) or _Owner(runtime)
                            with owner.lock, registry_lock:
                                if owner.closed:
                                    raise IngressAbort(
                                        FailureCode.OPERATIONAL_EFFECT_AUTHORITY_STALE
                                    )
                                if len(owner.seal_index) + len(owner.index) >= min(
                                    runtime.policy.max_commits_per_owner,
                                    len(item.budget.index[0]),
                                ):
                                    raise IngressAbort(FailureCode.CAPACITY_ABORT)
                                operation = contract(PredictionOperation.SEAL, "SEAL")
                                reservation, plan, reserved = _prepare_reservation(
                                    item, 1, operation.work_class
                                )
                                old_budget = item.budget.index
                                try:
                                    item.budget.index = reserved
                                    charge, charged = _prepare_consumption(
                                        item,
                                        reservation,
                                        plan.units[0],
                                        operation.work_class,
                                    )
                                    item.budget.index = charged
                                    pool, delegated = _prepare_forecast_delegation(
                                        item,
                                        horizon,
                                        d(
                                            "ForecastEscrowOwner",
                                            item.identity,
                                            audit.values[2],
                                            target,
                                            horizon,
                                        ),
                                    )
                                finally:
                                    item.budget.index = old_budget
                                policy = (
                                    runtime.prediction_policy.canonical_descriptor()
                                )
                                guard = TargetGuard(
                                    target, policy
                                ).canonical_descriptor()
                                observation = d(
                                    "ForecastObservationPolicy",
                                    "ROOT_SEEDED_SOURCE_VIEW_ONLY_V1",
                                    snapshot.cie.environment.l2_policy,
                                )
                                boundary = d(
                                    "ForecastBoundaryPolicy",
                                    "TERMINATE_ON_HARD_BOUNDARY_V1",
                                )
                                scope = ScopeIdentity(
                                    "PREDICTION",
                                    reader.runtime,
                                    d(
                                        "ForecastScope",
                                        item.identity,
                                        audit.values[2],
                                        target,
                                        horizon,
                                    ),
                                )
                                future = d(
                                    "FutureEvaluationBinding",
                                    reader.runtime,
                                    reader.binding.core_policy,
                                    reader.revision,
                                    reader.continuity,
                                    policy,
                                    guard,
                                    observation,
                                    boundary,
                                )
                                commitment = ForecastCommitmentView(
                                    origin_core,
                                    provenance,
                                    target,
                                    guard,
                                    horizon,
                                    scope,
                                    policy,
                                    observation,
                                    boundary,
                                    future,
                                    pool.identity,
                                )
                                effect = freeze_effect(
                                    runtime.policy,
                                    CanonicalEffectDescriptor(
                                        d("EffectType", PredictionOperation.SEAL.value),
                                        d("ForecastTarget", target),
                                        commitment.canonical_descriptor(),
                                        d("ForecastScopeBinding", scope),
                                        snapshot.cie.environment,
                                        d(
                                            "EffectOwnerBinding",
                                            item.identity,
                                            revision,
                                        ),
                                        operation.canonical_descriptor(),
                                    ),
                                    payload_limits=ValueLimits(),
                                )
                                identity = EffectCommitID(
                                    effect,
                                    d(
                                        "EffectAuthorityContext",
                                        effect.owner_binding,
                                        effect.environment_revision,
                                        snapshot,
                                    ),
                                )
                                view = EffectCommitView(identity, effect, charge)
                                # Prebuild independent returned data before publication.
                                returned = ForecastCommitmentView(
                                    *_snapshot(commitment.canonical_descriptor()).values
                                )
                                fda = object.__new__(ForecastDelegatedAuthority)
                                record = _Forecast(
                                    fda,
                                    commitment,
                                    pool,
                                    owner,
                                    work_runtime,
                                    reader.binding.next_root_id - 1,
                                    key,
                                    identity.canonical_bytes,
                                )
                                # Prospectively prove even the final gap ledger
                                # and its exact effect can fit. No later capture
                                # failure may strand a completed logical horizon.
                                try:
                                    preflight_forecast(runtime, record, reader)
                                except (ValueError, TypeError) as error:
                                    raise IngressAbort(
                                        FailureCode.CAPACITY_ABORT
                                    ) from error
                                forecast_key = canonical_identity_bytes(
                                    commitment.identity
                                )
                                index = dict(owner.index)
                                index[identity.canonical_bytes] = view
                                seals = dict(owner.seal_index)
                                seals[key] = forecast_key
                                forecasts = dict(runtime.forecasts)
                                forecasts[forecast_key] = record
                                owners = dict(runtime.owners)
                                owners[id(authority)] = owner
                                registrations = dict(forecast_handles)
                                registrations[id(fda)] = (ref(fda), runtime, record)
                                old = (
                                    item.budget.index,
                                    item.effect_owner,
                                    runtime.owners,
                                    owner.index,
                                    owner.seal_index,
                                    runtime.forecasts,
                                    dict(forecast_handles),
                                )
                                _before_effect_publish()
                                try:
                                    item.budget.index = delegated
                                    item.effect_owner = owner
                                    runtime.owners = owners
                                    owner.index = index
                                    owner.seal_index = seals
                                    runtime.forecasts = forecasts
                                    forecast_handles = registrations
                                except BaseException:
                                    (
                                        item.budget.index,
                                        item.effect_owner,
                                        runtime.owners,
                                        owner.index,
                                        owner.seal_index,
                                        runtime.forecasts,
                                        old_handles,
                                    ) = old
                                    forecast_handles = old_handles
                                    raise
                                return returned, fda

        def forecast_outcome(self, fda):
            with access(self) as runtime, _pinned_cie_parent(runtime.parent):
                return outcome(forecast_for(runtime, fda))

        def cancel_forecast(self, fda):
            with access(self) as runtime, _pinned_cie_parent(runtime.parent):
                record = forecast_for(runtime, fda)
                return retire(runtime, record, ForecastStatus.CANCELLED)

        def forecast_registry_status(self):
            with access(self) as runtime, _pinned_cie_parent(runtime.parent):
                if runtime.prediction_policy is None:
                    raise IngressAbort(FailureCode.UNKNOWN_OPERATION_TYPE)
                return len(
                    runtime.forecasts
                ), runtime.prediction_policy.max_live_forecasts

        def retry_forecast_publication(self, fda):
            """Attach an already-produced exact result, never retry computation."""
            with access(self) as runtime:
                with _pinned_cie_parent(runtime.parent) as (domain, _, _):
                    ingress = domain.ingress
                with _pinned_prediction_core(ingress) as reader:  # noqa: SIM117 -- explicit Core -> Life boundary
                    with _pinned_cie_parent(runtime.parent):
                        record = forecast_for(runtime, fda)
                        stale = forecast_staleness(runtime, record, reader)
                        if stale is not None:
                            return retire(runtime, record, stale)
                        if record.pending is None:
                            return outcome(record)
                        with record.pool.budget.lock:
                            return publish_forecast(runtime, record)

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

    def bootstrap(
        parent, cie, policy, mechanical, reasoning_policy=None, prediction_policy=None
    ):
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
        if prediction_policy is not None:
            from .prediction.projection import PredictionPolicy

            if mechanical or type(prediction_policy) is not PredictionPolicy:
                raise IngressAbort(FailureCode.INVALID_POLICY_BINDING)
            prediction_policy = PredictionPolicy(
                *prediction_policy.canonical_descriptor().values[:6]
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
            if prediction_policy is not None and (
                cie_state.prediction_policy != prediction_policy
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
            if prediction_policy is not None:
                l3 = _snapshot(
                    d(
                        "L3Unit8Effects",
                        *l3.values,
                        prediction_policy.canonical_descriptor(),
                    )
                )
            handle = object.__new__(EffectRuntime)
            runtime = _Runtime(
                parent,
                cie,
                frozen,
                mechanical,
                reasoning_policy=reasoning_policy,
                prediction_policy=prediction_policy,
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

    def forecast_staleness(runtime, record, reader):
        binding = record.commitment.future_evaluation_binding.values
        if (
            reader.runtime != binding[0]
            or reader.binding.core_policy != binding[1]
            or reader.revision != binding[2]
            or reader.continuity != binding[3]
            or runtime.prediction_policy.canonical_descriptor() != binding[4]
        ):
            return ForecastStatus.ENVIRONMENT_STALE
        if not reader.target_valid(record.commitment.target):
            return ForecastStatus.TARGET_STALE
        return None

    def publish_forecast(runtime, record):
        """Exact prepared result publication under Life/pool-ledger barriers.

        A failed publication retains ONE already-paid result for descriptor
        attachment; it never reruns capture/matching or allocates another unit.
        """
        from .prediction.observation import ForecastOutcomeView

        coverage, status, stored, returned = record.pending
        owner = record.evaluation_owner
        with owner.lock, registry_lock:
            candidate = dict(owner.index)
            candidate[stored.commit_id.canonical_bytes] = stored
            old = (
                record.coverage,
                record.status,
                record.revision,
                record.pending,
                owner.index,
            )
            _before_effect_publish()
            try:
                record.coverage = coverage
                record.status = status
                record.revision += 1
                record.pending = None
                owner.index = candidate
            except BaseException:
                (
                    record.coverage,
                    record.status,
                    record.revision,
                    record.pending,
                    owner.index,
                ) = old
                raise
        if status is not ForecastStatus.PENDING:
            # The semantic result is already complete. Negative cleanup cannot
            # mint another status/evaluation, refund budget, or retain payloads.
            return retire(runtime, record, status)
        return ForecastOutcomeView(
            returned.commitment, returned.status, returned.coverage
        )

    def forecast_evaluation_effect(
        runtime, record, binding, future, offset, state, capture, previous, charge
    ):
        from .prediction.contracts import PredictionOperation, contract
        from .prediction.observation import ForecastEvaluationID

        operation = contract(PredictionOperation.EVALUATE, "EVALUATION", offset)
        evaluation = ForecastEvaluationID(
            record.commitment.identity, future
        ).canonical_descriptor()
        payload = d(
            "ForecastEvaluationInput", evaluation, offset, state, capture, previous
        )
        effect = freeze_effect(
            runtime.policy,
            CanonicalEffectDescriptor(
                d("EffectType", PredictionOperation.EVALUATE.value),
                d("ForecastTarget", record.commitment.target),
                payload,
                d("ForecastScopeBinding", record.commitment.scope),
                environment(runtime, binding),
                d("ForecastEffectOwnerBinding", record.pool.identity, record.revision),
                operation.canonical_descriptor(),
            ),
            payload_limits=ValueLimits(),
        )
        identity = EffectCommitID(
            effect,
            d("ForecastEffectAuthorityContext", record.pool.identity, record.revision),
        )
        return EffectCommitView(identity, effect, charge)

    def preflight_forecast(runtime, record, reader):
        from .identity import CoreStateBinding
        from .prediction.observation import (
            ForecastOutcomeView,
            FutureTrustedOccurrenceID,
        )

        horizon = record.commitment.horizon
        if horizon > runtime.policy.max_commits_per_owner:
            raise IngressAbort(
                FailureCode.CAPACITY_ABORT,
                "complete forecast evaluation history exceeds effect owner envelope",
            )
        origin = reader.binding
        last = CoreStateBinding(
            origin.core_identity,
            origin.version + horizon,
            origin.tick + horizon,
            origin.next_root_id + horizon,
            origin.core_policy,
        )
        coverage = tuple(
            d(
                "ForecastCoverage",
                offset,
                FutureTrustedOccurrenceID(
                    reader.runtime,
                    d(
                        "TrustedCoreOccurrence",
                        origin.version + offset,
                        origin.tick + offset,
                        origin.next_root_id + offset - 1,
                    ),
                ).canonical_descriptor(),
                CaptureState.OBSERVATION_GAP,
                False,
            )
            for offset in range(1, horizon + 1)
        )
        future = FutureTrustedOccurrenceID(*coverage[-1].values[1].values)
        charge, _ = _prepare_forecast_consumption(record.pool, horizon, "EVALUATION")
        forecast_evaluation_effect(
            runtime,
            record,
            last,
            future,
            horizon,
            CaptureState.OBSERVATION_GAP,
            d("PredictionRetrievalCapture", (), (), ()),
            coverage[:-1],
            charge,
        )
        ForecastOutcomeView(
            record.commitment, ForecastStatus.INCONCLUSIVE_OBSERVATION_GAP, coverage
        )

    def evaluate_forecast(runtime, record, reader):
        from dgca_lite.memory.config import MemoryConfig

        from .prediction.evaluation import match, status_after
        from .prediction.observation import (
            ForecastOutcomeView,
            FutureTrustedOccurrenceID,
        )

        if record.pending is not None:
            completed = publish_forecast(runtime, record)
            if completed.status is not ForecastStatus.PENDING:
                return completed
        future = FutureTrustedOccurrenceID(reader.runtime, reader.occurrence)
        occurrence = future.canonical_descriptor()
        if any(entry.values[1] == occurrence for entry in record.coverage):
            return outcome(record)
        if reader.occurrence.values[2] <= record.origin_root:
            raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
        offset = len(record.coverage) + 1
        capture_charge, captured_budget = _prepare_forecast_consumption(
            record.pool, offset, "CAPTURE"
        )
        record.pool.budget.index = captured_budget
        capture = d("PredictionRetrievalCapture", (), (), ())
        state = CaptureState.OBSERVATION_GAP
        try:
            _before_forecast_capture()
            config = MemoryConfig(
                **dict(record.commitment.observation_policy.values[1].values)
            )
            capture = _forecast_capture(
                record.work, record, reader, config, offset, capture_charge
            )
            state = (
                CaptureState.PROVEN_EMPTY
                if reader.explicitly_empty
                else CaptureState.CAPTURED
            )
        except (ValueError, TypeError, RuntimeError, MemoryError, OSError):
            # The trusted occurrence is genuine independently of this failure.
            # No fallback emptiness, retry capture, or gap rewriting is allowed.
            from .work import _retire_forecast_work

            _retire_forecast_work(record.work, record, terminal=False)
        evaluation_charge, evaluated_budget = _prepare_forecast_consumption(
            record.pool, offset, "EVALUATION"
        )
        try:
            stored = forecast_evaluation_effect(
                runtime,
                record,
                reader.binding,
                future,
                offset,
                state,
                capture,
                record.coverage,
                evaluation_charge,
            )
        except ValueError:
            # An unrepresentable complete capture is a failed capture, never a
            # truncated result. Sealing preflight already proved the gap frame.
            capture = d("PredictionRetrievalCapture", (), (), ())
            state = CaptureState.OBSERVATION_GAP
            stored = forecast_evaluation_effect(
                runtime,
                record,
                reader.binding,
                future,
                offset,
                state,
                capture,
                record.coverage,
                evaluation_charge,
            )
        # An operational effect is the fixed evaluate-and-record handler. Its
        # complete immutable INPUT descriptor is known before execution; the
        # corresponding match/closure/record work fits this one allocation.
        record.pool.budget.index = evaluated_budget
        matched = state is not CaptureState.OBSERVATION_GAP and match(
            record.commitment.target, capture.values[1], capture.values[0]
        )
        coverage = record.coverage + (
            d("ForecastCoverage", offset, occurrence, state, matched),
        )
        status = status_after(
            record.commitment.horizon, tuple(e.values[2] for e in coverage), matched
        )
        returned = ForecastOutcomeView(
            outcome(record).commitment, status, _snapshot(coverage)
        )
        record.pending = (coverage, status, stored, returned)
        if record.evaluation_owner is None:
            record.evaluation_owner = _Owner(runtime)
        return publish_forecast(runtime, record)

    def deliver_event(handle, work, receipt, boundary):
        """Fixed normal trusted path. Receipts cannot be supplied by cognition."""
        with access(handle) as runtime:
            with _pinned_cie_parent(runtime.parent) as (domain, _, _):
                ingress = domain.ingress
            with (
                _pinned_prediction_core(
                    ingress, receipt, delivery=True, boundary=boundary
                ) as reader,
                _pinned_cie_parent(runtime.parent),
            ):
                if runtime.prediction_policy is None:
                    raise IngressAbort(FailureCode.INVALID_POLICY_BINDING)
                records = tuple(runtime.forecasts[k] for k in sorted(runtime.forecasts))
                returned = []
                for record in records:
                    if record.work is not work:
                        raise IngressAbort(FailureCode.INVALID_POLICY_BINDING)
                    if record.status is not ForecastStatus.PENDING:
                        # Only retry authority-reducing cleanup. No capture,
                        # evaluation, offset, or budget allocation is permitted.
                        returned.append(retire(runtime, record, record.status))
                        continue
                    if boundary:
                        returned.append(
                            retire(runtime, record, ForecastStatus.BOUNDARY_TERMINATED)
                        )
                        continue
                    stale = forecast_staleness(runtime, record, reader)
                    if stale is not None:
                        returned.append(retire(runtime, record, stale))
                        continue
                    with record.pool.budget.lock:
                        try:
                            returned.append(evaluate_forecast(runtime, record, reader))
                        except (
                            IngressAbort,
                            ValueError,
                            TypeError,
                            RuntimeError,
                            MemoryError,
                            OSError,
                        ):
                            # No semantic fallback. The genuine Core event
                            # stays committed; prepared publication, if any,
                            # is retained within its original paid envelope.
                            returned.append(
                                d(
                                    "ForecastProcessingFailure",
                                    record.commitment.identity,
                                    FailureCode.INTERNAL_CONTRACT_VIOLATION,
                                )
                            )
                return tuple(returned)

    def validate_forecast(record, work):
        if type(record) is not _Forecast:
            raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
        with registry_lock:
            entry = forecast_handles.get(id(record.fda))
            if (
                entry is None
                or entry[0]() is not record.fda
                or entry[2] is not record
                or record.work is not work
            ):
                raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)

    def retire_environment(handle):
        # Issuer holds the Core barrier. This is strictly authority reducing and
        # must work before its issuer/domain becomes inaccessible.
        with access(handle) as runtime, _pinned_cie_parent(runtime.parent):
            records = tuple(runtime.forecasts[k] for k in sorted(runtime.forecasts))
            return tuple(
                retire(runtime, record, ForecastStatus.ENVIRONMENT_STALE)
                for record in records
            )

    def validate_attachment(handle, work, ingress):
        from .work import _validate_prediction_attachment

        with (
            access(handle) as runtime,
            _pinned_cie_parent(runtime.parent) as (domain, _, _),
        ):
            if domain.ingress is not ingress or runtime.prediction_policy is None:
                raise IngressAbort(FailureCode.INVALID_POLICY_BINDING)
            _validate_prediction_attachment(
                work, runtime.parent, runtime.cie, runtime.prediction_policy
            )

    def create_effect_runtime(
        parent, cie, *, policy=None, reasoning_policy=None, prediction_policy=None
    ):
        """Production bootstrap: no concrete semantic effect catalogue yet."""
        return bootstrap(
            parent, cie, policy, False, reasoning_policy, prediction_policy
        )

    def mechanical_harness(parent, cie, *, policy=None):
        """Private fixed test-only audit operations. No executor/handler argument."""
        return bootstrap(parent, cie, policy, True)

    return (
        EffectRuntime,
        create_effect_runtime,
        mechanical_harness,
        deliver_event,
        validate_forecast,
        retire_environment,
        validate_attachment,
    )


(
    EffectRuntime,
    create_effect_runtime,
    _create_mechanical_effect_harness,
    _deliver_prediction_event,
    _validate_forecast_record,
    _retire_prediction_environment,
    _validate_prediction_attachment,
) = _build_effect_system()
del _build_effect_system
