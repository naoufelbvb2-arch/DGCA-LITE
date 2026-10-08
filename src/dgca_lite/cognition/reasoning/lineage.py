"""Bounded same-CIE acyclic proof paths, not learned evidence ancestry."""

from ..types import AssertionBasis
from .assertions import key
from .fab import d


def context_key(aec, constraint_keys, schema_identity):
    # A local reference is resolved under the enclosing genuine CIE binding.
    # Historical output contains that complete binding in its ArenaSnapshot.
    return d(
        "DerivationContextReference",
        key(aec.branch_identity),
        tuple(key(r) for r in aec.dependencies),
        key(aec.cie.identity),
        tuple(key(c) for c in constraint_keys),
        schema_identity,
    )


def parent_witness(
    ask,
    snapshot,
    sources,
    derivations,
    context,
    conclusion,
    policy,
    *,
    references=False,
):
    source_set = sources.get(key(ask), {})
    if ask.basis is not AssertionBasis.DERIVED:
        if not source_set:
            return None
        support, ancestry = source_set[min(source_set)], ()
    else:
        paths = []
        for record in derivations.get(key(ask), ()):
            _, _, producing_context, ancestors, _, _ = record.values
            if producing_context == context and key(conclusion) not in ancestors:
                paths.append(record)
        if not paths:
            return None
        record = min(paths, key=key)
        ancestry = record.values[3]
        support = (
            d("ModalDerivationSupportReference", record.values[1], record.values[2])
            if references
            else d(
                "DerivationSupportReference",
                key(record.values[1]),
                key(record.values[2]),
            )
        )
    if ask == conclusion or key(conclusion) in ancestry:
        return None
    ref = d(
        "SnapshotReference",
        key(snapshot.cie.identity),
        snapshot.arena_version,
        snapshot.round_identity,
    )
    return d(
        "ParentAssertionWitness",
        key(ask),
        ref,
        support if references and ask.basis is AssertionBasis.DERIVED else key(support),
    ), ancestry


def lineage(conclusion, schema_identity, roles, witnesses, context, gate, policy):
    ancestry = {key(ask) for _, ask in roles}
    for _, ancestors in witnesses:
        ancestry.update(ancestors)
    if key(conclusion) in ancestry or len(ancestry) > policy.max_ancestry:
        raise ValueError("circular or oversized support path")
    derivation_key = derivation_identity(conclusion, schema_identity, roles)
    acyclic = tuple(sorted(ancestry))
    return d(
        "DerivationLineage",
        conclusion,
        derivation_key,
        context,
        acyclic,
        tuple(w[0] for w in witnesses),
        gate,
    )


def derivation_identity(conclusion, schema_identity, roles):
    # Canonical bytes are exact complete identities, not hash indexes. Local
    # references avoid repeatedly embedding the same immutable proof objects.
    return d(
        "DerivationKey",
        key(conclusion),
        schema_identity,
        tuple((role, key(ask)) for role, ask in roles),
    )
