"""Semantic ASK records, bounded independent provenance, immutable contexts."""

from dataclasses import dataclass, fields

from ..authority import IngressAbort
from ..identity import (
    ActiveEpistemicContextIdentity,
    AssertionSemanticKey,
    DependencyRootIdentity,
    ScopeIdentity,
    SnapshotBinding,
    SourceAssertionKey,
    canonical_dependencies,
)
from ..serialization import canonical_identity_bytes
from ..types import AssertionBasis, DependencyKind, FailureCode
from .fab import d, ground, validate


def key(value):
    return canonical_identity_bytes(value)


@dataclass(frozen=True, slots=True)
class ActiveEpistemicContext:
    identity: ActiveEpistemicContextIdentity
    parent: ActiveEpistemicContextIdentity | None = None

    def __post_init__(self):
        if type(self.identity) is not ActiveEpistemicContextIdentity:
            raise TypeError("exact AEC identity required")
        if self.parent is not None and (
            type(self.parent) is not ActiveEpistemicContextIdentity
            or self.parent.cie != self.identity.cie
            or not set(self.parent.dependencies) <= set(self.identity.dependencies)
        ):
            raise ValueError("child contexts cannot discharge dependencies")
        key(self.identity)

    def admits(self, assertion):
        return set(assertion.dependencies) <= set(self.identity.dependencies)

    def child(self, root, branch_identity):
        if type(root) is not DependencyRootIdentity:
            raise TypeError("lawful root required")
        return ActiveEpistemicContext(
            ActiveEpistemicContextIdentity(
                branch_identity,
                canonical_dependencies(self.identity.dependencies + (root,)),
                self.identity.cie,
            ),
            self.identity,
        )


def assertion_record(ask):
    if type(ask) is not AssertionSemanticKey:
        raise TypeError("ASK required; no basis-label constructor")
    validate(ask.content)
    return d("AssertionRecord", ask)


def source_support(ask, source):
    if type(source) is not SourceAssertionKey:
        raise TypeError("source occurrence identity required")
    return d("SourceSupport", ask, source)


def derived_key(content, parents, scope):
    roots = canonical_dependencies(tuple(r for p in parents for r in p.dependencies))
    return AssertionSemanticKey(content, AssertionBasis.DERIVED, scope, roots)


def semantic_records(entries, policy, snapshot=None):
    if type(entries) is not tuple or len(entries) > 128:
        raise ValueError("bounded complete arena required")
    assertions, sources, derivations, constraints = {}, {}, {}, {}
    from .modal import validate_supports

    for ask, source in validate_supports(entries, snapshot):
        sources.setdefault(key(ask), {})[key(source)] = source
    constraint_sources = set()
    for entry in entries:
        from .modal import resolve_payload

        payload = resolve_payload(entry, entries, snapshot)
        if entry.category == "ASSERTION":
            ask = payload.values[0]
            assertion_record(ask)
            assertions[key(ask)] = ask
        elif entry.category == "SOURCE_SUPPORT":
            if payload.kind == "SourceSupport":
                ask, source = payload.values
                sources.setdefault(key(ask), {})[key(source)] = source
            elif payload.kind == "ConstraintSourceSupport":
                constraint_sources.add(key(payload.values[1]))
        elif entry.category == "DERIVATION_WITNESS":
            ask = payload.values[0]
            derivations.setdefault(key(ask), []).append(payload)
        elif payload.kind == "ActiveConstraintRecord":
            constraints[key(payload.values[0])] = payload
    if (
        len(assertions) > policy.max_assertions
        or sum(map(len, sources.values())) + len(constraint_sources)
        > policy.max_sources
    ):
        raise IngressAbort(
            FailureCode.CAPACITY_ABORT, "complete semantic state exceeds policy"
        )
    return assertions, sources, derivations, constraints


def internal_retrieval_view(result, snapshot):
    """Literal L2-result statement only; never a formal proposition decoder.

    Copies only the frozen L2 public result schema. No handle/receipt/Core,
    text interpretation, executable schema, or trusted-root re-ingress exists.
    The exact serialized result is provenance, not authority or a digest ID.
    """
    from dgca_lite.memory import types as l2

    if type(result) is not l2.RetrievalResult or type(snapshot) is not SnapshotBinding:
        raise TypeError("typed internal retrieval result and snapshot required")
    if type(result.root) is not l2.RootView or result.root.trusted_root_id is not None:
        raise ValueError("internal adapter never imports trusted-root authority")
    allowed = (
        l2.RetrievalResult,
        l2.RootView,
        l2.SourceView,
        l2.DirectHit,
        l2.BranchView,
        l2.RetrievalProvenance,
        l2.SourceID,
        l2.FamilyID,
        l2.BranchID,
        l2.SeedState,
        l2.SeedValue,
        l2.FrozenFloatMap,
    )
    count = 0

    def closed(value, depth=0):
        nonlocal count
        count += 1
        if count > 512 or depth > 16:
            raise ValueError("L2 adapter traversal bound")
        if type(value) is tuple:
            if len(value) > min(64, 512 - count):
                raise ValueError("L2 adapter outer tuple bound")
            return tuple(closed(v, depth + 1) for v in value)
        if value is None or type(value) in (bool, int, float, str, bytes):
            return value
        if type(value) in (l2.ProvenanceKind, l2.SourceKind):
            return d(type(value).__name__, value.value)
        if type(value) not in allowed:
            raise TypeError("unknown/authority-bearing L2 payload")
        return d(
            type(value).__name__,
            tuple(
                (f.name, closed(getattr(value, f.name), depth + 1))
                for f in fields(value)
            ),
        )

    image = key(closed(result))
    from .constraints import snapshot_ref

    origin = d("InternalRetrievalAdapter", snapshot_ref(snapshot))
    scope = ScopeIdentity(
        "INTERNAL_RETRIEVAL",
        origin,
        d("L2RetrievalScope", key(snapshot.cie.environment)),
    )
    root = DependencyRootIdentity(
        DependencyKind.INTERNAL_RETRIEVAL, origin, d("L2Result", image)
    )
    ask = AssertionSemanticKey(
        ground("InternalRetrievalStatement", image),
        AssertionBasis.INTERNAL_RETRIEVAL,
        scope,
        (root,),
    )
    return d(
        "IngressAssertionView",
        ask,
        SourceAssertionKey("INTERNAL_RETRIEVAL", origin, d("L2Result", image)),
    )
