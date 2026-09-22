import json

import pytest

from dgca_lite import CoreConfig, CoreEngine, SurfaceEvent
from dgca_lite.model import AdjudicatedEvidence, Cell, SynapseScope, Territory
from dgca_lite.persistence import engine_state


def test_end_to_end_recruit_then_reuse_without_more_recruitment() -> None:
    config = CoreConfig(receptor_fanout=1, K_R=32)
    engine = CoreEngine(config)
    first = engine.process_event(SurfaceEvent.from_text("x"))
    assert 0 < first.diagnostics.ordinary_recruitments <= config.K_R
    second = engine.process_event(SurfaceEvent.from_text("x"))
    assert second.novelty.surface_familiarity == 1
    assert second.novelty.context_compatibility == 1
    assert second.novelty.novelty == 0
    assert second.diagnostics.ordinary_recruitments == 0
    assert second.activation.learning_frontier


def test_one_event_is_one_atomic_root_and_tick() -> None:
    engine = CoreEngine(CoreConfig(receptor_fanout=1, K_R=32))
    first = engine.process_event(SurfaceEvent.from_text("a"))
    second = engine.process_event(SurfaceEvent.from_text("b"))
    assert (first.root_id, second.root_id) == (0, 1)
    assert engine.network.tick == engine.network.version == 2
    assert engine.temporal.open_root is None


def test_external_evidence_flows_through_candidate_creation() -> None:
    config = CoreConfig(E_max=1, local_radius=3, receptor_fanout=1)
    engine = CoreEngine(config)
    source = 0
    target = engine.network.topology.neighborhood(source, SynapseScope.LOCAL)[0]
    engine.network.seed_cell(Cell(source, Territory.LANGUAGE, True, 0, 4))
    engine.network.seed_cell(Cell(target, Territory.LANGUAGE, True, 0, 4))
    result = engine.process_event(
        SurfaceEvent.from_text("evidence"),
        additional_evidence=(
            AdjudicatedEvidence(source, target, SynapseScope.LOCAL, 1.0, 1),
        ),
    )
    edge = engine.network.edge(source, target, SynapseScope.LOCAL)
    assert result.diagnostics.accepted_new_edges == 1
    assert edge is not None and edge.state.value == "CANDIDATE"


def test_hard_boundary_clears_prior_context_and_emission() -> None:
    engine = CoreEngine(CoreConfig(receptor_fanout=1, K_R=32))
    engine.process_event(SurfaceEvent.from_text("x"))
    engine.process_event(SurfaceEvent.from_text("x"))
    assert len(engine.temporal.events) == 2
    result = engine.process_event(SurfaceEvent.from_text("y"), boundary=True)
    assert len(engine.temporal.events) == 1
    assert result.activation.emission_frontier == frozenset()


def test_failure_aborts_root_without_partial_network_mutation() -> None:
    engine = CoreEngine(CoreConfig())
    before = engine_state(engine)
    with pytest.raises(ValueError):
        engine.process_event(
            SurfaceEvent.from_text("bad"),
            additional_evidence=(
                AdjudicatedEvidence(1, 2, SynapseScope.LOCAL, 2.0, 1),
            ),
        )
    assert engine_state(engine)["network"] == before["network"]
    assert engine.temporal.open_root is None


def test_same_inputs_replay_to_identical_canonical_state() -> None:
    config = CoreConfig(receptor_fanout=1, K_R=32)
    left = CoreEngine(config)
    right = CoreEngine(config)
    for text, boundary in (("same", False), ("same", False), ("new", True), ("new", False)):
        left.process_event(SurfaceEvent.from_text(text), boundary=boundary)
        right.process_event(SurfaceEvent.from_text(text), boundary=boundary)
    assert engine_state(left) == engine_state(right)


def test_persistence_round_trip_and_continued_replay(tmp_path) -> None:
    config = CoreConfig(receptor_fanout=1, K_R=32)
    engine = CoreEngine(config)
    engine.process_event(SurfaceEvent.from_text("persist"))
    engine.process_event(SurfaceEvent.from_text("persist"))
    path = tmp_path / "core.json"
    engine.save(path)
    restored = CoreEngine.load(path)
    assert engine_state(restored) == engine_state(engine)
    assert json.loads(path.read_text(encoding="utf-8"))["format"] == "DGCA-LITE-Core-v0.3"
    engine.process_event(SurfaceEvent.from_text("continue"))
    restored.process_event(SurfaceEvent.from_text("continue"))
    assert engine_state(restored) == engine_state(engine)


def test_diagnostics_are_transient_not_serialized(tmp_path) -> None:
    engine = CoreEngine(CoreConfig(receptor_fanout=1, K_R=32))
    result = engine.process_event(SurfaceEvent.from_text("x"))
    assert result.diagnostics.transaction_mutations > 0
    path = tmp_path / "state.json"
    engine.save(path)
    assert "diagnostics" not in path.read_text(encoding="utf-8")
