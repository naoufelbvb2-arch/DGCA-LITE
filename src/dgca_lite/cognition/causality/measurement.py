"""Frozen exact-outcome classifier. Inequality is never contrary authority."""

from dataclasses import dataclass

from ..serialization import canonical_identity_bytes
from .contracts import closed, d, fields, integer, ordered


@dataclass(frozen=True, slots=True)
class OutcomeSpec:
    lawful_outcomes: tuple

    def __post_init__(self):
        object.__setattr__(
            self, "lawful_outcomes", ordered(self.lawful_outcomes, 32, nonempty=True)
        )

    def canonical_descriptor(self):
        self.__post_init__()
        return d("OutcomeSpec", self.lawful_outcomes)

    def permits(self, value):
        self.__post_init__()
        value = closed(value)
        image = canonical_identity_bytes(value)
        return any(image == canonical_identity_bytes(v) for v in self.lawful_outcomes)


@dataclass(frozen=True, slots=True)
class ExactOutcomeClassification:
    expected_outcome: object
    explicit_conflict_outcomes: tuple = ()

    def __post_init__(self):
        conflicts = ordered(self.explicit_conflict_outcomes, 32)
        expected = closed(self.expected_outcome)
        if any(expected == v for v in conflicts):
            raise ValueError("expected outcome overlaps explicit conflict set")
        object.__setattr__(self, "expected_outcome", expected)
        object.__setattr__(self, "explicit_conflict_outcomes", conflicts)

    def canonical_descriptor(self):
        self.__post_init__()
        return d(
            "ExactOutcomeClassification",
            self.expected_outcome,
            self.explicit_conflict_outcomes,
        )

    def classify(self, outcome, spec, *, measurement_status="MEASURED"):
        self.__post_init__()
        if type(spec) is not OutcomeSpec:
            raise TypeError("frozen OutcomeSpec required")
        if (
            measurement_status
            not in (
                "MEASURED",
                "MISSING",
                "FAILED",
                "INVALID",
                "UNAVAILABLE",
                "INCOMPLETE",
            )
            or type(measurement_status) is not str
        ):
            raise ValueError("closed measurement status required")
        if measurement_status != "MEASURED":
            if outcome is not None:
                raise ValueError("unsuccessful measurement supplies no outcome")
            return "UNRESOLVED"
        if not spec.permits(outcome):
            raise ValueError("outcome outside frozen OutcomeSpec")
        image = canonical_identity_bytes(outcome)
        if image == canonical_identity_bytes(self.expected_outcome):
            return "MATCH"
        if any(
            image == canonical_identity_bytes(v)
            for v in self.explicit_conflict_outcomes
        ):
            return "CONFLICT"
        return "UNRESOLVED"


@dataclass(frozen=True, slots=True)
class MeasurementContract:
    target: object
    logical_slot: int
    outcome_spec: OutcomeSpec
    treatment_label_blind: bool = True

    def __post_init__(self):
        if (
            type(self.outcome_spec) is not OutcomeSpec
            or type(self.treatment_label_blind) is not bool
        ):
            raise TypeError("closed measurement contract required")
        object.__setattr__(self, "target", closed(self.target))
        integer(self.logical_slot)
        canonical_identity_bytes(self.canonical_descriptor())

    def canonical_descriptor(self):
        return d(
            "MeasurementContract",
            self.target,
            self.logical_slot,
            self.outcome_spec.canonical_descriptor(),
            self.treatment_label_blind,
        )


def spec_from_data(data):
    return OutcomeSpec(*fields(data, "OutcomeSpec", 1))


def classifier_from_data(data):
    return ExactOutcomeClassification(*fields(data, "ExactOutcomeClassification", 2))


def measurement_from_data(data):
    target, time, spec, blind = fields(data, "MeasurementContract", 4)
    return MeasurementContract(target, time, spec_from_data(spec), blind)
