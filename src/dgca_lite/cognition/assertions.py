"""Capability-free ingress outputs, not operational authority or executable rules.

These historical data views may be copied/reconstructed. Their labels do not
authorize ingress, CIE admission, inference, or constraint evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass

from .identity import (
    AssertionSemanticKey,
    CanonicalDescriptor,
    ClaimContentID,
    DependencyRootIdentity,
    ScopeIdentity,
    SourceAssertionKey,
    canonical_dependencies,
)
from .serialization import canonical_identity_bytes
from .types import AssertionBasis, DependencyKind


@dataclass(frozen=True, slots=True)
class IngressAssertionView:
    semantic_key: AssertionSemanticKey
    source_key: SourceAssertionKey

    def canonical_descriptor(self) -> CanonicalDescriptor:
        if (
            type(self.semantic_key) is not AssertionSemanticKey
            or type(self.source_key) is not SourceAssertionKey
        ):
            raise TypeError("invalid assertion/source identity")
        descriptor = CanonicalDescriptor(
            "IngressAssertionView", (self.semantic_key, self.source_key)
        )
        # The complete descriptor validates bounds/types before root inspection.
        if self.semantic_key.basis is AssertionBasis.FORMAL_ASSUMPTION and not any(
            root.kind is DependencyKind.ASSUMPTION
            for root in self.semantic_key.dependencies
        ):
            raise ValueError("formal assumption requires its assumption dependency")
        return descriptor

    def __post_init__(self) -> None:
        canonical_identity_bytes(self.canonical_descriptor())


def validate_ground_referent(node: CanonicalDescriptor, role: str) -> None:
    """Closed typed referent shape shared by formal ingress and FAB closure."""
    if (
        type(node) is not CanonicalDescriptor
        or type(node.kind) is not str
        or node.kind != role
        or type(node.values) is not tuple
        or len(node.values) != 1
    ):
        raise TypeError("closed typed ground referent required")
    value = node.values[0]
    if not (
        (type(value) is str and 0 < len(value) <= 256)
        or (type(value) is int and 0 <= value < 2**63)
    ):
        raise ValueError("invalid bounded referent identity")


def validate_constraint_content(content: ClaimContentID) -> None:
    """Validate the three Section-70 premise shapes; execute no constraint."""
    if (
        type(content) is not ClaimContentID
        or type(content.descriptor) is not CanonicalDescriptor
    ):
        raise TypeError("invalid constraint content identity")
    node = content.descriptor
    if type(node.kind) is not str or type(node.values) is not tuple:
        raise TypeError("invalid constraint premise shape")
    if node.kind == "FormalNegation":
        arity, member_type = 1, ClaimContentID
    elif node.kind == "MutuallyExclusive":
        arity, member_type = 2, CanonicalDescriptor
    elif node.kind == "SingleValued":
        arity, member_type = 1, CanonicalDescriptor
    else:
        raise TypeError("unknown constraint premise family")
    # The closed shape's own outer bound precedes even member type inspection.
    if len(node.values) != arity:
        raise ValueError("invalid constraint premise arity")
    if any(type(member) is not member_type for member in node.values):
        raise TypeError("invalid constraint premise referent type")
    if node.kind == "MutuallyExclusive":
        for member in node.values:
            validate_ground_referent(member, "state")
    canonical_identity_bytes(content)
    if node.kind == "MutuallyExclusive" and node.values[0] == node.values[1]:
        raise ValueError("self-exclusion is not a lawful constraint premise")


@dataclass(frozen=True, slots=True)
class ActiveConstraintPremiseView:
    content: ClaimContentID
    basis: AssertionBasis
    scope: ScopeIdentity
    dependencies: tuple[DependencyRootIdentity, ...]
    source_authority: CanonicalDescriptor
    occurrence: CanonicalDescriptor

    @property
    def semantic_key(self) -> CanonicalDescriptor:
        validate_constraint_content(self.content)
        if (
            self.basis is not AssertionBasis.FORMAL_GIVEN
            and self.basis is not AssertionBasis.FORMAL_ASSUMPTION
        ):
            raise TypeError("constraint activation requires an authorized formal basis")
        if (
            type(self.scope) is not ScopeIdentity
            or type(self.source_authority) is not CanonicalDescriptor
            or type(self.occurrence) is not CanonicalDescriptor
        ):
            raise TypeError("invalid constraint scope/provenance type")
        roots = canonical_dependencies(self.dependencies)
        if roots != self.dependencies:
            raise ValueError("noncanonical constraint dependencies")
        if self.basis is AssertionBasis.FORMAL_ASSUMPTION and not any(
            root.kind is DependencyKind.ASSUMPTION for root in roots
        ):
            raise ValueError("assumed constraint requires its assumption dependency")
        return CanonicalDescriptor(
            "ConstraintSemanticKey", (self.content, self.basis, self.scope, roots)
        )

    @property
    def source_key(self) -> CanonicalDescriptor:
        _ = self.semantic_key
        return CanonicalDescriptor(
            "ConstraintSourceKey",
            (self.source_authority, self.occurrence, self.content, self.scope),
        )

    def canonical_descriptor(self) -> CanonicalDescriptor:
        return CanonicalDescriptor(
            "ActiveConstraintPremiseView", (self.semantic_key, self.source_key)
        )

    def __post_init__(self) -> None:
        canonical_identity_bytes(self.canonical_descriptor())
