"""Event-driven Assembly MAINTAIN, GROW and FORM for Core v0.3."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import comb

from .activation import scoped_quality
from .config import CoreConfig
from .model import Assembly, Synapse, SynapseScope, SynapseState, TickSnapshot
from .topology import Topology

EdgeKey = tuple[int, int, SynapseScope]
Pair = tuple[int, int]


@dataclass(frozen=True, slots=True)
class AssemblyResult:
    upserts: Mapping[int, Assembly]
    deletes: frozenset[int]
    delta_local: frozenset[Pair]
    delta_support: frozenset[Pair]
    maintain_workset: tuple[int, ...]
    assembly_seeds: int
    bfs_visits: int
    grown: int
    formed: int


class StructuralOverlay:
    """Read-only Synaptic view after learning/resource arbitration."""

    def __init__(
        self,
        snapshot: TickSnapshot,
        upserts: Mapping[EdgeKey, Synapse],
        deletes: frozenset[EdgeKey],
    ) -> None:
        self.snapshot = snapshot
        self.upserts = upserts
        self.deletes = deletes

    def edge(self, source: int, target: int, scope: SynapseScope) -> Synapse | None:
        key = (source, target, scope)
        if key in self.deletes:
            return None
        changed = self.upserts.get(key)
        if changed is not None:
            return changed
        return self.snapshot.outgoing.get(source, {}).get((target, scope))

    def outgoing(self, source: int, scope: SynapseScope) -> tuple[Synapse, ...]:
        result = {
            (edge.target_id, edge.scope): edge
            for edge in self.snapshot.outgoing.get(source, {}).values()
            if edge.scope is scope and (source, edge.target_id, edge.scope) not in self.deletes
        }
        for (changed_source, target, changed_scope), edge in self.upserts.items():
            if changed_source == source and changed_scope is scope:
                result[(target, changed_scope)] = edge
        return tuple(result[key] for key in sorted(result, key=lambda item: item[0]))


def reciprocal_quality(
    source: int,
    target: int,
    scope: SynapseScope,
    edge_getter,
    config: CoreConfig,
) -> float:
    if scope not in (SynapseScope.LOCAL, SynapseScope.ASSOCIATIVE):
        return 0.0
    forward = edge_getter(source, target, scope)
    reverse = edge_getter(target, source, scope)
    if (
        forward is None
        or reverse is None
        or forward.state is not SynapseState.CONSOLIDATED
        or reverse.state is not SynapseState.CONSOLIDATED
    ):
        return 0.0
    return min(scoped_quality(forward, config), scoped_quality(reverse, config))


def _snapshot_edge(snapshot: TickSnapshot, source: int, target: int, scope: SynapseScope):
    return snapshot.outgoing.get(source, {}).get((target, scope))


def changed_support(
    snapshot: TickSnapshot,
    overlay: StructuralOverlay,
    touched_pairs: Iterable[Pair],
    config: CoreConfig,
) -> tuple[frozenset[Pair], frozenset[Pair]]:
    delta_local: set[Pair] = set()
    delta_support: set[Pair] = set()
    for source, target in sorted({tuple(sorted(pair)) for pair in touched_pairs}):
        pre_local = reciprocal_quality(
            source, target, SynapseScope.LOCAL,
            lambda a, b, s: _snapshot_edge(snapshot, a, b, s), config,
        )
        post_local = reciprocal_quality(source, target, SynapseScope.LOCAL, overlay.edge, config)
        pre_assoc = reciprocal_quality(
            source, target, SynapseScope.ASSOCIATIVE,
            lambda a, b, s: _snapshot_edge(snapshot, a, b, s), config,
        )
        post_assoc = reciprocal_quality(
            source, target, SynapseScope.ASSOCIATIVE, overlay.edge, config
        )
        if pre_local != post_local:
            delta_local.add((source, target))
        if pre_local != post_local or pre_assoc != post_assoc:
            delta_support.add((source, target))
    return frozenset(delta_local), frozenset(delta_support)


def density(cell_id: int, members: frozenset[int], overlay: StructuralOverlay, config: CoreConfig) -> float:
    return sum(
        reciprocal_quality(cell_id, member, SynapseScope.LOCAL, overlay.edge, config) >= config.theta_A
        for member in members
    ) / len(members)


def mean_reciprocal(
    cell_id: int, members: frozenset[int], overlay: StructuralOverlay, config: CoreConfig
) -> float:
    return sum(
        reciprocal_quality(cell_id, member, SynapseScope.LOCAL, overlay.edge, config)
        for member in members
    ) / len(members)


def specificity(
    cell_id: int,
    members: frozenset[int],
    overlay: StructuralOverlay,
    topology: Topology,
    config: CoreConfig,
) -> float:
    numerator = sum(
        reciprocal_quality(cell_id, member, SynapseScope.LOCAL, overlay.edge, config)
        for member in members
    )
    denominator = 0.0
    for neighbor in topology.specificity_neighborhood(cell_id):
        local = reciprocal_quality(
            cell_id, neighbor, SynapseScope.LOCAL, overlay.edge, config
        )
        associative = reciprocal_quality(
            cell_id, neighbor, SynapseScope.ASSOCIATIVE, overlay.edge, config
        )
        denominator += 1.0 - (1.0 - local) * (1.0 - associative)
    return numerator / (denominator + config.epsilon)


def connected(members: frozenset[int], overlay: StructuralOverlay, config: CoreConfig) -> bool:
    if not members:
        return False
    seen = {min(members)}
    pending = [min(members)]
    while pending:
        source = pending.pop()
        for target in sorted(members - seen):
            if reciprocal_quality(source, target, SynapseScope.LOCAL, overlay.edge, config) >= config.theta_A:
                seen.add(target)
                pending.append(target)
    return seen == set(members)


def core_coverage(members: frozenset[int], overlay: StructuralOverlay, config: CoreConfig) -> float:
    qualifying = 0
    for source in members:
        degree = sum(
            source != target
            and reciprocal_quality(source, target, SynapseScope.LOCAL, overlay.edge, config)
            >= config.theta_A
            for target in members
        )
        qualifying += degree >= config.d_min
    return qualifying / len(members)


def cohesion(members: frozenset[int], overlay: StructuralOverlay, config: CoreConfig) -> float:
    if len(members) < 2:
        return 0.0
    ordered = sorted(members)
    total = sum(
        reciprocal_quality(left, right, SynapseScope.LOCAL, overlay.edge, config)
        for index, left in enumerate(ordered)
        for right in ordered[index + 1 :]
    )
    return total / comb(len(members), 2)


def _maintain(
    assembly: Assembly,
    overlay: StructuralOverlay,
    topology: Topology,
    config: CoreConfig,
) -> Assembly | None:
    members = assembly.members
    while members:
        failing = {
            member
            for member in members
            if density(member, members, overlay, config) < config.rho_keep
            or specificity(member, members, overlay, topology, config) < config.sigma_keep
        }
        if not failing:
            break
        members = members - failing
    if len(members) < config.K_min or not connected(members, overlay, config):
        return None
    return Assembly(assembly.id, assembly.territory, members)


def _form_candidate(
    seed: int,
    overlay: StructuralOverlay,
    topology: Topology,
    config: CoreConfig,
) -> tuple[frozenset[int] | None, int]:
    members = frozenset({seed})
    queued = {seed}
    queue = deque([seed])
    visits = 0
    while queue:
        source = queue.popleft()
        visits += 1
        neighbors = []
        for edge in overlay.outgoing(source, SynapseScope.LOCAL):
            target = edge.target_id
            if target in queued:
                continue
            if reciprocal_quality(source, target, SynapseScope.LOCAL, overlay.edge, config) >= config.theta_A:
                neighbors.append(target)
        for target in sorted(neighbors):
            proposal = members | {target}
            if len(proposal) > config.K_max or topology.diameter(proposal) > config.assembly_radius:
                return None, visits
            members = proposal
            queued.add(target)
            queue.append(target)
    return members, visits


def process_assemblies(
    snapshot: TickSnapshot,
    edge_upserts: Mapping[EdgeKey, Synapse],
    edge_deletes: frozenset[EdgeKey],
    touched_pairs: Iterable[Pair],
    topology: Topology,
    config: CoreConfig,
    next_assembly_id: int,
) -> AssemblyResult:
    overlay = StructuralOverlay(snapshot, edge_upserts, edge_deletes)
    delta_local, delta_support = changed_support(snapshot, overlay, touched_pairs, config)

    maintain_ids = sorted(
        {
            assembly_id
            for left, right in delta_support
            for endpoint in (left, right)
            for assembly_id in snapshot.memberships.get(endpoint, frozenset())
        }
    )
    current: dict[int, Assembly] = {}
    deletes: set[int] = set()
    # This overlay is lazy: only touched Assemblies are copied into ``current``.
    for assembly_id in maintain_ids:
        original = snapshot.assemblies.get(assembly_id)
        if original is None:
            continue
        maintained = _maintain(original, overlay, topology, config)
        if maintained is None:
            deletes.add(assembly_id)
        elif maintained != original:
            current[assembly_id] = maintained

    def assembly_at(assembly_id: int) -> Assembly | None:
        if assembly_id in deletes:
            return None
        return current.get(assembly_id, snapshot.assemblies.get(assembly_id))

    # Membership counts begin at the indexed pre-tick values and are adjusted only
    # for the bounded structural workset.
    membership_counts: dict[int, int] = {}

    def count(member: int) -> int:
        if member in membership_counts:
            return membership_counts[member]
        value = len(snapshot.memberships.get(member, frozenset()))
        for assembly_id in snapshot.memberships.get(member, frozenset()):
            old = snapshot.assemblies.get(assembly_id)
            new = assembly_at(assembly_id)
            if old is not None and member in old.members and (new is None or member not in new.members):
                value -= 1
        membership_counts[member] = value
        return value

    growth_identities: set[tuple[int, int]] = set()
    for left, right in sorted(delta_local):
        if reciprocal_quality(left, right, SynapseScope.LOCAL, overlay.edge, config) < config.theta_A:
            continue
        for assembly_id in sorted(snapshot.memberships.get(left, frozenset())):
            assembly = assembly_at(assembly_id)
            if assembly is not None and right not in assembly.members:
                growth_identities.add((assembly_id, right))
        for assembly_id in sorted(snapshot.memberships.get(right, frozenset())):
            assembly = assembly_at(assembly_id)
            if assembly is not None and left not in assembly.members:
                growth_identities.add((assembly_id, left))

    scored_growth: list[tuple[float, float, float, int, int]] = []
    for assembly_id, candidate in sorted(growth_identities):
        assembly = assembly_at(assembly_id)
        cell = snapshot.cells.get(candidate)
        if assembly is None or cell is None or cell.territory is not assembly.territory:
            continue
        d_value = density(candidate, assembly.members, overlay, config)
        spec_value = specificity(candidate, assembly.members, overlay, topology, config)
        mean_value = mean_reciprocal(candidate, assembly.members, overlay, config)
        if d_value >= config.rho_G and spec_value >= config.sigma_G:
            scored_growth.append(
                (-d_value, -spec_value, -mean_value, assembly_id, candidate)
            )
    scored_growth.sort()

    grown = 0
    for _, _, _, assembly_id, candidate in scored_growth:
        assembly = assembly_at(assembly_id)
        if assembly is None or candidate in assembly.members:
            continue
        proposed = assembly.members | {candidate}
        if (
            len(proposed) > config.K_max
            or topology.diameter(proposed) > config.assembly_radius
            or count(candidate) >= config.M_max
        ):
            continue
        current[assembly_id] = Assembly(assembly.id, assembly.territory, proposed)
        membership_counts[candidate] = count(candidate) + 1
        grown += 1

    seeds = sorted(
        {
            endpoint
            for left, right in delta_local
            if reciprocal_quality(left, right, SynapseScope.LOCAL, overlay.edge, config)
            >= config.theta_A
            for endpoint in (left, right)
        }
    )
    candidates: set[frozenset[int]] = set()
    bfs_visits = 0
    for seed in seeds:
        members, visits = _form_candidate(seed, overlay, topology, config)
        bfs_visits += visits
        if members is None or not config.K_min <= len(members) <= config.K_max:
            continue
        if core_coverage(members, overlay, config) >= config.rho and connected(members, overlay, config):
            candidates.add(members)

    existing_sets = {
        assembly.members
        for assembly_id in {
            assembly_id
            for members in candidates
            for member in members
            for assembly_id in snapshot.memberships.get(member, frozenset())
        }
        if (assembly := assembly_at(assembly_id)) is not None
    }
    ranked_forms = sorted(
        (
            (-core_coverage(members, overlay, config), -cohesion(members, overlay, config), tuple(sorted(members)), members)
            for members in candidates
            if members not in existing_sets
        ),
        key=lambda item: (item[0], item[1], item[2]),
    )
    accepted_forms: list[frozenset[int]] = []
    for _, _, _, members in ranked_forms:
        if any(count(member) >= config.M_max for member in members):
            continue
        if topology.diameter(members) > config.assembly_radius:
            continue
        accepted_forms.append(members)
        for member in members:
            membership_counts[member] = count(member) + 1

    # IDs are allocated in lexicographic final-member-set order at transaction build.
    for offset, members in enumerate(sorted(accepted_forms, key=lambda item: tuple(sorted(item)))):
        assembly_id = next_assembly_id + offset
        territory = topology.territory(min(members))
        current[assembly_id] = Assembly(assembly_id, territory, members)

    return AssemblyResult(
        current,
        frozenset(deletes),
        delta_local,
        delta_support,
        tuple(maintain_ids),
        len(seeds),
        bfs_visits,
        grown,
        len(accepted_forms),
    )
