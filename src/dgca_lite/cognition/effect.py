"""Canonical Unit-6 effect/commit data. Descriptors are NEVER live authority."""

import hashlib
from dataclasses import dataclass

from .budget import BudgetChargeView
from .identity import CanonicalDescriptor, CognitiveEnvironmentBinding, SnapshotBinding
from .ingress import _snapshot
from .policy import ValueLimits
from .serialization import canonical_identity_bytes


@dataclass(frozen=True, slots=True)
class EffectPolicy:
    max_commits_per_owner: int = 64
    max_payload_nodes: int = 64
    max_payload_depth: int = 16
    max_scalar_bytes: int = 4096
    max_descriptor_bytes: int = 131072

    def __post_init__(self):
        for value, ceiling in (
            (self.max_commits_per_owner, 256),
            (self.max_payload_nodes, 128),
            (self.max_payload_depth, 24),
            (self.max_scalar_bytes, 8192),
            (self.max_descriptor_bytes, 262144),
        ):
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError("invalid finite effect policy")

    def canonical_descriptor(self):
        self.__post_init__()
        return CanonicalDescriptor(
            "Unit6EffectPolicy",
            (
                self.max_commits_per_owner,
                self.max_payload_nodes,
                self.max_payload_depth,
                self.max_scalar_bytes,
                self.max_descriptor_bytes,
            ),
        )

    @property
    def payload_limits(self):
        self.__post_init__()
        return ValueLimits(
            self.max_payload_nodes, self.max_payload_depth, self.max_scalar_bytes
        )


@dataclass(frozen=True, slots=True)
class CanonicalEffectDescriptor:
    effect_type: CanonicalDescriptor
    target_identity: CanonicalDescriptor
    canonical_payload: object
    scope_binding: CanonicalDescriptor
    environment_revision: CognitiveEnvironmentBinding
    owner_binding: CanonicalDescriptor
    execution_contract: CanonicalDescriptor

    def canonical_descriptor(self):
        if (
            any(
                type(value) is not CanonicalDescriptor
                for value in (
                    self.effect_type,
                    self.target_identity,
                    self.scope_binding,
                    self.owner_binding,
                    self.execution_contract,
                )
            )
            or type(self.environment_revision) is not CognitiveEnvironmentBinding
        ):
            raise TypeError("closed exact effect fields required")
        return CanonicalDescriptor(
            "CanonicalEffectDescriptor",
            (
                self.effect_type,
                self.target_identity,
                self.canonical_payload,
                self.scope_binding,
                self.environment_revision,
                self.owner_binding,
                self.execution_contract,
            ),
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


def freeze_effect(policy, effect, *, payload_limits=None):
    if (
        type(policy) is not EffectPolicy
        or type(effect) is not CanonicalEffectDescriptor
    ):
        raise TypeError("exact frozen effect/policy required")
    # Capture each reference once. Every tighter input bound precedes copying or
    # broader complete-descriptor encoding, including frozen-field bypass races.
    kind, target, payload, scope, environment, owner, contract = (
        effect.effect_type,
        effect.target_identity,
        effect.canonical_payload,
        effect.scope_binding,
        effect.environment_revision,
        effect.owner_binding,
        effect.execution_contract,
    )
    payload = _snapshot(
        payload,
        limits=policy.payload_limits if payload_limits is None else payload_limits,
    )
    small = (
        ValueLimits(32, 16, policy.max_scalar_bytes)
        if payload_limits is None
        else ValueLimits(128, 48, policy.max_scalar_bytes)
    )
    target = _snapshot(target, limits=small)
    scope = _snapshot(scope, limits=small)
    fields = _snapshot(
        CanonicalDescriptor("EffectContextFields", (kind, environment, owner, contract))
    )
    frozen = CanonicalEffectDescriptor(
        fields.values[0], target, payload, scope, *fields.values[1:]
    )
    if (
        len(canonical_identity_bytes(frozen.canonical_descriptor()))
        > policy.max_descriptor_bytes
    ):
        raise ValueError("complete descriptor exceeds byte bound")
    return frozen


@dataclass(frozen=True, slots=True)
class EffectCommitID:
    effect: CanonicalEffectDescriptor
    authority_context: CanonicalDescriptor

    def canonical_descriptor(self):
        if (
            type(self.effect) is not CanonicalEffectDescriptor
            or type(self.authority_context) is not CanonicalDescriptor
        ):
            raise TypeError("invalid exact logical commit identity")
        return CanonicalDescriptor(
            "EffectCommitID",
            (self.effect.canonical_descriptor(), self.authority_context),
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())

    @property
    def canonical_bytes(self):
        return canonical_identity_bytes(self.canonical_descriptor())

    @property
    def index_digest(self):
        """Convenience index only. Full canonical bytes remain identity."""
        return hashlib.sha256(self.canonical_bytes).hexdigest()


@dataclass(frozen=True, slots=True)
class PreparedEffect:
    effect: CanonicalEffectDescriptor
    snapshot_binding: SnapshotBinding | None
    charge: BudgetChargeView
    unit_ordinal: int

    def canonical_descriptor(self):
        if (
            type(self.effect) is not CanonicalEffectDescriptor
            or (
                self.snapshot_binding is not None
                and type(self.snapshot_binding) is not SnapshotBinding
            )
            or type(self.charge) is not BudgetChargeView
            or type(self.unit_ordinal) is not int
            or not 0 <= self.unit_ordinal < 256
        ):
            raise TypeError("invalid closed prepared effect")
        return CanonicalDescriptor(
            "PreparedEffect",
            (
                self.effect.canonical_descriptor(),
                self.snapshot_binding,
                self.charge.canonical_descriptor(),
                self.unit_ordinal,
            ),
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


@dataclass(frozen=True, slots=True)
class EffectCommitView:
    commit_id: EffectCommitID
    effect: CanonicalEffectDescriptor
    charge: BudgetChargeView
    status: str = "COMMITTED"

    def canonical_descriptor(self):
        if (
            type(self.commit_id) is not EffectCommitID
            or type(self.effect) is not CanonicalEffectDescriptor
            or type(self.charge) is not BudgetChargeView
            or type(self.status) is not str
            or self.status != "COMMITTED"
        ):
            raise TypeError("invalid capability-free historical commit view")
        # Full byte equality, never Python scalar/hash equality.
        if canonical_identity_bytes(
            self.commit_id.effect.canonical_descriptor()
        ) != canonical_identity_bytes(self.effect.canonical_descriptor()):
            raise ValueError("commit/effect mismatch")
        reasoning = self.effect.effect_type == CanonicalDescriptor(
            "EffectType", ("REASONING_PUBLISH",)
        )
        prediction = self.effect.effect_type in (
            CanonicalDescriptor("EffectType", ("PREDICTION_SEAL_AND_DELEGATE",)),
            CanonicalDescriptor("EffectType", ("PREDICTION_EVALUATE_AND_RECORD",)),
        )
        from .causality.contracts import CausalOperation

        causal = self.effect.effect_type in tuple(
            CanonicalDescriptor("EffectType", (operation.value,))
            for operation in CausalOperation
        )
        if reasoning or prediction or causal:
            # The complete effect is already present in commit_id. Avoid a
            # second copy of a bounded reasoning publication's proof graph.
            return CanonicalDescriptor(
                "ReasoningEffectCommitView"
                if reasoning
                else "PredictionEffectCommitView"
                if prediction
                else "CausalEffectCommitView",
                (
                    self.commit_id.canonical_descriptor(),
                    self.charge.canonical_descriptor(),
                    self.status,
                ),
            )
        return CanonicalDescriptor(
            "EffectCommitView",
            (
                self.commit_id.canonical_descriptor(),
                self.effect.canonical_descriptor(),
                self.charge.canonical_descriptor(),
                self.status,
            ),
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


def clone_commit_view(policy, view, *, payload_limits=None):
    effect = freeze_effect(policy, view.effect, payload_limits=payload_limits)
    context = _snapshot(view.commit_id.authority_context)
    data = _snapshot(view.charge.canonical_descriptor())
    return EffectCommitView(
        EffectCommitID(effect, context),
        effect,
        BudgetChargeView(*data.values[1:], source_kind=data.values[0]),
    )
