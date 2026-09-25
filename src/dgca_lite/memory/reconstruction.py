"""Canonical lane-scoped pattern reconstruction P(G, eta)."""

from __future__ import annotations

from math import prod

from dgca_lite.model import SynapseState

from .types import (
    CompletionStep,
    FrozenParameters,
    ReciprocalLink,
    ReconstructionGraph,
    ReconstructionLane,
    RetrievalSnapshot,
    SeedState,
)


def build_reconstruction_graph(
    snapshot: RetrievalSnapshot,
    assembly_id: int,
    parameters: FrozenParameters,
) -> ReconstructionGraph:
    """Build one known Assembly graph; this performs no candidate discovery."""
    assembly = snapshot.assembly_map().get(assembly_id)
    if assembly is None:
        raise ValueError("unknown captured Assembly")
    edges = snapshot.local_edge_map()
    links: list[ReciprocalLink] = []
    for index, left in enumerate(assembly.members):
        for right in assembly.members[index + 1 :]:
            forward = edges.get((left, right))
            reverse = edges.get((right, left))
            quality = 0.0
            if (
                forward is not None
                and reverse is not None
                and forward.state is SynapseState.CONSOLIDATED
                and reverse.state is SynapseState.CONSOLIDATED
            ):
                quality = min(
                    forward.quality(parameters.E_max),
                    reverse.quality(parameters.E_max),
                )
            if quality >= parameters.theta_A:
                links.append(ReciprocalLink(left, right, quality))
    return ReconstructionGraph(assembly_id, assembly.members, tuple(links))


def reconstruct_pattern(
    graph: ReconstructionGraph,
    seed_state: SeedState,
    theta_pc: float,
) -> ReconstructionLane:
    """Compute P(G, eta) with synchronous admission and frozen drives."""
    members = set(graph.members)
    seeds = seed_state.to_dict()
    if not set(seeds) <= members:
        raise ValueError("Seed State domain must be a subset of the Assembly")
    if not 0.0 < theta_pc <= 1.0:
        raise ValueError("theta_pc must be in (0, 1]")

    adjacency: dict[int, dict[int, float]] = {member: {} for member in graph.members}
    for link in graph.links:
        adjacency[link.left][link.right] = link.quality
        adjacency[link.right][link.left] = link.quality

    admitted = set(seeds)
    drives = {cell_id: value.drive for cell_id, value in seeds.items()}
    exact_one = {cell_id: value.exact_one for cell_id, value in seeds.items()}
    rounds = {cell_id: 0 for cell_id in seeds}
    completion_steps: list[CompletionStep] = []

    frontier = {
        neighbor
        for cell_id in admitted
        for neighbor in adjacency[cell_id]
        if neighbor not in admitted
    }

    def semantic_residual(cell_id: int) -> float:
        supporters = sorted(admitted & set(adjacency[cell_id]))
        return prod(
            1.0 - drives[supporter] * adjacency[cell_id][supporter]
            for supporter in supporters
        )

    residual = {cell_id: semantic_residual(cell_id) for cell_id in frontier}
    round_index = 0
    while frontier:
        exact_new = {
            cell_id: any(
                exact_one[supporter]
                and adjacency[cell_id][supporter] == 1.0
                for supporter in sorted(admitted & set(adjacency[cell_id]))
            )
            for cell_id in frontier
        }
        if theta_pc == 1.0:
            proposals = {cell_id for cell_id in frontier if exact_new[cell_id]}
        else:
            residual_limit = 1.0 - theta_pc
            proposals = {
                cell_id for cell_id in frontier if residual[cell_id] <= residual_limit
            }
        if not proposals:
            break

        round_index += 1
        old_frontier = set(frontier)
        pre_round_admitted = set(admitted)
        for cell_id in sorted(proposals):
            supporters = tuple(sorted(pre_round_admitted & set(adjacency[cell_id])))
            is_exact = exact_new[cell_id]
            drives[cell_id] = 1.0 if is_exact else 1.0 - residual[cell_id]
            exact_one[cell_id] = is_exact
            rounds[cell_id] = round_index
            completion_steps.append(CompletionStep(cell_id, round_index, supporters))

        admitted.update(proposals)
        frontier = (
            old_frontier
            | {
                neighbor
                for cell_id in proposals
                for neighbor in adjacency[cell_id]
            }
        ) - admitted

        next_residual: dict[int, float] = {}
        for cell_id in sorted(frontier):
            if cell_id in old_frontier:
                incremental = prod(
                    1.0 - drives[supporter] * adjacency[cell_id][supporter]
                    for supporter in sorted(proposals & set(adjacency[cell_id]))
                )
                next_residual[cell_id] = residual[cell_id] * incremental
            else:
                next_residual[cell_id] = semantic_residual(cell_id)
        residual = next_residual

    return ReconstructionLane(
        tuple(sorted(admitted)),
        tuple(sorted(drives.items())),
        tuple(sorted(exact_one.items())),
        tuple(sorted(rounds.items())),
        tuple(completion_steps),
    )
