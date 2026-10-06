"""Fixed inference/constraint catalogue; no runtime registration API."""

from dataclasses import dataclass
from enum import Enum

from ..contracts import ConstraintFamily, InferenceFamily
from ..identity import CanonicalDescriptor
from ..policy import ValueLimits
from ..serialization import canonical_identity_bytes
from .fab import d


class ReasoningOperation(Enum):
    SEED = "REASONING_SEED"
    DISCOVER = "REASONING_DISCOVER"
    EVALUATE = "REASONING_EVALUATE"
    PUBLISH = "REASONING_PUBLISH"


@dataclass(frozen=True, slots=True)
class ReasoningPolicy:
    max_assertions: int = 16
    max_sources: int = 32
    max_frontier: int = 16
    max_ancestry: int = 16
    max_checks: int = 128

    def canonical_descriptor(self):
        values = (
            self.max_assertions,
            self.max_sources,
            self.max_frontier,
            self.max_ancestry,
            self.max_checks,
        )
        if any(
            type(v) is not int or not 1 <= v <= cap
            for v, cap in zip(values, (16, 64, 32, 32, 256), strict=True)
        ):
            raise ValueError("finite reasoning policy required")
        return d("ReasoningPolicy", *values)

    def __post_init__(self):
        self.canonical_descriptor()

    @property
    def value_limits(self):
        return ValueLimits(3072, 48, 65536)


def schema(family):
    if family is InferenceFamily.GROUND_MODUS_PONENS:
        roles, formal = ("conditional", "antecedent"), "conditional"
    elif family is InferenceFamily.TRANSITIVE_COMPOSITION:
        roles, formal = (
            ("transitivity_property", "left_relation", "right_relation"),
            "transitivity_property",
        )
    else:
        raise TypeError("unknown executable inference schema")
    return d(
        "InferenceSchema",
        family,
        roles,
        formal,
        ("FORMAL_GIVEN", "FORMAL_ASSUMPTION"),
        tuple(ConstraintFamily),
    )


def catalogue(policy):
    if type(policy) is not ReasoningPolicy:
        raise TypeError("trusted reasoning policy required")
    return d(
        "ReasoningCatalogue",
        policy.canonical_descriptor(),
        tuple(schema(f) for f in InferenceFamily),
        tuple(ConstraintFamily),
        tuple(op.value for op in ReasoningOperation),
    )


def require_schema(value):
    if type(value) is not CanonicalDescriptor:
        raise TypeError("closed schema identity required")
    for family in InferenceFamily:
        if canonical_identity_bytes(value) == canonical_identity_bytes(schema(family)):
            return family
    raise ValueError("caller data cannot register a schema")
