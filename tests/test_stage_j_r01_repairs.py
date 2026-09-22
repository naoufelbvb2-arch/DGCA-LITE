from copy import deepcopy
from math import exp

import pytest

from dgca_lite import CoreConfig, CoreEngine, SurfaceEvent
from dgca_lite.model import (
    AdjudicatedEvidence,
    Cell,
    SparseSignature,
    Synapse,
    SynapseScope,
    SynapseState,
    TemporalEvent,
    Territory,
)
from dgca_lite.persistence import engine_state


@pytest.mark.parametrize("boundary", [False, True])
def test_failed_tick_preserves_complete_engine_state(boundary: bool) -> None:
    engine = CoreEngine(CoreConfig(receptor_fanout=1, K_R=32, temporal_horizon=2))
    engine.process_event(SurfaceEvent.from_text("establish context"))
    before = deepcopy(engine_state(engine))

    with pytest.raises(ValueError):
        engine.process_event(
            SurfaceEvent.from_text("must fail"),
            boundary=boundary,
            additional_evidence=(
                AdjudicatedEvidence(1, 2, SynapseScope.LOCAL, 2.0, 1),
            ),
        )

    assert engine_state(engine) == before
    assert engine.temporal.next_root_id == before["temporal"]["next_root_id"]
    assert engine.temporal.events
    accepted = engine.process_event(SurfaceEvent.from_text("accepted"))
    assert accepted.root_id == before["temporal"]["next_root_id"]


@pytest.mark.parametrize("existing_edge", [False, True])
def test_dormant_cells_cannot_receive_supplied_evidence(existing_edge: bool) -> None:
    config = CoreConfig(E_max=1, local_radius=3, receptor_fanout=1)
    engine = CoreEngine(config)
    source = engine.network.topology.bounds(Territory.AUDIO)[0]
    target = engine.network.topology.neighborhood(source, SynapseScope.LOCAL)[0]
    engine.network.seed_cell(Cell(source, Territory.AUDIO, True, 0, 4))
    engine.network.seed_cell(Cell(target, Territory.AUDIO, True, 0, 4))
    if existing_edge:
        engine.network.seed_synapse(
            source,
            Synapse(target, 0.8, 0.8, SynapseState.CANDIDATE, SynapseScope.LOCAL),
        )
    before = deepcopy(engine_state(engine))

    with pytest.raises(ValueError, match="learning-active frontier"):
        engine.process_event(
            SurfaceEvent.from_text("unrelated language input"),
            additional_evidence=(
                AdjudicatedEvidence(
                    source,
                    target,
                    SynapseScope.LOCAL,
                    0.5,
                    0 if existing_edge else 1,
                ),
            ),
        )

    assert engine_state(engine) == before


def test_supplied_associative_evidence_requires_historical_provenance() -> None:
    config = CoreConfig(E_max=1, associative_radius=5, receptor_fanout=1)
    engine = CoreEngine(config)
    source = 100
    target = engine.network.topology.neighborhood(
        source, SynapseScope.ASSOCIATIVE
    )[0]
    engine.network.seed_cell(Cell(source, Territory.LANGUAGE, True, 0, 4))
    engine.network.seed_cell(Cell(target, Territory.LANGUAGE, True, 0.8, 4))
    before = deepcopy(engine_state(engine))

    with pytest.raises(ValueError, match="lacks lawful bounded temporal provenance"):
        engine.process_event(
            SurfaceEvent.from_text("current target only"),
            additional_evidence=(
                AdjudicatedEvidence(
                    source, target, SynapseScope.ASSOCIATIVE, 0.1, 1
                ),
            ),
        )

    assert engine_state(engine) == before


def test_long_running_boundary_stream_reclaims_expired_unsupported_recruits() -> None:
    config = CoreConfig(
        E_max=1,
        temporal_horizon=1,
        receptor_fanout=1,
        K_R=64,
        local_radius=0.1,
        associative_radius=0.1,
        specificity_radius=0.1,
    )
    engine = CoreEngine(config)
    for index in range(25):
        event = SurfaceEvent.from_text(f"isolated-{index:04d}-surface")
        current_receptors = {
            cell_id
            for cell_id, _ in engine.surface.receptor_drive(engine.surface.encode(event))
        }
        engine.process_event(event, boundary=True)
        assert set(engine.network.cells) <= current_receptors
        assert engine.temporal.referenced_cells() == current_receptors


def test_supported_cell_is_not_reclaimed_when_provenance_expires() -> None:
    config = CoreConfig(
        E_max=1, temporal_horizon=1, receptor_fanout=1, K_R=64, local_radius=3
    )
    engine = CoreEngine(config)
    first = engine.process_event(SurfaceEvent.from_text("protected-origin"))
    next_event = SurfaceEvent.from_text("entirely-new-boundary-event")
    next_receptors = {
        cell_id
        for cell_id, _ in engine.surface.receptor_drive(engine.surface.encode(next_event))
    }
    protected = next(
        item.cell_id
        for item in first.resources.ordinary_recruitments
        if item.cell_id not in next_receptors
    )
    neighbor = engine.network.topology.neighborhood(protected, SynapseScope.LOCAL)[0]
    if neighbor not in engine.network.cells:
        engine.network.seed_cell(Cell(neighbor, Territory.LANGUAGE, True, 0, 4))
    engine.network.seed_synapse(
        protected,
        Synapse(neighbor, 1, 1, SynapseState.CONSOLIDATED, SynapseScope.LOCAL),
    )

    engine.process_event(next_event, boundary=True)
    assert protected in engine.network.cells
    assert engine.network.edge(protected, neighbor, SynapseScope.LOCAL) is not None


def test_expansion_cell_is_reclaimed_when_historical_provenance_expires() -> None:
    config = CoreConfig(
        E_max=1,
        temporal_horizon=2,
        receptor_fanout=1,
        K_R=2,
        theta_R=0,
        associative_radius=5,
        local_radius=5,
    )
    engine = CoreEngine(config)
    current = SurfaceEvent.from_text("current-fully-familiar")
    current_drive = dict(engine.surface.receptor_drive(engine.surface.encode(current)))
    next_event = SurfaceEvent.from_text("next-event-evicts-history")
    next_ids = {
        cell_id
        for cell_id, _ in engine.surface.receptor_drive(engine.surface.encode(next_event))
    }

    excluded = set(current_drive) | next_ids
    source = next(cell_id for cell_id in range(100, 10_000) if cell_id not in excluded)
    neighbors = [
        cell_id
        for cell_id in engine.network.topology.neighborhood(
            source, SynapseScope.ASSOCIATIVE
        )
        if cell_id not in excluded
    ]
    target, filler = neighbors[:2]
    reserve_ids = tuple(
        cell_id
        for cell_id in range(10_000, 20_000)
        if cell_id not in excluded and cell_id not in (source, target, filler)
    )[:2]

    for cell_id in current_drive:
        engine.network.seed_cell(Cell(cell_id, Territory.LANGUAGE, True, 0, 4))
    engine.network.seed_cell(Cell(source, Territory.LANGUAGE, True, 0, 1))
    engine.network.seed_cell(Cell(target, Territory.LANGUAGE, True, 0.8, 4))
    engine.network.seed_cell(Cell(filler, Territory.LANGUAGE, True, 0, 4))
    engine.network.seed_synapse(
        source,
        Synapse(filler, 1, 1, SynapseState.CONSOLIDATED, SynapseScope.ASSOCIATIVE),
    )
    historical = TemporalEvent(
        -1,
        ((source, 1.0),),
        SparseSignature((b"history",), ()),
        tuple((cell_id, 1.0) for cell_id in reserve_ids),
    )
    engine.temporal.load((historical,), next_root_id=1)

    result = engine.process_event(current)
    expansion_ids = {item.cell_id for item in result.resources.expansion_recruitments}
    assert expansion_ids == set(reserve_ids)
    assert result.novelty.novelty == 1
    assert exp(-config.alpha) * 0.6 >= config.theta_create
    assert all(cell_id in engine.network.cells for cell_id in expansion_ids)

    engine.process_event(next_event)
    assert all(cell_id not in engine.network.cells for cell_id in expansion_ids)
