"""Prediction data stays modal. This adapter never issues live authority."""

from dataclasses import dataclass

from ..identity import (
    AssertionSemanticKey,
    CanonicalDescriptor,
    DependencyRootIdentity,
    ScopeIdentity,
    SourceAssertionKey,
)
from ..ingress import _snapshot
from ..reasoning.fab import ground
from ..serialization import canonical_identity_bytes
from ..types import AssertionBasis, DependencyKind, ForecastStatus
from .commitment import ForecastCommitmentView
from .observation import ForecastOutcomeView, FutureTrustedOccurrenceID
from .targets import d, target_from_data


def dependency(commitment):
    return DependencyRootIdentity(
        DependencyKind.PREDICTION,
        d("PredictionAdapter", commitment.origin_core.core_identity),
        d("PredictionResultDependency", canonical_identity_bytes(commitment.identity)),
    )


@dataclass(frozen=True, slots=True)
class PredictionOutcomeCognitiveView:
    commitment_identity: CanonicalDescriptor
    prediction_class: str
    target_descriptor: CanonicalDescriptor
    outcome_status: ForecastStatus
    prediction_scope_descriptor: ScopeIdentity
    future_observation_provenance_descriptor: CanonicalDescriptor | None
    prediction_dependency_root: DependencyRootIdentity

    def canonical_descriptor(self):
        identity = self.commitment_identity
        if (
            type(identity) is not CanonicalDescriptor
            or identity.kind != "ForecastCommitmentID"
            or type(identity.values) is not tuple
            or len(identity.values) != 1
        ):
            raise ValueError("closed commitment identity required")
        data = identity.values[0]
        if (
            type(data) is not CanonicalDescriptor
            or data.kind != "ForecastCommitment"
            or type(data.values) is not tuple
            or len(data.values) != 11
        ):
            raise ValueError("closed commitment identity payload required")
        commitment = ForecastCommitmentView(*data.values)
        target_from_data(self.target_descriptor)
        if (
            type(self.prediction_class) is not str
            or self.prediction_class != "ROOT_ANCHORED_FORECAST"
            or type(self.outcome_status) is not ForecastStatus
            or self.target_descriptor != commitment.target
            or type(self.prediction_scope_descriptor) is not ScopeIdentity
            or self.prediction_scope_descriptor != commitment.scope
            or type(self.prediction_dependency_root) is not DependencyRootIdentity
            or self.prediction_dependency_root != dependency(commitment)
        ):
            raise ValueError(
                "prediction view cannot strengthen/relabel source semantics"
            )
        future = self.future_observation_provenance_descriptor
        if future is not None:
            if (
                type(future) is not CanonicalDescriptor
                or future.kind != "FutureTrustedOccurrenceID"
                or type(future.values) is not tuple
                or len(future.values) != 2
            ):
                raise ValueError("closed future observation provenance required")
            FutureTrustedOccurrenceID(*future.values)
            if future.values[0] != commitment.origin_core.core_identity:
                raise ValueError("cross-Core provenance")
        return d(
            "PredictionOutcomeCognitiveView",
            identity,
            self.prediction_class,
            self.target_descriptor,
            self.outcome_status,
            self.prediction_scope_descriptor,
            future,
            self.prediction_dependency_root,
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


def prediction_outcome_view(outcome):
    if type(outcome) is not ForecastOutcomeView:
        raise TypeError("typed prediction outcome required; no generic decoder")
    # The complete closed result is validated before copying fields.
    data = _snapshot(outcome.canonical_descriptor())
    commitment = ForecastCommitmentView(*data.values[0].values)
    return PredictionOutcomeCognitiveView(
        commitment.identity,
        "ROOT_ANCHORED_FORECAST",
        commitment.target,
        data.values[1],
        commitment.scope,
        data.values[2][-1].values[1] if data.values[2] else None,
        dependency(commitment),
    )


def reasoning_view(view):
    """Literal readonly statement, never a formal AST/proposition decoder.

    The byte payload is the COMPLETE canonical typed view, not a hash. Generic
    schemas do not inspect it, and its mandatory modal dependency is retained.
    Copies remain data and cannot grant trusted/formal/operational authority.
    """
    if type(view) is not PredictionOutcomeCognitiveView:
        raise TypeError("typed capability-free prediction view required")
    image = canonical_identity_bytes(view.canonical_descriptor())
    ask = AssertionSemanticKey(
        ground("PredictionOutcomeStatement", image),
        AssertionBasis.PREDICTION_VIEW,
        view.prediction_scope_descriptor,
        (view.prediction_dependency_root,),
    )
    source = SourceAssertionKey(
        "PREDICTION_VIEW",
        view.prediction_dependency_root.origin_authority_binding,
        d("PredictionResultOccurrence", image),
    )
    return d("IngressAssertionView", ask, source)
