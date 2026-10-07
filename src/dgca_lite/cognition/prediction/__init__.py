"""Read-only Prediction: structural projections and prospective forecasts."""

from .commitment import ForecastCommitment, ForecastCommitmentView
from .fda import ForecastDelegatedAuthority
from .observation import (
    ForecastEvaluationID,
    ForecastOutcomeView,
    FutureTrustedOccurrenceID,
)
from .projection import ConditionalProjectionView, PredictionPolicy
from .targets import AtomicCarrier, BranchPattern, TargetGuard

__all__ = [
    "AtomicCarrier",
    "BranchPattern",
    "ConditionalProjectionView",
    "ForecastCommitment",
    "ForecastCommitmentView",
    "ForecastDelegatedAuthority",
    "ForecastEvaluationID",
    "ForecastOutcomeView",
    "FutureTrustedOccurrenceID",
    "PredictionOutcomeCognitiveView",
    "PredictionPolicy",
    "PredictionRuntime",
    "TargetGuard",
    "create_prediction_runtime",
    "prediction_outcome_view",
]


def __getattr__(name):
    # Fixed lazy imports avoid bootstrapping runtime from the shared operation
    # vocabulary import; this is not an extensible authority/handler registry.
    if name in ("PredictionRuntime", "create_prediction_runtime"):
        from .runtime import PredictionRuntime, create_prediction_runtime

        return {
            "PredictionRuntime": PredictionRuntime,
            "create_prediction_runtime": create_prediction_runtime,
        }[name]
    if name in ("PredictionOutcomeCognitiveView", "prediction_outcome_view"):
        from .adapters import PredictionOutcomeCognitiveView, prediction_outcome_view

        return {
            "PredictionOutcomeCognitiveView": PredictionOutcomeCognitiveView,
            "prediction_outcome_view": prediction_outcome_view,
        }[name]
    raise AttributeError(name)
