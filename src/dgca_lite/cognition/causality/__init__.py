"""Prospective, bounded Causality. Data is never operational authority."""

from .cases import CaseSlotReport, TrustedCaseOccurrence
from .contracts import CausalityPolicy
from .intervention import (
    AppliedInterventionReceipt,
    BranchIsolationReceipt,
    ExposureDescriptor,
    ProtocolControlReceipt,
    TreatmentDescriptor,
)
from .measurement import ExactOutcomeClassification, MeasurementContract, OutcomeSpec
from .replay import (
    BranchExecutionReceipt,
    ClosedReplayDomainContract,
    MeasurementReceipt,
    ReplayComparisonEpoch,
    ReplayEnvironmentBinding,
    ReplayExecutionBundle,
    ReplayOrigin,
    ReplayOriginAuthority,
)
from .results import CausalResultView, CausalStudyReport
from .study import (
    CaseSlot,
    CausalHypothesis,
    CausalStudyAuthority,
    CausalStudyPlan,
    Comparison,
)

__all__ = [
    "AppliedInterventionReceipt",
    "BranchExecutionReceipt",
    "BranchIsolationReceipt",
    "CaseSlot",
    "CaseSlotReport",
    "CausalHypothesis",
    "CausalResultCognitiveView",
    "CausalResultView",
    "CausalStudyAuthority",
    "CausalStudyPlan",
    "CausalStudyReport",
    "CausalityPolicy",
    "CausalityRuntime",
    "ClosedReplayDomainContract",
    "Comparison",
    "ExactOutcomeClassification",
    "ExposureDescriptor",
    "MeasurementContract",
    "MeasurementReceipt",
    "OutcomeSpec",
    "ProtocolControlReceipt",
    "ReplayComparisonEpoch",
    "ReplayEnvironmentBinding",
    "ReplayExecutionBundle",
    "ReplayOrigin",
    "ReplayOriginAuthority",
    "TreatmentDescriptor",
    "TrustedCaseOccurrence",
    "causal_result_view",
    "create_causality_runtime",
]


def __getattr__(name):
    if name in ("CausalityRuntime", "create_causality_runtime"):
        from .runtime import CausalityRuntime, create_causality_runtime

        return {
            "CausalityRuntime": CausalityRuntime,
            "create_causality_runtime": create_causality_runtime,
        }[name]
    if name in ("CausalResultCognitiveView", "causal_result_view"):
        from .adapters import CausalResultCognitiveView, causal_result_view

        return {
            "CausalResultCognitiveView": CausalResultCognitiveView,
            "causal_result_view": causal_result_view,
        }[name]
    raise AttributeError(name)
