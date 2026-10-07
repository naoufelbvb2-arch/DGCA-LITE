"""Self-contained immutable historical commitments, never live FDA."""

from dataclasses import dataclass

from ..identity import CanonicalDescriptor, CoreStateBinding, ScopeIdentity
from ..serialization import canonical_identity_bytes
from .targets import TargetGuard, d, target_from_data


@dataclass(frozen=True, slots=True)
class ForecastCommitmentView:
    origin_core: CoreStateBinding
    origin_provenance: CanonicalDescriptor
    target: CanonicalDescriptor
    target_guard: CanonicalDescriptor
    horizon: int
    scope: ScopeIdentity
    prediction_policy: CanonicalDescriptor
    observation_policy: CanonicalDescriptor
    boundary_policy: CanonicalDescriptor
    future_evaluation_binding: CanonicalDescriptor
    escrow_identity: CanonicalDescriptor

    @property
    def identity(self):
        return d("ForecastCommitmentID", self.canonical_descriptor())

    def canonical_descriptor(self):
        target_from_data(self.target)
        if type(self.target_guard) is not CanonicalDescriptor:
            raise TypeError("exact target guard required")
        if (
            self.target_guard.kind != "TargetGuard"
            or type(self.target_guard.values) is not tuple
            or len(self.target_guard.values) != 2
        ):
            raise ValueError("closed guard shape")
        TargetGuard(*self.target_guard.values)
        if self.target_guard.values[0] != self.target:
            raise ValueError("target guard does not bind target")
        if type(self.horizon) is not int or not 1 <= self.horizon <= 64:
            raise ValueError("exact positive bounded horizon required")
        if (
            type(self.origin_core) is not CoreStateBinding
            or type(self.scope) is not ScopeIdentity
        ):
            raise TypeError("closed origin/scope required")
        fields = (
            self.origin_provenance,
            self.prediction_policy,
            self.observation_policy,
            self.boundary_policy,
            self.future_evaluation_binding,
            self.escrow_identity,
        )
        if any(type(f) is not CanonicalDescriptor for f in fields):
            raise TypeError("closed commitment bindings required")
        return d(
            "ForecastCommitment",
            self.origin_core,
            self.origin_provenance,
            self.target,
            self.target_guard,
            self.horizon,
            self.scope,
            *fields[1:],
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


ForecastCommitment = ForecastCommitmentView
