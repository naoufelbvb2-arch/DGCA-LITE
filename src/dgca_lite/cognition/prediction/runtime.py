"""Thin Prediction scheduling over shared ingress, Invocation, CIE, Work and effects."""

from dataclasses import dataclass

from ..arena import CIEPolicy
from ..cie import create_cie_runtime
from ..effect import EffectPolicy
from ..effects import create_effect_runtime
from ..ingress import _attach_prediction
from ..invocation import InvocationLimits, create_invocation_runtime
from ..reasoning.runtime import ReasoningRuntime
from ..reasoning.schemas import ReasoningPolicy
from ..work import _prediction_project, create_work_runtime
from .projection import ConditionalProjectionView, PredictionPolicy
from .targets import AtomicCarrier, BranchPattern


@dataclass(frozen=True, slots=True)
class PredictionRuntime:
    invocations: object
    cie: object
    work: object
    effects: object
    policy: PredictionPolicy
    reasoning_policy: ReasoningPolicy

    @property
    def reasoning(self):
        return ReasoningRuntime(self.invocations, self.cie, self.work, self.effects)

    def project(
        self,
        authority,
        revision,
        ledger,
        cie,
        *,
        receipt=None,
        internal_cue=(),
        reasoning_claims=(),
    ):
        snapshot = self.cie.snapshot(cie).binding
        permit, frame = _prediction_project(
            self.work,
            authority,
            revision,
            cie,
            ledger,
            snapshot,
            receipt,
            internal_cue,
            reasoning_claims,
        )
        result = self.work.execute(permit, frame)
        return ConditionalProjectionView(*result.output.values), permit

    def seal(
        self, authority, revision, ledger, cie, projection_permit, target, horizon
    ):
        if type(target) in (AtomicCarrier, BranchPattern):
            target = target.canonical_descriptor()
        return self.effects.seal_forecast(
            authority,
            revision,
            ledger,
            cie,
            self.work,
            projection_permit,
            target,
            horizon,
        )

    def outcome(self, fda):
        return self.effects.forecast_outcome(fda)

    def cancel(self, fda):
        return self.effects.cancel_forecast(fda)

    def forecast_registry_status(self):
        return self.effects.forecast_registry_status()


def create_prediction_runtime(
    cause_ingress,
    *,
    invocation_limits=None,
    cie_policy=None,
    policy=None,
    l2_config=None,
    reasoning_policy=None,
    effect_policy=None,
):
    from dgca_lite.memory.config import MemoryConfig

    policy = PredictionPolicy() if policy is None else policy
    if type(policy) is not PredictionPolicy:
        raise TypeError("exact frozen Prediction policy required")
    policy = PredictionPolicy(*policy.canonical_descriptor().values[:6])
    if l2_config is None:
        l2_config = MemoryConfig(
            max_snapshot_cells=policy.max_capture_cells,
            max_snapshot_assemblies=policy.max_capture_assemblies,
            max_snapshot_synapses=policy.max_capture_synapses,
        )
    if type(l2_config) is not MemoryConfig:
        raise TypeError("exact frozen L2 capture policy required")
    for value, maximum in (
        (l2_config.max_snapshot_cells, policy.max_capture_cells),
        (l2_config.max_snapshot_assemblies, policy.max_capture_assemblies),
        (l2_config.max_snapshot_synapses, policy.max_capture_synapses),
    ):
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValueError("Prediction capture requires finite prospective L2 bounds")
    if invocation_limits is None:
        invocation_limits = InvocationLimits(128)
    reasoning_policy = (
        ReasoningPolicy() if reasoning_policy is None else reasoning_policy
    )
    parent = create_invocation_runtime(cause_ingress, invocation_limits)
    cie = create_cie_runtime(
        parent, policy=cie_policy or CIEPolicy(), l2_config=l2_config
    )
    work = create_work_runtime(
        parent, cie, reasoning_policy=reasoning_policy, prediction_policy=policy
    )
    effects = create_effect_runtime(
        parent,
        cie,
        reasoning_policy=reasoning_policy,
        prediction_policy=policy,
        policy=EffectPolicy(max_descriptor_bytes=262144)
        if effect_policy is None
        else effect_policy,
    )
    _attach_prediction(cause_ingress, effects, work)
    return PredictionRuntime(parent, cie, work, effects, policy, reasoning_policy)
