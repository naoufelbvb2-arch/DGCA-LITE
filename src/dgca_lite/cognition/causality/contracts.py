"""Closed v0 contracts and conservative prospective resource accounting."""

from dataclasses import dataclass
from enum import Enum

from ..identity import CanonicalDescriptor
from ..ingress import _snapshot
from ..serialization import canonical_identity_bytes


def d(kind, *values):
    return CanonicalDescriptor(kind, values)


def integer(value, maximum=64, minimum=0):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("bounded exact integer required")
    return value


def outer(values, maximum=64):
    if type(values) is not tuple or len(values) > maximum:
        raise ValueError("causal container outer bound")


def closed(value):
    if type(value) is not CanonicalDescriptor:
        raise TypeError("complete canonical typed descriptor required")
    image = canonical_identity_bytes(value)
    if len(image) > 262144:
        raise ValueError("causal descriptor byte bound")
    return _snapshot(value)


def fields(value, kind, count):
    if (
        type(value) is not CanonicalDescriptor
        or type(value.values) is not tuple
        or len(value.values) != count
        or type(value.kind) is not str
        or value.kind != kind
    ):
        raise ValueError("closed causal envelope required")
    return value.values


def ordered(values, maximum=64, *, nonempty=False):
    outer(values, maximum)
    if nonempty and not values:
        raise ValueError("nonempty prospective set required")
    copied = tuple(closed(v) for v in values)
    keys = tuple(canonical_identity_bytes(v) for v in copied)
    if keys != tuple(sorted(set(keys))):
        raise ValueError("canonical ordered unique typed set required")
    return copied


class CausalOperation(Enum):
    OPEN_STUDY = "CAUSAL_OPEN_STUDY"
    REQUEST_CASE = "CAUSAL_REQUEST_CASE"
    ADMIT_CASE = "CAUSAL_ADMIT_CASE"
    CLASSIFY_CASE = "CAUSAL_CLASSIFY_CASE"
    COMPARE_CASES = "CAUSAL_COMPARE_CASES"
    PUBLISH_STUDY = "CAUSAL_PUBLISH_STUDY"
    OPEN_RCE = "CAUSAL_OPEN_RCE_AND_REQUEST"
    ADMIT_BUNDLE = "CAUSAL_ADMIT_BUNDLE"
    COMPARE_REPLAY = "CAUSAL_COMPARE_REPLAY"
    PUBLISH_REPLAY = "CAUSAL_PUBLISH_REPLAY"


@dataclass(frozen=True, slots=True)
class CausalityPolicy:
    max_domains: int = 8
    max_studies: int = 16
    max_slots: int = 8
    max_comparisons: int = 8
    max_repetitions: int = 4
    max_horizon: int = 32
    max_contrasts: int = 64

    def __post_init__(self):
        for value, maximum in zip(
            self.values, (16, 64, 16, 16, 8, 64, 256), strict=True
        ):
            integer(value, maximum, 1)

    @property
    def values(self):
        return (
            self.max_domains,
            self.max_studies,
            self.max_slots,
            self.max_comparisons,
            self.max_repetitions,
            self.max_horizon,
            self.max_contrasts,
        )

    def canonical_descriptor(self):
        self.__post_init__()
        return d("CausalityPolicy", *self.values)


def contract(operation, ordinal=0):
    from ..operation import (
        AuthorityRequirement,
        BudgetClass,
        OperationContract,
        PublicationPolicy,
        ResourceEnvelope,
    )
    from ..types import WorkEffectClass

    if type(operation) is not CausalOperation:
        raise TypeError("fixed Causality operation required")
    integer(ordinal, 255)
    pure = operation in (
        CausalOperation.CLASSIFY_CASE,
        CausalOperation.COMPARE_CASES,
        CausalOperation.COMPARE_REPLAY,
    )
    return OperationContract(
        operation,
        BudgetClass.CHARGED_WORK,
        WorkEffectClass.PURE_COMPUTE if pure else WorkEffectClass.OPERATIONAL_EFFECT,
        ((AuthorityRequirement.CIE_CURRENT,) if pure else ())
        + (
            AuthorityRequirement.ENVIRONMENT_CURRENT,
            AuthorityRequirement.INVOCATION_CURRENT,
        )
        + ((AuthorityRequirement.SNAPSHOT_CURRENT,) if pure else ()),
        d("CausalWorkClass", operation.value, ordinal),
        ResourceEnvelope(1, 4096, 262144),
        PublicationPolicy.STAGED_IMMUTABLE_ONLY
        if pure
        else PublicationPolicy.SEPARATE_EFFECT_GATE_REQUIRED,
    )


def work_frontier(plan):
    """Complete plan work, independent of budget and outcomes. One unit per
    bounded handler envelope; physical execution is bound by the replay request.
    No optional attempt/repetition can acquire an unplanned charge.
    """
    from .study import CausalStudyPlan

    if type(plan) is not CausalStudyPlan:
        raise TypeError("exact prospective plan required")
    result = []
    if plan.query != "CLOSED_REPLAY":
        for slot in plan.execute_slots:
            if plan.query == "INTERVENTIONAL":
                result.append((CausalOperation.REQUEST_CASE, slot))
            for attempt in range(plan.slots[slot].attempts):
                result.append((CausalOperation.CLASSIFY_CASE, slot * 4 + attempt))
                result.append((CausalOperation.ADMIT_CASE, slot * 4 + attempt))
        result.extend(
            ((CausalOperation.COMPARE_CASES, 0), (CausalOperation.PUBLISH_STUDY, 0))
        )
    else:
        for comparison in range(len(plan.comparisons)):
            for repeat in range(plan.repetitions):
                ordinal = comparison * 8 + repeat
                result.extend(
                    (op, ordinal)
                    for op in (
                        CausalOperation.OPEN_RCE,
                        CausalOperation.ADMIT_BUNDLE,
                        CausalOperation.COMPARE_REPLAY,
                        CausalOperation.PUBLISH_REPLAY,
                    )
                )
        result.append((CausalOperation.PUBLISH_STUDY, 0))
    if len(result) > 255:
        raise ValueError("complete study envelope exceeds ledger bound")
    return tuple(contract(op, ordinal).work_class for op, ordinal in result)
