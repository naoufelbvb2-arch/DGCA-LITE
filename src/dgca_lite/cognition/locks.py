"""Mechanical lock-order enforcement, never canonical identity or authority."""

from threading import RLock, local

from .authority import IngressAbort
from .types import FailureCode

_held = local()


def _deferred_cleanup(function):
    """Weakref cleanup is authority-reducing, never a dispatch callback.

    GC may interrupt allocation while any barrier is held. Queue only private
    bounded registry cleanup and drain at the outermost barrier release, before
    returning to caller. No worker, effect or positive authority is deferred.
    Each entry corresponds to one already-bounded, nonrenewable live handle.
    """

    def invoke(reference):
        if getattr(_held, "stack", ()) or getattr(_held, "draining", False):
            pending = getattr(_held, "cleanup", None)
            if pending is None:
                pending = _held.cleanup = []
            pending.append((function, reference))
        else:
            function(reference)

    return invoke


def _drain_cleanup():
    if getattr(_held, "stack", ()) or getattr(_held, "draining", False):
        return
    _held.draining = True
    try:
        while getattr(_held, "cleanup", None):
            function, reference = _held.cleanup.pop()
            function(reference)
    finally:
        _held.draining = False


class RankedBarrier:
    """Reject inversion before touching a mutex; reentry is same-lock only.

    Core=0, lifecycle=1, ledger=2, arena=3, owner=4, registry=5.
    Thread identity is used only by the mutex, never in canonical data.
    """

    def __init__(self, rank):
        if type(rank) is not int or not 0 <= rank <= 5:
            raise ValueError("invalid lock rank")
        self.rank = rank
        self._lock = RLock()

    def acquire(self, blocking=True, timeout=-1):
        stack = getattr(_held, "stack", ())
        if stack and (
            self.rank < stack[-1].rank
            or (self.rank == stack[-1].rank and self is not stack[-1])
        ):
            raise IngressAbort(
                FailureCode.INTERNAL_CONTRACT_VIOLATION, "lock inversion"
            )
        # Allocate the stack before acquiring, so failure cannot strand a lock.
        next_stack = (*stack, self)
        acquired = self._lock.acquire(blocking, timeout)
        if acquired:
            try:
                _held.stack = next_stack
            except BaseException:
                self._lock.release()
                raise
        return acquired

    def release(self):
        stack = getattr(_held, "stack", ())
        if not stack or stack[-1] is not self:
            raise IngressAbort(
                FailureCode.INTERNAL_CONTRACT_VIOLATION, "lock release order"
            )
        previous = stack[:-1]
        self._lock.release()
        _held.stack = previous
        _drain_cleanup()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exception):
        self.release()
