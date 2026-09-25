"""Canonical Layer 2 session orchestration and atomic result publication."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace

from dgca_lite.engine import CoreEngine

from .acquisition import acquire
from .association import retrieve_associations
from .config import MemoryConfig
from .reconstruction import build_reconstruction_graph, reconstruct_pattern
from .separation import separate_sources
from .target import reconstruct_target_branches
from .types import (
    FailureCode,
    ProvenanceKind,
    ReconstructionGraph,
    RetrievalAbort,
    RetrievalDiagnostics,
    RetrievalFailure,
    RetrievalProvenance,
    RetrievalResult,
    RetrievalUniverse,
    RootView,
    SeedState,
    SeedValue,
    SourceActivity,
    SourceID,
    SourceView,
    canonical_source_key,
)

RetrievalOutcome = RetrievalResult | RetrievalFailure
DiagnosticsSink = Callable[[RetrievalDiagnostics], None]
GraphGetter = Callable[[int], ReconstructionGraph]


def _build_sources(
    universe: RetrievalUniverse,
    graph_for: GraphGetter,
) -> tuple[tuple[SourceView, ...], tuple[SourceActivity, ...]]:
    snapshot = universe.snapshot
    parameters = universe.parameters
    merged = universe.merged_cue.to_dict()
    seed_ids = set(universe.seed_ids)
    authorized = frozenset(universe.authorized_ids)
    memberships = snapshot.membership_map()
    assemblies = snapshot.assembly_map()

    source_assembly_ids = sorted(
        {
            assembly_id
            for cell_id in universe.seed_ids
            for assembly_id in memberships.get(cell_id, ())
        }
    )
    atomic_ids = tuple(
        cell_id for cell_id in universe.seed_ids if not memberships.get(cell_id, ())
    )

    views: list[SourceView] = []
    activities: list[SourceActivity] = []
    source_seeds: dict[int, frozenset[int]] = {}
    source_members: dict[int, frozenset[int]] = {}

    for assembly_id in source_assembly_ids:
        assembly = assemblies[assembly_id]
        assembly_seed_ids = tuple(sorted(seed_ids & set(assembly.members)))
        seed_state = SeedState.from_dict(
            {
                cell_id: SeedValue(merged[cell_id], merged[cell_id] == 1.0)
                for cell_id in assembly_seed_ids
            }
        )
        graph = graph_for(assembly_id)
        lane = reconstruct_pattern(graph, seed_state, parameters.theta_PC)
        source_id = SourceID.assembly(assembly_id)
        witnesses = tuple(sorted(set(assembly.members) & authorized))
        provenance = tuple(
            RetrievalProvenance(
                ProvenanceKind.SOURCE_COMPLETION,
                source_id,
                step.cell_id,
                step.admission_round,
                supporters=step.supporters,
            )
            for step in lane.completion_steps
        )
        views.append(
            SourceView(
                source_id,
                seed_state,
                witnesses,
                lane.admitted_cells,
                lane.drives,
                lane.exact_one,
                lane.admission_rounds,
                None,
                (),
                (),
                provenance,
            )
        )
        activities.append(
            SourceActivity(
                source_id, lane.admitted_cells, lane.drives, lane.exact_one
            )
        )
        source_seeds[assembly_id] = frozenset(assembly_seed_ids)
        source_members[assembly_id] = frozenset(assembly.members)

    separation = separate_sources(source_seeds, source_members, authorized)
    family_by_source = {
        source: family.family_id
        for family in separation.families
        for source in family.sources
    }
    dominates_by_source: dict[SourceID, list[SourceID]] = {}
    dominated_by_source: dict[SourceID, list[SourceID]] = {}
    for dominant, subordinate in separation.dominance:
        dominates_by_source.setdefault(dominant, []).append(subordinate)
        dominated_by_source.setdefault(subordinate, []).append(dominant)
    views = [
        replace(
            view,
            family_id=family_by_source[view.source_id],
            dominates=tuple(
                sorted(
                    dominates_by_source.get(view.source_id, ()),
                    key=canonical_source_key,
                )
            ),
            dominated_by=tuple(
                sorted(
                    dominated_by_source.get(view.source_id, ()),
                    key=canonical_source_key,
                )
            ),
        )
        for view in views
    ]

    for cell_id in atomic_ids:
        source_id = SourceID.atomic(cell_id)
        value = SeedValue(merged[cell_id], merged[cell_id] == 1.0)
        seed_state = SeedState.from_dict({cell_id: value})
        witnesses = (cell_id,) if cell_id in authorized else ()
        views.append(
            SourceView(
                source_id,
                seed_state,
                witnesses,
                (cell_id,),
                ((cell_id, value.drive),),
                ((cell_id, value.exact_one),),
                ((cell_id, 0),),
                None,
                (),
                (),
                (),
            )
        )
        activities.append(
            SourceActivity(
                source_id,
                (cell_id,),
                ((cell_id, value.drive),),
                ((cell_id, value.exact_one),),
            )
        )

    return (
        tuple(sorted(views, key=lambda item: item.source_id.canonical_key())),
        tuple(sorted(activities, key=lambda item: item.source_id.canonical_key())),
    )


def _validate_result(result: RetrievalResult) -> None:
    source_ids = tuple(item.source_id for item in result.sources)
    if source_ids != tuple(sorted(source_ids, key=canonical_source_key)):
        raise ValueError("noncanonical SourceView ordering")
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("duplicate SourceID")
    if result.root.authorized_witnesses != tuple(
        sorted(set(result.root.authorized_witnesses))
    ):
        raise ValueError("noncanonical authority set")
    if not set(result.root.authorized_witnesses) <= {
        cell_id for cell_id, _ in result.root.merged_cue.entries
    }:
        raise ValueError("authority must be a subset of merged cue")
    if result.direct_hits != tuple(
        sorted(result.direct_hits, key=lambda item: item.canonical_key())
    ):
        raise ValueError("noncanonical DirectHit ordering")
    if result.branches != tuple(
        sorted(result.branches, key=lambda item: item.branch_id.canonical_key())
    ):
        raise ValueError("noncanonical BranchView ordering")
    if any(branch.branch_id.source_id not in source_ids for branch in result.branches):
        raise ValueError("branch references unknown SourceID")


def _settle(
    universe: RetrievalUniverse, use_cache: bool
) -> tuple[RetrievalResult, RetrievalDiagnostics]:
    """Settle one closed universe.  This function has no Core parameter."""
    graph_cache: dict[int, ReconstructionGraph] = {}
    cache_hits = 0

    def graph_for(assembly_id: int) -> ReconstructionGraph:
        nonlocal cache_hits
        if use_cache and assembly_id in graph_cache:
            cache_hits += 1
            return graph_cache[assembly_id]
        graph = build_reconstruction_graph(
            universe.snapshot, assembly_id, universe.parameters
        )
        if use_cache:
            graph_cache[assembly_id] = graph
        return graph

    sources, activities = _build_sources(universe, graph_for)
    associations = retrieve_associations(
        activities, universe.snapshot, universe.parameters
    )
    target_ids = {
        branch_id.target_assembly_id for branch_id, _ in associations.branch_seeds
    }
    target_graphs = {
        assembly_id: graph_for(assembly_id)
        for assembly_id in sorted(target_ids)
    }
    branches = reconstruct_target_branches(
        associations.branch_seeds,
        target_graphs,
        universe.parameters.theta_PC,
    )
    result = RetrievalResult(
        RootView(
            universe.trusted_root_id,
            universe.merged_cue,
            universe.authorized_ids,
        ),
        sources,
        associations.direct_hits,
        branches,
    )
    _validate_result(result)
    diagnostics = RetrievalDiagnostics(
        snapshot_cells=len(universe.snapshot.cells),
        snapshot_assemblies=len(universe.snapshot.assemblies),
        snapshot_synapses=(
            len(universe.snapshot.local_synapses)
            + len(universe.snapshot.associative_synapses)
        ),
        source_count=len(sources),
        branch_count=len(branches),
        reconstruction_rounds=sum(
            max((round_index for _, round_index in source.admission_rounds), default=0)
            for source in sources
        )
        + sum(
            max((round_index for _, round_index in branch.admission_rounds), default=0)
            for branch in branches
        ),
        cache_hits=cache_hits,
    )
    return result, diagnostics


def _retrieve(
    core: CoreEngine,
    internal_cue: Mapping[int, float],
    memory_config: MemoryConfig,
    receipt: object | None,
    diagnostics_sink: DiagnosticsSink | None,
    use_cache: bool,
) -> RetrievalOutcome:
    try:
        universe = acquire(core, internal_cue, memory_config, receipt)
    except RetrievalAbort as error:
        return RetrievalFailure(error.code, error.detail)
    try:
        result, diagnostics = _settle(universe, use_cache)
    except Exception as error:  # noqa: BLE001 - canonical INTERNAL_ABORT boundary
        return RetrievalFailure(FailureCode.INTERNAL_ABORT, type(error).__name__)
    if diagnostics_sink is not None:
        try:
            diagnostics_sink(diagnostics)
        except Exception as error:  # noqa: BLE001 - diagnostics lack authority
            # Observability failure has no cognitive authority.
            _ = error
    return result


def retrieve_internal(
    core: CoreEngine,
    internal_cue: Mapping[int, float],
    memory_config: MemoryConfig | None = None,
    *,
    diagnostics_sink: DiagnosticsSink | None = None,
    use_cache: bool = False,
) -> RetrievalOutcome:
    return _retrieve(
        core,
        internal_cue,
        memory_config or MemoryConfig(),
        None,
        diagnostics_sink,
        use_cache,
    )


def retrieve_after_core_event(
    core: CoreEngine,
    receipt: object,
    internal_cue: Mapping[int, float] | None = None,
    memory_config: MemoryConfig | None = None,
    *,
    diagnostics_sink: DiagnosticsSink | None = None,
    use_cache: bool = False,
) -> RetrievalOutcome:
    return _retrieve(
        core,
        {} if internal_cue is None else internal_cue,
        memory_config or MemoryConfig(),
        receipt,
        diagnostics_sink,
        use_cache,
    )
