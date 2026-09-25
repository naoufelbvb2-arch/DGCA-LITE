"""Trusted Core-to-Layer-2 operational capability boundary."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from weakref import ReferenceType, ref

from dgca_lite.engine import CoreEngine, TickResult
from dgca_lite.model import AdjudicatedEvidence, HardBoundary, SurfaceEvent

from .types import FailureCode, FrozenFloatMap, RetrievalAbort


def _build_authority_boundary():
    """Create one identity-backed issuer registry hidden from module callers."""

    @dataclass(frozen=True, slots=True)
    class _IssuanceRecord:
        core: CoreEngine
        post_commit_version: int
        post_commit_tick: int
        root_id: int
        frontier: tuple[int, ...]
        activation_entries: tuple[tuple[int, float], ...]

    class TrustedRetrievalReceipt:
        """Opaque identity token whose visible values carry no authority."""

        __slots__ = ("__weakref__",)

        def __new__(cls, *args: Any, **kwargs: Any):
            raise TypeError("TrustedRetrievalReceipt is issued only by TrustedCoreAdapter")

        def __reduce__(self):
            raise TypeError("TrustedRetrievalReceipt cannot be serialized")

        def __reduce_ex__(self, protocol: int):
            raise TypeError("TrustedRetrievalReceipt cannot be serialized")

        def __copy__(self):
            raise TypeError("TrustedRetrievalReceipt cannot be copied")

        def __deepcopy__(self, memo: dict[int, object]):
            raise TypeError("TrustedRetrievalReceipt cannot be copied")

        @property
        def post_commit_version(self) -> int:
            return _issued_record(self).post_commit_version

        @property
        def post_commit_tick(self) -> int:
            return _issued_record(self).post_commit_tick

        @property
        def root_id(self) -> int:
            return _issued_record(self).root_id

        @property
        def learning_frontier(self) -> tuple[int, ...]:
            return _issued_record(self).frontier

        @property
        def activation(self) -> FrozenFloatMap:
            return FrozenFloatMap(_issued_record(self).activation_entries)

    records: dict[
        int, tuple[ReferenceType[TrustedRetrievalReceipt], _IssuanceRecord]
    ] = {}

    def _issued_record(receipt: TrustedRetrievalReceipt) -> _IssuanceRecord:
        registered = records.get(id(receipt))
        if registered is None or registered[0]() is not receipt:
            raise LookupError("receipt was not issued by this authority boundary")
        return registered[1]

    def _issue(record: _IssuanceRecord) -> TrustedRetrievalReceipt:
        receipt = object.__new__(TrustedRetrievalReceipt)
        identity = id(receipt)

        def discard(reference: ReferenceType[TrustedRetrievalReceipt]) -> None:
            current = records.get(identity)
            if current is not None and current[0] is reference:
                records.pop(identity, None)

        reference = ref(receipt, discard)
        records[identity] = (reference, record)
        return receipt

    @dataclass(frozen=True, slots=True)
    class TrustedCoreEvent:
        tick_result: TickResult
        receipt: TrustedRetrievalReceipt

    class TrustedCoreAdapter:
        """The sole receipt issuer at the genuine external-event boundary."""

        @staticmethod
        def process_event(
            core: CoreEngine,
            event: SurfaceEvent,
            *,
            boundary: bool | HardBoundary = False,
            additional_evidence: Iterable[AdjudicatedEvidence] = (),
        ) -> TrustedCoreEvent:
            result = core.process_event(
                event,
                boundary=boundary,
                additional_evidence=additional_evidence,
            )
            frontier = tuple(sorted(result.activation.learning_frontier))
            activation = FrozenFloatMap(
                tuple(
                    (cell_id, result.activation.next_activation[cell_id])
                    for cell_id in frontier
                )
            )
            receipt = _issue(
                _IssuanceRecord(
                    core,
                    core.network.version,
                    core.network.tick,
                    result.root_id,
                    frontier,
                    activation.entries,
                )
            )
            return TrustedCoreEvent(result, receipt)

    def validate_receipt(
        core: CoreEngine,
        receipt: object,
        version: int,
        tick: int,
    ) -> tuple[
        int,
        int,
        int,
        tuple[int, ...],
        tuple[tuple[int, float], ...],
    ]:
        if not isinstance(receipt, TrustedRetrievalReceipt):
            raise RetrievalAbort(FailureCode.STALE_TRUSTED_ROOT)
        try:
            record = _issued_record(receipt)
        except LookupError as error:
            raise RetrievalAbort(FailureCode.STALE_TRUSTED_ROOT) from error
        if (
            record.core is not core
            or record.post_commit_version != version
            or record.post_commit_tick != tick
        ):
            raise RetrievalAbort(FailureCode.STALE_TRUSTED_ROOT)
        return (
            record.post_commit_version,
            record.post_commit_tick,
            record.root_id,
            record.frontier,
            record.activation_entries,
        )

    return (
        TrustedRetrievalReceipt,
        TrustedCoreEvent,
        TrustedCoreAdapter,
        validate_receipt,
    )


(
    TrustedRetrievalReceipt,
    TrustedCoreEvent,
    TrustedCoreAdapter,
    validate_receipt,
) = _build_authority_boundary()
del _build_authority_boundary
