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
            or type(identity.kind) is not str
            or identity.kind != "ForecastCommitmentID"
            or type(identity.values) is not tuple
            or len(identity.values) != 1
        ):
            raise ValueError("closed commitment identity required")
        data = identity.values[0]
        if (
            type(data) is not CanonicalDescriptor
            or type(data.kind) is not str
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
                or type(future.kind) is not str
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
    """Exact readonly semantic statement. This creates data, never authority."""
    if type(view) is not PredictionOutcomeCognitiveView:
        raise TypeError("typed capability-free prediction view required")
    view.canonical_descriptor()
    identity = semantic_identity(view)
    ask = AssertionSemanticKey(
        ground("PredictionOutcomeStatement", identity),
        AssertionBasis.PREDICTION_VIEW,
        view.prediction_scope_descriptor,
        (view.prediction_dependency_root,),
    )
    source = SourceAssertionKey(
        "PREDICTION_VIEW",
        view.prediction_dependency_root.origin_authority_binding,
        d("PredictionResultOccurrence", identity),
    )
    return d("IngressAssertionView", ask, source)


def semantic_identity(view):
    return d(
        "PredictionOutcomeSemanticIdentity",
        d(
            "ExactForecastCommitmentIdentity",
            canonical_identity_bytes(view.commitment_identity),
        ),
        view.prediction_class,
        view.outcome_status,
        view.future_observation_provenance_descriptor,
    )


def validate_semantic_identity(identity):
    if (
        type(identity) is not CanonicalDescriptor
        or type(identity.kind) is not str
        or identity.kind != "PredictionOutcomeSemanticIdentity"
        or type(identity.values) is not tuple
        or len(identity.values) != 4
    ):
        raise ValueError("closed prediction semantic identity required")
    # The finite closed encoder rejects opaque nested members before any
    # semantic comparison/constructor can invoke caller-defined hooks.
    canonical_identity_bytes(identity)
    commitment_id, prediction_class, status, future = identity.values
    if (
        type(commitment_id) is not CanonicalDescriptor
        or type(commitment_id.kind) is not str
        or commitment_id.kind != "ExactForecastCommitmentIdentity"
        or type(commitment_id.values) is not tuple
        or len(commitment_id.values) != 1
        or type(commitment_id.values[0]) is not bytes
        or not 0 < len(commitment_id.values[0]) <= 65536
        or type(prediction_class) is not str
        or prediction_class != "ROOT_ANCHORED_FORECAST"
        or type(status) is not ForecastStatus
    ):
        raise ValueError("closed exact forecast source identity required")
    if future is not None:
        if (
            type(future) is not CanonicalDescriptor
            or type(future.kind) is not str
            or future.kind != "FutureTrustedOccurrenceID"
            or type(future.values) is not tuple
            or len(future.values) != 2
        ):
            raise ValueError("closed future identity required")
        FutureTrustedOccurrenceID(*future.values)


def prediction_reasoning_claim(view):
    return reasoning_view(view).values[0].content
