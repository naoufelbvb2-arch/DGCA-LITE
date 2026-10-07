"""Closed replay data and opaque exact-RCE authority; no physical executor."""

from dataclasses import dataclass

from ..authority import _OpaqueHandle
from ..serialization import canonical_identity_bytes
from .contracts import closed, d, fields, integer, outer
from .intervention import TreatmentDescriptor, treatment_from_data
from .measurement import MeasurementContract, measurement_from_data


class ReplayComparisonEpoch(_OpaqueHandle):
    __slots__ = ()


class ReplayOriginAuthority(_OpaqueHandle):
    __slots__ = ()


class BranchExecutionReceipt(_OpaqueHandle):
    __slots__ = ()


class MeasurementReceipt(_OpaqueHandle):
    __slots__ = ()


@dataclass(frozen=True, slots=True)
class ReplayEnvironmentBinding:
    domain_runtime: object
    environment: object
    revision: int

    def canonical_descriptor(self):
        integer(self.revision, 2**63 - 1)
        return d(
            "ReplayEnvironmentBinding",
            closed(self.domain_runtime),
            closed(self.environment),
            self.revision,
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


@dataclass(frozen=True, slots=True)
class ClosedReplayDomainContract:
    relevant_state: object
    exogenous_schedule: tuple
    horizon: int
    treatments: tuple
    branch_isolation: object
    execution_bound: int
    measurement: MeasurementContract
    determinism_property: object

    def __post_init__(self):
        # All container outer bounds precede any member inspection.
        outer(self.exogenous_schedule, 65)
        outer(self.treatments, 16)
        integer(self.horizon, 64, 1)
        integer(self.execution_bound, 4096, 1)
        if (
            type(self.measurement) is not MeasurementContract
            or self.measurement.logical_slot > self.horizon
        ):
            raise ValueError("measurement must lie in frozen logical horizon")
        if len(self.exogenous_schedule) != self.horizon + 1:
            raise ValueError("complete exact logical exogenous schedule required")
        for row in self.exogenous_schedule:
            if type(row) is not tuple or len(row) != 2:
                raise ValueError("schedule row outer bound")
        schedule = tuple((integer(t), closed(v)) for t, v in self.exogenous_schedule)
        if tuple(t for t, _ in schedule) != tuple(range(self.horizon + 1)):
            raise ValueError("exact logical schedule order required")
        if not self.treatments or any(
            type(v) is not TreatmentDescriptor for v in self.treatments
        ):
            raise TypeError("closed treatment semantics required")
        treatment_keys = tuple(
            canonical_identity_bytes(t.canonical_descriptor()) for t in self.treatments
        )
        if treatment_keys != tuple(sorted(set(treatment_keys))):
            raise ValueError("canonical unique treatment semantics required")
        for name in ("relevant_state", "branch_isolation", "determinism_property"):
            object.__setattr__(self, name, closed(getattr(self, name)))
        object.__setattr__(self, "exogenous_schedule", schedule)
        canonical_identity_bytes(self.canonical_descriptor())

    def canonical_descriptor(self):
        return d(
            "ClosedReplayDomainContract",
            self.relevant_state,
            self.exogenous_schedule,
            d("LogicalTimeContract", self.horizon),
            tuple(t.canonical_descriptor() for t in self.treatments),
            self.branch_isolation,
            self.execution_bound,
            self.measurement.canonical_descriptor(),
            self.determinism_property,
        )


@dataclass(frozen=True, slots=True)
class ReplayOrigin:
    domain_runtime: object
    occurrence_index: int
    state: object

    def canonical_descriptor(self):
        integer(self.occurrence_index, 2**63 - 1)
        return d(
            "ReplayOrigin",
            closed(self.domain_runtime),
            self.occurrence_index,
            closed(self.state),
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


def identification_basis(contract, environment):
    if (
        type(contract) is not ClosedReplayDomainContract
        or type(environment) is not ReplayEnvironmentBinding
    ):
        raise TypeError("complete identification basis required")
    data = contract.canonical_descriptor()
    # Complete typed bytes are references, NOT hashes; avoid repeated proof graphs.
    return d(
        "IdentificationBasisIdentity",
        canonical_identity_bytes(data),
        environment.canonical_descriptor(),
        data.values[2],
        data.values[4],
        data.values[5],
        d("ExogenousBinding", data.values[1]),
        data.values[6],
    )


def contrast_identity(domain, origin, pair, basis):
    if type(origin) is not ReplayOrigin:
        raise TypeError("exact immutable origin required")
    return d(
        "CanonicalReplayContrastIdentity",
        closed(domain),
        origin.canonical_descriptor(),
        closed(pair),
        closed(basis),
    )


@dataclass(frozen=True, slots=True)
class ReplayExecutionBundle:
    rce_binding: object
    receipts: tuple

    def canonical_descriptor(self):
        outer(self.receipts, 10)
        return d(
            "ReplayExecutionBundle",
            closed(self.rce_binding),
            tuple(closed(v) for v in self.receipts),
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


def replay_contract_from_data(data):
    state, schedule, time, treatments, isolation, bound, measurement, deterministic = (
        fields(data, "ClosedReplayDomainContract", 8)
    )
    outer(schedule, 65)
    outer(treatments, 16)
    return ClosedReplayDomainContract(
        state,
        schedule,
        *fields(time, "LogicalTimeContract", 1),
        tuple(treatment_from_data(t) for t in treatments),
        isolation,
        bound,
        measurement_from_data(measurement),
        deterministic,
    )
