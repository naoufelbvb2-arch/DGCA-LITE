"""Rollback-safe external-root staging and bounded temporal provenance."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from .config import CoreConfig
from .model import TemporalEvent


@dataclass(slots=True)
class ExternalRoot:
    id: int
    open: bool = True


@dataclass(frozen=True, slots=True)
class TemporalTransaction:
    """Prospective temporal/root state published only after Network commit."""

    base_next_root_id: int
    root_id: int
    events: tuple[TemporalEvent, ...]
    surviving_history: tuple[TemporalEvent, ...]
    pre_references: frozenset[int]
    post_references: frozenset[int]
    expired_references: frozenset[int]


def event_references(event: TemporalEvent) -> frozenset[int]:
    return frozenset(
        [cell_id for cell_id, _ in event.activations]
        + [cell_id for cell_id, _ in event.receptor_drive]
    )


def context_references(events: Iterable[TemporalEvent]) -> frozenset[int]:
    return frozenset(
        cell_id for event in events for cell_id in event_references(event)
    )


class TemporalStream:
    def __init__(self, config: CoreConfig) -> None:
        self.config = config
        self._events: deque[TemporalEvent] = deque(maxlen=config.temporal_horizon)
        self._next_root_id = 0
        self._root: ExternalRoot | None = None

    @property
    def events(self) -> tuple[TemporalEvent, ...]:
        return tuple(self._events)

    @property
    def open_root(self) -> ExternalRoot | None:
        return self._root

    @property
    def next_root_id(self) -> int:
        return self._next_root_id

    def prospective(
        self, event: TemporalEvent, *, boundary: bool = False
    ) -> TemporalTransaction:
        """Construct post-commit context without mutating live temporal state."""
        if self._root is not None and self._root.open:
            raise RuntimeError("an external root is already open")
        before = tuple(self._events)
        base_history = () if boundary else before
        combined = (*base_history, event)
        post = tuple(combined[-self.config.temporal_horizon :])
        surviving_history = tuple(item for item in base_history if item in post)
        pre_references = context_references(before)
        post_references = context_references(post)
        return TemporalTransaction(
            self._next_root_id,
            self._next_root_id,
            post,
            surviving_history,
            pre_references,
            post_references,
            pre_references - post_references,
        )

    def validate(self, transaction: TemporalTransaction) -> None:
        if self._root is not None and self._root.open:
            raise RuntimeError("an external root is already open")
        if transaction.base_next_root_id != self._next_root_id:
            raise RuntimeError("stale temporal transaction")
        if transaction.root_id != self._next_root_id:
            raise ValueError("noncanonical external root allocation")
        if len(transaction.events) > self.config.temporal_horizon:
            raise ValueError("temporal transaction exceeds bounded horizon")

    def publish(self, transaction: TemporalTransaction) -> None:
        """Publish a transaction validated before Network commit."""
        self._events = deque(transaction.events, maxlen=self.config.temporal_horizon)
        self._next_root_id = transaction.root_id + 1
        self._root = None

    def begin(self) -> ExternalRoot:
        if self._root is not None and self._root.open:
            raise RuntimeError("an external root is already open")
        root = ExternalRoot(self._next_root_id)
        self._next_root_id += 1
        self._root = root
        return root

    def finalize(self, event: TemporalEvent) -> None:
        if self._root is None or not self._root.open:
            raise RuntimeError("no open root to finalize")
        self._root.open = False
        self._root = None
        if self.config.temporal_horizon:
            self._events.append(event)

    def abort(self) -> None:
        if self._root is not None:
            self._root.open = False
        self._root = None

    def clear_boundary(self) -> None:
        self.abort()
        self._events.clear()

    def referenced_cells(self) -> frozenset[int]:
        return context_references(self._events)

    def load(self, events: Iterable[TemporalEvent], next_root_id: int) -> None:
        self._events.clear()
        self._events.extend(events)
        self._next_root_id = next_root_id
        self._root = None
