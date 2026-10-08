"""Exact two-schema matching over one frozen snapshot; no recursive dispatch."""

from itertools import product

from ..arena import ArenaEntry
from ..authority import IngressAbort
from ..contracts import ConstraintFamily, InferenceFamily
from ..identity import ActiveEpistemicContextIdentity
from ..types import AssertionBasis, FailureCode
from .assertions import ActiveEpistemicContext, derived_key, key, semantic_records
from .constraints import gate_witness, preflight
from .fab import d, ground, validate
from .lineage import context_key, derivation_identity, lineage, parent_witness
from .schemas import schema

FORMAL_RULE_BASES = (AssertionBasis.FORMAL_GIVEN, AssertionBasis.FORMAL_ASSUMPTION)


def finding_identity(finding, entries):
    if any(e.category in ("PREDICTION_VIEW", "CAUSAL_RESULT_VIEW") for e in entries):
        return d(
            "ModalFindingWitnessIdentity",
            finding.values[0],
            finding.values[-1],
            finding.values[6],
        )
    return d(
        "FindingWitnessIdentity",
        key(finding.values[0]),
        finding.values[-1],
        key(finding.values[6]),
    )


def active_context(entries, snapshot, branch):
    if type(branch) is not int or branch < 0:
        raise ValueError("canonical branch index required")
    for entry in entries:
        if entry.payload.kind == "AECRecord" and entry.payload.values[0] == branch:
            _, roots, _parent = entry.payload.values
            return ActiveEpistemicContext(
                ActiveEpistemicContextIdentity(
                    d("BranchIdentity", snapshot.cie.identity, branch),
                    roots,
                    snapshot.cie,
                )
            )
    raise ValueError("unknown current-CIE AEC")


def candidates(entries, snapshot, branch, policy):
    assertions, sources, derivations, constraints = semantic_records(
        entries, policy, snapshot
    )
    aec = active_context(entries, snapshot, branch)
    modal = any(
        e.category in ("PREDICTION_VIEW", "CAUSAL_RESULT_VIEW") for e in entries
    )
    pool = tuple(a for _, a in sorted(assertions.items()) if aec.admits(a))
    active_keys = tuple(constraints[k].values[0] for k in sorted(constraints))
    result = {}
    from .modal import resolve_payload

    completed = {
        key(payload.values[1])
        for e in entries
        for payload in (resolve_payload(e, entries, snapshot),)
        if payload.kind == "CompletedInferenceUse"
    }
    for family in InferenceFamily:
        schema_identity = schema(family)
        context = context_key(aec.identity, active_keys, schema_identity)
        arity = 2 if family is InferenceFamily.GROUND_MODUS_PONENS else 3
        # Raw independent role bindings are a bounded structural partition.
        # Source support never participates in this Cartesian product.
        for parents in product(pool, repeat=arity):
            if any(p.scope != parents[0].scope for p in parents):
                continue
            rule = parents[0]
            if rule.basis not in FORMAL_RULE_BASES:
                continue
            node = rule.content.descriptor
            if family is InferenceFamily.GROUND_MODUS_PONENS:
                if (
                    node.kind != "GroundConditional"
                    or node.values[0] != parents[1].content
                ):
                    continue
                conclusion = node.values[1]
            else:
                left, right = (p.content.descriptor for p in parents[1:])
                if (
                    node.kind != "Transitive"
                    or left.kind != "GroundRelation"
                    or right.kind != "GroundRelation"
                    or node.values[0] != left.values[0]
                    or left.values[0] != right.values[0]
                    or left.values[2] != right.values[1]
                ):
                    continue
                conclusion = ground(
                    "GroundRelation", left.values[0], left.values[1], right.values[2]
                )
            referents = frozenset().union(*(validate(p.content) for p in parents))
            validate(conclusion, allowed_referents=referents)
            ask = derived_key(conclusion, parents, parents[0].scope)
            roles = tuple(zip(schema_identity.values[1], parents, strict=True))
            derivation_key = derivation_identity(ask, schema_identity, roles)
            completion_key = d("InferenceUseIdentity", derivation_key, context)
            if key(completion_key) in completed:
                continue
            if any(
                v.values[1] == derivation_key and v.values[2] == context
                for v in derivations.get(key(ask), ())
            ):
                continue
            witnesses = tuple(
                parent_witness(
                    p,
                    snapshot,
                    sources,
                    derivations,
                    context,
                    ask,
                    policy,
                    references=modal,
                )
                for p in parents
            )
            if any(w is None for w in witnesses):
                continue
            ancestry = {key(p) for p in parents}
            for _, ancestors in witnesses:
                ancestry.update(ancestors)
            if len(ancestry) > policy.max_ancestry:
                raise IngressAbort(
                    FailureCode.CAPACITY_ABORT,
                    "complete acyclic support exceeds prospective policy",
                )
            candidate = d(
                "InferenceCandidate",
                ask,
                schema_identity,
                roles,
                context,
                tuple(w[0] for w in witnesses),
                tuple(w[1] for w in witnesses),
            )
            result[key(derivation_key)] = candidate
            if len(result) > policy.max_frontier:
                raise IngressAbort(
                    FailureCode.CAPACITY_ABORT,
                    "complete frontier exceeds prospective policy",
                )
    return tuple(result[k] for k in sorted(result))


def evaluate(
    entries, snapshot, branch, frontier, policy, query_mode="EXISTS_INCOMPATIBILITY"
):
    assertions, _, _, constraints = semantic_records(entries, policy, snapshot)
    aec = active_context(entries, snapshot, branch)
    output = []
    incomplete = False
    scopes = {}
    for _, ask in sorted(assertions.items()):
        if aec.admits(ask):
            scopes.setdefault(key(ask.scope), []).append(ask)
    for scope in sorted(scopes):
        roles = tuple((f"participant_{i}", ask) for i, ask in enumerate(scopes[scope]))
        check = preflight(
            d("ConstraintQuerySchema", tuple(f.value for f in ConstraintFamily)),
            roles,
            aec.identity,
            snapshot,
            constraints,
            policy,
            mode=query_mode,
        )
        if check.kind == "CONSTRAINT_CHECK_INCOMPLETE":
            incomplete = True
        elif check.kind == "CONSTRAINT_BLOCKED":
            for finding in check.values[2]:
                output.append(
                    ArenaEntry(
                        "CONSTRAINT_FINDING",
                        finding_identity(finding, entries),
                        finding,
                    )
                )
    for candidate in frontier:
        ask, schema_identity, roles, context, witness_data, ancestry = candidate.values
        check = preflight(
            schema_identity, roles, aec.identity, snapshot, constraints, policy
        )
        if check.kind == "CONSTRAINT_CHECK_INCOMPLETE":
            incomplete = True
            continue
        if check.kind == "CONSTRAINT_BLOCKED":
            for finding in check.values[2]:
                output.append(
                    ArenaEntry(
                        "CONSTRAINT_FINDING",
                        finding_identity(finding, entries),
                        finding,
                    )
                )
            identity = d(
                "InferenceUseIdentity",
                derivation_identity(ask, schema_identity, roles),
                context,
            )
            output.append(
                ArenaEntry(
                    "STAGING_RECORD",
                    identity,
                    d("CompletedInferenceUse", "BLOCKED", identity),
                )
            )
            continue
        gate = gate_witness(check)
        record = lineage(
            ask,
            schema_identity,
            roles,
            tuple(zip(witness_data, ancestry, strict=True)),
            context,
            gate,
            policy,
        )
        output.extend(
            (
                ArenaEntry("ASSERTION", d("ASK", key(ask)), d("AssertionRecord", ask)),
                ArenaEntry(
                    "DERIVATION_WITNESS",
                    d("ModalDerivationSupportIdentity", record.values[1], context)
                    if any(
                        e.category in ("PREDICTION_VIEW", "CAUSAL_RESULT_VIEW")
                        for e in entries
                    )
                    else d(
                        "DerivationSupportIdentity", key(record.values[1]), key(context)
                    ),
                    record,
                ),
                ArenaEntry(
                    "CLEARANCE_RECORD",
                    check.values[0].values[0].values[0],
                    check.values[0],
                ),
            )
        )
    return tuple(output), incomplete
