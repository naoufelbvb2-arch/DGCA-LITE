"""Causal results remain literal, scoped, modal data, never generic CAUSES."""

from dataclasses import dataclass

from ..identity import AssertionSemanticKey, DependencyRootIdentity, SourceAssertionKey
from ..ingress import _snapshot
from ..reasoning.fab import ground
from ..serialization import canonical_identity_bytes
from ..types import AssertionBasis, DependencyKind
from .contracts import d, fields
from .results import CausalResultView, result_from_data


def dependency(result):
    return DependencyRootIdentity(
        DependencyKind.CAUSAL_RESULT,
        d("CausalAdapter", result.domain),
        d("CausalResultDependency", canonical_identity_bytes(result.identity)),
    )


@dataclass(frozen=True, slots=True)
class CausalResultCognitiveView:
    result_descriptor: object
    causal_dependency_root: DependencyRootIdentity

    def canonical_descriptor(self):
        result = result_from_data(self.result_descriptor)
        if type(
            self.causal_dependency_root
        ) is not DependencyRootIdentity or self.causal_dependency_root != dependency(
            result
        ):
            raise ValueError("mandatory exact causal dependency required")
        return d(
            "CausalResultCognitiveView",
            result.canonical_descriptor(),
            self.causal_dependency_root,
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())

    @property
    def result(self):
        return result_from_data(self.result_descriptor)

    @property
    def canonical_result_identity(self):
        return self.result.identity

    @property
    def result_class(self):
        return self.result.result_class

    @property
    def crci(self):
        result = self.result
        return (
            result.contrast
            if result.result_class
            in (
                "REPLAY_IDENTIFIED_TREATMENT_EFFECT",
                "NO_PRESPECIFIED_OUTCOME_DISCRIMINATION",
            )
            else None
        )

    @property
    def treatment_pair_descriptor(self):
        return self.result.treatment_pair

    @property
    def treatment_outcome_map(self):
        return self.result.treatment_outcome_map

    @property
    def outcome_relation(self):
        return self.result.outcome_relation

    @property
    def replay_scope_descriptor(self):
        return self.result.scope

    @property
    def domain_descriptor(self):
        return self.result.domain

    @property
    def measurement_contract_descriptor(self):
        return self.result.measurement


def causal_result_view(result):
    if type(result) is not CausalResultView:
        raise TypeError("valid typed narrow causal result required")
    copy = result_from_data(_snapshot(result.canonical_descriptor()))
    return CausalResultCognitiveView(copy.canonical_descriptor(), dependency(copy))


def reasoning_view(view):
    if type(view) is not CausalResultCognitiveView:
        raise TypeError("typed capability-free causal view required")
    fields(view.canonical_descriptor(), "CausalResultCognitiveView", 2)
    # The literal carries the result once. Its mandatory modal dependency is
    # already an exact separate ASK field, not duplicated inside the literal.
    image = canonical_identity_bytes(view.result.canonical_descriptor())
    ask = AssertionSemanticKey(
        ground("CausalResultStatement", image),
        AssertionBasis.CAUSAL_RESULT_VIEW,
        view.result.scope,
        (view.causal_dependency_root,),
    )
    source = SourceAssertionKey(
        "CAUSAL_RESULT_VIEW",
        view.causal_dependency_root.origin_authority_binding,
        d("CausalResultOccurrence", image),
    )
    return d("IngressAssertionView", ask, source)
