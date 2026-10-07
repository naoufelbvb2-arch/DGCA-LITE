"""Trusted composition-root issuance and closed ingress/event boundaries.

create_trusted_ingress_boundary is a trusted external bootstrap, not a cognitive
API. Its returned issuer must stay with the trusted source/controller. Pass
only the narrower adapters and explicitly issued handles to consumers. A new
formal authorization is an explicit source action, never text interpretation.

External Core transitions use the issuer's complete Core barrier. Without
Prediction, core_transition permits the existing TrustedCoreAdapter path.
With Prediction attached, process_core_event dispatches that same normal path
exactly once and delivers its genuine occurrence to the fixed forecast handler
before releasing the barrier. Cognitive operators receive neither this issuer
nor a live Core/receipt. Invocation, CIE, budget and effect machinery remain in
their existing modules; this ingress boundary grants no semantic work exemption.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from threading import RLock
from weakref import ReferenceType, ref

from dgca_lite.engine import CoreEngine
from dgca_lite.memory.integration import TrustedRetrievalReceipt, validate_receipt
from dgca_lite.memory.types import RetrievalAbort

from .assertions import (
    ActiveConstraintPremiseView,
    IngressAssertionView,
    validate_constraint_content,
)
from .authority import (
    AssumptionIssuanceCapability,
    ExternalOccurrenceBinding,
    ExternalOccurrenceCapability,
    FormalConstraintOccurrenceCapability,
    FormalSourceOccurrenceCapability,
    IngressAbort,
    _OpaqueHandle,
)
from .identity import (
    _RECORD_SCHEMAS,
    AssertionSemanticKey,
    CanonicalDescriptor,
    ClaimContentID,
    CoreStateBinding,
    DependencyRootIdentity,
    InvocationCauseID,
    ScopeIdentity,
    SourceAssertionKey,
    _validated_record_fields,
    canonical_dependencies,
)
from .locks import RankedBarrier, _deferred_cleanup
from .policy import DEFAULT_VALUE_LIMITS
from .serialization import canonical_identity_bytes
from .types import AssertionBasis, DependencyKind, FailureCode


def _snapshot(value: object, *, limits=None) -> object:
    """Deep independent closed-data snapshot; recheck boundedness while copying.

    Frozen-record bypass/races cannot share caller references into issuance state.
    The final image must exactly equal the validated initial image or fail closed.
    """
    custom_limits = limits is not None
    if not custom_limits:
        limits = DEFAULT_VALUE_LIMITS

    def encode(item):
        # Preserve the default codec call path, including its established
        # validation/fault-injection contract. Unit 5 supplies tighter bounds.
        if not custom_limits:
            return canonical_identity_bytes(item)
        return canonical_identity_bytes(item, limits)

    before = encode(value)
    nodes = 0
    ancestors: set[int] = set()

    def clone(item: object, depth: int) -> object:
        nonlocal nodes
        nodes += 1
        if nodes > limits.max_nodes or depth > limits.max_depth:
            raise ValueError("issuance snapshot exceeds node/depth bound")
        item_type = type(item)
        if item is None or any(
            item_type is primitive for primitive in (bool, int, float, str, bytes)
        ):
            return item
        if item_type is not tuple and not any(
            item_type is record_type for record_type in _RECORD_SCHEMAS
        ):
            # Enum encodings also charge their class-name and value nodes.
            nodes += 2
            if nodes > limits.max_nodes or depth + 1 > limits.max_depth:
                raise ValueError("issuance snapshot exceeds node/depth bound")
            encode(item)  # Only a genuine closed Enum can pass.
            return item
        identity = id(item)
        if identity in ancestors:
            raise ValueError("cyclic issuance snapshot")
        ancestors.add(identity)
        try:
            if item_type is tuple:
                if len(item) > limits.max_nodes - nodes:
                    raise ValueError("issuance tuple exceeds remaining node bound")
                return tuple(clone(member, depth + 1) for member in item)
            fields = _validated_record_fields(item, limits.max_nodes - nodes)
            # Match the encoder's shared budget, including schema metadata,
            # before examining a later field's tuple members.
            clone(item_type.__name__, depth + 1)
            copied = {}
            for name, member in fields:
                clone(name, depth + 1)
                copied[name] = clone(member, depth + 1)
            return item_type(**copied)
        finally:
            ancestors.remove(identity)

    result = clone(value, 0)
    if encode(result) != before:
        raise ValueError("issuance input changed during snapshot")
    return result


def _build_authority_system():
    # Fixed lifetime bound includes tombstones for canonical runtime identities.
    # These are noncognitive anti-ABA audit identities, not a knowledge store.
    max_domains = 64
    registry_lock = RLock()
    used_runtime_ids: set[bytes] = set()
    handles: dict[int, tuple[ReferenceType, object, str, type]] = {}
    domains: dict[int, tuple[ReferenceType, object]] = {}
    core_audits: tuple = ()
    read_facets = {}

    @dataclass(slots=True)
    class _CoreAudit:
        core: ReferenceType
        barrier: object = field(default_factory=lambda: RankedBarrier(0))
        last_observation: tuple[int, int, int] = (-1, -1, -1)
        last_domain: object = None
        prediction: object = None
        continuity_revision: int = 0

    @dataclass(frozen=True, slots=True)
    class _Record:
        capability: _OpaqueHandle
        capability_type: type
        role: str
        basis: AssertionBasis
        revision: int
        content: ClaimContentID
        scope: ScopeIdentity
        occurrence: CanonicalDescriptor
        dependencies: tuple[DependencyRootIdentity, ...]
        source_authority: CanonicalDescriptor
        payload: CanonicalDescriptor
        frozen_bytes: bytes

    @dataclass(slots=True)
    class _State:
        core: CoreEngine
        runtime: CanonicalDescriptor
        formal: CanonicalDescriptor
        capacity: int
        core_audit: _CoreAudit
        barrier: object = field(default_factory=lambda: RankedBarrier(0))
        domain_nonce: object = field(default_factory=object)
        revision: int = 0
        closed: bool = False
        index: tuple[dict[bytes, _Record], dict[int, _Record]] = field(
            default_factory=lambda: ({}, {})
        )
        adapters: tuple = ()
        owner_id: int = 0
        prediction: object = None
        active_prediction_event: object = None

        @property
        def occurrences(self) -> dict[bytes, _Record]:
            return self.index[0]

        @property
        def tokens(self) -> dict[int, _Record]:
            return self.index[1]

    def state_for(handle: object, role: str) -> _State:
        with registry_lock:
            entry = handles.get(id(handle))
            if (
                entry is None
                or entry[0]() is not handle
                or entry[2] != role
                or type(handle) is not entry[3]
            ):
                raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
            return entry[1]

    def live(state: _State) -> None:
        if state.closed:
            raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)

    @contextmanager
    def pinned_adapter(handle: object, role: str):
        # Pin the issuer for the whole use, including waiting for the barrier.
        # Implicit GC retirement therefore runs only after every use quiesces.
        with registry_lock:
            state = state_for(handle, role)
            registered = domains.get(state.owner_id)
            owner = None if registered is None else registered[0]()
            if owner is None:
                raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
            if type(owner) is not TrustedIngressIssuer:
                raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
        with state.barrier:
            live(state)
            yield state
        # The local strong owner is intentionally retained through the yield.
        del owner

    def record_for(
        state: _State, capability: object, allowed: tuple[type, ...]
    ) -> _Record:
        live(state)
        if not any(type(capability) is expected for expected in allowed):
            raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
        record = state.tokens.get(id(capability))
        if record is None or record.capability is not capability:
            raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
        if type(capability) is not record.capability_type or not any(
            record.capability_type is expected for expected in allowed
        ):
            raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
        if record.revision != state.revision:
            raise IngressAbort(FailureCode.OWNER_AUTHORITY_STALE)
        if canonical_identity_bytes(record.payload) != record.frozen_bytes:
            raise IngressAbort(FailureCode.INTERNAL_CONTRACT_VIOLATION)
        return record

    def issue(
        state: _State,
        role: str,
        capability_type: type,
        basis: AssertionBasis,
        content: ClaimContentID,
        scope: ScopeIdentity,
        occurrence: CanonicalDescriptor,
        dependencies: tuple = (),
    ):
        live(state)
        if (
            type(content) is not ClaimContentID
            or type(scope) is not ScopeIdentity
            or type(occurrence) is not CanonicalDescriptor
        ):
            raise IngressAbort(FailureCode.INVALID_INPUT)
        try:
            roots = canonical_dependencies(dependencies)
            if role.startswith("CONSTRAINT"):
                validate_constraint_content(content)
            source_kind = "FORMAL_CONSTRAINT" if role.startswith("CONSTRAINT") else role
            source_authority = CanonicalDescriptor(
                "IngressSourceAuthority",
                (
                    state.runtime,
                    state.formal if role != "EXTERNAL_OBSERVATION" else state.runtime,
                    source_kind,
                ),
            )
            if role == "FORMAL_ASSUMPTION":
                assumption = DependencyRootIdentity(
                    DependencyKind.ASSUMPTION,
                    source_authority,
                    CanonicalDescriptor(
                        "FormalAssumptionOccurrence", (occurrence, scope)
                    ),
                )
                roots = canonical_dependencies(roots + (assumption,))
            payload = _snapshot(
                CanonicalDescriptor(
                    "IngressIssuance",
                    (
                        role,
                        basis,
                        content,
                        scope,
                        occurrence,
                        roots,
                        source_authority,
                        state.runtime,
                        state.revision,
                    ),
                )
            )
            (
                _,
                basis,
                content,
                scope,
                occurrence,
                roots,
                source_authority,
                _,
                revision,
            ) = payload.values
            frozen = canonical_identity_bytes(payload)
            occurrence_key = canonical_identity_bytes(
                CanonicalDescriptor(
                    "IngressSourceOccurrence",
                    (
                        source_kind,
                        source_authority,
                        occurrence,
                    ),
                )
            )
        except (TypeError, ValueError) as error:
            raise IngressAbort(FailureCode.INVALID_INPUT) from error
        previous = state.occurrences.get(occurrence_key)
        if previous is not None:
            record_for(state, previous.capability, (capability_type,))
            if previous.frozen_bytes != frozen:
                raise IngressAbort(
                    FailureCode.EFFECT_PAYLOAD_MISMATCH,
                    "same occurrence has different authorized payload",
                )
            return previous.capability
        if len(state.occurrences) >= state.capacity:
            raise IngressAbort(FailureCode.CAPACITY_ABORT)
        token = object.__new__(capability_type)
        record = _Record(
            token,
            capability_type,
            role,
            basis,
            revision,
            content,
            scope,
            occurrence,
            roots,
            source_authority,
            payload,
            frozen,
        )
        # All semantic validation/allocation above precedes registry publication.
        occurrences = dict(state.occurrences)
        tokens = dict(state.tokens)
        occurrences[occurrence_key] = record
        tokens[id(token)] = record
        state.index = (occurrences, tokens)
        return token

    def assertion_view(record: _Record) -> IngressAssertionView:
        image = _snapshot(
            CanonicalDescriptor(
                "IngressAssertionFields",
                (
                    record.content,
                    record.basis,
                    record.scope,
                    record.dependencies,
                    record.source_authority,
                    record.occurrence,
                    record.role,
                ),
            )
        )
        content, basis, scope, roots, source, occurrence, role = image.values
        return IngressAssertionView(
            AssertionSemanticKey(content, basis, scope, roots),
            SourceAssertionKey(role, source, occurrence),
        )

    class FormalReasoningIngress(_OpaqueHandle):
        __slots__ = ()

        def accept(self, capability: object) -> IngressAssertionView:
            with pinned_adapter(self, "REASONING") as state:
                record = record_for(
                    state,
                    capability,
                    (FormalSourceOccurrenceCapability, AssumptionIssuanceCapability),
                )
                return assertion_view(record)

    class TrustedObservationAdapter(_OpaqueHandle):
        __slots__ = ()

        def accept(self, capability: object) -> IngressAssertionView:
            with pinned_adapter(self, "OBSERVATION") as state:
                return assertion_view(
                    record_for(state, capability, (ExternalOccurrenceCapability,))
                )

    class FormalConstraintIngress(_OpaqueHandle):
        __slots__ = ()

        def accept(self, capability: object) -> ActiveConstraintPremiseView:
            with pinned_adapter(self, "CONSTRAINT") as state:
                record = record_for(
                    state, capability, (FormalConstraintOccurrenceCapability,)
                )
                image = _snapshot(
                    CanonicalDescriptor(
                        "ConstraintIngressFields",
                        (
                            record.content,
                            record.basis,
                            record.scope,
                            record.dependencies,
                            record.source_authority,
                            record.occurrence,
                        ),
                    )
                )
                return ActiveConstraintPremiseView(*image.values)

    class InvocationCauseIngress(_OpaqueHandle):
        """Narrow bootstrap/admission handle; exposes no source-issuance methods."""

        __slots__ = ()

    @contextmanager
    def pinned_invocation_cause(ingress: object, capability: object = None):
        """Private Unit-3 bridge: keep genuine issuance current through admission.

        The returned identities are data, not admission capabilities. Unit 3
        invokes this guard itself; it accepts neither these identities nor
        caller-provided validator callbacks as proof. No issuer/Core reference
        crosses the bridge, and the Core barrier remains held through the yield.
        None is used only by trusted runtime bootstrap, never cause admission.
        """
        with pinned_adapter(ingress, "INVOCATION_CAUSE") as state:
            cause = None
            if capability is not None:
                record = record_for(
                    state,
                    capability,
                    (
                        ExternalOccurrenceCapability,
                        FormalSourceOccurrenceCapability,
                        AssumptionIssuanceCapability,
                        FormalConstraintOccurrenceCapability,
                    ),
                )
                cause = _snapshot(
                    InvocationCauseID(record.source_authority, record.occurrence)
                )
            yield _snapshot(state.runtime), cause

    @contextmanager
    def pinned_core_binding(ingress: object):
        """Unit-4 capture under the SAME complete Core transition barrier.

        Only closed binding data crosses this bridge, never Core or its issuer.
        The trusted composition root must route every external transition through
        core_transition, as required by the existing Unit-2 integration contract.
        """
        from dgca_lite.config import CoreConfig

        with pinned_adapter(ingress, "INVOCATION_CAUSE") as state:
            core = state.core
            if type(core.config) is not CoreConfig:
                raise IngressAbort(FailureCode.INVALID_POLICY_BINDING)
            try:
                values = {
                    f.name: getattr(core.config, f.name) for f in fields(CoreConfig)
                }
                frozen_config = CoreConfig(**values)
                policy = CanonicalDescriptor(
                    "CoreConfig",
                    tuple(
                        (f.name, getattr(frozen_config, f.name))
                        for f in fields(CoreConfig)
                    ),
                )
                binding = _snapshot(
                    CoreStateBinding(
                        state.runtime,
                        core.network.version,
                        core.network.tick,
                        core.temporal.next_root_id,
                        policy,
                    )
                )
            except (TypeError, ValueError, AttributeError) as error:
                raise IngressAbort(FailureCode.INVALID_POLICY_BINDING) from error
            yield binding

    def remove_domain(state: _State) -> None:
        if state.prediction is not None:
            from .effects import _retire_prediction_environment

            with state.barrier:
                _retire_prediction_environment(state.prediction[0])
                state.prediction = None
                if (
                    state.core_audit.prediction is not None
                    and state.core_audit.prediction[0] is state
                ):
                    state.core_audit.prediction = None
        state.closed = True
        state.revision += 1
        state.index = ({}, {})
        with registry_lock:
            registered = domains.get(state.owner_id)
            if registered is not None and registered[1] is state:
                domains.pop(state.owner_id)
            registered_handle = handles.get(state.owner_id)
            if registered_handle is not None and registered_handle[1] is state:
                handles.pop(state.owner_id)
            for adapter in state.adapters:
                registered_handle = handles.get(id(adapter))
                if registered_handle is not None and registered_handle[1] is state:
                    handles.pop(id(adapter))
        state.adapters = ()

    class TrustedIngressIssuer(_OpaqueHandle):
        """Keep at the trusted composition root, never in cognitive inputs.

        Formal authorize_* calls assert genuinely new source authorization; they are
        not invoked from text, retrieval or result adapters. Receipt conversion admits
        only the exact observed structural frontier, never a caller's arbitrary claim.
        """

        __slots__ = ()

        @property
        def formal_reasoning(self) -> FormalReasoningIngress:
            state = state_for(self, "ISSUER")
            with state.barrier:
                live(state)
                return state.adapters[0]

        @property
        def formal_constraints(self) -> FormalConstraintIngress:
            state = state_for(self, "ISSUER")
            with state.barrier:
                live(state)
                return state.adapters[1]

        @property
        def observations(self) -> TrustedObservationAdapter:
            state = state_for(self, "ISSUER")
            with state.barrier:
                live(state)
                return state.adapters[2]

        @property
        def invocation_causes(self) -> InvocationCauseIngress:
            state = state_for(self, "ISSUER")
            with state.barrier:
                live(state)
                return state.adapters[3]

        @contextmanager
        def core_transition(self):
            state = state_for(self, "ISSUER")
            with state.barrier:
                live(state)
                if state.core_audit.prediction is not None:
                    raise IngressAbort(
                        FailureCode.INVALID_FORMAL_AUTHORITY,
                        "Prediction requires the trusted process_core_event boundary",
                    )
                yield

        def process_core_event(self, event, *, boundary=False, additional_evidence=()):
            """Trusted composition-root event route; no operator/FDA can call it.

            The genuine lower-layer receipt exists before forecast acquisition.
            Delivery is synchronous under the same complete Core barrier, so
            capture completion/thread order cannot reorder trusted occurrences.
            """
            from dgca_lite.memory.integration import TrustedCoreAdapter
            from dgca_lite.model import HardBoundary

            from .effects import _deliver_prediction_event

            state = state_for(self, "ISSUER")
            with state.barrier:
                live(state)
                if type(boundary) not in (bool, HardBoundary):
                    raise IngressAbort(FailureCode.INVALID_INPUT)
                present = (
                    boundary.present if type(boundary) is HardBoundary else boundary
                )
                if type(present) is not bool:
                    raise IngressAbort(FailureCode.INVALID_INPUT)
                result = TrustedCoreAdapter.process_event(
                    state.core,
                    event,
                    boundary=boundary,
                    additional_evidence=additional_evidence,
                )
                if present:
                    state.core_audit.continuity_revision += 1
                outcomes = ()
                if state.core_audit.prediction is not None:
                    prediction_state, effects, work = state.core_audit.prediction
                    prediction_state.active_prediction_event = (result.receipt, present)
                    try:
                        outcomes = _deliver_prediction_event(
                            effects, work, result.receipt, present
                        )
                    finally:
                        prediction_state.active_prediction_event = None
                return result, outcomes

        @property
        def registry_status(self) -> tuple[int, int, int]:
            state = state_for(self, "ISSUER")
            with state.barrier:
                live(state)
                return state.revision, len(state.occurrences), state.capacity

        def describe(self, capability: object) -> ExternalOccurrenceBinding:
            state = state_for(self, "ISSUER")
            with state.barrier:
                record = record_for(
                    state,
                    capability,
                    (
                        ExternalOccurrenceCapability,
                        FormalSourceOccurrenceCapability,
                        AssumptionIssuanceCapability,
                        FormalConstraintOccurrenceCapability,
                    ),
                )
                image = _snapshot(
                    CanonicalDescriptor(
                        "OccurrenceBindingFields",
                        (
                            record.role,
                            record.occurrence,
                            state.runtime,
                            record.revision,
                            record.scope,
                        ),
                    )
                )
                # Translate the private constraint role into the canonical ingress class.
                role, occurrence, runtime, revision, scope = image.values
                ingress_class = (
                    "FORMAL_" + role if role.startswith("CONSTRAINT") else role
                )
                return ExternalOccurrenceBinding(
                    ingress_class, occurrence, runtime, revision, scope
                )

        def authorize_given(
            self,
            content: ClaimContentID,
            scope: ScopeIdentity,
            occurrence: CanonicalDescriptor,
            *,
            dependencies: tuple = (),
        ):
            state = state_for(self, "ISSUER")
            with state.barrier:
                return issue(
                    state,
                    "FORMAL_GIVEN",
                    FormalSourceOccurrenceCapability,
                    AssertionBasis.FORMAL_GIVEN,
                    content,
                    scope,
                    occurrence,
                    dependencies,
                )

        def authorize_assumption(
            self,
            content: ClaimContentID,
            scope: ScopeIdentity,
            occurrence: CanonicalDescriptor,
            *,
            dependencies: tuple = (),
        ):
            state = state_for(self, "ISSUER")
            with state.barrier:
                return issue(
                    state,
                    "FORMAL_ASSUMPTION",
                    AssumptionIssuanceCapability,
                    AssertionBasis.FORMAL_ASSUMPTION,
                    content,
                    scope,
                    occurrence,
                    dependencies,
                )

        def authorize_constraint_given(
            self,
            content: ClaimContentID,
            scope: ScopeIdentity,
            occurrence: CanonicalDescriptor,
            *,
            dependencies: tuple = (),
        ):
            state = state_for(self, "ISSUER")
            with state.barrier:
                return issue(
                    state,
                    "CONSTRAINT_GIVEN",
                    FormalConstraintOccurrenceCapability,
                    AssertionBasis.FORMAL_GIVEN,
                    content,
                    scope,
                    occurrence,
                    dependencies,
                )

        def authorize_constraint_assumption(
            self,
            content: ClaimContentID,
            occurrence: CanonicalDescriptor,
            assumption: object,
        ):
            state = state_for(self, "ISSUER")
            with state.barrier:
                parent = record_for(state, assumption, (AssumptionIssuanceCapability,))
                return issue(
                    state,
                    "CONSTRAINT_ASSUMPTION",
                    FormalConstraintOccurrenceCapability,
                    AssertionBasis.FORMAL_ASSUMPTION,
                    content,
                    parent.scope,
                    occurrence,
                    parent.dependencies,
                )

        def authorize_core_observation(self, receipt: object, scope: ScopeIdentity):
            state = state_for(self, "ISSUER")
            with state.barrier:
                live(state)
                if type(receipt) is not TrustedRetrievalReceipt:
                    raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
                version, tick = state.core.network.version, state.core.network.tick
                try:
                    post_version, post_tick, root, frontier, activation = (
                        validate_receipt(state.core, receipt, version, tick)
                    )
                except RetrievalAbort as error:
                    raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY) from error
                if state.core.temporal.next_root_id != root + 1 or (
                    state.core.network.version,
                    state.core.network.tick,
                ) != (post_version, post_tick):
                    raise IngressAbort(FailureCode.ENVIRONMENT_STALE)
                observed = (post_version, post_tick, root)
                audit = state.core_audit
                last_root = audit.last_observation[2]
                if root < last_root or (
                    root == last_root
                    and (
                        observed != audit.last_observation
                        or audit.last_domain is not state.domain_nonce
                    )
                ):
                    raise IngressAbort(
                        FailureCode.OWNER_AUTHORITY_STALE,
                        "the Core occurrence was already authorized by a retired issuer",
                    )
                # Literal observed structure only; no inferred semantic proposition,
                # lexical negation, missing-value evidence or arbitrary claim input.
                content = ClaimContentID(
                    CanonicalDescriptor("ObservedCoreFrontier", (frontier, activation))
                )
                occurrence = CanonicalDescriptor(
                    "TrustedCoreOccurrence", (post_version, post_tick, root)
                )
                capability = issue(
                    state,
                    "EXTERNAL_OBSERVATION",
                    ExternalOccurrenceCapability,
                    AssertionBasis.EXTERNAL_OBSERVATION,
                    content,
                    scope,
                    occurrence,
                )
                # Publish the bounded anti-reingress watermark only on success,
                # under the shared Core barrier. No claim/graph history is kept.
                audit.last_observation = observed
                audit.last_domain = state.domain_nonce
                return capability

        def invalidate(self) -> None:
            state = state_for(self, "ISSUER")
            with state.barrier:
                live(state)
                if state.prediction is not None:
                    from .effects import _retire_prediction_environment

                    _retire_prediction_environment(state.prediction[0])
                state.revision += 1
                # Retain bounded occurrence tombstones: no stale replay can reissue.

        def close(self) -> None:
            state = state_for(self, "ISSUER")
            with state.barrier:
                remove_domain(state)

    def create_trusted_ingress_boundary(
        core: CoreEngine,
        runtime_identity: CanonicalDescriptor,
        formal_source_identity: CanonicalDescriptor,
        *,
        capacity: int = 128,
    ):
        """Trusted bootstrap only. One live owner/Core; runtime IDs never recycle.

        capacity bounds lifetime source occurrences, including invalidated tombstones.
        Both identity inputs are assigned by the trusted composition root, not taken
        from claims. Copied identities cannot attach to an existing authority domain.
        """
        nonlocal handles, domains, used_runtime_ids, core_audits
        if (
            type(core) is not CoreEngine
            or type(runtime_identity) is not CanonicalDescriptor
            or type(formal_source_identity) is not CanonicalDescriptor
        ):
            raise TypeError("invalid trusted bootstrap input")
        if type(capacity) is not int or capacity <= 0:
            raise ValueError("ingress capacity must be a positive integer")
        runtime = _snapshot(runtime_identity)
        formal = _snapshot(formal_source_identity)
        runtime_key = canonical_identity_bytes(runtime)
        with registry_lock:
            if runtime_key in used_runtime_ids or any(
                entry[1].core is core for entry in domains.values()
            ):
                raise IngressAbort(
                    FailureCode.INVALID_FORMAL_AUTHORITY,
                    "runtime/Core domain already registered",
                )
            if len(used_runtime_ids) >= max_domains:
                raise IngressAbort(
                    FailureCode.CAPACITY_ABORT, "bounded ingress-domain audit is full"
                )
            owner = object.__new__(TrustedIngressIssuer)
            audit = next((entry for entry in core_audits if entry.core() is core), None)
            next_audits = core_audits
            if audit is None:
                audit = _CoreAudit(ref(core))
                next_audits = core_audits + (audit,)
            state = _State(
                core, runtime, formal, capacity, audit, barrier=audit.barrier
            )
            state.owner_id = id(owner)
            state.adapters = tuple(
                object.__new__(kind)
                for kind in (
                    FormalReasoningIngress,
                    FormalConstraintIngress,
                    TrustedObservationAdapter,
                    InvocationCauseIngress,
                )
            )

            @_deferred_cleanup
            def discard(reference: ReferenceType) -> None:
                # Every use pins the owner. At this point there is no in-flight
                # use, so cleanup needs no Core barrier (nor lock inversion).
                remove_domain(state)

            owner_ref = ref(owner, discard)
            # Stage every index/weak reference before the lock-protected publish.
            next_domains = dict(domains)
            next_handles = dict(handles)
            next_runtime_ids = set(used_runtime_ids)
            next_domains[id(owner)] = (owner_ref, state)
            next_handles[id(owner)] = (owner_ref, state, "ISSUER", TrustedIngressIssuer)
            for adapter, role in zip(
                state.adapters,
                ("REASONING", "CONSTRAINT", "OBSERVATION", "INVOCATION_CAUSE"),
                strict=True,
            ):
                next_handles[id(adapter)] = (ref(adapter), state, role, type(adapter))
            next_runtime_ids.add(runtime_key)
            domains, handles, used_runtime_ids = (
                next_domains,
                next_handles,
                next_runtime_ids,
            )
            core_audits = next_audits
            return owner

    def reasoning_sources(ingress, capabilities):
        """Private read-only transfer; caller holds the existing Core barrier.

        Genuine occurrence handles are validated; copied view fields never mint
        a basis. No issuer, Core object or capability crosses this bridge.
        """
        if type(capabilities) is not tuple or len(capabilities) > 64:
            raise IngressAbort(FailureCode.CAPACITY_ABORT)
        state = state_for(ingress, "INVOCATION_CAUSE")
        output = []
        for cap in capabilities:
            record = record_for(
                state,
                cap,
                (
                    FormalSourceOccurrenceCapability,
                    AssumptionIssuanceCapability,
                    ExternalOccurrenceCapability,
                    FormalConstraintOccurrenceCapability,
                ),
            )
            if record.role.startswith("CONSTRAINT"):
                view = ActiveConstraintPremiseView(
                    record.content,
                    record.basis,
                    record.scope,
                    record.dependencies,
                    record.source_authority,
                    record.occurrence,
                )
            else:
                view = assertion_view(record)
            output.append(view.canonical_descriptor())
        return tuple(output)

    @dataclass(frozen=True, slots=True)
    class _PredictionRead:
        state: _State
        receipt: object
        binding: CoreStateBinding
        occurrence: object
        explicitly_empty: bool

        @property
        def runtime(self):
            return self.state.runtime

        @property
        def revision(self):
            return self.state.revision

        @property
        def continuity(self):
            return self.state.core_audit.continuity_revision

        def retrieve(self, config, cue):
            from dgca_lite.memory.session import (
                retrieve_after_core_event,
                retrieve_internal,
            )

            validate_prediction_reader(self)
            if self.receipt is None:
                return retrieve_internal(self.state.core, dict(cue), config)
            return retrieve_after_core_event(
                self.state.core, self.receipt, dict(cue), config
            )

        def target_valid(self, descriptor):
            from .prediction.targets import AtomicCarrier, target_from_data

            validate_prediction_reader(self)
            target = target_from_data(descriptor)
            network = self.state.core.network
            if type(target) is AtomicCarrier:
                cell = network.cells.get(target.carrier_id)
                return (
                    cell is not None and cell.committed and cell.id == target.carrier_id
                )
            assembly = network.assemblies.get(target.target_assembly_id)
            if assembly is None or assembly.id != target.target_assembly_id:
                return False
            if not set(target.pattern_cells) <= assembly.members:
                return False
            return all(
                (cell := network.cells.get(cid)) is not None
                and cell.committed
                and cell.id == cid
                for cid in target.pattern_cells
            )

    @contextmanager
    def prediction_core(ingress, receipt=None, *, delivery=False, boundary=None):
        """Private bounded read facet under existing Core barrier, never a worker argument."""
        with pinned_adapter(ingress, "INVOCATION_CAUSE") as state:
            if delivery and (
                state.active_prediction_event is None
                or state.active_prediction_event[0] is not receipt
                or state.active_prediction_event[1] is not boundary
            ):
                raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
            occurrence, empty = None, False
            if receipt is not None:
                if type(receipt) is not TrustedRetrievalReceipt:
                    raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
                try:
                    version, tick, root, frontier, _ = validate_receipt(
                        state.core,
                        receipt,
                        state.core.network.version,
                        state.core.network.tick,
                    )
                except RetrievalAbort as error:
                    raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY) from error
                if state.core.temporal.next_root_id != root + 1:
                    raise IngressAbort(FailureCode.ENVIRONMENT_STALE)
                occurrence = CanonicalDescriptor(
                    "TrustedCoreOccurrence", (version, tick, root)
                )
                empty = not frontier
            with pinned_core_binding(ingress) as binding:
                reader = _PredictionRead(state, receipt, binding, occurrence, empty)
                with registry_lock:
                    if len(read_facets) >= 4 * max_domains:
                        raise IngressAbort(FailureCode.CAPACITY_ABORT)
                    read_facets[id(reader)] = reader
                try:
                    yield reader
                finally:
                    with registry_lock:
                        read_facets.pop(id(reader), None)

    def attach_prediction(ingress, effects, work):
        from .effects import EffectRuntime
        from .work import WorkRuntime

        if type(effects) is not EffectRuntime or type(work) is not WorkRuntime:
            raise IngressAbort(FailureCode.INVALID_POLICY_BINDING)
        with pinned_adapter(ingress, "INVOCATION_CAUSE") as state:
            if state.prediction is not None or state.core_audit.prediction is not None:
                raise IngressAbort(FailureCode.INVALID_POLICY_BINDING)
            from .effects import _validate_prediction_attachment

            _validate_prediction_attachment(effects, work, ingress)
            state.prediction = (effects, work)
            state.core_audit.prediction = (state, effects, work)

    def validate_prediction_reader(reader):
        with registry_lock:
            if (
                type(reader) is not _PredictionRead
                or read_facets.get(id(reader)) is not reader
            ):
                raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
        # This private read facet is created only inside the existing pinned
        # Core gate, not from public RootView/receipt descriptor reconstruction.
        state = reader.state
        if (
            state.closed
            or state.prediction is None
            or reader.binding.core_identity != state.runtime
        ):
            raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)

    return (
        TrustedIngressIssuer,
        FormalReasoningIngress,
        FormalConstraintIngress,
        TrustedObservationAdapter,
        create_trusted_ingress_boundary,
        InvocationCauseIngress,
        pinned_invocation_cause,
        pinned_core_binding,
        reasoning_sources,
        prediction_core,
        attach_prediction,
        validate_prediction_reader,
    )


(
    TrustedIngressIssuer,
    FormalReasoningIngress,
    FormalConstraintIngress,
    TrustedObservationAdapter,
    create_trusted_ingress_boundary,
    InvocationCauseIngress,
    _pinned_invocation_cause,
    _pinned_core_binding,
    _reasoning_sources,
    _pinned_prediction_core,
    _attach_prediction,
    _validate_prediction_reader,
) = _build_authority_system()
del _build_authority_system
