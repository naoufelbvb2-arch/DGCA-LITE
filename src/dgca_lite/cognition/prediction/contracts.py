"""Closed production Prediction work/effect vocabulary, no caller callbacks."""

from enum import Enum

from .targets import d


class PredictionOperation(Enum):
    PROJECT = "PREDICTION_PROJECT"
    CAPTURE = "PREDICTION_CAPTURE"
    EVALUATE = "PREDICTION_EVALUATE_AND_RECORD"
    SEAL = "PREDICTION_SEAL_AND_DELEGATE"


def contract(operation, phase, offset=0):
    from ..operation import (
        AuthorityRequirement,
        BudgetClass,
        OperationContract,
        PublicationPolicy,
        ResourceEnvelope,
    )
    from ..types import WorkEffectClass

    if type(operation) is not PredictionOperation:
        raise TypeError("fixed Prediction operation required")
    delegated = operation in (PredictionOperation.CAPTURE, PredictionOperation.EVALUATE)
    requirements = (
        (
            AuthorityRequirement.ENVIRONMENT_CURRENT,
            AuthorityRequirement.FORECAST_CURRENT,
        )
        if delegated
        else (
            AuthorityRequirement.CIE_CURRENT,
            AuthorityRequirement.ENVIRONMENT_CURRENT,
            AuthorityRequirement.INVOCATION_CURRENT,
            AuthorityRequirement.SNAPSHOT_CURRENT,
        )
    )
    pure = operation in (PredictionOperation.PROJECT, PredictionOperation.CAPTURE)
    return OperationContract(
        operation,
        BudgetClass.CHARGED_WORK,
        WorkEffectClass.PURE_COMPUTE if pure else WorkEffectClass.OPERATIONAL_EFFECT,
        requirements,
        d("PredictionWorkClass", phase, offset),
        ResourceEnvelope(1, 4096, 262144),
        PublicationPolicy.STAGED_IMMUTABLE_ONLY
        if pure
        else PublicationPolicy.SEPARATE_EFFECT_GATE_REQUIRED,
    )


def compact_retrieval(result, policy, *, targets):
    from dgca_lite.memory.types import RetrievalResult

    from .targets import cell_set

    if type(result) is not RetrievalResult:
        raise ValueError("failed trusted capture")
    if (
        type(result.sources) is not tuple
        or len(result.sources)
        > policy.max_capture_assemblies + policy.max_capture_cells
    ):
        raise ValueError("source capture outer bound")
    cell_set(
        result.root.authorized_witnesses,
        maximum=policy.max_capture_cells,
        nonempty=False,
    )
    # Bounds of every lane precede member traversal of any lane.
    for source in result.sources:
        for values in (source.root_authorized_witnesses, source.reconstructed_cells):
            if type(values) is not tuple or len(values) > policy.max_capture_cells:
                raise ValueError("source lane outer bound")
    lanes = []
    for source in result.sources:
        cell_set(
            source.root_authorized_witnesses,
            maximum=policy.max_capture_cells,
            nonempty=False,
        )
        cell_set(
            source.reconstructed_cells, maximum=policy.max_capture_cells, nonempty=False
        )
        lanes.append(
            (
                source.source_id.as_tuple(),
                source.root_authorized_witnesses,
                source.reconstructed_cells,
            )
        )
    raw_targets = []
    if targets:
        if (
            type(result.branches) is not tuple
            or type(result.direct_hits) is not tuple
            or len(result.branches) + len(result.direct_hits) > policy.max_targets
        ):
            raise ValueError("complete target discovery outer bound")
        for branch in result.branches:
            if (
                type(branch.target_seed_state.entries) is not tuple
                or len(branch.target_seed_state.entries) > 256
            ):
                raise ValueError("branch seed outer bound")
            cell_set(branch.reconstructed_target_cells)
            raw_targets.append(
                (
                    "BRANCH",
                    branch.branch_id.target_assembly_id,
                    branch.branch_id.source_id.as_tuple(),
                    tuple(cid for cid, _ in branch.target_seed_state.entries),
                    branch.reconstructed_target_cells,
                )
            )
        for hit in result.direct_hits:
            raw_targets.append(("ATOM", hit.cell_id, hit.source_id.as_tuple()))
    return d(
        "PredictionRetrievalCapture",
        result.root.authorized_witnesses,
        tuple(lanes),
        tuple(raw_targets),
    )


def projection_targets(raw_targets):
    from ..serialization import canonical_identity_bytes
    from .targets import AtomicCarrier, BranchPattern

    if type(raw_targets) is not tuple or len(raw_targets) > 256:
        raise ValueError("target input outer bound")
    for row in raw_targets:
        if type(row) is not tuple or len(row) not in (3, 5):
            raise ValueError("closed target row required")
        if type(row[0]) is not str or row[0] not in ("BRANCH", "ATOM"):
            raise ValueError("unknown target row")
        expected = 5 if row[0] == "BRANCH" else 3
        if len(row) != expected or type(row[2]) is not tuple or len(row[2]) != 2:
            raise ValueError("closed target/source row required")
        if expected == 5 and any(
            type(v) is not tuple or len(v) > 256 for v in (row[3], row[4])
        ):
            raise ValueError("target row outer bound")
    result, covered = [], set()
    for row in raw_targets:
        if row[0] == "BRANCH":
            _, number, source, anchors, cells = row
            sid = d("PredictionSourceIdentity", *source)
            result.append(
                BranchPattern(number, anchors, cells, sid).canonical_descriptor()
            )
            covered.update((source, cid) for cid in anchors)
    for row in raw_targets:
        if row[0] == "ATOM":
            _, cid, source = row
            if (source, cid) not in covered:
                result.append(
                    AtomicCarrier(
                        cid, d("PredictionSourceIdentity", *source)
                    ).canonical_descriptor()
                )
    keyed = {canonical_identity_bytes(t): t for t in result}
    return tuple(keyed[k] for k in sorted(keyed))


def compute(operation, data):
    from ..ingress import _snapshot
    from .projection import ConditionalProjectionView

    if operation is PredictionOperation.PROJECT:
        origin_class, snapshot, capture, provenance = data.values
        return ConditionalProjectionView(
            origin_class, snapshot, projection_targets(capture.values[2]), provenance
        ).canonical_descriptor()
    if operation is PredictionOperation.CAPTURE:
        return _snapshot(data)
    raise TypeError("effect operation is not a pure worker")
