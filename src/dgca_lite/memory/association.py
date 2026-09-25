"""One-hop directed ASSOCIATIVE retrieval from finalized source activity."""

from __future__ import annotations

from math import prod

from dgca_lite.model import SynapseScope, SynapseState

from .types import (
    AssociationResult,
    BranchID,
    DirectHit,
    FrozenParameters,
    ProvenanceKind,
    RetrievalProvenance,
    RetrievalSnapshot,
    SeedState,
    SeedValue,
    SourceActivity,
)


def retrieve_associations(
    activities: tuple[SourceActivity, ...],
    snapshot: RetrievalSnapshot,
    parameters: FrozenParameters,
) -> AssociationResult:
    """Apply exactly one forward ASSOCIATIVE traversal for every SourceID."""
    outgoing = snapshot.associative_by_source()
    memberships = snapshot.membership_map()
    assemblies = snapshot.assembly_map()
    direct_hits: list[DirectHit] = []
    branch_seeds: list[tuple[BranchID, SeedState]] = []

    for activity in sorted(activities, key=lambda item: item.source_id.canonical_key()):
        drives = dict(activity.drives)
        exact_one = dict(activity.exact_one)
        if set(activity.cells) != set(drives) or set(activity.cells) != set(exact_one):
            raise ValueError("Source activity maps must exactly cover source Cells")

        contributors: dict[int, list[tuple[int, float]]] = {}
        for source in sorted(activity.cells):
            for edge in outgoing.get(source, ()):
                if (
                    edge.scope is not SynapseScope.ASSOCIATIVE
                    or edge.state is not SynapseState.CONSOLIDATED
                ):
                    continue
                contributors.setdefault(edge.target_id, []).append(
                    (source, edge.quality(parameters.E_max))
                )

        source_hits: dict[int, DirectHit] = {}
        for target in sorted(contributors):
            ordered = tuple(sorted(contributors[target], key=lambda item: item[0]))
            residual = prod(
                1.0 - drives[source] * quality for source, quality in ordered
            )
            exact = any(
                exact_one[source] and quality == 1.0 for source, quality in ordered
            )
            eligible = (
                exact
                if parameters.theta_AR == 1.0
                else residual <= 1.0 - parameters.theta_AR
            )
            if not eligible:
                continue
            hit = DirectHit(
                activity.source_id,
                target,
                1.0 if exact else 1.0 - residual,
                exact,
                tuple(source for source, _ in ordered),
                RetrievalProvenance(
                    ProvenanceKind.ASSOCIATIVE,
                    activity.source_id,
                    target,
                    supporters=tuple(source for source, _ in ordered),
                ),
            )
            source_hits[target] = hit
            direct_hits.append(hit)

        target_assemblies = sorted(
            {
                assembly_id
                for target in source_hits
                for assembly_id in memberships.get(target, ())
            }
        )
        for assembly_id in target_assemblies:
            assembly = assemblies.get(assembly_id)
            if assembly is None:
                raise ValueError("captured target membership is incomplete")
            seed_values = {
                target: SeedValue(source_hits[target].drive, source_hits[target].exact_one)
                for target in assembly.members
                if target in source_hits
            }
            if seed_values:
                branch_seeds.append(
                    (
                        BranchID(activity.source_id, assembly_id),
                        SeedState.from_dict(seed_values),
                    )
                )

    return AssociationResult(
        tuple(sorted(direct_hits, key=lambda item: item.canonical_key())),
        tuple(
            sorted(branch_seeds, key=lambda item: item[0].canonical_key())
        ),
    )
