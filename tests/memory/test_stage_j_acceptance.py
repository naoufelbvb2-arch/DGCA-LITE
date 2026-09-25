import ast
import inspect
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from dgca_lite import CoreConfig, CoreEngine, SurfaceEvent
from dgca_lite.memory import target as target_module
from dgca_lite.memory.acquisition import acquire
from dgca_lite.memory.config import MemoryConfig
from dgca_lite.memory.integration import TrustedCoreAdapter, validate_receipt
from dgca_lite.memory.serialization import canonical_result_bytes
from dgca_lite.memory.session import (
    _settle,
    retrieve_after_core_event,
    retrieve_internal,
)
from dgca_lite.memory.target import reconstruct_target_branches
from dgca_lite.memory.types import (
    BranchID,
    FailureCode,
    ReciprocalLink,
    ReconstructionGraph,
    RetrievalAbort,
    RetrievalFailure,
    RetrievalResult,
    SeedState,
    SeedValue,
    SourceID,
    immutable_value_tree,
)
from dgca_lite.model import (
    Assembly,
    Cell,
    SynapseScope,
    Territory,
    TickTransaction,
)
from dgca_lite.persistence import engine_state

from .helpers import consolidated, retrieval_core, seed_pair


def test_internal_and_trusted_retrieval_conserve_complete_core_state() -> None:
    internal_core = retrieval_core()
    internal_before = engine_state(internal_core)
    memberships_before = dict(internal_core.network.memberships)
    internal = retrieve_internal(internal_core, {0: 1.0}, MemoryConfig())
    assert isinstance(internal, RetrievalResult)
    assert engine_state(internal_core) == internal_before
    assert internal_core.network.memberships == memberships_before

    trusted_core = CoreEngine(CoreConfig(receptor_fanout=1, K_R=32))
    TrustedCoreAdapter.process_event(trusted_core, SurfaceEvent.from_text("x"))
    trusted = TrustedCoreAdapter.process_event(
        trusted_core, SurfaceEvent.from_text("x")
    )
    trusted_before = engine_state(trusted_core)
    memberships_before = dict(trusted_core.network.memberships)
    result = retrieve_after_core_event(
        trusted_core, trusted.receipt, memory_config=MemoryConfig(K_C=128)
    )
    assert isinstance(result, RetrievalResult)
    assert engine_state(trusted_core) == trusted_before
    assert trusted_core.network.memberships == memberships_before


def test_result_is_deeply_immutable_and_contains_no_core_reference() -> None:
    result = retrieve_internal(retrieval_core(), {0: 1.0}, MemoryConfig())
    assert isinstance(result, RetrievalResult)
    assert immutable_value_tree(result)
    with pytest.raises(FrozenInstanceError):
        result.sources = ()  # type: ignore[misc]
    assert all(not isinstance(value, CoreEngine) for value in result.sources)


def test_remote_disconnected_graph_does_not_change_result_or_bounded_work() -> None:
    baseline_diagnostics = []
    baseline = retrieve_internal(
        retrieval_core(),
        {0: 1.0},
        MemoryConfig(),
        diagnostics_sink=baseline_diagnostics.append,
    )
    remote = retrieval_core()
    for cell_id in (50, 51, 52):
        remote.network.seed_cell(Cell(cell_id, Territory.LANGUAGE, True, 0.0, 32))
    for left, right in ((50, 51), (50, 52), (51, 52)):
        seed_pair(remote, left, right)
    remote.network.seed_assembly(
        Assembly(99, Territory.LANGUAGE, frozenset({50, 51, 52}))
    )
    remote_diagnostics = []
    result = retrieve_internal(
        remote,
        {0: 1.0},
        MemoryConfig(),
        diagnostics_sink=remote_diagnostics.append,
    )
    assert isinstance(baseline, RetrievalResult)
    assert isinstance(result, RetrievalResult)
    assert canonical_result_bytes(result) == canonical_result_bytes(baseline)
    assert remote_diagnostics == baseline_diagnostics


def test_maximal_cue_cardinality_is_accepted_without_truncation() -> None:
    core = CoreEngine(CoreConfig(logical_capacity=300))
    cue = {}
    for cell_id in range(8):
        core.network.seed_cell(Cell(cell_id, Territory.LANGUAGE, True, 0.0, 32))
        cue[cell_id] = 1.0
    universe = acquire(core, cue, MemoryConfig(K_C=8))
    assert universe.seed_ids == tuple(range(8))
    assert len(universe.snapshot.cells) == 8


def test_maximal_membership_bound_obeys_source_space_theorem() -> None:
    config = CoreConfig(
        logical_capacity=300,
        default_synaptic_budget=64,
        E_max=1.0,
        local_radius=20.0,
        assembly_radius=20.0,
        K_min=3,
        K_max=3,
        M_max=4,
    )
    core = CoreEngine(config)
    for cell_id in range(9):
        core.network.seed_cell(Cell(cell_id, Territory.LANGUAGE, True, 0.0, 64))
    for assembly_id in range(config.M_max):
        members = (0, 1 + 2 * assembly_id, 2 + 2 * assembly_id)
        for index, left in enumerate(members):
            for right in members[index + 1 :]:
                if core.network.edge(left, right, SynapseScope.LOCAL) is None:
                    seed_pair(core, left, right)
        core.network.seed_assembly(
            Assembly(assembly_id, Territory.LANGUAGE, frozenset(members))
        )
    universe = acquire(core, {0: 1.0}, MemoryConfig(K_C=1))
    h_0 = len(core.network.memberships[0])
    v_s = len(universe.snapshot.cells)
    assert h_0 == config.M_max == 4
    assert h_0 <= universe.parameters.K_C * universe.parameters.M_max
    assert v_s <= universe.parameters.K_C * (
        universe.parameters.M_max * universe.parameters.K_max + 1
    )


def test_maximal_outgoing_budget_is_captured_locally() -> None:
    budget = 32
    config = CoreConfig(
        logical_capacity=300,
        default_synaptic_budget=budget,
        E_max=1.0,
        associative_radius=100.0,
    )
    core = CoreEngine(config)
    for cell_id in range(budget + 1):
        core.network.seed_cell(Cell(cell_id, Territory.LANGUAGE, True, 0.0, budget))
    for target in range(1, budget + 1):
        core.network.seed_synapse(
            0, consolidated(target, SynapseScope.ASSOCIATIVE, 0.5)
        )
    universe = acquire(core, {0: 1.0}, MemoryConfig(K_C=1))
    assert len(universe.snapshot.associative_synapses) == budget
    bound = len(universe.seed_ids) * (
        universe.parameters.M_max * universe.parameters.K_max + 1
    ) * budget
    assert len(universe.snapshot.associative_synapses) <= bound


def test_observed_branch_count_respects_canonical_bound() -> None:
    core = retrieval_core()
    universe = acquire(core, {0: 1.0}, MemoryConfig(K_C=1))
    result, _ = _settle(universe, False)
    source_cells = {cell.id: cell for cell in universe.snapshot.cells}
    source_members = universe.snapshot.assembly_map()[0].members
    b_r = max(source_cells[cell_id].synaptic_budget for cell_id in source_members)
    bound = (
        universe.parameters.K_C
        * b_r
        * universe.parameters.M_max
        * (
            universe.parameters.M_max * universe.parameters.K_max
            + 1
        )
    )
    assert len(result.branches) <= bound


def test_stale_version_and_stale_tick_fail_independently() -> None:
    version_core = CoreEngine(CoreConfig(receptor_fanout=1, K_R=32))
    version_receipt = TrustedCoreAdapter.process_event(
        version_core, SurfaceEvent.from_text("x")
    ).receipt
    version_core.network.version += 1
    with pytest.raises(RetrievalAbort) as stale_version:
        validate_receipt(
            version_core,
            version_receipt,
            version_core.network.version,
            version_core.network.tick,
        )
    assert stale_version.value.code is FailureCode.STALE_TRUSTED_ROOT

    tick_core = CoreEngine(CoreConfig(receptor_fanout=1, K_R=32))
    tick_receipt = TrustedCoreAdapter.process_event(
        tick_core, SurfaceEvent.from_text("x")
    ).receipt
    tick_core.network.tick += 1
    with pytest.raises(RetrievalAbort) as stale_tick:
        validate_receipt(
            tick_core,
            tick_receipt,
            tick_core.network.version,
            tick_core.network.tick,
        )
    assert stale_tick.value.code is FailureCode.STALE_TRUSTED_ROOT


def test_independent_frozen_sessions_survive_later_core_change() -> None:
    core = retrieval_core()
    first = acquire(core, {0: 1.0}, MemoryConfig())
    second = acquire(core, {0: 1.0}, MemoryConfig())
    core.network.commit(TickTransaction(base_version=core.network.version))
    first_result, _ = _settle(first, False)
    second_result, _ = _settle(second, True)
    assert canonical_result_bytes(first_result) == canonical_result_bytes(second_result)


def test_final_branch_failure_exposes_no_completed_prefix(monkeypatch) -> None:
    graph = ReconstructionGraph(
        7,
        (10, 11, 12),
        (ReciprocalLink(10, 11, 1.0), ReciprocalLink(11, 12, 1.0)),
    )
    branches = (
        (BranchID(SourceID.atomic(1), 7), SeedState.from_dict({10: SeedValue(1.0, True)})),
        (BranchID(SourceID.atomic(2), 7), SeedState.from_dict({11: SeedValue(1.0, True)})),
    )
    original = target_module.reconstruct_pattern
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("final branch failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(target_module, "reconstruct_pattern", fail_second)
    with pytest.raises(RuntimeError):
        reconstruct_target_branches(branches, {7: graph}, 1.0)
    assert calls == 2


def test_snapshot_synapse_capacity_aborts_instead_of_top_k() -> None:
    with pytest.raises(RetrievalAbort) as caught:
        acquire(
            retrieval_core(),
            {0: 1.0},
            MemoryConfig(max_snapshot_synapses=1),
        )
    assert caught.value.code is FailureCode.SNAPSHOT_CAPACITY_ABORT


def test_normal_retrieval_modules_cannot_call_core_event_or_mutation_apis() -> None:
    package = Path(inspect.getfile(retrieve_internal)).parent
    integration = package / "integration.py"
    forbidden_calls = {
        "commit",
        "process_event",
        "seed_assembly",
        "seed_cell",
        "seed_synapse",
    }
    for path in package.glob("*.py"):
        if path == integration:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert not calls & forbidden_calls, (path.name, calls & forbidden_calls)


def test_only_integration_module_owns_one_core_process_event_call() -> None:
    package = Path(inspect.getfile(retrieve_internal)).parent
    integration = package / "integration.py"
    tree = ast.parse(integration.read_text(encoding="utf-8"), filename=str(integration))
    process_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "process_event"
    ]
    assert len(process_calls) == 1


def test_public_failure_not_partial_result_on_invalid_cue() -> None:
    outcome = retrieve_internal(retrieval_core(), {0: float("nan")}, MemoryConfig())
    assert outcome == RetrievalFailure(FailureCode.INVALID_CUE)
    assert not isinstance(outcome, RetrievalResult)
