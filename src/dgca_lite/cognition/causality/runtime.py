"""Fixed causal scheduling over the shared Invocation, Work and effect gate.

There is no executor/plugin callback. Trusted controllers attest physical work;
the cognitive runtime validates their exact opaque receipts. The private system
uses the ACTUAL Unit-6 registry/mutex and ACTUAL parent ledger, not substitutes.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
from dataclasses import fields as data_fields
from weakref import ref

from ..authority import IngressAbort, _OpaqueHandle
from ..budget import BudgetChargeView
from ..cie import _pinned_cie_work
from ..effect import (
    CanonicalEffectDescriptor,
    EffectCommitID,
    EffectCommitView,
)
from ..ingress import _pinned_causal_domain_root, _snapshot
from ..invocation import (
    _causal_retirement,
    _pinned_cie_parent,
    _pinned_effect_budget,
    _prepare_causal_consumption,
    _prepare_causal_reservation,
    _prepare_consumption,
    _prepare_reservation,
    _validate_causal_charge,
)
from ..serialization import canonical_identity_bytes
from ..types import FailureCode, InvocationState
from ..work import (
    _causal_permit_charge,
    _causal_prepare,
    _completed_causal_result,
    _discard_causal_permit,
)
from .cases import CaseSlotReport, TrustedCaseOccurrence
from .contracts import (
    CausalityPolicy,
    CausalOperation,
    closed,
    contract,
    d,
    fields,
    integer,
    outer,
    work_frontier,
)
from .intervention import (
    AppliedInterventionReceipt,
    BranchIsolationReceipt,
    ProtocolControlReceipt,
    treatment_pair,
)
from .measurement import MeasurementContract, measurement_from_data
from .replay import (
    BranchExecutionReceipt,
    ClosedReplayDomainContract,
    MeasurementReceipt,
    ReplayComparisonEpoch,
    ReplayEnvironmentBinding,
    ReplayExecutionBundle,
    ReplayOrigin,
    ReplayOriginAuthority,
    contrast_identity,
    identification_basis,
    replay_contract_from_data,
)
from .results import CausalStudyReport, result_from_data
from .study import CausalStudyAuthority, CausalStudyPlan, plan_from_data


def abort(code=FailureCode.OWNER_AUTHORITY_STALE, detail=""):
    raise IngressAbort(code, detail)


def clone_view(view):
    """Clone within the fixed causal envelope, before publication. Generic
    leaf-effect schema bounds do not describe complete prospective study IDs.
    """
    effect = CanonicalEffectDescriptor(
        *_snapshot(view.effect.canonical_descriptor()).values
    )
    charge = _snapshot(view.charge.canonical_descriptor()).values
    return EffectCommitView(
        EffectCommitID(effect, _snapshot(view.commit_id.authority_context)),
        effect,
        BudgetChargeView(*charge[1:], source_kind=charge[0]),
    )


def _root(handle, operation, *args):
    from ..effects import _causal_root

    return _causal_root(handle, operation, *args)


class CausalDomainIssuer(_OpaqueHandle):
    __slots__ = ()

    @property
    def environment(self):
        return _root(self, "ENVIRONMENT")

    @property
    def controllers(self):
        return _root(self, "CONTROLLERS")

    def capture_origin(self, state):
        return _root(self, "ORIGIN", state)

    def capture_case(
        self, study, slot, outcome, *, measurement_status="MEASURED", attempt=0
    ):
        return _root(
            self, "CASE", study, slot, outcome, measurement_status, attempt, None
        )

    def bind_case(self, study, slot, occurrence, *, attempt=0):
        return _root(self, "CASE", study, slot, None, None, attempt, occurrence)

    def revise_environment(self, environment, *, replay_contract=None):
        return _root(self, "REVISE", environment, replay_contract)

    def close(self):
        return _root(self, "CLOSE")


class InterventionController(_OpaqueHandle):
    __slots__ = ()

    def receipt(self, owner, branch):
        return _root(self, "APPLICATION", owner, branch)


class ProtocolController(_OpaqueHandle):
    __slots__ = ()

    def receipt(self, owner):
        return _root(self, "RANDOMIZATION", owner, 0)


class IsolationController(_OpaqueHandle):
    __slots__ = ()

    def receipt(self, rce, branch):
        return _root(self, "ISOLATION", rce, branch)


class ExecutionController(_OpaqueHandle):
    __slots__ = ()

    def receipt(self, rce, branch, *, actual_origin, actual_schedule, consumed_steps):
        return _root(
            self,
            "EXECUTION",
            rce,
            branch,
            actual_origin,
            actual_schedule,
            consumed_steps,
        )


class MeasurementController(_OpaqueHandle):
    __slots__ = ()

    def receipt(
        self,
        rce,
        branch,
        outcome,
        *,
        measurement_status="MEASURED",
        target,
        logical_slot,
        treatment_label_blind,
    ):
        return _root(
            self,
            "MEASUREMENT",
            rce,
            branch,
            outcome,
            measurement_status,
            target,
            logical_slot,
            treatment_label_blind,
        )


@dataclass(slots=True)
class _Domain:
    identity: object
    environment: object
    measurement: object
    replay_contract: object
    issuer: object = None
    controllers: tuple = ()
    revision: int = 0
    sequence: int = 0
    closed: bool = False
    handle_ids: set = field(default_factory=set)
    contrasts: dict = field(default_factory=dict)

    def binding(self):
        return ReplayEnvironmentBinding(self.identity, self.environment, self.revision)


@dataclass(slots=True)
class _Study:
    system: object
    token: object
    item: object
    owner: object
    domain: object
    plan: object
    identity: object
    pool: object
    revision: int = 0
    state: str = "ACTIVE"
    slots: dict = field(default_factory=dict)
    attempts: dict = field(default_factory=dict)
    requests: dict = field(default_factory=dict)
    issued: dict = field(default_factory=dict)
    pending: dict = field(default_factory=dict)
    rces: dict = field(default_factory=dict)
    next_rce: int = 0
    results: tuple = ()
    report: object = None

    def parent_close(self):
        self.system.reduce(self)


@dataclass(slots=True)
class _RCE:
    token: object
    study: _Study
    comparison: int
    repeat: int
    ordinal: int
    identity: object
    contrast: object
    pair: object
    request: object
    revision: int = 0
    state: str = "ACTIVE"
    bundle: object = None
    cases: tuple = ()
    result: object = None

    def binding(self):
        return d(
            "RCEBinding",
            self.identity,
            self.revision,
            self.study.plan.domain.canonical_descriptor(),
        )


@dataclass(frozen=True, slots=True)
class _StudyTombstone:
    state: str
    domain: object


class _CausalSystem:
    """An installed FIXED Unit-6 handler set. All handles use its existing index.
    Constructors alone cannot install a handler or confer any operational role.
    """

    def __init__(self, runtime, work, policy, registry, registry_lock, owner_type):
        self.runtime, self.work, self.policy = runtime, work, policy
        self.registry, self.registry_lock, self.owner_type = (
            registry,
            registry_lock,
            owner_type,
        )
        self.domains = {}
        self.studies = {}

    def register(self, token, role, record, domain):
        with self.registry_lock:
            previous = self.registry.get(id(token))
            if previous is not None:
                if previous[0]() is not None:
                    abort(FailureCode.INTERNAL_CONTRACT_VIOLATION)
                if len(previous) == 6 and previous[2] == "CAUSAL":
                    previous[5].handle_ids.discard(id(token))
            self.registry[id(token)] = (
                ref(token),
                self.runtime,
                "CAUSAL",
                role,
                record,
                domain,
            )
            domain.handle_ids.add(id(token))

    def unregister(self, token, domain):
        with self.registry_lock:
            value = self.registry.get(id(token))
            if (
                value is not None
                and value[0]() is token
                and len(value) == 6
                and value[5] is domain
            ):
                self.registry.pop(id(token), None)
                domain.handle_ids.discard(id(token))

    @contextmanager
    def pinned_source(self, token):
        _, domain = self.entry(token)
        issuer = domain.issuer()
        if issuer is None or type(issuer) is not CausalDomainIssuer:
            abort()
        # Preserve the genuine issuer through the whole call/linearization.
        # Implicit GC cannot invalidate it between validation and publication.
        yield issuer

    def entry(self, token, role=None):
        with self.registry_lock:
            value = self.registry.get(id(token))
            if (
                value is None
                or len(value) != 6
                or value[0]() is not token
                or value[1] is not self.runtime
                or value[2] != "CAUSAL"
                or (role is not None and value[3] != role)
            ):
                abort()
            domain = value[5]
            if domain.closed or domain.issuer() is None:
                abort()
            return value[4], domain

    def study(self, token, item=None):
        study, _ = self.entry(token, "STUDY")
        if (
            type(token) is not CausalStudyAuthority
            or type(study) is not _Study
            or study.token is not token
            or study.state != "ACTIVE"
            or (item is not None and study.item is not item)
        ):
            abort()
        if study.item.lifecycle != (InvocationState.ACTIVE, 0):
            abort(FailureCode.PARENT_AUTHORITY_STALE)
        if (
            study.plan.domain.canonical_descriptor()
            != study.domain.binding().canonical_descriptor()
        ):
            abort(FailureCode.ENVIRONMENT_STALE)
        return study

    def rce(self, token, study=None):
        rce, _ = self.entry(token, "RCE")
        if (
            type(token) is not ReplayComparisonEpoch
            or type(rce) is not _RCE
            or rce.state != "ACTIVE"
            or (study is not None and rce.study is not study)
        ):
            abort()
        self.study(rce.study.token)
        return rce

    @contextmanager
    def guard(self, authority, revision, ledger):
        with _pinned_effect_budget(
            self.runtime.parent, authority, ledger, core=True
        ) as (_, item, core):
            if type(revision) is not int or item.lifecycle != (
                InvocationState.ACTIVE,
                revision,
            ):
                abort(FailureCode.INVOCATION_NOT_ACTIVE)
            yield item, core

    def new_domain(self, issuer, name, environment, measurement, replay_contract=None):
        if type(measurement) is not MeasurementContract or (
            replay_contract is not None
            and type(replay_contract) is not ClosedReplayDomainContract
        ):
            abort(FailureCode.INVALID_INPUT)
        name, environment = closed(name), closed(environment)
        measured = measurement_from_data(_snapshot(measurement.canonical_descriptor()))
        replay = (
            None
            if replay_contract is None
            else replay_contract_from_data(
                _snapshot(replay_contract.canonical_descriptor())
            )
        )
        if replay is not None and (
            replay.measurement.canonical_descriptor() != measured.canonical_descriptor()
            or replay.horizon > self.policy.max_horizon
        ):
            abort(FailureCode.INVALID_POLICY_BINDING)
        with _pinned_cie_parent(self.runtime.parent) as (parent, _, _):
            registered_ingress = parent.ingress
        with (
            _pinned_causal_domain_root(issuer, registered_ingress),
            _pinned_cie_parent(self.runtime.parent, core=True) as (parent, _, _),
        ):
            identity = d("DomainRuntimeIdentity", parent.runtime, name)
            key = canonical_identity_bytes(identity)
            if key in self.domains or len(self.domains) >= self.policy.max_domains:
                abort(FailureCode.CAPACITY_ABORT)
            root = object.__new__(CausalDomainIssuer)
            domain = _Domain(identity, environment, measured, replay, issuer=ref(root))
            controllers = tuple(
                object.__new__(cls)
                for cls in (
                    InterventionController,
                    ProtocolController,
                    IsolationController,
                    ExecutionController,
                    MeasurementController,
                )
            )
            domain.controllers = controllers
            all_handles = (root,) + controllers
            roles = (
                "ROOT",
                "APPLICATION",
                "RANDOMIZATION",
                "ISOLATION",
                "EXECUTION",
                "MEASUREMENT",
            )
            try:
                for token, role in zip(all_handles, roles, strict=True):
                    self.register(token, role, domain, domain)
                self.domains[key] = domain
            except BaseException:
                with self.registry_lock:
                    for token in all_handles:
                        self.registry.pop(id(token), None)
                raise
            return root

    def root_call(self, handle, operation, *args):
        if type(operation) is not str:
            abort(FailureCode.UNKNOWN_OPERATION_TYPE)
        with (
            _pinned_cie_parent(self.runtime.parent, core=True),
            self.pinned_source(handle),
        ):
            domain, actual = self.entry(handle)
            if type(domain) is not _Domain or domain is not actual:
                abort(FailureCode.INVALID_FORMAL_AUTHORITY)
            role = self.registry[id(handle)][3]
            allowed = {
                "ROOT": (
                    "ENVIRONMENT",
                    "CONTROLLERS",
                    "ORIGIN",
                    "CASE",
                    "REVISE",
                    "CLOSE",
                )
            }
            if operation not in allowed.get(role, (role,)):
                abort(FailureCode.INVALID_FORMAL_AUTHORITY)
            if operation == "ENVIRONMENT":
                return ReplayEnvironmentBinding(
                    *_snapshot(domain.binding().canonical_descriptor()).values
                )
            if operation == "CONTROLLERS":
                return domain.controllers
            if operation == "ORIGIN":
                state = closed(args[0])
                if (
                    domain.replay_contract is None
                    or state != domain.replay_contract.relevant_state
                ):
                    abort(
                        FailureCode.INVALID_POLICY_BINDING,
                        "origin not complete bound domain state",
                    )
                if domain.sequence >= 4 * self.policy.max_studies:
                    abort(FailureCode.CAPACITY_ABORT)
                origin = ReplayOrigin(domain.identity, domain.sequence, state)
                returned = ReplayOrigin(
                    *_snapshot(origin.canonical_descriptor()).values
                )
                token = object.__new__(ReplayOriginAuthority)
                try:
                    self.register(token, "ORIGIN", (origin, domain.revision), domain)
                except BaseException:
                    self.unregister(token, domain)
                    raise
                domain.sequence += 1
                return returned, token
            if operation in ("REVISE", "CLOSE"):
                environment = None if operation == "CLOSE" else closed(args[0])
                replacement = None
                if operation == "REVISE" and args[1] is not None:
                    replacement = replay_contract_from_data(
                        _snapshot(args[1].canonical_descriptor())
                    )
                    if (
                        replacement.measurement.canonical_descriptor()
                        != domain.measurement.canonical_descriptor()
                        or replacement.horizon > self.policy.max_horizon
                    ):
                        abort(FailureCode.INVALID_POLICY_BINDING)
                if domain.revision == 2**63 - 1:
                    abort(FailureCode.CAPACITY_ABORT)
                domain.revision += 1
                if environment is not None:
                    domain.environment = environment
                if replacement is not None:
                    domain.replay_contract = replacement
                for study in tuple(self.studies.values()):
                    if study.domain is domain and study.state == "ACTIVE":
                        self.reduce(study)
                if operation == "CLOSE":
                    domain.closed = True
                    with self.registry_lock:
                        for key in domain.handle_ids:
                            entry = self.registry.get(key)
                            if (
                                entry is not None
                                and len(entry) == 6
                                and entry[5] is domain
                            ):
                                self.registry.pop(key, None)
                        domain.handle_ids = set()
                    domain.controllers = ()
                    domain.replay_contract = domain.measurement = domain.environment = (
                        None
                    )
                return None
            if operation == "CASE":
                return self.issue_case(domain, *args)
            return self.issue_controller(domain, operation, *args)

    def issue_case(self, domain, token, slot, outcome, status, attempt, source):
        study = self.study(token)
        integer(slot, len(study.plan.slots) - 1)
        integer(attempt, study.plan.slots[slot].attempts - 1)
        if (
            study.domain is not domain
            or slot not in study.plan.execute_slots
            or study.plan.query == "CLOSED_REPLAY"
        ):
            abort(FailureCode.INVALID_SCOPE)
        if source is not None:
            record, own = self.entry(source, "CASE")
            if own is not domain or record[0] is not study:
                abort(FailureCode.INVALID_FORMAL_AUTHORITY)
            _, _, _, occurrence, outcome, status = record
        else:
            status, outcome = self.measurement_value(study, outcome, status)
            occurrence = d(
                "TrustedCaseOccurrenceIdentity", domain.identity, domain.sequence
            )
        key = ("CASE", slot, attempt)
        old = study.issued.get(key)
        if old is not None:
            actual, _ = self.entry(old, "CASE")
            if actual[4:] != (outcome, status) or (
                source is not None and actual[3] != occurrence
            ):
                abort(FailureCode.EFFECT_PAYLOAD_MISMATCH)
            return old
        if domain.sequence >= 4096:
            abort(FailureCode.CAPACITY_ABORT)
        cap = object.__new__(TrustedCaseOccurrence)
        record = (study, slot, attempt, occurrence, outcome, status)
        staged_issued = {**study.issued, key: cap}
        try:
            self.register(cap, "CASE", record, domain)
        except BaseException:
            self.unregister(cap, domain)
            raise
        study.issued = staged_issued
        if source is None:
            domain.sequence += 1
        return cap

    def measurement_value(self, study, outcome, status):
        if type(status) is not str or status not in (
            "MEASURED",
            "MISSING",
            "FAILED",
            "INVALID",
            "UNAVAILABLE",
            "INCOMPLETE",
        ):
            abort(FailureCode.INVALID_INPUT)
        if status != "MEASURED":
            if outcome is not None:
                abort(FailureCode.INVALID_INPUT, "failed measurement is not an outcome")
            return status, None
        outcome = closed(outcome)
        if not study.plan.outcome_spec.permits(outcome):
            abort(FailureCode.INVALID_INPUT, "unlawful measured outcome")
        return status, outcome

    def branch_binding(self, rce, branch):
        integer(branch, 1)
        comparison = rce.study.plan.comparisons[rce.comparison]
        slot = comparison.left if branch == 0 else comparison.right
        treatment = rce.study.plan.slots[slot].treatment.canonical_descriptor()
        return d(
            "ReplayBranchBinding",
            rce.binding(),
            branch,
            treatment,
            rce.study.domain.replay_contract.measurement.logical_slot,
        )

    def issue_controller(self, domain, kind, token, branch, *extra):
        if type(token) is ReplayComparisonEpoch:
            rce = self.rce(token)
            study = rce.study
            binding = self.branch_binding(rce, branch)
        else:
            study = self.study(token)
            rce = None
            integer(branch, len(study.plan.slots) - 1)
            if study.plan.query != "INTERVENTIONAL" or (
                kind == "APPLICATION" and branch not in study.requests
            ):
                abort(FailureCode.INVALID_SCOPE)
            binding = d(
                "CaseApplicationBinding",
                study.identity,
                branch,
                study.plan.slots[branch].treatment.canonical_descriptor(),
                study.plan.domain.canonical_descriptor(),
            )
        if study.domain is not domain:
            abort(FailureCode.INVALID_FORMAL_AUTHORITY)
        if rce is None and kind not in ("APPLICATION", "RANDOMIZATION"):
            abort(FailureCode.INVALID_SCOPE)
        key = (kind, binding)
        payload = ()
        if kind == "EXECUTION":
            origin, schedule, consumed = extra
            outer(schedule, 65)
            bound = domain.replay_contract
            if (
                closed(origin) != study.plan.origin.canonical_descriptor()
                or _snapshot(schedule) != bound.exogenous_schedule
                or type(consumed) is not int
                or not 0 < consumed <= bound.execution_bound
            ):
                abort(
                    FailureCode.INVALID_POLICY_BINDING,
                    "unbound origin/schedule/execution",
                )
            payload = (closed(origin), _snapshot(schedule), consumed)
        elif kind == "MEASUREMENT":
            outcome, status, target, logical_slot, blind = extra
            measurement = domain.measurement
            if (
                closed(target) != measurement.target
                or type(logical_slot) is not int
                or logical_slot != measurement.logical_slot
                or type(blind) is not bool
                or blind != measurement.treatment_label_blind
            ):
                abort(FailureCode.INVALID_POLICY_BINDING, "measurement cannot adapt")
            status, outcome = self.measurement_value(study, outcome, status)
            payload = (status, outcome, measurement.canonical_descriptor())
        elif kind == "RANDOMIZATION":
            if not study.plan.randomization_required:
                abort(FailureCode.INVALID_SCOPE)
            # Protocol authority is study-bound, not branch-dependent.
            binding = d(
                "CausalProtocolBinding",
                study.identity,
                None if rce is None else rce.binding(),
                study.plan.protocol,
            )
            key = (kind, binding)
        old = study.issued.get(key)
        if old is not None:
            record, _ = self.entry(old, kind)
            if record[3].values[-1] != payload:
                abort(FailureCode.EFFECT_PAYLOAD_MISMATCH)
            return old
        cls = {
            "APPLICATION": AppliedInterventionReceipt,
            "RANDOMIZATION": ProtocolControlReceipt,
            "ISOLATION": BranchIsolationReceipt,
            "EXECUTION": BranchExecutionReceipt,
            "MEASUREMENT": MeasurementReceipt,
        }[kind]
        occurrence = d("ControllerOccurrenceIdentity", domain.identity, domain.sequence)
        descriptor = d("CausalControllerReceipt", kind, binding, occurrence, payload)
        token = object.__new__(cls)
        staged_issued = dict(study.issued)
        case_token = None
        if kind == "MEASUREMENT":
            # A genuine measurement occurrence is minted by the trusted source,
            # not reconstructed from its public receipt descriptor (§40).
            case_token = object.__new__(TrustedCaseOccurrence)
            case_record = (study, rce, branch, occurrence, outcome, status)
            staged_issued[("REPLAY_CASE", binding)] = case_token
        record = (study, rce, branch, descriptor, case_token)
        staged_issued[key] = token
        previous_handles = set(domain.handle_ids)
        try:
            if case_token is not None:
                self.register(case_token, "REPLAY_CASE", case_record, domain)
            self.register(token, kind, record, domain)
            study.issued = staged_issued
        except BaseException:
            with self.registry_lock:
                for handle_id in domain.handle_ids - previous_handles:
                    self.registry.pop(handle_id, None)
                self.registry.pop(id(token), None)
                if case_token is not None:
                    self.registry.pop(id(case_token), None)
                domain.handle_ids = previous_handles
            raise
        domain.sequence += 1
        return token

    def effect_view(self, item, core, target, operation, ordinal, payload, charge):
        from ..effects import _causal_environment

        compiled = contract(operation, ordinal)
        target = _snapshot(target)
        effect = CanonicalEffectDescriptor(
            d("EffectType", operation.value),
            target,
            _snapshot(payload),
            d("CausalEffectScope", target),
            _causal_environment(self.runtime, core),
            d("EffectOwnerBinding", item.identity, item.lifecycle[1]),
            compiled.canonical_descriptor(),
        )
        if (
            len(canonical_identity_bytes(effect.canonical_descriptor()))
            > self.runtime.policy.max_descriptor_bytes
        ):
            abort(FailureCode.CAPACITY_ABORT)
        identity = EffectCommitID(
            effect, d("CausalEffectAuthorityContext", effect.owner_binding, target)
        )
        return EffectCommitView(identity, effect, charge)

    def publish(
        self, study, item, core, operation, ordinal, payload, mutation, *, new_tokens=()
    ):
        """All prospective data is built BEFORE the single shared effect hook.
        The fixed private mutation is selected by compiled code, never a caller.
        """
        from ..effects import _before_effect_publish

        wc = contract(operation, ordinal).work_class
        charge, staged_budget = _prepare_causal_consumption(study.pool, wc)
        target = study.identity
        view = self.effect_view(item, core, target, operation, ordinal, payload, charge)
        returned = clone_view(view)
        with study.owner.lock:
            if len(study.owner.index) >= self.runtime.policy.max_commits_per_owner:
                abort(FailureCode.CAPACITY_ABORT)
            staged = dict(study.owner.index)
            staged[view.commit_id.canonical_bytes] = view
            _before_effect_publish()
            self.study(study.token, item)
            self.check_environment(view, core)
            if operation in (
                CausalOperation.ADMIT_BUNDLE,
                CausalOperation.PUBLISH_REPLAY,
            ):
                self.rce(study.rces[ordinal].token, study)
            # Snapshot only this bounded operational owner. No global registry
            # scan or rollback of another authority/runtime is permitted.
            saved = self.save(study)
            saved_rces = tuple((rce, self.save(rce)) for rce in study.rces.values())
            handles, contrasts = (
                set(study.domain.handle_ids),
                dict(study.domain.contrasts),
            )
            old_budget, old_index = item.budget.index, study.owner.index
            with self.registry_lock:
                try:
                    mutation()
                    study.revision += 1
                    item.budget.index = staged_budget
                    study.owner.index = staged
                except BaseException:
                    # A reused object ID may already belong to the historical
                    # local index. Set difference alone cannot identify the new
                    # registration. Revoke the exact prospectively created token.
                    for token in new_tokens:
                        self.unregister(token, study.domain)
                    for handle_id in study.domain.handle_ids - handles:
                        self.registry.pop(handle_id, None)
                    study.domain.handle_ids = handles
                    study.domain.contrasts = contrasts
                    self.restore(study, saved)
                    for rce, values in saved_rces:
                        self.restore(rce, values)
                    item.budget.index, study.owner.index = old_budget, old_index
                    raise
        return returned

    @staticmethod
    def save(record):
        return tuple(
            (f.name, dict(value) if type(value) is dict else value)
            for f in data_fields(record)
            for value in (getattr(record, f.name),)
        )

    @staticmethod
    def restore(record, saved):
        for name, value in saved:
            setattr(record, name, value)

    def check_environment(self, view, core):
        from ..effects import _causal_environment

        if view.effect.environment_revision != _causal_environment(self.runtime, core):
            abort(FailureCode.ENVIRONMENT_STALE)

    def open_study(
        self, authority, revision, ledger, domain_handle, plan, origin_authority=None
    ):
        from ..effects import _before_effect_publish

        if type(plan) is not CausalStudyPlan:
            abort(FailureCode.INVALID_INPUT)
        frozen = plan_from_data(_snapshot(plan.canonical_descriptor()))
        with self.guard(authority, revision, ledger) as (item, core):
            domain, _ = self.entry(domain_handle, "ROOT")
            if (
                frozen.policy.canonical_descriptor()
                != self.policy.canonical_descriptor()
                or frozen.domain.canonical_descriptor()
                != domain.binding().canonical_descriptor()
                or frozen.outcome_spec.canonical_descriptor()
                != domain.measurement.outcome_spec.canonical_descriptor()
            ):
                abort(FailureCode.INVALID_POLICY_BINDING)
            if frozen.query == "CLOSED_REPLAY":
                origin, own = self.entry(origin_authority, "ORIGIN")
                if (
                    own is not domain
                    or origin[0].canonical_descriptor()
                    != frozen.origin.canonical_descriptor()
                    or origin[1] != domain.revision
                    or domain.replay_contract is None
                ):
                    abort(FailureCode.INVALID_FORMAL_AUTHORITY)
                for slot in frozen.slots:
                    if slot.treatment not in domain.replay_contract.treatments:
                        abort(FailureCode.INVALID_POLICY_BINDING)
            elif origin_authority is not None:
                abort(FailureCode.INVALID_SCOPE)
            for slot in frozen.slots:
                if (
                    slot.treatment is not None
                    and slot.treatment.domain != domain.identity.values[1]
                ):
                    abort(FailureCode.INVALID_SCOPE, "treatment domain mismatch")
            identity = d("CausalStudyIdentity", item.identity, frozen.identity)
            key = canonical_identity_bytes(identity)
            previous = self.studies.get(key)
            if previous is not None:
                if previous.state != "ACTIVE":
                    abort()
                return previous.token
            if len(self.studies) >= self.policy.max_studies:
                abort(FailureCode.CAPACITY_ABORT)
            wc = contract(CausalOperation.OPEN_STUDY).work_class
            token, reservation, staged = _prepare_reservation(item, 1, wc)
            old_budget = item.budget.index
            # Prospective parent-index construction, invisible behind the ledger.
            try:
                item.budget.index = staged
                charge, charged = _prepare_consumption(
                    item, token, reservation.units[0], wc
                )
                item.budget.index = charged
                pool, reserved = _prepare_causal_reservation(
                    item, work_frontier(frozen), identity
                )
            finally:
                item.budget.index = old_budget
            owner = item.effect_owner or self.owner_type(self.runtime)
            if owner.closed or owner.runtime is not self.runtime:
                abort()
            view = self.effect_view(
                item,
                core,
                identity,
                CausalOperation.OPEN_STUDY,
                0,
                frozen.canonical_descriptor(),
                charge,
            )
            cap = object.__new__(CausalStudyAuthority)
            study = _Study(self, cap, item, owner, domain, frozen, identity, pool)
            with owner.lock:
                if (
                    len(owner.index) + len(work_frontier(frozen))
                    > self.runtime.policy.max_commits_per_owner
                ):
                    abort(FailureCode.CAPACITY_ABORT)
                effects = dict(owner.index)
                effects[view.commit_id.canonical_bytes] = view
                _before_effect_publish()
                if item.lifecycle != (InvocationState.ACTIVE, revision):
                    abort(FailureCode.INVOCATION_NOT_ACTIVE)
                if (
                    frozen.domain.canonical_descriptor()
                    != domain.binding().canonical_descriptor()
                ):
                    abort(FailureCode.ENVIRONMENT_STALE)
                self.check_environment(view, core)
                old_owner, old_index, children = (
                    item.effect_owner,
                    owner.index,
                    owner.causal_children,
                )
                old_runtime_owner = self.runtime.owners.get(item.image)
                old_count = item.nondelegated_children
                with self.registry_lock:
                    try:
                        self.register(cap, "STUDY", study, domain)
                        self.studies[key] = study
                        owner.causal_children = children + (study,)
                        item.budget.index = reserved
                        owner.index = effects
                        item.effect_owner = owner
                        item.nondelegated_children += 1
                        self.runtime.owners[item.image] = owner
                    except BaseException:
                        self.registry.pop(id(cap), None)
                        domain.handle_ids.discard(id(cap))
                        self.studies.pop(key, None)
                        owner.causal_children, owner.index = children, old_index
                        item.budget.index, item.effect_owner = old_budget, old_owner
                        item.nondelegated_children = old_count
                        if old_runtime_owner is None:
                            self.runtime.owners.pop(item.image, None)
                        else:
                            self.runtime.owners[item.image] = old_runtime_owner
                        raise
            return cap

    def prepare_compute(
        self,
        authority,
        revision,
        ledger,
        cie,
        study_token,
        operation,
        ordinal,
        data,
        pending_key,
    ):
        snapshot = self.runtime.cie.snapshot(cie).binding
        # Descriptors are not authority. Reconstruct the unique lawful input
        # from registered source handles and bind it to the observed revision.
        with _pinned_cie_parent(self.runtime.parent, authority, revision, core=True):
            registered = self.study(study_token)
            observed_revision = registered.revision
            if operation is CausalOperation.CLASSIFY_CASE:
                outer(pending_key, 3)
                if len(pending_key) != 3 or pending_key[0] != "CASE":
                    abort(FailureCode.INVALID_INPUT)
                slot, attempt = pending_key[1:]
                integer(slot, len(registered.plan.slots) - 1)
                integer(attempt, registered.plan.slots[slot].attempts - 1)
                source = registered.issued.get(("CASE", slot, attempt))
                application = None
                if registered.plan.query == "INTERVENTIONAL":
                    application = registered.issued.get(
                        (
                            "APPLICATION",
                            d(
                                "CaseApplicationBinding",
                                registered.identity,
                                slot,
                                registered.plan.slots[
                                    slot
                                ].treatment.canonical_descriptor(),
                                registered.plan.domain.canonical_descriptor(),
                            ),
                        )
                    )
                protocol = (
                    registered.issued.get(
                        (
                            "RANDOMIZATION",
                            d(
                                "CausalProtocolBinding",
                                registered.identity,
                                None,
                                registered.plan.protocol,
                            ),
                        )
                    )
                    if registered.plan.randomization_required
                    else None
                )
            elif operation is CausalOperation.COMPARE_REPLAY:
                outer(pending_key, 2)
                if pending_key != ("RCE", ordinal):
                    abort(FailureCode.INVALID_INPUT)
                integer(ordinal, 255)
                actual_rce = registered.rces.get(ordinal)
                if actual_rce is None:
                    abort(FailureCode.INVALID_INPUT)
                source = actual_rce.token
            elif operation is CausalOperation.COMPARE_CASES:
                if pending_key != ("STUDY", 0) or ordinal != 0:
                    abort(FailureCode.INVALID_INPUT)
                source = None
            else:
                abort(FailureCode.UNKNOWN_OPERATION_TYPE)
        if operation is CausalOperation.CLASSIFY_CASE:
            _, coordinate, expected = self.case_input(
                authority,
                revision,
                ledger,
                study_token,
                source,
                application,
                protocol,
            )
            if ordinal != coordinate[1] * 4 + coordinate[2] or expected is None:
                abort(FailureCode.INVALID_INPUT)
        else:
            _, expected_operation, expected_ordinal, expected, expected_key = (
                self.comparison_input(
                    authority,
                    revision,
                    ledger,
                    study_token,
                    source,
                )
            )
            if (operation, ordinal, pending_key) != (
                expected_operation,
                expected_ordinal,
                expected_key,
            ):
                abort(FailureCode.INVALID_INPUT)
        if canonical_identity_bytes(data) != canonical_identity_bytes(expected):
            abort(
                FailureCode.INVALID_FORMAL_AUTHORITY,
                "caller data is not the registered causal input",
            )
        with self.guard(authority, revision, ledger) as (item, core):
            study = self.study(study_token, item)
            if study.revision != observed_revision:
                abort(FailureCode.OWNER_AUTHORITY_STALE)
            previous = study.pending.get(pending_key)
            if previous is not None:
                return previous
            with _pinned_cie_work(self.runtime.cie, cie, item, snapshot, core):
                charge, staged = _prepare_causal_consumption(
                    study.pool, contract(operation, ordinal).work_class
                )
                permit, frame = _causal_prepare(
                    self.work,
                    item,
                    revision,
                    study,
                    operation,
                    ordinal,
                    snapshot,
                    data,
                    charge,
                    staged,
                    pending_key,
                    cie,
                )
                return permit, frame, snapshot, cie

    def read_compute(self, study, key, operation, ordinal, core):
        pending = study.pending.get(key)
        if pending is None:
            abort(FailureCode.MISSING_BUDGET_CHARGE)
        permit, _frame, snapshot, cie = pending
        with _pinned_cie_work(self.runtime.cie, cie, study.item, snapshot, core):
            output = _completed_causal_result(
                self.work, permit, study, operation, ordinal, snapshot
            )
        # The exact already-consumed STUDY charge is revalidated, not data authority.
        charge = _causal_permit_charge(self.work, permit)
        _validate_causal_charge(
            study.pool, contract(operation, ordinal).work_class, charge
        )
        return output

    def request_case(self, authority, revision, ledger, token, slot):
        with self.guard(authority, revision, ledger) as (item, core):
            study = self.study(token, item)
            integer(slot, len(study.plan.slots) - 1)
            if (
                study.plan.query != "INTERVENTIONAL"
                or slot not in study.plan.execute_slots
            ):
                abort(FailureCode.INVALID_SCOPE)
            if slot in study.requests:
                payload = study.requests[slot]
                with study.owner.lock:
                    for view in study.owner.index.values():
                        if (
                            view.effect.effect_type
                            == d("EffectType", CausalOperation.REQUEST_CASE.value)
                            and view.effect.canonical_payload == payload
                        ):
                            return clone_view(view)
                abort(FailureCode.INTERNAL_CONTRACT_VIOLATION)
            payload = d(
                "CausalCaseRequest",
                study.identity,
                slot,
                study.plan.slots[slot].treatment.canonical_descriptor(),
                study.plan.protocol,
            )
            return self.publish(
                study,
                item,
                core,
                CausalOperation.REQUEST_CASE,
                slot,
                payload,
                lambda: study.requests.__setitem__(slot, payload),
            )

    def case_input(
        self, authority, revision, ledger, token, case, application=None, protocol=None
    ):
        with self.guard(authority, revision, ledger) as (item, _):
            study = self.study(token, item)
            record, domain = self.entry(case, "CASE")
            if (
                type(case) is not TrustedCaseOccurrence
                or domain is not study.domain
                or record[0] is not study
            ):
                abort(FailureCode.INVALID_FORMAL_AUTHORITY)
            _, slot, attempt, occurrence, outcome, measured = record
            if study.plan.query == "CLOSED_REPLAY":
                abort(FailureCode.INVALID_SCOPE)
            previous = study.slots.get(slot)
            if previous is not None:
                if previous.occurrence == occurrence:
                    return None, (None, slot, attempt), None
                if (
                    previous.measurement_status == "MEASURED"
                    or attempt != study.attempts[slot] + 1
                ):
                    abort(
                        FailureCode.EFFECT_PAYLOAD_MISMATCH,
                        "outcome-based substitution forbidden",
                    )
            elif attempt != 0:
                abort(FailureCode.INVALID_INPUT)
            for comparator in study.plan.comparisons:
                if comparator.independent and slot in (
                    comparator.left,
                    comparator.right,
                ):
                    peer = (
                        comparator.right if slot == comparator.left else comparator.left
                    )
                    if (
                        peer in study.slots
                        and study.slots[peer].occurrence == occurrence
                    ):
                        abort(
                            FailureCode.INVALID_INPUT,
                            "independent comparator occurrence reused",
                        )
            if study.plan.query == "INTERVENTIONAL":
                applied, _ = self.entry(application, "APPLICATION")
                expected = d(
                    "CaseApplicationBinding",
                    study.identity,
                    slot,
                    study.plan.slots[slot].treatment.canonical_descriptor(),
                    study.plan.domain.canonical_descriptor(),
                )
                if (
                    type(application) is not AppliedInterventionReceipt
                    or applied[0] is not study
                    or applied[1] is not None
                    or applied[3].values[1] != expected
                ):
                    abort(FailureCode.INVALID_FORMAL_AUTHORITY)
            elif application is not None:
                abort(FailureCode.INVALID_SCOPE)
            if study.plan.randomization_required:
                controlled, _ = self.entry(protocol, "RANDOMIZATION")
                if (
                    type(protocol) is not ProtocolControlReceipt
                    or controlled[0] is not study
                    or controlled[1] is not None
                ):
                    abort(FailureCode.INVALID_FORMAL_AUTHORITY)
            elif protocol is not None:
                abort(FailureCode.INVALID_SCOPE)
            state = (
                "FULFILLED"
                if measured == "MEASURED"
                else "FAILED"
                if measured == "FAILED"
                else "UNRESOLVED"
            )
            orientation = d("CaseConditionRole", slot, study.plan.slots[slot].condition)
            row = (slot, state, occurrence, outcome, measured, orientation)
            data = d(
                "CausalCaseClassificationInput",
                study.plan.matching.canonical_descriptor(),
                study.plan.outcome_spec.canonical_descriptor(),
                (row,),
            )
            return None, (None, slot, attempt), data

    def publish_case(
        self, authority, revision, ledger, token, case, application=None, protocol=None
    ):
        _unused, record, data = self.case_input(
            authority, revision, ledger, token, case, application, protocol
        )
        if data is None:
            with self.guard(authority, revision, ledger) as (item, _):
                study = self.study(token, item)
            return CaseSlotReport(
                *_snapshot(study.slots[record[1]].canonical_descriptor()).values
            )
        with self.guard(authority, revision, ledger) as (item, core):
            study = self.study(token, item)
            slot, attempt = record[1:3]
            key = ("CASE", slot, attempt)
            output = self.read_compute(
                study, key, CausalOperation.CLASSIFY_CASE, slot * 4 + attempt, core
            )
            report = CaseSlotReport(*fields(output, "CaseSlotReport", 6))
            returned = CaseSlotReport(*_snapshot(report.canonical_descriptor()).values)
            staged_slots = {**study.slots, slot: report}
            staged_attempts = {**study.attempts, slot: attempt}

            def commit():
                study.slots, study.attempts = staged_slots, staged_attempts

            self.publish(
                study,
                item,
                core,
                CausalOperation.ADMIT_CASE,
                slot * 4 + attempt,
                output,
                commit,
            )
            _discard_causal_permit(self.work, study.pending.pop(key)[0])
            return returned

    def open_rce(self, authority, revision, ledger, token, comparison, repeat):
        with self.guard(authority, revision, ledger) as (item, core):
            study = self.study(token, item)
            if study.plan.query != "CLOSED_REPLAY":
                abort(FailureCode.INVALID_SCOPE)
            integer(comparison, len(study.plan.comparisons) - 1)
            integer(repeat, study.plan.repetitions - 1)
            ordinal = comparison * 8 + repeat
            old = study.rces.get(ordinal)
            if old is not None:
                if old.state != "ACTIVE":
                    abort()
                return old.token
            if comparison * study.plan.repetitions + repeat != study.next_rce or any(
                v.state == "ACTIVE" for v in study.rces.values()
            ):
                abort(
                    FailureCode.INVALID_INPUT,
                    "canonical prospective RCE order required",
                )
            cmp = study.plan.comparisons[comparison]
            pair = treatment_pair(
                study.plan.slots[cmp.left].treatment,
                study.plan.slots[cmp.right].treatment,
            )
            basis = identification_basis(
                study.domain.replay_contract, study.plan.domain
            )
            crci = contrast_identity(
                study.domain.identity, study.plan.origin, pair, basis
            )
            identity = d("RCEIdentity", study.identity, ordinal)
            cap = object.__new__(ReplayComparisonEpoch)
            request = d(
                "ReplayRequest",
                identity,
                canonical_identity_bytes(crci),
                (0, 1),
                study.domain.replay_contract.canonical_descriptor(),
            )
            rce = _RCE(
                cap, study, comparison, repeat, ordinal, identity, crci, pair, request
            )

            def commit():
                self.register(cap, "RCE", rce, study.domain)
                study.rces[ordinal] = rce

            self.publish(
                study,
                item,
                core,
                CausalOperation.OPEN_RCE,
                ordinal,
                request,
                commit,
                new_tokens=(cap,),
            )
            return cap

    def admit_bundle(self, authority, revision, ledger, token, rce_token, receipts):
        outer(receipts, 9)
        with self.guard(authority, revision, ledger) as (item, core):
            study = self.study(token, item)
            rce = self.rce(rce_token, study)
            expected_count = 9 if study.plan.randomization_required else 8
            if len(receipts) != expected_count:
                abort(FailureCode.INVALID_INPUT, "partial execution bundle")
            required = {
                (kind, branch)
                for kind in ("APPLICATION", "ISOLATION", "EXECUTION", "MEASUREMENT")
                for branch in range(2)
            }
            if study.plan.randomization_required:
                required.add(("RANDOMIZATION", 0))
            by_role = {}
            for receipt in receipts:
                data, domain = self.entry(receipt)
                kind = self.registry[id(receipt)][3]
                if (
                    domain is not study.domain
                    or type(data) is not tuple
                    or len(data) != 5
                    or data[0] is not study
                    or data[1] is not rce
                    or kind
                    not in (
                        "APPLICATION",
                        "ISOLATION",
                        "EXECUTION",
                        "MEASUREMENT",
                        "RANDOMIZATION",
                    )
                ):
                    abort(FailureCode.INVALID_FORMAL_AUTHORITY)
                key = (kind, data[2])
                if key not in required or key in by_role:
                    abort(FailureCode.INVALID_INPUT, "duplicate/wrong branch receipt")
                by_role[key] = _snapshot(data[3])
                if kind == "MEASUREMENT":
                    measured_case, own = self.entry(data[4], "REPLAY_CASE")
                    if (
                        type(data[4]) is not TrustedCaseOccurrence
                        or own is not domain
                        or measured_case[0] is not study
                        or measured_case[1] is not rce
                        or measured_case[2] != data[2]
                    ):
                        abort(FailureCode.INVALID_FORMAL_AUTHORITY)
            if set(by_role) != required:
                abort(FailureCode.INVALID_INPUT)
            ordered_receipts = tuple(by_role[k] for k in sorted(by_role))
            bundle = ReplayExecutionBundle(rce.binding(), ordered_receipts)
            returned = ReplayExecutionBundle(
                *_snapshot(bundle.canonical_descriptor()).values
            )
            if rce.bundle is not None:
                if rce.bundle.canonical_descriptor() != bundle.canonical_descriptor():
                    abort(FailureCode.EFFECT_PAYLOAD_MISMATCH)
                return returned
            cases = tuple(
                self.entry(receipt, "REPLAY_CASE")[0]
                for branch in range(2)
                for receipt in (
                    study.issued[("REPLAY_CASE", self.branch_binding(rce, branch))],
                )
            )

            def commit():
                rce.bundle, rce.cases = bundle, cases

            self.publish(
                study,
                item,
                core,
                CausalOperation.ADMIT_BUNDLE,
                rce.ordinal,
                bundle.canonical_descriptor(),
                commit,
            )
            return returned

    def comparison_input(self, authority, revision, ledger, token, rce_token=None):
        with self.guard(authority, revision, ledger) as (item, _):
            study = self.study(token, item)
            matching = study.plan.matching.canonical_descriptor()
            spec = study.plan.outcome_spec.canonical_descriptor()
            measurement = study.domain.measurement.canonical_descriptor()
            if rce_token is not None:
                rce = self.rce(rce_token, study)
                if rce.bundle is None:
                    abort(FailureCode.INVALID_INPUT, "complete bundle required")
                cmp = study.plan.comparisons[rce.comparison]
                rows = []
                for branch, slot in enumerate((cmp.left, cmp.right)):
                    receipt = rce.cases[branch]
                    occurrence, outcome, measured = receipt[3:]
                    rows.append(
                        (
                            slot,
                            "FULFILLED"
                            if measured == "MEASURED"
                            else "FAILED"
                            if measured == "FAILED"
                            else "UNRESOLVED",
                            occurrence,
                            outcome,
                            measured,
                            study.plan.slots[slot].treatment.canonical_descriptor(),
                        )
                    )
                return (
                    None,
                    CausalOperation.COMPARE_REPLAY,
                    rce.ordinal,
                    d(
                        "CausalReplayComparisonInput",
                        matching,
                        spec,
                        tuple(rows),
                        cmp.requires_resolved,
                        rce.contrast,
                        rce.pair,
                        study.domain.identity,
                        measurement,
                    ),
                    ("RCE", rce.ordinal),
                )
            if study.plan.query == "CLOSED_REPLAY":
                abort(FailureCode.INVALID_SCOPE)
            rows = []
            for slot, planned in enumerate(study.plan.slots):
                report = study.slots.get(
                    slot,
                    CaseSlotReport(
                        slot,
                        "LAWFULLY_UNEXECUTED"
                        if slot not in study.plan.execute_slots
                        else "UNRESOLVED",
                        "UNRESOLVED",
                    ),
                )
                orientation = d(
                    "CaseConditionRole",
                    slot,
                    planned.condition
                    if planned.treatment is None
                    else planned.treatment.canonical_descriptor(),
                )
                rows.append(
                    (
                        slot,
                        report.terminal_state,
                        report.occurrence,
                        report.outcome,
                        report.measurement_status,
                        orientation,
                    )
                )
            return (
                None,
                CausalOperation.COMPARE_CASES,
                0,
                d(
                    "CausalCaseComparisonInput",
                    matching,
                    spec,
                    tuple(rows),
                    tuple(c.canonical_descriptor() for c in study.plan.comparisons),
                    study.plan.query,
                    study.plan.identity,
                    study.domain.identity,
                    measurement,
                ),
                ("STUDY", 0),
            )

    def publish_comparison(self, authority, revision, ledger, token, rce_token=None):
        with self.guard(authority, revision, ledger) as (item, core):
            study = self.study(token, item)
            rce = None if rce_token is None else self.rce(rce_token, study)
            key, op, ordinal = (
                (("STUDY", 0), CausalOperation.COMPARE_CASES, 0)
                if rce is None
                else (("RCE", rce.ordinal), CausalOperation.COMPARE_REPLAY, rce.ordinal)
            )
            output = self.read_compute(study, key, op, ordinal, core)
            status, reports, results = fields(output, "CausalComparisonOutput", 3)
            copied = tuple(result_from_data(v) for v in results)
            returned_result = (
                None
                if not copied
                else result_from_data(_snapshot(copied[0].canonical_descriptor()))
            )
            slots = {
                v.values[0]: CaseSlotReport(*fields(v, "CaseSlotReport", 6))
                for v in reports
            }
            if rce is None:
                report = CausalStudyReport(
                    status,
                    study.plan.identity,
                    tuple(slots[i] for i in range(len(study.plan.slots))),
                    copied,
                )

                def commit():
                    study.slots, study.report, study.results = slots, report, copied

                self.publish(
                    study,
                    item,
                    core,
                    CausalOperation.PUBLISH_STUDY,
                    0,
                    report.canonical_descriptor(),
                    commit,
                )
                self.reduce(study, terminal="COMPLETE")
                return report
            audit_key = canonical_identity_bytes(rce.contrast)
            audit = None if not copied else canonical_identity_bytes(copied[0].identity)
            previous = study.domain.contrasts.get(audit_key)
            if previous is not None and audit is not None and previous != audit:
                abort(
                    FailureCode.INTERNAL_CONTRACT_VIOLATION,
                    "DETERMINISM_CONTRACT_VIOLATION",
                )
            if (
                audit is not None
                and previous is None
                and len(study.domain.contrasts) >= self.policy.max_contrasts
            ):
                abort(FailureCode.CAPACITY_ABORT)

            # Registry audit stores full canonical identity ONLY; no replay/case
            # history or semantic lookup API exists. Equal repeats verify one ID.
            def commit():
                if audit is not None:
                    study.domain.contrasts[audit_key] = audit
                rce.result, rce.state = copied[0] if copied else None, "TERMINAL"
                rce.revision += 1
                study.next_rce += 1
                study.slots = {**slots, **study.slots}
                study.results += copied

            self.publish(
                study,
                item,
                core,
                CausalOperation.PUBLISH_REPLAY,
                ordinal,
                output,
                commit,
            )
            self.unregister(rce.token, study.domain)
            _discard_causal_permit(self.work, study.pending.pop(key)[0])
            rce.bundle, rce.cases = None, ()
            return returned_result

    def finish_replay_study(self, authority, revision, ledger, token):
        with self.guard(authority, revision, ledger) as (item, core):
            study = self.study(token, item)
            if (
                study.plan.query != "CLOSED_REPLAY"
                or study.next_rce
                != len(study.plan.comparisons) * study.plan.repetitions
            ):
                abort(
                    FailureCode.INVALID_INPUT,
                    "complete frozen replay frontier required",
                )
            slots = tuple(
                study.slots.get(i, CaseSlotReport(i, "UNRESOLVED", "UNRESOLVED"))
                for i in range(len(study.plan.slots))
            )
            status = (
                "COMPLETE"
                if all(v.result is not None for v in study.rces.values())
                else "INCOMPLETE"
            )
            # Repeated CRCI is one canonical result, not independent evidence.
            unique = {canonical_identity_bytes(v.identity): v for v in study.results}
            report = CausalStudyReport(
                status,
                study.plan.identity,
                slots,
                tuple(unique[k] for k in sorted(unique)),
            )
            self.publish(
                study,
                item,
                core,
                CausalOperation.PUBLISH_STUDY,
                0,
                report.canonical_descriptor(),
                lambda: setattr(study, "report", report),
            )
            self.reduce(study, terminal="COMPLETE")
            return report

    def reduce(self, study, terminal="ABORTED"):
        if study.state != "ACTIVE":
            return study.report
        with study.pool.budget.lock:
            staged = _causal_retirement(study.pool)
            if study.report is None:
                slots = tuple(
                    study.slots.get(
                        i,
                        CaseSlotReport(
                            i,
                            "LAWFULLY_UNEXECUTED"
                            if i not in study.plan.execute_slots
                            else "UNRESOLVED",
                            "UNRESOLVED",
                        ),
                    )
                    for i in range(len(study.plan.slots))
                )
                report = CausalStudyReport(
                    "ABORTED", study.plan.identity, slots, study.results
                )
            else:
                report = study.report
            with study.owner.lock:
                study.state, study.revision, study.report = (
                    terminal,
                    study.revision + 1,
                    report,
                )
                for rce in study.rces.values():
                    rce.state, rce.revision = "TERMINAL", rce.revision + 1
                    rce.bundle, rce.cases = None, ()
                with self.registry_lock:
                    for token in study.issued.values():
                        self.unregister(token, study.domain)
                    for rce in study.rces.values():
                        self.unregister(rce.token, study.domain)
                    self.unregister(study.token, study.domain)
                study.pool.budget.index = staged
                pending = tuple(study.pending.values())
                study.pending = {}
                study.issued, study.requests, study.slots, study.attempts = (
                    {},
                    {},
                    {},
                    {},
                )
                study.rces, study.results = {}, ()
                self.studies[canonical_identity_bytes(study.identity)] = (
                    _StudyTombstone(terminal, study.domain)
                )
                study.owner.causal_children = tuple(
                    s for s in study.owner.causal_children if s is not study
                )
                study.item.nondelegated_children -= 1
                study.plan, study.report = None, None
            for permit, _frame, _snapshot_binding, _cie in pending:
                try:
                    _discard_causal_permit(self.work, permit)
                except IngressAbort:
                    # Parent Work cleanup may already have retired the payload.
                    pass
            return report

    def check_completed(self, token, key, operation, ordinal):
        with _pinned_cie_parent(self.runtime.parent):
            study = self.study(token)
            authority, ledger = study.item.authority, study.item.ledger
        with self.guard(authority, 0, ledger) as (_, core):
            self.read_compute(study, key, operation, ordinal, core)
            return True

    def abort_study(self, authority, revision, ledger, token):
        with self.guard(authority, revision, ledger) as (item, _):
            return self.reduce(self.study(token, item))

    def registry_status(self):
        with _pinned_cie_parent(self.runtime.parent):
            return d(
                "CausalRegistryStatus",
                len(self.domains),
                sum(s.state == "ACTIVE" for s in self.studies.values()),
                sum(len(v.contrasts) for v in self.domains.values()),
            )


@dataclass(frozen=True, slots=True)
class CausalityRuntime:
    invocations: object
    cie: object
    work: object
    effects: object
    policy: CausalityPolicy
    prediction: object

    @property
    def reasoning(self):
        return self.prediction.reasoning

    def _call(self, operation, *args):
        from ..effects import _causal_call

        return _causal_call(self.effects, operation, *args)

    def trusted_domain(
        self, issuer, name, environment, measurement, *, replay_contract=None
    ):
        """TRUSTED COMPOSITION ROOT ONLY; never pass this issuer to operators."""
        return self._call(
            "new_domain", issuer, name, environment, measurement, replay_contract
        )

    def open_study(
        self, authority, revision, ledger, domain, plan, *, origin_authority=None
    ):
        return self._call(
            "open_study", authority, revision, ledger, domain, plan, origin_authority
        )

    def request_case(self, authority, revision, ledger, study, slot):
        return self._call("request_case", authority, revision, ledger, study, slot)

    def admit_case(
        self,
        authority,
        revision,
        ledger,
        cie,
        study,
        case,
        *,
        application=None,
        protocol=None,
    ):
        _owner, record, data = self._call(
            "case_input",
            authority,
            revision,
            ledger,
            study,
            case,
            application,
            protocol,
        )
        if data is not None:
            ordinal = record[1] * 4 + record[2]
            permit, frame, _, _cie = self._call(
                "prepare_compute",
                authority,
                revision,
                ledger,
                cie,
                study,
                CausalOperation.CLASSIFY_CASE,
                ordinal,
                data,
                ("CASE", record[1], record[2]),
            )
            try:
                self.work.execute(permit, frame)
            except IngressAbort:
                # A paid, already-DONE exact result may be attached on retry.
                self._call(
                    "check_completed",
                    study,
                    ("CASE", record[1], record[2]),
                    CausalOperation.CLASSIFY_CASE,
                    ordinal,
                )
        return self._call(
            "publish_case",
            authority,
            revision,
            ledger,
            study,
            case,
            application,
            protocol,
        )

    def open_rce(self, authority, revision, ledger, study, comparison=0, repeat=0):
        return self._call(
            "open_rce", authority, revision, ledger, study, comparison, repeat
        )

    def admit_bundle(self, authority, revision, ledger, study, rce, receipts):
        return self._call(
            "admit_bundle", authority, revision, ledger, study, rce, receipts
        )

    def compare(self, authority, revision, ledger, cie, study, *, rce=None):
        _owner, op, ordinal, data, key = self._call(
            "comparison_input", authority, revision, ledger, study, rce
        )
        permit, frame, _, _cie = self._call(
            "prepare_compute",
            authority,
            revision,
            ledger,
            cie,
            study,
            op,
            ordinal,
            data,
            key,
        )
        try:
            self.work.execute(permit, frame)
        except IngressAbort:
            self._call("check_completed", study, key, op, ordinal)
        return self._call("publish_comparison", authority, revision, ledger, study, rce)

    def finish_study(self, authority, revision, ledger, study):
        return self._call("finish_replay_study", authority, revision, ledger, study)

    def abort(self, authority, revision, ledger, study):
        return self._call("abort_study", authority, revision, ledger, study)

    def registry_status(self):
        return self._call("registry_status")


def create_causality_runtime(
    cause_ingress, *, policy=None, invocation_limits=None, **foundation_options
):
    from ..effects import _attach_causality
    from ..prediction.runtime import create_prediction_runtime

    policy = CausalityPolicy() if policy is None else policy
    if type(policy) is not CausalityPolicy:
        raise TypeError("exact Causality policy required")
    frozen = CausalityPolicy(*policy.canonical_descriptor().values)
    foundation = create_prediction_runtime(
        cause_ingress, invocation_limits=invocation_limits, **foundation_options
    )
    _attach_causality(foundation.effects, foundation.work, frozen)
    return CausalityRuntime(
        foundation.invocations,
        foundation.cie,
        foundation.work,
        foundation.effects,
        frozen,
        foundation,
    )
