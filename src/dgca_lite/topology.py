"""Deterministic sparse 3-D logical topology."""

from __future__ import annotations

from math import ceil, dist

from .config import CoreConfig
from .model import SynapseScope, Territory


class Topology:
    """Maps logical IDs to positions without materializing logical Cells."""

    def __init__(self, config: CoreConfig) -> None:
        self.config = config
        base, remainder = divmod(config.logical_capacity, 3)
        sizes = [base + (1 if index < remainder else 0) for index in range(3)]
        self._bounds: dict[Territory, tuple[int, int]] = {}
        start = 0
        for territory, size in zip(Territory, sizes, strict=True):
            self._bounds[territory] = (start, start + size)
            start += size
        self._side = {
            territory: ceil((end - start) ** (1 / 3))
            for territory, (start, end) in self._bounds.items()
        }

    def validate_id(self, cell_id: int) -> None:
        if not isinstance(cell_id, int) or not 0 <= cell_id < self.config.logical_capacity:
            raise ValueError(f"invalid logical Cell ID: {cell_id!r}")

    def bounds(self, territory: Territory) -> tuple[int, int]:
        return self._bounds[territory]

    def territory(self, cell_id: int) -> Territory:
        self.validate_id(cell_id)
        for territory, (start, end) in self._bounds.items():
            if start <= cell_id < end:
                return territory
        raise AssertionError("validated ID must belong to a territory")

    def position(self, cell_id: int) -> tuple[int, int, int]:
        territory = self.territory(cell_id)
        start, _ = self._bounds[territory]
        local = cell_id - start
        side = self._side[territory]
        x = local % side
        y = (local // side) % side
        z = local // (side * side)
        return (x, y, z)

    def _id_at(self, territory: Territory, position: tuple[int, int, int]) -> int | None:
        x, y, z = position
        side = self._side[territory]
        if min(x, y, z) < 0 or max(x, y, z) >= side:
            return None
        start, end = self._bounds[territory]
        cell_id = start + x + side * (y + side * z)
        return cell_id if cell_id < end else None

    def distance(self, left: int, right: int) -> float:
        self.validate_id(left)
        self.validate_id(right)
        return dist(self.position(left), self.position(right))

    def radius_for(self, scope: SynapseScope) -> float:
        if scope is SynapseScope.LOCAL:
            return self.config.local_radius
        if scope is SynapseScope.ASSOCIATIVE:
            return self.config.associative_radius
        return self.config.associative_radius

    def scope_eligible(self, source: int, target: int, scope: SynapseScope) -> bool:
        if source == target:
            return False
        same = self.territory(source) is self.territory(target)
        if scope in (SynapseScope.LOCAL, SynapseScope.ASSOCIATIVE):
            return same and self.distance(source, target) <= self.radius_for(scope)
        return (not same) and self.distance(source, target) <= self.radius_for(scope)

    def neighborhood(
        self,
        source: int,
        scope: SynapseScope,
        *,
        radius: float | None = None,
    ) -> tuple[int, ...]:
        """Enumerate a finite spatial cube, never the logical capacity."""
        self.validate_id(source)
        source_territory = self.territory(source)
        if scope is SynapseScope.CROSS_TERRITORY:
            return ()  # Cross-modal creation is deliberately dormant in LANGUAGE-only v0.
        actual_radius = self.radius_for(scope) if radius is None else radius
        limit = ceil(actual_radius)
        x0, y0, z0 = self.position(source)
        candidates: list[tuple[float, int]] = []
        for dz in range(-limit, limit + 1):
            for dy in range(-limit, limit + 1):
                for dx in range(-limit, limit + 1):
                    candidate = self._id_at(source_territory, (x0 + dx, y0 + dy, z0 + dz))
                    if candidate is None or candidate == source:
                        continue
                    distance = self.distance(source, candidate)
                    if distance <= actual_radius:
                        candidates.append((distance, candidate))
        candidates.sort(key=lambda item: (item[0], item[1]))
        return tuple(cell_id for _, cell_id in candidates[: self.config.max_neighborhood])

    def specificity_neighborhood(self, source: int) -> tuple[int, ...]:
        return self.neighborhood(
            source,
            SynapseScope.ASSOCIATIVE,
            radius=self.config.specificity_radius,
        )

    def diameter(self, members: set[int] | frozenset[int]) -> float:
        ordered = sorted(members)
        maximum = 0.0
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                maximum = max(maximum, self.distance(left, right))
        return maximum
