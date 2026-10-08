"""Causal results remain literal, scoped, modal data, never generic CAUSES."""

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
from ..types import AssertionBasis, DependencyKind
from .contracts import d, fields
from .results import CausalResultView, result_from_data


def dependency(result):
    return DependencyRootIdentity(
        DependencyKind.CAUSAL_RESULT,
        d("CausalAdapter", result.domain),
        d(
            "CausalResultDependency",
            canonical_identity_bytes(semantic_identity(result)),
        ),
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
    identity = semantic_identity(view.result)
    ask = AssertionSemanticKey(
        ground("CausalResultStatement", identity),
        AssertionBasis.CAUSAL_RESULT_VIEW,
        view.result.scope,
        (view.causal_dependency_root,),
    )
    source = SourceAssertionKey(
        "CAUSAL_RESULT_VIEW",
        view.causal_dependency_root.origin_authority_binding,
        d("CausalResultOccurrence", canonical_identity_bytes(identity)),
    )
    return d("IngressAssertionView", ask, source)


def semantic_identity(result):
    """Lossless domain-specific factoring, never a digest or a CIE identity.

    The CRCI already carries the pair/domain/measurement. Only EXACT equal
    redundant fields use typed roles. Noncanonical historical data retains
    its complete fields instead; no source distinctions are discarded.
    """
    data = result.canonical_descriptor()
    if result.result_class not in (
        "REPLAY_IDENTIFIED_TREATMENT_EFFECT",
        "NO_PRESPECIFIED_OUTCOME_DISCRIMINATION",
    ):
        return d("CausalResultSemanticIdentity", data)
    crci = result.contrast
    domain, _origin, pair, basis = crci.values
    expected_scope = ScopeIdentity(
        "CLOSED_REPLAY", domain, d("ClosedReplayScope", canonical_identity_bytes(crci))
    )
    measurement = (
        basis.values[6]
        if type(basis) is CanonicalDescriptor
        and basis.kind == "IdentificationBasisIdentity"
        and len(basis.values) == 7
        else None
    )
    return d(
        "CausalReplaySemanticIdentity",
        result.result_class,
        d("ExactReplayContrastIdentity", canonical_identity_bytes(crci)),
        tuple(outcome for _, outcome in result.treatment_outcome_map),
        result.outcome_relation,
        d("CRCIDomain")
        if result.domain == domain
        else d("ExplicitCausalDomain", result.domain),
        d("CRCIScope")
        if result.scope == expected_scope
        else d("ExplicitCausalScope", result.scope),
        d("CRCIMeasurement")
        if result.measurement == measurement
        else d("ExplicitCausalMeasurement", result.measurement),
        d("CRCIPair")
        if result.treatment_pair == pair
        else d("ExplicitCausalPair", result.treatment_pair),
    )


def validate_semantic_identity(identity):
    if type(identity) is not CanonicalDescriptor:
        raise TypeError("closed causal semantic identity required")
    if type(identity.kind) is not str or type(identity.values) is not tuple:
        raise TypeError("closed causal semantic envelope required")
    if identity.kind == "CausalResultSemanticIdentity":
        (data,) = fields(identity, "CausalResultSemanticIdentity", 1)
        canonical_identity_bytes(identity)
        result = result_from_data(data)
    else:
        cls, crci, outcomes, relation, domain, scope, measurement, pair = fields(
            identity, "CausalReplaySemanticIdentity", 8
        )
        # Reject unknown nested members within the shared finite traversal
        # envelope before outcome equality or role comparisons inspect them.
        canonical_identity_bytes(identity)
        (image,) = fields(crci, "ExactReplayContrastIdentity", 1)
        if type(image) is not bytes or not 0 < len(image) <= 65536:
            raise ValueError("exact bounded typed CRCI identity required")
        if type(outcomes) is not tuple or len(outcomes) != 2:
            raise ValueError("complete two-role outcomes required")
        if (
            type(cls) is not str
            or cls
            not in (
                "REPLAY_IDENTIFIED_TREATMENT_EFFECT",
                "NO_PRESPECIFIED_OUTCOME_DISCRIMINATION",
            )
            or type(relation) is not str
            or relation not in ("SAME", "DIFFERENT")
            or (outcomes[0] == outcomes[1]) != (relation == "SAME")
            or (cls == "NO_PRESPECIFIED_OUTCOME_DISCRIMINATION") != (relation == "SAME")
        ):
            raise ValueError("exact replay class/outcome distinction required")
        for value, role, explicit in (
            (domain, "CRCIDomain", "ExplicitCausalDomain"),
            (scope, "CRCIScope", "ExplicitCausalScope"),
            (measurement, "CRCIMeasurement", "ExplicitCausalMeasurement"),
            (pair, "CRCIPair", "ExplicitCausalPair"),
        ):
            if (
                type(value) is not CanonicalDescriptor
                or type(value.kind) is not str
                or type(value.values) is not tuple
            ):
                raise TypeError("closed causal semantic role required")
            if value != d(role):
                (field,) = fields(value, explicit, 1)
                if role == "CRCIScope" and type(field) is not ScopeIdentity:
                    raise TypeError("exact explicit causal scope required")
                if role == "CRCIPair":
                    fields(field, "CanonicalTreatmentPair", 2)
        # Exact source-identity image, not a view blob or decoder/authority API.
        # Source-link validation resolves the COMPLETE CRCI in the modal Arena
        # entry and compares its generated structural semantic identity.
        canonical_identity_bytes(identity)
        return None
    if semantic_identity(result) != identity:
        raise ValueError("noncanonical causal semantic factoring")
    return result


def causal_reasoning_claim(view):
    return reasoning_view(view).values[0].content
