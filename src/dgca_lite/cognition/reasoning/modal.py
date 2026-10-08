"""Bounded CIE-local modal imports. No registry, capability, or persistent state.

The full view is stored once. References are structural data resolved only in
the exact snapshot, and never stand in for source semantic identity/authority.
"""

from ..arena import ArenaEntry
from ..identity import CanonicalDescriptor
from ..serialization import canonical_identity_bytes as key
from .fab import d

CATEGORIES = ("PREDICTION_VIEW", "CAUSAL_RESULT_VIEW")


def source_input(view):
    from ..causality.adapters import CausalResultCognitiveView
    from ..prediction.adapters import PredictionOutcomeCognitiveView

    if type(view) is PredictionOutcomeCognitiveView:
        category = CATEGORIES[0]
    elif type(view) is CausalResultCognitiveView:
        category = CATEGORIES[1]
    else:
        raise TypeError("closed modal view required")
    return d("ModalIngressView", category, view.canonical_descriptor())


def fields(data, kind, arity):
    if (
        type(data) is not CanonicalDescriptor
        or type(data.kind) is not str
        or data.kind != kind
        or type(data.values) is not tuple
        or len(data.values) != arity
    ):
        raise ValueError("closed modal descriptor required")
    return data.values


def assertion(category, payload):
    from ..causality.adapters import CausalResultCognitiveView
    from ..causality.adapters import reasoning_view as causal
    from ..prediction.adapters import PredictionOutcomeCognitiveView
    from ..prediction.adapters import reasoning_view as prediction

    if category == CATEGORIES[0]:
        view = PredictionOutcomeCognitiveView(
            *fields(payload, "PredictionOutcomeCognitiveView", 7)
        )
        return prediction(view).values
    if category == CATEGORIES[1]:
        view = CausalResultCognitiveView(
            *fields(payload, "CausalResultCognitiveView", 2)
        )
        return causal(view).values
    raise ValueError("wrong modal category")


def validate_ref(ref, kind, snapshot):
    cie, category, ordinal = fields(ref, kind, 3)
    if (
        snapshot is None
        or cie != key(snapshot.cie.identity)
        or category not in CATEGORIES
        or type(ordinal) is not int
        or not 0 <= ordinal < 128
    ):
        raise ValueError("foreign/stale/noncanonical modal reference")
    return category, ordinal


def imports(entries, sources, snapshot):
    """Allocate from the COMPLETE canonically sorted seed set, not arrival time."""
    existing = {}
    count = 0
    for entry in entries:
        if entry.identity.kind in ("SeedAssertionArenaRef", "DerivedAssertionArenaRef"):
            cie, ordinal = fields(entry.identity, entry.identity.kind, 2)
            if (
                snapshot is None
                or cie != key(snapshot.cie.identity)
                or type(ordinal) is not int
                or not 0 <= ordinal < 128
                or entry.category != "ASSERTION"
            ):
                raise ValueError("foreign/noncanonical assertion reference")
        if entry.category in CATEGORIES:
            validate_ref(entry.identity, "ModalArenaRef", snapshot)
            existing[key((entry.category, entry.payload))] = entry.identity
            count += 1
    unique = {}
    for source in sources:
        category, payload = fields(source, "ModalIngressView", 2)
        ask, occurrence = assertion(category, payload)
        unique[key((category, payload))] = (category, payload, ask, occurrence)
    additions = []
    roots = []
    for source_key in sorted(unique):
        category, payload, ask, occurrence = unique[source_key]
        roots.extend(ask.dependencies)
        if source_key in existing:
            continue
        if count >= 128:
            raise ValueError("modal import outer bound")
        ref = d("ModalArenaRef", key(snapshot.cie.identity), category, count)
        aref = d("AssertionArenaRef", key(snapshot.cie.identity), category, count)
        additions.extend(
            (
                ArenaEntry(category, ref, payload),
                ArenaEntry("ASSERTION", aref, d("AssertionRecord", ask)),
                ArenaEntry(
                    "SOURCE_SUPPORT",
                    d("ModalSourceSupportRef", aref, ref),
                    d("ModalSourceSupport", aref, ref, occurrence),
                ),
            )
        )
        count += 1
    return tuple(additions), tuple(roots)


def validate_supports(entries, snapshot):
    """Resolve all closed links BEFORE either inference or pointer publication."""
    modal, assertions, supports = {}, {}, {}
    for entry in entries:
        if entry.identity.kind in ("SeedAssertionArenaRef", "DerivedAssertionArenaRef"):
            cie, ordinal = fields(entry.identity, entry.identity.kind, 2)
            if (
                snapshot is None
                or cie != key(snapshot.cie.identity)
                or type(ordinal) is not int
                or not 0 <= ordinal < 128
                or entry.category != "ASSERTION"
            ):
                raise ValueError("foreign/noncanonical assertion reference")
        if entry.category in CATEGORIES:
            category, ordinal = validate_ref(entry.identity, "ModalArenaRef", snapshot)
            if category != entry.category or ordinal in modal:
                raise ValueError("duplicate/wrong-category modal reference")
            modal[ordinal] = entry
        if entry.identity.kind == "AssertionArenaRef":
            category, ordinal = validate_ref(
                entry.identity, "AssertionArenaRef", snapshot
            )
            if entry.category != "ASSERTION" or ordinal in assertions:
                raise ValueError("wrong assertion reference")
            assertions[ordinal] = entry
        if entry.payload.kind == "ModalSourceSupport":
            aref, ref, source = fields(entry.payload, "ModalSourceSupport", 3)
            category, ordinal = validate_ref(ref, "ModalArenaRef", snapshot)
            if (
                validate_ref(aref, "AssertionArenaRef", snapshot) != (category, ordinal)
                or entry.category != "SOURCE_SUPPORT"
                or entry.identity != d("ModalSourceSupportRef", aref, ref)
                or ordinal in supports
            ):
                raise ValueError("wrong modal support binding")
            supports[ordinal] = (aref, ref, source)
    if (
        set(modal) != set(assertions)
        or set(modal) != set(supports)
        or set(modal) != set(range(len(modal)))
    ):
        raise ValueError("partial modal publication/noncanonical ordinals")
    result = []
    semantic = set()
    for ordinal in sorted(modal):
        entry = modal[ordinal]
        ask, occurrence = assertion(entry.category, entry.payload)
        aref, ref, source = supports[ordinal]
        if (
            ref != entry.identity
            or aref != assertions[ordinal].identity
            or assertions[ordinal].payload != d("AssertionRecord", ask)
            or source != occurrence
        ):
            raise ValueError("modal source/view/ASK provenance mismatch")
        identity = key(ask)
        if identity in semantic:
            raise ValueError("same semantic modal identity cannot bind distinct views")
        semantic.add(identity)
        result.append((ask, source))
    from ..types import AssertionBasis

    supported = {key(ask) for ask, _ in result}
    for entry in entries:
        if (
            entry.category == "ASSERTION"
            and entry.payload.values[0].basis
            in (
                AssertionBasis.PREDICTION_VIEW,
                AssertionBasis.CAUSAL_RESULT_VIEW,
            )
            and (
                entry.identity.kind != "AssertionArenaRef"
                or key(entry.payload.values[0]) not in supported
            )
        ):
            raise ValueError("modal assertions require complete referenced provenance")
    return tuple(result)


def proof_codec(entries, snapshot):
    """References for the fixed Reasoning proof contracts, NOT a serializer.

    Only exact ASK/root/source identities and their full canonical KEY images
    are factored. The existing Unit-1 encoder still encodes every closed value.
    All maps below are bounded transient work over one supplied Arena snapshot.
    """
    from ..identity import AssertionSemanticKey, DependencyRootIdentity, ScopeIdentity

    if type(entries) is not tuple or len(entries) > 128:
        raise ValueError("complete modal proof arena outer bound")
    asks, roots, sources, scopes, proof_entries = {}, {}, {}, {}, {}
    constraints = {}
    for entry in entries:
        if entry.identity.kind == "ActiveConstraintArenaRef":
            cie, ordinal = fields(entry.identity, entry.identity.kind, 2)
            if (
                snapshot is None
                or cie != key(snapshot.cie.identity)
                or type(ordinal) is not int
                or not 0 <= ordinal < 128
                or ordinal in constraints
                or entry.category != "STAGING_RECORD"
            ):
                raise ValueError("foreign/duplicate constraint reference")
            (semantic,) = fields(entry.payload, "ActiveConstraintRecord", 1)
            constraints[ordinal] = semantic
        if entry.identity.kind != "ReasoningProofArenaRef":
            continue
        cie, category, ordinal = fields(entry.identity, entry.identity.kind, 3)
        if (
            snapshot is None
            or cie != key(snapshot.cie.identity)
            or category != entry.category
            or category
            not in (
                "DERIVATION_WITNESS",
                "CLEARANCE_RECORD",
                "CONSTRAINT_FINDING",
                "STAGING_RECORD",
            )
            or type(ordinal) is not int
            or not 0 <= ordinal < 128
            or ordinal in proof_entries
        ):
            raise ValueError("foreign/duplicate/noncanonical proof reference")
        proof_entries[ordinal] = entry
    support_refs, clearance_refs = {}, {}
    resolving = set()

    def assertion_ref(identity):
        if identity.kind in (
            "AssertionArenaRef",
            "SeedAssertionArenaRef",
            "DerivedAssertionArenaRef",
        ):
            return d("ReasoningAssertionReference", identity.kind, identity.values[-1])
        return d("ReasoningAssertionReference", "ExactExistingAssertion", key(identity))

    def modal_ref(identity):
        return d("ModalProofReference", *identity.values[1:])

    for entry in entries:
        if entry.category == "ASSERTION":
            asks[key(assertion_ref(entry.identity))] = entry.payload.values[0]
        if entry.category in CATEGORIES:
            ask, source = assertion(entry.category, entry.payload)
            sources[key(modal_ref(entry.identity))] = source
            scopes[key(modal_ref(entry.identity))] = ask.scope
            for root in ask.dependencies:
                roots.setdefault(key(root), (entry.identity, root))
    ask_refs = {
        key(ask): assertion_ref(entry_identity)
        for entry_identity in (e.identity for e in entries if e.category == "ASSERTION")
        for ask in (asks[key(assertion_ref(entry_identity))],)
    }
    root_refs = {
        k: d("ModalDependencyReference", modal_ref(ref))
        for k, (ref, _) in roots.items()
    }
    scope_refs = {
        key(scope): d("ModalScopeReference", ref)
        for entry in reversed(entries)
        if entry.category in CATEGORIES
        for ref in (modal_ref(entry.identity),)
        for scope in (scopes[key(ref)],)
    }
    constraint_refs = {
        key(semantic): d("ReasoningConstraintReference", ordinal)
        for ordinal, semantic in constraints.items()
    }
    key_refs = {
        k: d("ReasoningCanonicalKeyReference", ref)
        for k, ref in (
            *ask_refs.items(),
            *root_refs.items(),
            *scope_refs.items(),
            *constraint_refs.items(),
        )
    }
    key_refs.update(
        (key(source), d("ModalSourceCanonicalKeyReference", modal_ref(e.identity)))
        for e in entries
        if e.category in CATEGORIES
        for source in (sources[key(modal_ref(e.identity))],)
    )

    def walk(value, inverse=False, depth=0):
        if depth > 48:
            raise ValueError("modal proof depth bound")
        if inverse and type(value) is CanonicalDescriptor:
            if value.kind == "ReasoningConstraintReference":
                (ordinal,) = fields(value, value.kind, 1)
                if type(ordinal) is not int or ordinal not in constraints:
                    raise ValueError("unknown constraint reference")
                return constraints[ordinal]
            if value.kind in (
                "PreviousModalDerivationReference",
                "ReasoningClearanceReference",
            ):
                (ordinal,) = fields(value, value.kind, 1)
                if (
                    type(ordinal) is not int
                    or ordinal not in proof_entries
                    or ordinal in resolving
                ):
                    raise ValueError("unknown/cyclic proof reference")
                entry = proof_entries[ordinal]
                cie, data = fields(entry.payload, "ReferencedReasoningPayload", 2)
                if cie != key(snapshot.cie.identity):
                    raise ValueError("foreign proof source")
                resolving.add(ordinal)
                try:
                    record = walk(data, True, depth + 1)
                finally:
                    resolving.remove(ordinal)
                if value.kind == "PreviousModalDerivationReference":
                    fields(record, "DerivationLineage", 6)
                    return d(
                        "ModalDerivationSupportReference",
                        record.values[1],
                        record.values[2],
                    )
                fields(record, "ConstraintClearanceView", 6)
                return d("ConstraintGateWitness", record.values[0].values[0])
            if value.kind == "ReferencedConstraintUse":
                sr, schema, roles, profile, aec = walk(value.values, True, depth + 1)
                operation = d("ConsumerOperationIdentity", sr, schema, roles, aec)
                return d("ConstraintUseBinding", operation, schema, roles, profile, aec)
            if value.kind == "ReferencedConstraintClearance":
                use, env, scope, coverage = walk(value.values, True, depth + 1)
                fields(use, "ConstraintUseBinding", 5)
                return d(
                    "ConstraintClearanceView",
                    use,
                    env,
                    use.values[4],
                    scope,
                    use.values[0].values[0],
                    coverage,
                )
            if value.kind == "ReasoningAssertionReference":
                fields(value, value.kind, 2)
                if key(value) not in asks:
                    raise ValueError("unknown/foreign assertion reference")
                return asks[key(value)]
            if value.kind == "ModalDependencyReference":
                (ref,) = fields(value, value.kind, 1)
                matching = [
                    root
                    for identity, root in roots.values()
                    if modal_ref(identity) == ref
                ]
                if len(matching) != 1:
                    raise ValueError("unknown/ambiguous modal origin")
                return matching[0]
            if value.kind == "ModalSourceCanonicalKeyReference":
                (ref,) = fields(value, value.kind, 1)
                if key(ref) not in sources:
                    raise ValueError("unknown modal occurrence")
                return key(sources[key(ref)])
            if value.kind == "ModalScopeReference":
                (ref,) = fields(value, value.kind, 1)
                if key(ref) not in scopes:
                    raise ValueError("unknown modal scope")
                return scopes[key(ref)]
            if value.kind == "ReasoningCanonicalKeyReference":
                (ref,) = fields(value, value.kind, 1)
                return key(walk(ref, True, depth + 1))
        if not inverse:
            if type(value) is CanonicalDescriptor:
                if (
                    value.kind == "ConstraintSemanticKey"
                    and key(value) in constraint_refs
                ):
                    return constraint_refs[key(value)]
                if (
                    value.kind == "ModalDerivationSupportReference"
                    and key(value.values) in support_refs
                ):
                    return support_refs[key(value.values)]
                if (
                    value.kind == "ConstraintGateWitness"
                    and key(value.values[0]) in clearance_refs
                ):
                    return clearance_refs[key(value.values[0])]
            if (
                type(value) is CanonicalDescriptor
                and value.kind == "ConstraintUseBinding"
            ):
                operation, schema, roles, profile, aec = fields(value, value.kind, 5)
                sr, op_schema, op_roles, op_aec = fields(
                    operation, "ConsumerOperationIdentity", 4
                )
                if (schema, roles, aec) == (op_schema, op_roles, op_aec):
                    return d(
                        "ReferencedConstraintUse",
                        *walk((sr, schema, roles, profile, aec), False, depth + 1),
                    )
            if (
                type(value) is CanonicalDescriptor
                and value.kind == "ConstraintClearanceView"
            ):
                use, env, aec, scope, sr, coverage = fields(value, value.kind, 6)
                if aec == use.values[4] and sr == use.values[0].values[0]:
                    return d(
                        "ReferencedConstraintClearance",
                        *walk((use, env, scope, coverage), False, depth + 1),
                    )
            if type(value) is AssertionSemanticKey and key(value) in ask_refs:
                return ask_refs[key(value)]
            if type(value) is DependencyRootIdentity and key(value) in root_refs:
                return root_refs[key(value)]
            if type(value) is ScopeIdentity and key(value) in scope_refs:
                return scope_refs[key(value)]
            if type(value) is bytes and value in key_refs:
                return key_refs[value]
        if type(value) is tuple:
            if len(value) > 128:
                raise ValueError("modal proof outer bound")
            return tuple(walk(v, inverse, depth + 1) for v in value)
        if type(value) is CanonicalDescriptor:
            return d(value.kind, *walk(value.values, inverse, depth + 1))
        return value

    # Derivation/context KEY fields used by the frozen lineage contracts are
    # exact canonical images, not hashes. Replace those repeated images too.
    def collect(value):
        if type(value) is CanonicalDescriptor:
            if value.kind in ("DerivationKey", "DerivationContextReference"):
                key_refs[key(value)] = d("ReasoningCanonicalKeyReference", walk(value))
            for child in value.values:
                collect(child)
        elif type(value) is tuple:
            for child in value:
                collect(child)

    for entry in entries:
        if (
            entry.category == "DERIVATION_WITNESS"
            and entry.payload.kind == "DerivationLineage"
        ):
            collect(entry.payload)
    for ordinal, entry in sorted(proof_entries.items()):
        cie, data = fields(entry.payload, "ReferencedReasoningPayload", 2)
        if cie != key(snapshot.cie.identity):
            raise ValueError("foreign proof source")
        record = walk(data, True)
        if entry.category == "DERIVATION_WITNESS":
            fields(record, "DerivationLineage", 6)
            support_refs[key(record.values[1:3])] = d(
                "PreviousModalDerivationReference", ordinal
            )
            collect(record)
        elif entry.category == "CLEARANCE_RECORD":
            fields(record, "ConstraintClearanceView", 6)
            clearance_refs[key(record.values[0].values[0])] = d(
                "ReasoningClearanceReference", ordinal
            )
    return walk, collect


def normalize_frontier(frontier, entries, snapshot):
    if not any(e.category in CATEGORIES for e in entries):
        return frontier
    walk, _ = proof_codec(entries, snapshot)
    return d("ReferencedReasoningFrontier", key(snapshot.cie.identity), walk(frontier))


def resolve_frontier(frontier, entries, snapshot):
    if frontier.kind != "ReferencedReasoningFrontier":
        return frontier
    walk, _ = proof_codec(entries, snapshot)
    cie, data = fields(frontier, "ReferencedReasoningFrontier", 2)
    if cie != key(snapshot.cie.identity):
        raise ValueError("foreign frontier references")
    return walk(data, True)


def normalize_proofs(output, entries, snapshot):
    if not any(e.category in CATEGORIES for e in entries):
        return output
    known = {
        key(e.payload.values[0]): e.identity
        for e in entries
        if e.category == "ASSERTION"
    }
    count = sum(e.identity.kind == "DerivedAssertionArenaRef" for e in entries)
    new = {
        key(e.payload.values[0]): e
        for e in output
        if e.category == "ASSERTION" and key(e.payload.values[0]) not in known
    }
    for k in sorted(new):
        known[k] = d("DerivedAssertionArenaRef", key(snapshot.cie.identity), count)
        count += 1
    assertions = tuple(
        ArenaEntry("ASSERTION", known[key(e.payload.values[0])], e.payload)
        for e in output
        if e.category == "ASSERTION"
    )
    walk, collect = proof_codec((*entries, *assertions), snapshot)
    for entry in output:
        if entry.category != "ASSERTION":
            collect(entry.payload)
    # Proof identities are administrative Arena locations. The complete
    # semantic proof/use identity remains in the resolved payload. Allocate
    # from the complete canonical group, never worker completion order.
    existing = {
        key((e.category, e.payload)): e.identity
        for e in entries
        if e.identity.kind == "ReasoningProofArenaRef"
    }
    proof_payloads = {
        key((e.category, walk(e.payload))): (e.category, walk(e.payload), e.payload)
        for e in output
        if e.category != "ASSERTION"
    }
    count = len(existing)
    proofs = []
    ordered_originals = []
    for k in sorted(proof_payloads):
        category, payload, original = proof_payloads[k]
        wrapped = d("ReferencedReasoningPayload", key(snapshot.cie.identity), payload)
        identity = existing.get(key((category, wrapped)))
        if identity is None:
            if count >= 128:
                raise ValueError("reasoning proof outer bound")
            identity = d(
                "ReasoningProofArenaRef", key(snapshot.cie.identity), category, count
            )
            count += 1
        proofs.append(ArenaEntry(category, identity, wrapped))
        ordered_originals.append(original)
    # The whole group is available before publication. Replace repeated exact
    # gate/support objects with local links to their COMPLETE proof entries.
    walk, collect = proof_codec((*entries, *assertions, *proofs), snapshot)
    for entry in output:
        if entry.category != "ASSERTION":
            collect(entry.payload)
    # Pair the first-pass canonical payload ordering with its allocated refs;
    # it is frozen before this factoring pass (not arrival/completion ordered).
    return tuple(assertions) + tuple(
        ArenaEntry(
            e.category,
            e.identity,
            d("ReferencedReasoningPayload", key(snapshot.cie.identity), walk(original)),
        )
        for e, original in zip(proofs, ordered_originals, strict=True)
    )


def resolve_payload(entry, entries, snapshot):
    if entry.identity.kind == "ReasoningProofArenaRef":
        cie, category, ordinal = fields(entry.identity, entry.identity.kind, 3)
        if (
            snapshot is None
            or cie != key(snapshot.cie.identity)
            or category != entry.category
            or type(ordinal) is not int
            or not 0 <= ordinal < 128
            or entry.payload.kind != "ReferencedReasoningPayload"
        ):
            raise ValueError("foreign/noncanonical proof reference")
    if entry.payload.kind != "ReferencedReasoningPayload":
        return entry.payload
    walk, _ = proof_codec(entries, snapshot)
    cie, data = fields(entry.payload, "ReferencedReasoningPayload", 2)
    if cie != key(snapshot.cie.identity):
        raise ValueError("foreign proof references")
    return walk(data, True)
