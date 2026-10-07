"""Dumb synchronous scheduling over the existing work/effect/CIE foundations.

There is no authority registry, budget, arena, serializer or lock in this module.
Pure builtin workers consume closed inputs; publication requires genuine current
foundation authority, a fresh charge and the privately recorded worker output.
"""

from dataclasses import dataclass

from ..arena import ArenaEntry, ArenaSnapshot
from ..authority import IngressAbort
from ..budget import BudgetChargeView
from ..cie import create_cie_runtime
from ..effect import PreparedEffect
from ..effects import create_effect_runtime
from ..identity import CanonicalDescriptor, SnapshotBinding
from ..invocation import InvocationLimits, create_invocation_runtime
from ..types import FailureCode
from ..work import (
    _cleanup_reasoning_epoch,
    _reasoning_source_input,
    create_work_runtime,
)
from .assertions import assertion_record, key, semantic_records, source_support
from .constraints import snapshot_ref
from .fab import d, validate
from .inference import candidates, evaluate
from .schemas import ReasoningOperation, ReasoningPolicy


def entries_from_data(values):
    if type(values) is not tuple or len(values) > 128:
        raise ValueError("arena outer bound")
    result = []
    for value in values:
        if (
            type(value) is not CanonicalDescriptor
            or type(value.values) is not tuple
            or len(value.values) != 3
            or value.kind != "ArenaEntry"
        ):
            raise ValueError("closed arena entry envelope required")
        result.append(ArenaEntry(*value.values))
    return tuple(result)


def validate_work_input(work, snapshot, expected_sources, discovered, policy):
    data = work.frozen_input
    if data.kind != "ReasoningInput" or len(data.values) != 3:
        raise ValueError("closed reasoning input envelope required")
    entry_data, branch, extra = data.values
    if type(branch) is not int or branch < 0:
        raise ValueError("exact branch index required")
    if entry_data != tuple(e.canonical_descriptor() for e in snapshot.entries):
        raise IngressAbort(FailureCode.CIE_STALE)
    if work.contract.operation_type is ReasoningOperation.SEED:
        if extra != expected_sources:
            raise IngressAbort(FailureCode.INVALID_FORMAL_AUTHORITY)
    elif work.contract.operation_type is ReasoningOperation.DISCOVER:
        if type(extra) is not str or extra not in (
            "EXISTS_INCOMPATIBILITY",
            "ENUMERATE_ALL_INCOMPATIBILITIES",
        ):
            raise ValueError("discovery accepts no caller schema or frontier")
    elif work.contract.operation_type is ReasoningOperation.EVALUATE and (
        discovered is None
        or discovered.kind != "ReasoningFrontier"
        or discovered.values[0] != branch
        or extra != discovered
    ):
        raise IngressAbort(FailureCode.INVALID_INPUT)
    semantic_records(snapshot.entries, policy)


def _seed(entries, sources, snapshot, policy):
    if type(sources) is not tuple or len(sources) > policy.max_sources:
        raise IngressAbort(FailureCode.CAPACITY_ABORT, "source group outer bound")
    additions = []
    roots = {}
    contexts = {
        e.payload.values[0]: e.payload.values[1]
        for e in entries
        if e.payload.kind == "AECRecord"
    }
    if not contexts:
        additions.append(
            ArenaEntry(
                "STAGING_RECORD", d("AECIdentity", 0), d("AECRecord", 0, (), None)
            )
        )
        contexts[0] = ()
    known = {r for values in contexts.values() for r in values}
    for source in sources:
        if source.kind == "IngressAssertionView":
            ask, occurrence = source.values
            validate(ask.content)
            additions.extend(
                (
                    ArenaEntry("ASSERTION", d("ASK", key(ask)), assertion_record(ask)),
                    ArenaEntry(
                        "SOURCE_SUPPORT",
                        d("SourceAssertionSupport", key(ask), key(occurrence)),
                        source_support(ask, occurrence),
                    ),
                )
            )
            roots.update((key(r), r) for r in ask.dependencies)
        elif source.kind == "ActiveConstraintPremiseView":
            semantic, occurrence = source.values
            validate(semantic.values[0])
            additions.extend(
                (
                    ArenaEntry(
                        "STAGING_RECORD",
                        semantic,
                        d("ActiveConstraintRecord", semantic),
                    ),
                    ArenaEntry(
                        "SOURCE_SUPPORT",
                        d("ConstraintSourceIdentity", key(occurrence)),
                        d("ConstraintSourceSupport", semantic, occurrence),
                    ),
                )
            )
            roots.update((key(r), r) for r in semantic.values[3])
        else:
            raise ValueError("no generic basis constructor")
    from ..identity import canonical_dependencies

    last = max(contexts)
    for k in sorted(roots):
        root = roots[k]
        if root in known:
            continue
        parent = last
        last += 1
        if last > policy.max_sources:
            raise ValueError("branch bound")
        contexts[last] = canonical_dependencies(contexts[parent] + (root,))
        additions.append(
            ArenaEntry(
                "STAGING_RECORD",
                d("AECIdentity", last),
                d("AECRecord", last, contexts[last], parent),
            )
        )
        known.add(root)
    merged = {key(e.canonical_descriptor()): e for e in (*entries, *additions)}
    semantic_records(tuple(merged.values()), policy)
    ordered = {key(e.canonical_descriptor()): e for e in additions}
    return tuple(ordered[k] for k in sorted(ordered))


def group_capacity(work, policy):
    """Prospective complete-group entry envelope, never budget-first-N."""
    entry_data, _branch, extra = work.frozen_input.values
    if work.contract.operation_type is ReasoningOperation.SEED:
        return 3 * len(extra) + 1
    if work.contract.operation_type is ReasoningOperation.DISCOVER:
        return 0
    entries = entries_from_data(entry_data)
    assertions, _, _, constraints = semantic_records(entries, policy)
    prospective = set(assertions) | {key(c.values[0]) for c in extra.values[1]}
    if len(prospective) > policy.max_assertions:
        raise IngressAbort(
            FailureCode.CAPACITY_ABORT, "complete assertion group exceeds policy"
        )
    scopes = {}
    for ask in assertions.values():
        scopes[key(ask.scope)] = scopes.get(key(ask.scope), 0) + 1
    findings = 0
    if constraints:
        if extra.values[2] == "EXISTS_INCOMPATIBILITY":
            findings = len(scopes)
        else:
            for n in scopes.values():
                for record in constraints.values():
                    kind = record.values[0].values[0].descriptor.kind
                    findings += n if kind == "FormalNegation" else n * (n - 1) // 2
    return 3 * len(extra.values[1]) + findings


def compute(operation, data, snapshot, policy):
    entry_data, branch, extra = data.values
    entries = entries_from_data(entry_data)
    if operation is ReasoningOperation.SEED:
        output = _seed(entries, extra, snapshot, policy)
        return d(
            "ReasoningStage",
            "SEED",
            tuple(e.canonical_descriptor() for e in output),
            False,
        )
    if operation is ReasoningOperation.DISCOVER:
        return d(
            "ReasoningFrontier",
            branch,
            candidates(entries, snapshot, branch, policy),
            extra,
        )
    if operation is ReasoningOperation.EVALUATE:
        output, incomplete = evaluate(
            entries, snapshot, branch, extra.values[1], policy, extra.values[2]
        )
        return d(
            "ReasoningStage",
            "ROUND" if extra.values[1] else "FIXED_POINT",
            tuple(e.canonical_descriptor() for e in output),
            incomplete,
        )
    raise IngressAbort(FailureCode.UNKNOWN_OPERATION_TYPE)


def publication_from_output(output):
    if output.kind != "ReasoningStage" or len(output.values) != 3:
        raise IngressAbort(FailureCode.INVALID_INPUT)
    kind, entries, incomplete = output.values
    if incomplete:
        raise IngressAbort(FailureCode.CONSTRAINT_CHECK_INCOMPLETE)
    return d("ReasoningPublication", kind, entries, kind == "FIXED_POINT")


@dataclass(frozen=True, slots=True)
class ReasoningResult:
    status: str
    snapshot: ArenaSnapshot

    def __post_init__(self):
        if type(self.status) is not str or type(self.snapshot) is not ArenaSnapshot:
            raise TypeError("closed reasoning result required")
        key(self.canonical_descriptor())

    def canonical_descriptor(self):
        if self.status not in (
            "FIXED_POINT",
            "PARTIAL_BUDGET",
            "CONSTRAINT_CHECK_INCOMPLETE",
            "CAPACITY_ABORT",
            "ENVIRONMENT_STALE",
            "PARENT_AUTHORITY_STALE",
        ):
            raise ValueError("unknown reasoning completion")
        return d("ReasoningResult", self.status, self.snapshot.canonical_descriptor())

    @property
    def assertions(self):
        return tuple(
            e.payload.values[0]
            for e in self.snapshot.entries
            if e.category == "ASSERTION"
        )


@dataclass(frozen=True, slots=True)
class ReasoningRuntime:
    """Facade only: its fields/data never substitute for genuine inner handles."""

    parent: object
    cie: object
    work: object
    effects: object

    def _work(
        self,
        authority,
        revision,
        cie,
        ledger,
        snapshot,
        operation,
        data,
        *,
        sources=None,
        internal_results=(),
        prediction_views=(),
        causal_views=(),
        discovery=None,
        publication_charge=False,
    ):
        try:
            work = self.work.prepare_work(
                authority, revision, snapshot.binding, data, operation=operation
            )
        except IngressAbort as error:
            if (
                error.code is FailureCode.INVALID_INPUT
                and isinstance(error.__cause__, ValueError)
                and "bound" in str(error.__cause__)
            ):
                raise IngressAbort(FailureCode.CAPACITY_ABORT) from error
            raise
        reservation, prepared = self.work.reserve(
            authority, revision, cie, ledger, work
        )
        effect_reservation = None
        if publication_charge:
            effect_reservation = ledger.reserve(
                authority, revision, 1, d("ReasoningPublishWorkClass")
            )
        permit = self.work.authorize_and_charge(
            authority,
            revision,
            cie,
            ledger,
            reservation,
            prepared,
            source_capabilities=sources,
            internal_results=internal_results,
            prediction_views=prediction_views,
            causal_views=causal_views,
            discovery_permit=discovery,
        )
        output = self.work.execute(permit, work)
        return permit, output.output, effect_reservation

    def _publish(
        self, authority, revision, cie, ledger, snapshot, permit, output, reservation
    ):
        publication = publication_from_output(output)
        effect = self.effects.prepare_effect(
            authority,
            revision,
            d("ReasoningArenaTarget", snapshot_ref(snapshot.binding)),
            publication,
            d("ReasoningArenaScope", snapshot.binding.cie.identity),
            operation=ReasoningOperation.PUBLISH,
        )
        record = ledger.reservation_view(authority, revision, reservation)
        rid, units, work_class = record.values
        ordinal = units[0]
        charge = BudgetChargeView(
            self.parent.describe(authority).identity,
            rid,
            d("InvocationChargeUnitIdentity", rid, ordinal),
            work_class,
        )
        prepared = PreparedEffect(effect, snapshot.binding, charge, ordinal)
        binding = SnapshotBinding(
            snapshot.binding.cie,
            snapshot.binding.arena_version + 1,
            snapshot.binding.round_identity + 1,
        )
        merged = {
            key(d("ArenaEntryKey", e.category, e.identity)): e for e in snapshot.entries
        }
        for entry in entries_from_data(publication.values[1]):
            merged[key(d("ArenaEntryKey", entry.category, entry.identity))] = entry
        candidate = ArenaSnapshot(binding, tuple(merged[k] for k in sorted(merged)))
        if publication.values[2]:
            ReasoningResult("FIXED_POINT", candidate)
        commit = self.effects.authorize_charge_and_commit(
            authority,
            revision,
            ledger,
            reservation,
            prepared,
            cie=cie,
            work_runtime=self.work,
            work_permit=permit,
        )
        return candidate, commit

    def run(
        self,
        authority,
        revision,
        ledger,
        capabilities,
        *,
        branch=0,
        query_mode="EXISTS_INCOMPATIBILITY",
        internal_results=(),
        prediction_views=(),
        causal_views=(),
    ):
        if type(branch) is not int or branch < 0:
            raise ValueError("canonical branch index required")
        if type(query_mode) is not str or query_mode not in (
            "EXISTS_INCOMPATIBILITY",
            "ENUMERATE_ALL_INCOMPATIBILITIES",
        ):
            raise ValueError("unknown constraint query mode")
        cie = self.cie.open(authority, revision)
        snapshot = self.cie.snapshot(cie)
        try:
            data = _reasoning_source_input(
                self.work,
                authority,
                revision,
                cie,
                ledger,
                snapshot,
                capabilities,
                internal_results,
                prediction_views,
                causal_views,
            )
            permit, output, charge = self._work(
                authority,
                revision,
                cie,
                ledger,
                snapshot,
                ReasoningOperation.SEED,
                data,
                sources=capabilities,
                internal_results=internal_results,
                prediction_views=prediction_views,
                causal_views=causal_views,
                publication_charge=True,
            )
            snapshot, _ = self._publish(
                authority, revision, cie, ledger, snapshot, permit, output, charge
            )
            while True:
                data = d(
                    "ReasoningInput",
                    tuple(e.canonical_descriptor() for e in snapshot.entries),
                    branch,
                    query_mode,
                )
                discovery, frontier, _ = self._work(
                    authority,
                    revision,
                    cie,
                    ledger,
                    snapshot,
                    ReasoningOperation.DISCOVER,
                    data,
                )
                data = d(
                    "ReasoningInput",
                    tuple(e.canonical_descriptor() for e in snapshot.entries),
                    branch,
                    frontier,
                )
                permit, output, charge = self._work(
                    authority,
                    revision,
                    cie,
                    ledger,
                    snapshot,
                    ReasoningOperation.EVALUATE,
                    data,
                    discovery=discovery,
                    publication_charge=True,
                )
                snapshot, _ = self._publish(
                    authority, revision, cie, ledger, snapshot, permit, output, charge
                )
                if not frontier.values[1]:
                    return ReasoningResult("FIXED_POINT", snapshot)
        except IngressAbort as error:
            if self.cie.status(cie) == "OPEN":
                self.cie.abort(cie)
            status = (
                "PARTIAL_BUDGET"
                if error.code is FailureCode.BUDGET_ABORT
                else error.code.value
            )
            if status not in (
                "PARTIAL_BUDGET",
                "CONSTRAINT_CHECK_INCOMPLETE",
                "CAPACITY_ABORT",
                "ENVIRONMENT_STALE",
                "PARENT_AUTHORITY_STALE",
            ):
                raise
            return ReasoningResult(status, snapshot)
        except BaseException:
            if self.cie.status(cie) == "OPEN":
                self.cie.abort(cie)
            raise
        finally:
            _cleanup_reasoning_epoch(self.work, authority, snapshot.binding.cie)


def create_reasoning_runtime(
    cause_ingress, *, invocation_limits=None, cie_policy=None, policy=None
):
    policy = ReasoningPolicy() if policy is None else policy
    parent = create_invocation_runtime(
        cause_ingress,
        InvocationLimits(64) if invocation_limits is None else invocation_limits,
    )
    cie = create_cie_runtime(parent, policy=cie_policy)
    work = create_work_runtime(parent, cie, reasoning_policy=policy)
    effects = create_effect_runtime(parent, cie, reasoning_policy=policy)
    return ReasoningRuntime(parent, cie, work, effects)
