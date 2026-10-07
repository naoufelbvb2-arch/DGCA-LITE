"""Immutable prospective plans. No runtime authority resides in these values."""

from dataclasses import dataclass, field

from ..authority import _OpaqueHandle
from ..serialization import canonical_identity_bytes
from .contracts import CausalityPolicy, closed, d, fields, integer, ordered, outer
from .intervention import TreatmentDescriptor, treatment_from_data, treatment_pair
from .measurement import (
    ExactOutcomeClassification,
    OutcomeSpec,
    classifier_from_data,
    spec_from_data,
)
from .replay import ReplayEnvironmentBinding, ReplayOrigin


class CausalStudyAuthority(_OpaqueHandle):
    __slots__ = ()


@dataclass(frozen=True, slots=True)
class CausalHypothesis:
    claim: object
    provenance: tuple = ()

    def canonical_descriptor(self):
        outer(self.provenance, 32)
        return d("CausalHypothesis", closed(self.claim), ordered(self.provenance, 32))

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


@dataclass(frozen=True, slots=True)
class CaseSlot:
    condition: object
    treatment: TreatmentDescriptor | None = None
    attempts: int = 1

    def __post_init__(self):
        integer(self.attempts, 4, 1)
        if (
            self.treatment is not None
            and type(self.treatment) is not TreatmentDescriptor
        ):
            raise TypeError("exact optional treatment required")
        object.__setattr__(self, "condition", closed(self.condition))

    def canonical_descriptor(self):
        self.__post_init__()
        return d(
            "CaseSlot",
            self.condition,
            None if self.treatment is None else self.treatment.canonical_descriptor(),
            self.attempts,
        )


@dataclass(frozen=True, slots=True)
class Comparison:
    left: int
    right: int
    independent: bool = True
    requires_resolved: bool = True

    def canonical_descriptor(self):
        integer(self.left, 15)
        integer(self.right, 15)
        if (
            self.left == self.right
            or type(self.independent) is not bool
            or type(self.requires_resolved) is not bool
        ):
            raise ValueError("distinct role-bound comparator slots required")
        return d(
            "Comparison",
            self.left,
            self.right,
            self.independent,
            self.requires_resolved,
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


@dataclass(frozen=True, slots=True)
class CausalStudyPlan:
    query: str
    domain: ReplayEnvironmentBinding
    condition_axis: tuple
    outcome_spec: OutcomeSpec
    slots: tuple
    comparisons: tuple
    execute_slots: tuple
    matching: ExactOutcomeClassification
    protocol: object
    policy: CausalityPolicy = field(default_factory=CausalityPolicy)
    origin: ReplayOrigin | None = None
    repetitions: int = 1
    randomization_required: bool = False

    def __post_init__(self):
        # Even malformed members of an oversized plan are never traversed.
        outer(self.slots, 16)
        outer(self.comparisons, 16)
        outer(self.execute_slots, 16)
        outer(self.condition_axis, 32)
        if type(self.policy) is not CausalityPolicy:
            raise TypeError("frozen Causality policy required")
        self.policy.__post_init__()
        outer(self.slots, self.policy.max_slots)
        outer(self.comparisons, self.policy.max_comparisons)
        if type(self.query) is not str or self.query not in (
            "OBSERVATIONAL",
            "INTERVENTIONAL",
            "CLOSED_REPLAY",
        ):
            raise ValueError("closed v0 study class required")
        if (
            type(self.domain) is not ReplayEnvironmentBinding
            or type(self.outcome_spec) is not OutcomeSpec
            or type(self.matching) is not ExactOutcomeClassification
        ):
            raise TypeError("complete frozen plan bindings required")
        if not self.slots or not self.comparisons:
            raise ValueError("prospective contrast required")
        if any(type(v) is not CaseSlot for v in self.slots) or any(
            type(v) is not Comparison for v in self.comparisons
        ):
            raise TypeError("closed case/contrast plan required")
        object.__setattr__(
            self, "condition_axis", ordered(self.condition_axis, 32, nonempty=True)
        )
        for slot in self.slots:
            slot.__post_init__()
            if slot.condition not in self.condition_axis:
                raise ValueError("slot outside frozen condition axis")
            if self.query != "OBSERVATIONAL" and slot.treatment is None:
                raise ValueError("intervention requires explicit treatment")
        if any(
            type(i) is not int or not 0 <= i < len(self.slots)
            for i in self.execute_slots
        ) or self.execute_slots != tuple(sorted(set(self.execute_slots))):
            raise ValueError("frozen outcome-independent slot schedule required")
        keys = tuple(
            canonical_identity_bytes(v.canonical_descriptor()) for v in self.comparisons
        )
        if keys != tuple(sorted(set(keys))):
            raise ValueError("canonical unique complete comparator plan required")
        for pair in self.comparisons:
            if max(pair.left, pair.right) >= len(self.slots):
                raise ValueError("unplanned comparison slot")
            if self.query != "OBSERVATIONAL":
                treatment_pair(
                    self.slots[pair.left].treatment, self.slots[pair.right].treatment
                )
        self.matching.__post_init__()
        for value in (
            self.matching.expected_outcome,
        ) + self.matching.explicit_conflict_outcomes:
            if not self.outcome_spec.permits(value):
                raise ValueError("classifier outside frozen OutcomeSpec")
        integer(self.repetitions, self.policy.max_repetitions, 1)
        if type(self.randomization_required) is not bool:
            raise TypeError("frozen protocol requirement required")
        object.__setattr__(self, "protocol", closed(self.protocol))
        if self.query == "CLOSED_REPLAY":
            if type(self.origin) is not ReplayOrigin or self.execute_slots != tuple(
                range(len(self.slots))
            ):
                raise ValueError("complete origin/branch schedule required")
        elif self.origin is not None or self.repetitions != 1:
            raise ValueError("replay fields cannot strengthen nonidentified study")
        from .contracts import work_frontier

        work_frontier(self)

    def canonical_descriptor(self):
        from .contracts import work_frontier

        self.__post_init__()

        return d(
            "CausalStudyPlan",
            self.query,
            self.domain.canonical_descriptor(),
            self.condition_axis,
            self.outcome_spec.canonical_descriptor(),
            tuple(v.canonical_descriptor() for v in self.slots),
            tuple(v.canonical_descriptor() for v in self.comparisons),
            d("StoppingRule", self.execute_slots),
            self.matching.canonical_descriptor(),
            d("CausalStudyResourceEnvelope", work_frontier(self)),
            self.protocol,
            self.policy.canonical_descriptor(),
            None if self.origin is None else self.origin.canonical_descriptor(),
            self.repetitions,
            self.randomization_required,
        )

    @property
    def identity(self):
        return d(
            "CausalStudyPlanIdentity",
            canonical_identity_bytes(self.canonical_descriptor()),
        )


def plan_from_data(data):
    (
        query,
        domain,
        axis,
        spec,
        slots,
        comparisons,
        stop,
        matching,
        _envelope,
        protocol,
        policy,
        origin,
        repetitions,
        randomized,
    ) = fields(data, "CausalStudyPlan", 14)
    outer(slots, 16)
    outer(comparisons, 16)
    outer(fields(stop, "StoppingRule", 1)[0], 16)
    slot_fields = tuple(fields(v, "CaseSlot", 3) for v in slots)
    copied = CausalStudyPlan(
        query,
        ReplayEnvironmentBinding(*fields(domain, "ReplayEnvironmentBinding", 3)),
        axis,
        spec_from_data(spec),
        tuple(
            CaseSlot(
                condition,
                None if treatment is None else treatment_from_data(treatment),
                attempts,
            )
            for condition, treatment, attempts in slot_fields
        ),
        tuple(Comparison(*fields(v, "Comparison", 4)) for v in comparisons),
        stop.values[0],
        classifier_from_data(matching),
        protocol,
        CausalityPolicy(*fields(policy, "CausalityPolicy", 7)),
        None if origin is None else ReplayOrigin(*fields(origin, "ReplayOrigin", 3)),
        repetitions,
        randomized,
    )
    if copied.canonical_descriptor() != data:
        raise ValueError("noncanonical prospective plan/envelope")
    return copied
