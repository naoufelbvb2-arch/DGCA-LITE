from dgca_lite import CoreConfig, CoreEngine, SurfaceEvent
from dgca_lite.memory import session
from dgca_lite.memory.config import MemoryConfig
from dgca_lite.memory.integration import TrustedCoreAdapter
from dgca_lite.memory.session import retrieve_after_core_event, retrieve_internal
from dgca_lite.memory.types import FailureCode, RetrievalFailure, RetrievalResult
from dgca_lite.model import Assembly

from .helpers import retrieval_core, seed_pair


def test_internal_session_runs_complete_canonical_pipeline() -> None:
    result = retrieve_internal(retrieval_core(), {0: 1.0}, MemoryConfig())
    assert isinstance(result, RetrievalResult)
    assert result.root.authorized_witnesses == ()
    assert tuple(view.source_id.as_tuple() for view in result.sources) == (("ASM", 0),)
    assert tuple(hit.cell_id for hit in result.direct_hits) == (3,)
    assert tuple(branch.branch_id.target_assembly_id for branch in result.branches) == (1,)
    assert result.branches[0].reconstructed_target_cells == (3, 4, 5)


def test_trusted_session_publishes_complete_authority_without_receipt() -> None:
    core = CoreEngine(CoreConfig(receptor_fanout=1, K_R=32))
    TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("x"))
    trusted = TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("x"))
    result = retrieve_after_core_event(
        core, trusted.receipt, memory_config=MemoryConfig(K_C=128)
    )
    assert isinstance(result, RetrievalResult)
    assert result.root.authorized_witnesses == trusted.receipt.learning_frontier
    assert not hasattr(result, "receipt")


def test_zero_hits_and_seed_only_completion_are_lawful_results() -> None:
    core = retrieval_core()
    result = retrieve_internal(core, {6: 0.5}, MemoryConfig())
    assert isinstance(result, RetrievalResult)
    assert result.direct_hits == ()
    assert result.branches == ()
    assert result.sources[0].reconstructed_cells == (6,)


def test_unresolved_source_ambiguity_is_preserved() -> None:
    core = retrieval_core()
    for member in (0, 1, 2):
        seed_pair(core, member, 6)
    core.network.seed_assembly(
        Assembly(
            2,
            core.network.assemblies[0].territory,
            frozenset({0, 1, 2, 6}),
        )
    )
    result = retrieve_internal(core, {0: 1.0}, MemoryConfig())
    assert isinstance(result, RetrievalResult)
    assert len(result.sources) == 2
    assert all(not source.dominates for source in result.sources)


def test_canonical_acquisition_failures_are_public_failures() -> None:
    result = retrieve_internal(retrieval_core(), {}, MemoryConfig())
    assert result == RetrievalFailure(FailureCode.EMPTY_CUE)


def test_source_reconstruction_failure_publishes_no_partial_result(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("source failure")

    monkeypatch.setattr(session, "reconstruct_pattern", fail)
    result = retrieve_internal(retrieval_core(), {0: 1.0}, MemoryConfig())
    assert result == RetrievalFailure(FailureCode.INTERNAL_ABORT, "RuntimeError")


def test_association_failure_publishes_no_partial_result(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("association failure")

    monkeypatch.setattr(session, "retrieve_associations", fail)
    result = retrieve_internal(retrieval_core(), {0: 1.0}, MemoryConfig())
    assert result == RetrievalFailure(FailureCode.INTERNAL_ABORT, "RuntimeError")


def test_final_target_failure_publishes_no_earlier_branches(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("final branch failure")

    monkeypatch.setattr(session, "reconstruct_target_branches", fail)
    result = retrieve_internal(retrieval_core(), {0: 1.0}, MemoryConfig())
    assert result == RetrievalFailure(FailureCode.INTERNAL_ABORT, "RuntimeError")


def test_diagnostics_sink_cannot_change_or_abort_cognition() -> None:
    core = retrieval_core()
    baseline = retrieve_internal(core, {0: 1.0}, MemoryConfig())
    observed = []
    with_diagnostics = retrieve_internal(
        core, {0: 1.0}, MemoryConfig(), diagnostics_sink=observed.append
    )
    assert baseline == with_diagnostics
    assert len(observed) == 1

    def broken(_):
        raise RuntimeError("diagnostic failure")

    assert retrieve_internal(
        core, {0: 1.0}, MemoryConfig(), diagnostics_sink=broken
    ) == baseline
