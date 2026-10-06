"""Three frozen detection families; no truth arbitration or live gate handles."""

from itertools import combinations

from ..contracts import ConstraintFamily
from ..identity import ConstraintEnvironmentBinding, canonical_dependencies
from ..types import AssertionBasis
from .assertions import key
from .fab import d, validate


def environment(snapshot, active_keys):
    return ConstraintEnvironmentBinding(
        snapshot.cie,
        tuple(d("ConstraintSchema", f) for f in ConstraintFamily),
        active_keys,
        snapshot.cie.environment.l3_policy,
    )


def environment_ref(snapshot, active_keys):
    return d(
        "ConstraintEnvironmentReference",
        key(snapshot.cie.identity),
        tuple(d("ConstraintSchema", f) for f in ConstraintFamily),
        tuple(key(v) for v in active_keys),
    )


def aec_ref(aec):
    return d(
        "AECReference",
        key(aec.branch_identity),
        tuple(key(v) for v in aec.dependencies),
        key(aec.cie.identity),
    )


def snapshot_ref(snapshot):
    return d(
        "SnapshotReference",
        key(snapshot.cie.identity),
        snapshot.arena_version,
        snapshot.round_identity,
    )


def profile(schema_identity):
    # Both consumers may carry arbitrary lawful ordinary ground assertions.
    # Unknown interactions are therefore included, never optimistically omitted.
    return d("ConstraintPreflightProfile", schema_identity, tuple(ConstraintFamily))


def interaction_envelope(family):
    if type(family) is not ConstraintFamily:
        raise TypeError("closed constraint family required")
    return d(
        "ConstraintInteractionEnvelope",
        family,
        "EXACT_GROUND_SAME_SCOPE",
        "DEPENDENCY_SUBSET",
        "EXPLICIT_GROUND_STATE_ONLY"
        if family is ConstraintFamily.EXPLICIT_MUTUAL_EXCLUSION
        else "DECLARED_GROUND_ROLE_ONLY",
    )


def consumer_envelope(schema_identity):
    # An ordinary premise can be any lawful ground proposition. Both builtins
    # therefore conservatively interact with every frozen constraint family.
    return d(
        "ConsumerPremiseEnvelope",
        schema_identity,
        "GROUND_ASSERTIONS",
        "UNKNOWN_INCLUDED",
    )


def no_interaction_certificate(schema_identity):
    consumer_envelope(schema_identity)
    raise ValueError(
        "neither generic v0 consumer has a NoConstraintInteractionCertificate"
    )


def validate_profile(families, certificate=None):
    if type(families) is not tuple or len(families) > 3:
        raise ValueError("closed profile outer bound")
    if set(families) != set(ConstraintFamily) or certificate is not None:
        raise ValueError("all three families are relevant; no N/A certificate")
    return d("ConstraintPreflightProfileFamilies", tuple(ConstraintFamily))


def use_binding(schema_identity, roles, aec, snapshot):
    operation = d(
        "ConsumerOperationIdentity",
        snapshot_ref(snapshot),
        schema_identity,
        tuple((role, key(ask)) for role, ask in roles),
        aec_ref(aec),
    )
    return d(
        "ConstraintUseBinding",
        operation,
        schema_identity,
        tuple((role, key(ask)) for role, ask in roles),
        profile(schema_identity),
        aec_ref(aec),
    )


def participant_binding(content):
    validate(content)
    node = content.descriptor
    return node.values[0] if node.kind == "GroundState" else None


def state_identity_of(content):
    validate(content)
    node = content.descriptor
    return node.values[1] if node.kind == "GroundState" else None


def preflight(
    schema_identity,
    roles,
    aec,
    snapshot,
    constraints,
    policy,
    *,
    mode="EXISTS_INCOMPATIBILITY",
):
    if mode not in ("EXISTS_INCOMPATIBILITY", "ENUMERATE_ALL_INCOMPATIBILITIES"):
        raise ValueError("unknown constraint query mode")
    if type(roles) is not tuple or not 1 <= len(roles) <= policy.max_assertions:
        raise ValueError("constraint participant outer bound")
    if type(constraints) is not dict or len(constraints) > policy.max_sources:
        raise ValueError("active constraint outer bound")
    if aec.cie != snapshot.cie:
        raise ValueError("stale constraint context")
    validate_profile(tuple(ConstraintFamily))
    active_keys = tuple(constraints[k].values[0] for k in sorted(constraints))
    env = environment_ref(snapshot, active_keys)
    use = use_binding(schema_identity, roles, aec, snapshot)
    assertions = tuple(ask for _, ask in roles)
    scope = assertions[0].scope
    if any(
        a.scope != scope or not set(a.dependencies) <= set(aec.dependencies)
        for a in assertions
    ):
        raise ValueError("scope/AEC inapplicable participants")
    # Entire required frontier, independent of budget and finding outcomes.
    frontier = []
    for record in constraints.values():
        semantic = record.values[0]
        content, basis, c_scope, dependencies = semantic.values
        validate(content)
        if basis not in (AssertionBasis.FORMAL_GIVEN, AssertionBasis.FORMAL_ASSUMPTION):
            raise ValueError("constraint activation cannot be promoted")
        if c_scope != scope or not set(dependencies) <= set(aec.dependencies):
            continue
        node = content.descriptor
        if node.kind == "FormalNegation":
            candidates = tuple((a,) for a in assertions)
            family = ConstraintFamily.GROUND_NEGATION_CONFLICT
        elif node.kind == "MutuallyExclusive":
            # Only the explicitly declared participant-state role interacts.
            # Do not infer roles from ordinary relations, assignments or atoms.
            eligible = tuple(
                a for a in assertions if a.content.descriptor.kind == "GroundState"
            )
            candidates = tuple(combinations(eligible, 2))
            family = ConstraintFamily.EXPLICIT_MUTUAL_EXCLUSION
        else:
            candidates = tuple(combinations(assertions, 2))
            family = ConstraintFamily.SINGLE_VALUED_SLOT_CONFLICT
        if len(frontier) + len(candidates) > policy.max_checks:
            return d("CONSTRAINT_CHECK_INCOMPLETE", use, env)
        for participants in candidates:
            if len(participants) == 2:
                participants = tuple(sorted(participants, key=key))
            check = d(
                "ConstraintCheck",
                family,
                key(semantic),
                tuple(key(a) for a in participants),
            )
            frontier.append((key(check), check, participants, semantic))
    if len(frontier) > policy.max_checks:
        return d("CONSTRAINT_CHECK_INCOMPLETE", use, env)
    frontier.sort(key=lambda v: v[0])
    findings = []
    for _, check, participants, semantic in frontier:
        content, _, _, dependencies = semantic.values
        node = content.descriptor
        conflict = False
        if node.kind == "FormalNegation":
            conflict = participants[0].content == node.values[0]
        elif node.kind == "MutuallyExclusive":
            conflict = {key(state_identity_of(a.content)) for a in participants} == {
                key(v) for v in node.values
            } and participant_binding(participants[0].content) == participant_binding(
                participants[1].content
            )
        elif all(a.content.descriptor.kind == "Assign" for a in participants):
            left, right = (a.content.descriptor.values for a in participants)
            conflict = (
                left[:2] == right[:2]
                and left[1] == node.values[0]
                and key(left[2]) != key(right[2])
            )
        if conflict:
            roots = canonical_dependencies(
                tuple(dependencies)
                + tuple(root for a in participants for root in a.dependencies)
            )
            family = check.values[0]
            bound = tuple(
                (f"participant_{i}", key(a)) for i, a in enumerate(participants)
            )
            identity = d(
                "FindingID",
                d("ConstraintSchema", family),
                env,
                scope,
                bound,
                (key(semantic),),
                tuple(key(r) for r in roots),
            )
            findings.append(
                d(
                    "IncompatibilityView",
                    identity,
                    check,
                    bound,
                    (key(semantic),),
                    scope,
                    roots,
                    use,
                    env,
                    snapshot_ref(snapshot),
                )
            )
    required = tuple(v[1] for v in frontier)
    coverage = d("ConstraintCoverageLedger", required, required, True)
    if findings:
        # Preserve CHECK frontier order, not result sorting/completion order.
        selected = (
            tuple(findings[:1]) if mode == "EXISTS_INCOMPATIBILITY" else tuple(findings)
        )
        return d("CONSTRAINT_BLOCKED", use, env, selected, coverage)
    clearance = d(
        "ConstraintClearanceView",
        use,
        env,
        aec_ref(aec),
        scope,
        snapshot_ref(snapshot),
        coverage,
    )
    return d("CONSTRAINT_CLEARED", clearance)


def gate_witness(result):
    if result.kind != "CONSTRAINT_CLEARED":
        raise ValueError("incomplete/blocked is not clearance")
    # Exact same-arena reference; the complete clearance is published with the
    # lineage in one effect, never reconstructed as authority from this value.
    return d("ConstraintGateWitness", result.values[0].values[0].values[0])
