"""Capability-free occurrence/evaluation/coverage identities."""

from dataclasses import dataclass

from ..identity import CanonicalDescriptor
from ..serialization import canonical_identity_bytes
from ..types import CaptureState, ForecastStatus
from .commitment import ForecastCommitmentView
from .targets import d


@dataclass(frozen=True, slots=True)
class FutureTrustedOccurrenceID:
    core_runtime: CanonicalDescriptor
    trusted_occurrence: CanonicalDescriptor

    def canonical_descriptor(self):
        if (
            type(self.core_runtime) is not CanonicalDescriptor
            or type(self.trusted_occurrence) is not CanonicalDescriptor
        ):
            raise TypeError("closed occurrence provenance required")
        if (
            self.trusted_occurrence.kind != "TrustedCoreOccurrence"
            or type(self.trusted_occurrence.values) is not tuple
            or len(self.trusted_occurrence.values) != 3
            or any(type(v) is not int or v < 0 for v in self.trusted_occurrence.values)
        ):
            raise ValueError("exact trusted occurrence descriptor required")
        return d(
            "FutureTrustedOccurrenceID", self.core_runtime, self.trusted_occurrence
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


@dataclass(frozen=True, slots=True)
class ForecastEvaluationID:
    commitment_identity: CanonicalDescriptor
    future_occurrence: FutureTrustedOccurrenceID

    def canonical_descriptor(self):
        if (
            type(self.commitment_identity) is not CanonicalDescriptor
            or type(self.future_occurrence) is not FutureTrustedOccurrenceID
        ):
            raise TypeError("exact evaluation identity fields required")
        if (
            self.commitment_identity.kind != "ForecastCommitmentID"
            or type(self.commitment_identity.values) is not tuple
            or len(self.commitment_identity.values) != 1
        ):
            raise ValueError("closed commitment identity required")
        return d(
            "ForecastEvaluationID",
            self.commitment_identity,
            self.future_occurrence.canonical_descriptor(),
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


@dataclass(frozen=True, slots=True)
class ForecastOutcomeView:
    commitment: ForecastCommitmentView
    status: ForecastStatus
    coverage: tuple[CanonicalDescriptor, ...]

    def canonical_descriptor(self):
        if type(self.coverage) is not tuple or len(self.coverage) > 64:
            raise ValueError("coverage outer bound")
        if (
            type(self.commitment) is not ForecastCommitmentView
            or type(self.status) is not ForecastStatus
        ):
            raise TypeError("closed forecast outcome required")
        if len(self.coverage) > self.commitment.horizon:
            raise ValueError("coverage exceeds horizon")
        for offset, entry in enumerate(self.coverage, 1):
            if (
                type(entry) is not CanonicalDescriptor
                or entry.kind != "ForecastCoverage"
                or type(entry.values) is not tuple
                or len(entry.values) != 4
            ):
                raise ValueError("closed coverage record required")
            ordinal, occurrence, state, matched = entry.values
            if (
                type(ordinal) is not int
                or ordinal != offset
                or type(state) is not CaptureState
                or type(matched) is not bool
            ):
                raise ValueError("canonical offset/capture classification required")
            if (
                type(occurrence) is not CanonicalDescriptor
                or occurrence.kind != "FutureTrustedOccurrenceID"
            ):
                raise ValueError("closed future occurrence required")
            if type(occurrence.values) is not tuple or len(occurrence.values) != 2:
                raise ValueError("closed occurrence outer shape required")
            FutureTrustedOccurrenceID(*occurrence.values)
            if occurrence.values[0] != self.commitment.origin_core.core_identity:
                raise ValueError("cross-Core coverage provenance")
            if state is CaptureState.OBSERVATION_GAP and matched:
                raise ValueError("a gap cannot match")
        identities = tuple(canonical_identity_bytes(e.values[1]) for e in self.coverage)
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate trusted occurrence")
        matches = tuple(e.values[3] for e in self.coverage)
        if any(matches[:-1]) or (
            any(matches) and self.status is not ForecastStatus.MATCHED
        ):
            raise ValueError("a match terminalizes its exact offset")
        if self.status is ForecastStatus.MATCHED and (not matches or not matches[-1]):
            raise ValueError("MATCHED requires a lawful matching offset")
        if (
            self.status is ForecastStatus.PENDING
            and len(self.coverage) == self.commitment.horizon
        ):
            raise ValueError("a completed horizon cannot remain PENDING")
        if self.status in (
            ForecastStatus.WINDOW_ELAPSED_WITHOUT_MATCH,
            ForecastStatus.INCONCLUSIVE_OBSERVATION_GAP,
        ):
            from .evaluation import status_after

            if (
                len(self.coverage) != self.commitment.horizon
                or status_after(
                    self.commitment.horizon,
                    tuple(e.values[2] for e in self.coverage),
                    False,
                )
                is not self.status
            ):
                raise ValueError("coverage/status mismatch")
        return d(
            "ForecastOutcomeView",
            self.commitment.canonical_descriptor(),
            self.status,
            self.coverage,
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())
