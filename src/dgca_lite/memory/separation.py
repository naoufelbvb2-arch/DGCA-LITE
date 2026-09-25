"""Root-witness pattern separation for Assembly Sources."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping

from .types import (
    FamilyID,
    SeparationFamily,
    SeparationResult,
    SourceID,
    canonical_source_key,
)


def separate_sources(
    source_seeds: Mapping[int, frozenset[int]],
    source_members: Mapping[int, frozenset[int]],
    authorized_ids: frozenset[int],
) -> SeparationResult:
    """Build direct overlap families and strict witness dominance metadata."""
    assembly_ids = tuple(sorted(source_seeds))
    if set(assembly_ids) != set(source_members):
        raise ValueError("source seed/member domains must match")

    adjacency = {assembly_id: set() for assembly_id in assembly_ids}
    for index, left in enumerate(assembly_ids):
        for right in assembly_ids[index + 1 :]:
            if source_seeds[left] & source_seeds[right]:
                adjacency[left].add(right)
                adjacency[right].add(left)

    witnesses = {
        assembly_id: frozenset(source_members[assembly_id] & authorized_ids)
        for assembly_id in assembly_ids
    }
    dominance: set[tuple[int, int]] = set()
    for left in assembly_ids:
        for right in sorted(adjacency[left]):
            if witnesses[left] > witnesses[right]:
                dominance.add((left, right))

    families: list[SeparationFamily] = []
    unseen = set(assembly_ids)
    while unseen:
        first = min(unseen)
        component: set[int] = set()
        queue = deque([first])
        unseen.remove(first)
        while queue:
            current = queue.popleft()
            component.add(current)
            for neighbor in sorted(adjacency[current]):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
        ordered = tuple(sorted(component))
        source_ids = tuple(SourceID.assembly(item) for item in ordered)
        dominated = {target for source, target in dominance if source in component}
        undominated = tuple(
            SourceID.assembly(item) for item in ordered if item not in dominated
        )
        families.append(
            SeparationFamily(FamilyID(ordered), source_ids, undominated)
        )

    witness_records = tuple(
        (SourceID.assembly(assembly_id), tuple(sorted(witnesses[assembly_id])))
        for assembly_id in assembly_ids
    )
    dominance_records = tuple(
        sorted(
            (
                (SourceID.assembly(source), SourceID.assembly(target))
                for source, target in dominance
            ),
            key=lambda pair: (
                canonical_source_key(pair[0]),
                canonical_source_key(pair[1]),
            ),
        )
    )
    return SeparationResult(
        tuple(sorted(families, key=lambda item: item.family_id.assembly_ids)),
        witness_records,
        dominance_records,
    )
