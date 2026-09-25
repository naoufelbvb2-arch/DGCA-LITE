import copy
import pickle

import pytest

from dgca_lite import CoreConfig, CoreEngine, SurfaceEvent
from dgca_lite.memory import integration
from dgca_lite.memory.acquisition import acquire
from dgca_lite.memory.config import MemoryConfig
from dgca_lite.memory.integration import (
    TrustedCoreAdapter,
    TrustedRetrievalReceipt,
    validate_receipt,
)
from dgca_lite.memory.types import FailureCode, FrozenFloatMap, RetrievalAbort


def test_receipt_can_only_be_minted_by_trusted_adapter() -> None:
    with pytest.raises(TypeError):
        TrustedRetrievalReceipt(object())


def test_tick_result_is_not_receipt_authority() -> None:
    core = CoreEngine(CoreConfig(receptor_fanout=1, K_R=32))
    result = core.process_event(SurfaceEvent.from_text("x"))
    with pytest.raises(RetrievalAbort) as caught:
        validate_receipt(core, result, core.network.version, core.network.tick)
    assert caught.value.code is FailureCode.STALE_TRUSTED_ROOT


def test_receipt_is_bound_to_postcommit_state_and_complete_frontier() -> None:
    core = CoreEngine(CoreConfig(receptor_fanout=1, K_R=32))
    TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("x"))
    trusted = TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("x"))
    validated = validate_receipt(
        core, trusted.receipt, core.network.version, core.network.tick
    )
    assert validated[1] == core.network.tick
    assert validated[0] == core.network.version
    assert validated[3] == tuple(
        sorted(trusted.tick_result.activation.learning_frontier)
    )
    assert dict(validated[4]) == {
        cell_id: trusted.tick_result.activation.next_activation[cell_id]
        for cell_id in validated[3]
    }


def test_cross_core_and_stale_receipts_are_rejected() -> None:
    config = CoreConfig(receptor_fanout=1, K_R=32)
    left = CoreEngine(config)
    right = CoreEngine(config)
    trusted = TrustedCoreAdapter.process_event(left, SurfaceEvent.from_text("x"))
    with pytest.raises(RetrievalAbort):
        validate_receipt(right, trusted.receipt, right.network.version, right.network.tick)
    left.process_event(SurfaceEvent.from_text("advance"))
    with pytest.raises(RetrievalAbort):
        validate_receipt(left, trusted.receipt, left.network.version, left.network.tick)


def test_receipt_is_immutable_and_not_serializable() -> None:
    core = CoreEngine(CoreConfig(receptor_fanout=1, K_R=32))
    receipt = TrustedCoreAdapter.process_event(
        core, SurfaceEvent.from_text("x")
    ).receipt
    with pytest.raises(AttributeError):
        receipt._root_id = 999  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        pickle.dumps(receipt)


def test_copied_fields_and_previous_issuer_key_cannot_recreate_authority() -> None:
    core = CoreEngine(CoreConfig(receptor_fanout=4, K_R=32))
    TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("copy attack"))
    receipt = TrustedCoreAdapter.process_event(
        core, SurfaceEvent.from_text("copy attack")
    ).receipt

    assert not hasattr(integration, "_ISSUER_KEY")
    forged = object.__new__(TrustedRetrievalReceipt)
    copied_fields = {
        "_core": core,
        "_post_commit_version": receipt.post_commit_version,
        "_post_commit_tick": receipt.post_commit_tick,
        "_root_id": receipt.root_id,
        "_frontier": receipt.learning_frontier,
        "_activation": receipt.activation,
        "_seal": getattr(receipt, "_seal", object()),
    }
    for name, value in copied_fields.items():
        try:
            object.__setattr__(forged, name, value)
        except AttributeError:
            pass

    with pytest.raises(RetrievalAbort) as caught:
        validate_receipt(core, forged, core.network.version, core.network.tick)
    assert caught.value.code is FailureCode.STALE_TRUSTED_ROOT
    with pytest.raises(TypeError):
        copy.copy(receipt)
    with pytest.raises(TypeError):
        copy.deepcopy(receipt)


def test_object_setattr_tampering_cannot_change_authoritative_issuance(
    monkeypatch,
) -> None:
    core = CoreEngine(CoreConfig(receptor_fanout=4, K_R=32))
    TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("tamper attack"))
    receipt = TrustedCoreAdapter.process_event(
        core, SurfaceEvent.from_text("tamper attack")
    ).receipt
    original_root = receipt.root_id
    original_frontier = receipt.learning_frontier
    original_activation = receipt.activation
    assert len(original_frontier) > 1

    attempts = {
        "_root_id": original_root + 1000,
        "_frontier": original_frontier[:1],
        "_activation": FrozenFloatMap.from_dict(
            {original_frontier[0]: original_activation.to_dict()[original_frontier[0]]}
        ),
    }
    for name, value in attempts.items():
        try:
            object.__setattr__(receipt, name, value)
        except AttributeError:
            pass

    monkeypatch.setattr(
        type(receipt), "root_id", property(lambda self: original_root + 2000)
    )
    monkeypatch.setattr(
        type(receipt),
        "learning_frontier",
        property(lambda self: original_frontier[:1]),
    )
    monkeypatch.setattr(
        type(receipt),
        "activation",
        property(
            lambda self: FrozenFloatMap.from_dict(
                {
                    original_frontier[0]: original_activation.to_dict()[
                        original_frontier[0]
                    ]
                }
            )
        ),
    )

    validated = validate_receipt(
        core, receipt, core.network.version, core.network.tick
    )
    assert validated[2] == original_root
    assert validated[3] == original_frontier
    assert FrozenFloatMap(validated[4]) == original_activation
    universe = acquire(core, {}, MemoryConfig(K_C=128), receipt)
    assert universe.trusted_root_id == original_root
    assert universe.authorized_ids == original_frontier
    assert universe.trusted_cue == original_activation


def test_tampering_cannot_add_a_cell_or_change_trusted_magnitude() -> None:
    core = CoreEngine(CoreConfig(receptor_fanout=4, K_R=32))
    TrustedCoreAdapter.process_event(core, SurfaceEvent.from_text("addition attack"))
    receipt = TrustedCoreAdapter.process_event(
        core, SurfaceEvent.from_text("addition attack")
    ).receipt
    original_frontier = receipt.learning_frontier
    original_activation = FrozenFloatMap(receipt.activation.entries)
    added_cell = max(original_frontier) + 10_000
    replacement = original_activation.to_dict()
    replacement[original_frontier[0]] = 0.01
    replacement[added_cell] = 1.0
    try:
        object.__setattr__(
            receipt,
            "_frontier",
            tuple(sorted((*original_frontier, added_cell))),
        )
        object.__setattr__(receipt, "_activation", FrozenFloatMap.from_dict(replacement))
    except AttributeError:
        pass
    exposed_activation = receipt.activation
    object.__setattr__(
        exposed_activation,
        "entries",
        FrozenFloatMap.from_dict(replacement).entries,
    )

    universe = acquire(core, {}, MemoryConfig(K_C=128), receipt)
    assert universe.authorized_ids == original_frontier
    assert added_cell not in universe.authorized_ids
    assert universe.trusted_cue == original_activation
