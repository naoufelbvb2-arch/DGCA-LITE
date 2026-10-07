"""External occurrence capabilities and immutable slot reports, never evidence."""

from dataclasses import dataclass

from ..authority import _OpaqueHandle
from ..serialization import canonical_identity_bytes
from .contracts import closed, d, integer


class TrustedCaseOccurrence(_OpaqueHandle):
    __slots__ = ()


@dataclass(frozen=True, slots=True)
class CaseSlotReport:
    slot: int
    terminal_state: str
    classification: str
    occurrence: object = None
    outcome: object = None
    measurement_status: str = "MISSING"

    def canonical_descriptor(self):
        integer(self.slot, 15)
        if type(self.terminal_state) is not str or self.terminal_state not in (
            "FULFILLED",
            "FAILED",
            "UNRESOLVED",
            "LAWFULLY_UNEXECUTED",
        ):
            raise ValueError("closed terminal slot state required")
        if type(self.classification) is not str or self.classification not in (
            "MATCH",
            "CONFLICT",
            "UNRESOLVED",
        ):
            raise ValueError("closed causal classification required")
        if type(self.measurement_status) is not str or self.measurement_status not in (
            "MEASURED",
            "MISSING",
            "FAILED",
            "INVALID",
            "UNAVAILABLE",
            "INCOMPLETE",
        ):
            raise ValueError("closed measurement status required")
        if self.occurrence is not None:
            closed(self.occurrence)
        if self.measurement_status == "MEASURED":
            closed(self.outcome)
            if self.occurrence is None or self.terminal_state != "FULFILLED":
                raise ValueError("measurement requires a fulfilled genuine occurrence")
        if self.measurement_status != "MEASURED" and (
            self.outcome is not None or self.classification != "UNRESOLVED"
        ):
            raise ValueError("missing measurement is not an outcome")
        return d(
            "CaseSlotReport",
            self.slot,
            self.terminal_state,
            self.classification,
            self.occurrence,
            self.outcome,
            self.measurement_status,
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())
