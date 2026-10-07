"""Treatment identities and distinct opaque controller receipt boundaries."""

from dataclasses import dataclass

from ..authority import _OpaqueHandle
from ..serialization import canonical_identity_bytes
from .contracts import closed, d, fields, integer


class AppliedInterventionReceipt(_OpaqueHandle):
    __slots__ = ()


class ProtocolControlReceipt(_OpaqueHandle):
    __slots__ = ()


class BranchIsolationReceipt(_OpaqueHandle):
    __slots__ = ()


NOT_APPLICABLE = d("NOT_APPLICABLE")


@dataclass(frozen=True, slots=True)
class ExposureDescriptor:
    dose: object = NOT_APPLICABLE
    duration: object = NOT_APPLICABLE
    timing: object = NOT_APPLICABLE

    def __post_init__(self):
        for name in ("dose", "duration", "timing"):
            object.__setattr__(self, name, closed(getattr(self, name)))

    def canonical_descriptor(self):
        self.__post_init__()
        return d("ExposureDescriptor", self.dose, self.duration, self.timing)


@dataclass(frozen=True, slots=True)
class TreatmentDescriptor:
    operation: object
    mechanism: object
    assignment: object
    exposure: ExposureDescriptor
    domain: object
    protocol_revision: int

    def __post_init__(self):
        if type(self.exposure) is not ExposureDescriptor:
            raise TypeError("complete exposure descriptor required")
        integer(self.protocol_revision, 2**63 - 1)
        for name in ("operation", "mechanism", "assignment", "domain"):
            object.__setattr__(self, name, closed(getattr(self, name)))

    def canonical_descriptor(self):
        self.__post_init__()
        return d(
            "TreatmentDescriptor",
            self.operation,
            self.mechanism,
            self.assignment,
            self.exposure.canonical_descriptor(),
            self.domain,
            self.protocol_revision,
        )


def treatment_pair(left, right):
    if type(left) is not TreatmentDescriptor or type(right) is not TreatmentDescriptor:
        raise TypeError("exact treatments required")
    members = tuple(v.canonical_descriptor() for v in (left, right))
    keyed = {canonical_identity_bytes(v): v for v in members}
    if len(keyed) != 2:
        raise ValueError("treatment contrast requires two distinct treatments")
    return d("CanonicalTreatmentPair", *(keyed[k] for k in sorted(keyed)))


def treatment_from_data(data):
    op, mechanism, assignment, exposure, domain, revision = fields(
        data, "TreatmentDescriptor", 6
    )
    return TreatmentDescriptor(
        op,
        mechanism,
        assignment,
        ExposureDescriptor(*fields(exposure, "ExposureDescriptor", 3)),
        domain,
        revision,
    )
