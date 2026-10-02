"""DGCA LITE Layer 3 bounded cognition.

The initial foundation exposes authority-free values only. Constructing a
descriptor never issues invocation, formal, observation, or execution authority.
"""

from .identity import (
    AssertionSemanticKey,
    CanonicalDescriptor,
    ClaimContentID,
    DependencyRootIdentity,
    ScopeIdentity,
    SourceAssertionKey,
)
from .policy import ValueLimits
from .serialization import canonical_identity_bytes, identity_digest
from .types import AssertionBasis, DependencyKind

__all__ = [
    "AssertionBasis",
    "AssertionSemanticKey",
    "CanonicalDescriptor",
    "ClaimContentID",
    "DependencyKind",
    "DependencyRootIdentity",
    "ScopeIdentity",
    "SourceAssertionKey",
    "ValueLimits",
    "canonical_identity_bytes",
    "identity_digest",
]
