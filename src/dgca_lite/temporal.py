"""External-root lifecycle and bounded temporal provenance."""

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

    def apply_boundary(self) -> None:
        """Clear cross-boundary provenance while preserving the current root."""
        self._events.clear()

    def referenced_cells(self) -> frozenset[int]:
        return frozenset(cell_id for event in self._events for cell_id, _ in event.activations)

    def load(self, events: Iterable[TemporalEvent], next_root_id: int) -> None:
        self._events.clear()
        self._events.extend(events)
        self._next_root_id = next_root_id
        self._root = None
