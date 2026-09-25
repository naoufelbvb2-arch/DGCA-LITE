"""Authority-free target reconstruction with no associative capability."""

from __future__ import annotations

from collections.abc import Mapping

from .reconstruction import reconstruct_pattern
from .types import (
    BranchID,
    BranchView,
    ProvenanceKind,
    ReconstructionGraph,
    RetrievalProvenance,
    SeedState,
)


def reconstruct_target_branches(
    branch_seeds: tuple[tuple[BranchID, SeedState], ...],
    target_graphs: Mapping[int, ReconstructionGraph],
    theta_pc: float,
) -> tuple[BranchView, ...]:
    """Run P(G, eta) for known targets; association is not in this API."""
    branches: list[BranchView] = []
    for branch_id, seed_state in sorted(
        branch_seeds, key=lambda item: item[0].canonical_key()
    ):
        graph = target_graphs.get(branch_id.target_assembly_id)
        if graph is None:
            raise ValueError("target branch references unknown captured Assembly")
        lane = reconstruct_pattern(graph, seed_state, theta_pc)
        provenance = tuple(
            RetrievalProvenance(
                ProvenanceKind.TARGET_COMPLETION,
                branch_id.source_id,
                step.cell_id,
                step.admission_round,
                branch_id.target_assembly_id,
                step.supporters,
            )
            for step in lane.completion_steps
        )
        branches.append(
            BranchView(
                branch_id,
                seed_state,
                lane.admitted_cells,
                lane.drives,
                lane.exact_one,
                lane.admission_rounds,
                provenance,
            )
        )
    return tuple(branches)
