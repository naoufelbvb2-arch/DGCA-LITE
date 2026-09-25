from itertools import pairwise

from dgca_lite.memory import association, session
from dgca_lite.memory.acquisition import acquire
from dgca_lite.memory.config import MemoryConfig
from dgca_lite.memory.session import retrieve_internal
from dgca_lite.memory.target import reconstruct_target_branches
from dgca_lite.memory.types import (
    BranchID,
    ReciprocalLink,
    ReconstructionGraph,
    RetrievalResult,
    SeedState,
    SeedValue,
    SourceID,
)
from dgca_lite.model import SynapseScope, SynapseState

from .helpers import consolidated, retrieval_core


def graph(assembly_id: int, members: tuple[int, ...]) -> ReconstructionGraph:
    return ReconstructionGraph(
        assembly_id,
        members,
        tuple(
            ReciprocalLink(left, right, 1.0)
            for left, right in pairwise(members)
        ),
    )


def seed(cell_id: int) -> SeedState:
    return SeedState.from_dict({cell_id: SeedValue(1.0, True)})


def test_target_reconstruction_uses_known_graph_and_same_kernel() -> None:
    branch_id = BranchID(SourceID.assembly(1), 2)
    result = reconstruct_target_branches(
        ((branch_id, seed(10)),), {2: graph(2, (10, 11, 12))}, 1.0
    )
    assert result[0].reconstructed_target_cells == (10, 11, 12)
    assert dict(result[0].admission_rounds) == {10: 0, 11: 1, 12: 2}


def test_a_to_b_to_a_cycle_stops_after_one_session_hop(monkeypatch) -> None:
    core = retrieval_core()
    core.network.seed_synapse(
        3, consolidated(0, SynapseScope.ASSOCIATIVE, quality=1.0)
    )
    frozen = core.network.snapshot()
    forward = frozen.outgoing[0][(3, SynapseScope.ASSOCIATIVE)]
    reverse = frozen.outgoing[3][(0, SynapseScope.ASSOCIATIVE)]
    assert forward.state is SynapseState.CONSOLIDATED
    assert reverse.state is SynapseState.CONSOLIDATED

    universe = acquire(core, {0: 1.0}, MemoryConfig())
    captured_edges = {
        (edge.source_id, edge.target_id)
        for edge in universe.snapshot.associative_synapses
    }
    assert (0, 3) in captured_edges
    assert (3, 0) not in captured_edges

    calls = 0
    original = session.retrieve_associations

    def counted_association(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(session, "retrieve_associations", counted_association)
    result = retrieve_internal(core, {0: 1.0}, MemoryConfig())
    assert isinstance(result, RetrievalResult)
    assert calls == 1
    assert tuple(branch.branch_id for branch in result.branches) == (
        BranchID(SourceID.assembly(0), 1),
    )
    assert result.branches[0].reconstructed_target_cells == (3, 4, 5)
    assert all(branch.branch_id.target_assembly_id != 0 for branch in result.branches)


def test_self_target_is_a_distinct_isolated_branch() -> None:
    branch_id = BranchID(SourceID.assembly(4), 4)
    result = reconstruct_target_branches(
        ((branch_id, seed(20)),), {4: graph(4, (20, 21, 22))}, 1.0
    )
    assert result[0].branch_id == branch_id
    assert result[0].branch_id.source_id == SourceID.assembly(4)


def test_separate_sources_to_same_target_keep_separate_lane_state() -> None:
    first = BranchID(SourceID.assembly(1), 7)
    second = BranchID(SourceID.atomic(3), 7)
    result = reconstruct_target_branches(
        ((second, seed(10)), (first, seed(11))),
        {7: graph(7, (10, 11, 12))},
        1.0,
    )
    assert tuple(item.branch_id for item in result) == (first, second)
    assert result[0].target_seed_state != result[1].target_seed_state
    assert result[0].provenance != result[1].provenance


def test_target_api_has_no_association_or_discovery_input(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("association was called from target reconstruction")

    monkeypatch.setattr(association, "retrieve_associations", forbidden)
    branch_id = BranchID(SourceID.atomic(0), 2)
    result = reconstruct_target_branches(
        ((branch_id, seed(10)),), {2: graph(2, (10, 11, 12))}, 1.0
    )
    assert result[0].branch_id == branch_id


def test_unknown_target_graph_fails_instead_of_candidate_discovery() -> None:
    branch_id = BranchID(SourceID.atomic(0), 999)
    try:
        reconstruct_target_branches(((branch_id, seed(10)),), {}, 1.0)
    except ValueError as error:
        assert "unknown captured Assembly" in str(error)
    else:
        raise AssertionError("missing target graph did not fail closed")
