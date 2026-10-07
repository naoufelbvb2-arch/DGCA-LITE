"""Pure complete comparison and closed narrow result values. No authority API."""

from dataclasses import dataclass

from ..identity import ScopeIdentity
from ..serialization import canonical_identity_bytes
from .cases import CaseSlotReport
from .contracts import CausalOperation, closed, d, fields, outer
from .measurement import classifier_from_data, spec_from_data

RESULT_CLASSES = (
    "OBSERVATIONAL_COMPARISON",
    "INTERVENTIONAL_PROTOCOL_COMPARISON",
    "REPLAY_IDENTIFIED_TREATMENT_EFFECT",
    "NO_PRESPECIFIED_OUTCOME_DISCRIMINATION",
)


@dataclass(frozen=True, slots=True)
class CausalResultView:
    result_class: str
    contrast: object
    treatment_pair: object
    treatment_outcome_map: tuple
    outcome_relation: str
    scope: ScopeIdentity
    domain: object
    measurement: object

    def canonical_descriptor(self):
        outer(self.treatment_outcome_map, 2)
        if len(self.treatment_outcome_map) != 2:
            raise ValueError("complete two-role contrast required")
        for row in self.treatment_outcome_map:
            if type(row) is not tuple or len(row) != 2:
                raise ValueError("outcome map outer bound")
        if (
            type(self.result_class) is not str
            or self.result_class not in RESULT_CLASSES
            or type(self.outcome_relation) is not str
            or self.outcome_relation not in ("SAME", "DIFFERENT")
        ):
            raise ValueError("closed narrow result class/relation required")
        if type(self.scope) is not ScopeIdentity:
            raise TypeError("exact result scope required")
        mapping = tuple((closed(a), closed(b)) for a, b in self.treatment_outcome_map)
        if (mapping[0][1] == mapping[1][1]) != (self.outcome_relation == "SAME"):
            raise ValueError("result contradicts complete typed outcomes")
        replay = self.result_class in RESULT_CLASSES[2:]
        if replay:
            fields(self.contrast, "CanonicalReplayContrastIdentity", 4)
            members = fields(self.treatment_pair, "CanonicalTreatmentPair", 2)
            if tuple(k for k, _ in mapping) != members:
                raise ValueError("exact canonical treatment orientation required")
            if (self.result_class == RESULT_CLASSES[3]) != (
                self.outcome_relation == "SAME"
            ):
                raise ValueError("RICTE requires prespecified discrimination")
        elif self.treatment_pair is not None:
            raise ValueError("nonidentified result cannot claim replay identity")
        return d(
            "CausalResult",
            self.result_class,
            closed(self.contrast),
            self.treatment_pair,
            mapping,
            self.outcome_relation,
            self.scope,
            closed(self.domain),
            closed(self.measurement),
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())

    @property
    def identity(self):
        return d(
            "CanonicalCausalResultIdentity",
            canonical_identity_bytes(self.canonical_descriptor()),
        )


@dataclass(frozen=True, slots=True)
class CausalStudyReport:
    status: str
    plan_identity: object
    slots: tuple
    results: tuple

    def canonical_descriptor(self):
        outer(self.slots, 16)
        outer(self.results, 128)
        if type(self.status) is not str or self.status not in (
            "COMPLETE",
            "INCOMPLETE",
            "ABORTED",
        ):
            raise ValueError("closed terminal study status required")
        if any(type(v) is not CaseSlotReport for v in self.slots) or any(
            type(v) is not CausalResultView for v in self.results
        ):
            raise TypeError("closed terminal study records required")
        if tuple(v.slot for v in self.slots) != tuple(range(len(self.slots))):
            raise ValueError("every planned slot must remain represented")
        return d(
            "CausalStudyReport",
            self.status,
            closed(self.plan_identity),
            tuple(v.canonical_descriptor() for v in self.slots),
            tuple(v.canonical_descriptor() for v in self.results),
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


def result_from_data(data):
    return CausalResultView(*fields(data, "CausalResult", 8))


def comparison_rows(matching, spec, rows):
    outer(rows, 16)
    for row in rows:
        if type(row) is not tuple or len(row) != 6:
            raise ValueError("closed case row required")
    classifier = classifier_from_data(matching)
    outcomes = spec_from_data(spec)
    reports = []
    for slot, state, occurrence, outcome, measured, _orientation in rows:
        classification = classifier.classify(
            outcome, outcomes, measurement_status=measured
        )
        reports.append(
            CaseSlotReport(slot, state, classification, occurrence, outcome, measured)
        )
    return tuple(reports)


def compute(operation, data):
    """The only compiled causal computation. Its environment contains DATA only."""
    if operation is CausalOperation.CLASSIFY_CASE:
        matching, spec, rows = fields(data, "CausalCaseClassificationInput", 3)
        if type(rows) is not tuple or len(rows) != 1:
            raise ValueError("one exact planned occurrence required")
        return comparison_rows(matching, spec, rows)[0].canonical_descriptor()
    if operation is CausalOperation.COMPARE_CASES:
        matching, spec, rows, comparisons, query, plan_ref, domain, measurement = (
            fields(data, "CausalCaseComparisonInput", 8)
        )
        reports = comparison_rows(matching, spec, rows)
        outer(comparisons, 16)
        result = []
        incomplete = False
        for ordinal, comparison in enumerate(comparisons):
            left, right, _independent, resolved = fields(comparison, "Comparison", 4)
            a, b = reports[left], reports[right]
            if (
                a.outcome is None
                or b.outcome is None
                or (resolved and "UNRESOLVED" in (a.classification, b.classification))
            ):
                incomplete = True
                continue
            relation = "SAME" if a.outcome == b.outcome else "DIFFERENT"
            scope = ScopeIdentity(
                "CAUSAL_COMPARISON",
                domain,
                d("CausalComparisonScope", plan_ref, ordinal),
            )
            mapping = ((rows[left][5], a.outcome), (rows[right][5], b.outcome))
            result.append(
                CausalResultView(
                    RESULT_CLASSES[0 if query == "OBSERVATIONAL" else 1],
                    d("StudyComparisonIdentity", plan_ref, ordinal),
                    None,
                    mapping,
                    relation,
                    scope,
                    domain,
                    measurement,
                ).canonical_descriptor()
            )
        # A complete comparison group is never truncated to its resolved subset.
        return d(
            "CausalComparisonOutput",
            "INCOMPLETE" if incomplete else "COMPLETE",
            tuple(v.canonical_descriptor() for v in reports),
            () if incomplete else tuple(result),
        )
    if operation is CausalOperation.COMPARE_REPLAY:
        matching, spec, rows, resolved, crci, pair, domain, measurement = fields(
            data, "CausalReplayComparisonInput", 8
        )
        reports = comparison_rows(matching, spec, rows)
        if len(reports) != 2:
            raise ValueError("complete replay branch pair required")
        if any(v.outcome is None for v in reports) or (
            resolved and any(v.classification == "UNRESOLVED" for v in reports)
        ):
            return d(
                "CausalComparisonOutput",
                "INCOMPLETE",
                tuple(v.canonical_descriptor() for v in reports),
                (),
            )
        mapping = tuple(
            sorted(
                ((rows[i][5], reports[i].outcome) for i in range(2)),
                key=lambda row: canonical_identity_bytes(row[0]),
            )
        )
        same = mapping[0][1] == mapping[1][1]
        scope = ScopeIdentity(
            "CLOSED_REPLAY",
            domain,
            d("ClosedReplayScope", canonical_identity_bytes(crci)),
        )
        result = CausalResultView(
            RESULT_CLASSES[3 if same else 2],
            crci,
            pair,
            mapping,
            "SAME" if same else "DIFFERENT",
            scope,
            domain,
            measurement,
        )
        return d(
            "CausalComparisonOutput",
            "COMPLETE",
            tuple(v.canonical_descriptor() for v in reports),
            (result.canonical_descriptor(),),
        )
    raise TypeError("not a compiled pure causal operation")
