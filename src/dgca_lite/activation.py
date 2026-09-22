"""Pure snapshot-based activation dynamics."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import prod

from .config import CoreConfig
from .model import Synapse, TickSnapshot


def confidence(edge: Synapse, config: CoreConfig) -> float:
    return edge.evidence_mass / config.E_max


def scoped_quality(edge: Synapse, config: CoreConfig) -> float:
    return edge.strength * confidence(edge, config)


def effective_quality(edges: Iterable[Synapse], config: CoreConfig) -> float:
    ordered = sorted(edges, key=lambda edge: edge.scope.order)
    return 1.0 - prod(1.0 - scoped_quality(edge, config) for edge in ordered)


@dataclass(frozen=True, slots=True)
class ActivationResult:
    next_activation: Mapping[int, float]
    learning_frontier: frozenset[int]
    emission_frontier: frozenset[int]
    drives: Mapping[int, float]


def compute_activation(
    snapshot: TickSnapshot,
    external_drive: Mapping[int, float],
    config: CoreConfig,
    *,
    boundary_reset: bool = False,
) -> ActivationResult:
    """Compute A+ entirely from an immutable pre-tick snapshot."""
    if any(not 0 <= value <= 1 for value in external_drive.values()):
        raise ValueError("external drive must be in [0, 1]")

    emission = (
        frozenset()
        if boundary_reset
        else frozenset(
            cell_id
            for cell_id in snapshot.active_ids
            if (cell := snapshot.cells.get(cell_id)) is not None
            and cell.committed
            and cell.activation >= config.theta_emit
        )
    )

    # One contribution per ordered Cell pair after combining scopes.
    incoming: dict[int, list[tuple[int, float]]] = {}
    for source in sorted(emission):
        pair_edges: dict[int, list[Synapse]] = {}
        for edge in snapshot.outgoing.get(source, {}).values():
            if edge.target_id in snapshot.cells and snapshot.cells[edge.target_id].committed:
                pair_edges.setdefault(edge.target_id, []).append(edge)
        for target in sorted(pair_edges):
            incoming.setdefault(target, []).append(
                (source, effective_quality(pair_edges[target], config))
            )

    targets = set(snapshot.active_ids)
    targets.update(
        cell_id
        for cell_id in external_drive
        if (cell := snapshot.cells.get(cell_id)) is not None and cell.committed
    )
    targets.update(incoming)

    drives: dict[int, float] = {}
    next_activation: dict[int, float] = {}
    for target in sorted(targets):
        cell = snapshot.cells.get(target)
        if cell is None or not cell.committed:
            continue
        external = external_drive.get(target, 0.0)
        residual = 1.0 - external
        for source, quality in sorted(incoming.get(target, ()), key=lambda item: item[0]):
            source_activation = 0.0 if boundary_reset else snapshot.cells[source].activation
            residual *= 1.0 - source_activation * quality
        drive = 1.0 - residual
        old_activation = 0.0 if boundary_reset else cell.activation
        value = (1.0 - config.delta_A) * old_activation + config.gamma_A * drive
        value = min(1.0, max(0.0, value))
        drives[target] = drive
        next_activation[target] = value

    learning = frozenset(
        cell_id
        for cell_id, value in next_activation.items()
        if value >= config.theta_active
    )
    return ActivationResult(next_activation, learning, emission, drives)

