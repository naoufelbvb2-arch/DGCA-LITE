"""Closed Unit-4 storage values, not semantic constructors or live authority.

Entries are structural envelopes for already-produced data. A category label
does not mint an assertion basis, constraint activation, clearance, or result.
Future producers must supply their canonical semantic validation separately.
No callback, opaque payload, executable schema, or capability is admitted here.
"""

from dataclasses import dataclass, fields

from .identity import CanonicalDescriptor, SnapshotBinding
from .ingress import _snapshot
from .serialization import canonical_identity_bytes

ARENA_CATEGORIES = (
    "ASSERTION",
    "SOURCE_SUPPORT",
    "DEPENDENCY_ROOT",
    "SCOPE",
    "DERIVATION_WITNESS",
    "RETRIEVAL_VIEW",
    "PREDICTION_VIEW",
    "CAUSAL_RESULT_VIEW",
    "CONSTRAINT_FINDING",
    "CLEARANCE_RECORD",
    "STAGING_RECORD",
)
MAX_ARENA_ENTRIES = 128


@dataclass(frozen=True, slots=True)
class CIEPolicy:
    """Trusted mechanical foundation policy; no executable cognitive schemas."""

    max_entries: int = 64
    max_staged_entries: int = 64
    max_rounds: int = 32
    max_cies: int = 32
    max_snapshot_bytes: int = 262144

    def __post_init__(self):
        ceilings = (MAX_ARENA_ENTRIES, MAX_ARENA_ENTRIES, 256, 256, 4194304)
        for item, ceiling in zip(fields(self), ceilings, strict=True):
            value = getattr(self, item.name)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError(f"invalid mechanical CIE bound: {item.name}")

    def canonical_descriptor(self):
        self.__post_init__()
        return CanonicalDescriptor(
            "Unit4CIEFoundationPolicy",
            tuple((f.name, getattr(self, f.name)) for f in fields(self)),
        )


@dataclass(frozen=True, slots=True)
class ArenaEntry:
    category: str
    identity: CanonicalDescriptor
    payload: CanonicalDescriptor

    def canonical_descriptor(self):
        try:
            category, identity, payload = self.category, self.identity, self.payload
        except AttributeError as error:
            raise TypeError("incomplete arena entry") from error
        if type(category) is not str or category not in ARENA_CATEGORIES:
            raise TypeError("unknown arena category")
        if (
            type(identity) is not CanonicalDescriptor
            or type(payload) is not CanonicalDescriptor
        ):
            raise TypeError("arena identity/payload must be closed descriptors")
        return CanonicalDescriptor("ArenaEntry", (category, identity, payload))

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


def freeze_entry(entry):
    if type(entry) is not ArenaEntry:
        raise TypeError("unknown arena entry type")
    descriptor = _snapshot(entry.canonical_descriptor())
    return ArenaEntry(*descriptor.values)


def entry_key(entry):
    return canonical_identity_bytes(
        CanonicalDescriptor("ArenaEntryKey", (entry.category, entry.identity))
    )


@dataclass(frozen=True, slots=True)
class ArenaSnapshot:
    binding: SnapshotBinding
    entries: tuple[ArenaEntry, ...]

    def canonical_descriptor(self):
        try:
            binding, entries = self.binding, self.entries
        except AttributeError as error:
            raise TypeError("incomplete arena snapshot") from error
        if type(binding) is not SnapshotBinding or type(entries) is not tuple:
            raise TypeError("invalid arena snapshot")
        # Reject the OUTER bound before touching even one entry.
        if len(entries) > MAX_ARENA_ENTRIES:
            raise ValueError("snapshot entry bound exceeded")
        if any(type(entry) is not ArenaEntry for entry in entries):
            raise TypeError("unknown snapshot entry type")
        descriptor = CanonicalDescriptor(
            "ArenaSnapshot",
            (binding, tuple(e.canonical_descriptor() for e in entries)),
        )
        keys = tuple(entry_key(e) for e in entries)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("snapshot entries must be uniquely canonically ordered")
        return descriptor

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())

    @property
    def canonical_bytes(self):
        return canonical_identity_bytes(self.canonical_descriptor())


def clone_snapshot(snapshot):
    if type(snapshot) is not ArenaSnapshot:
        raise TypeError("unknown snapshot type")
    image = _snapshot(snapshot.canonical_descriptor())
    binding, entries = image.values
    return ArenaSnapshot(binding, tuple(ArenaEntry(*e.values) for e in entries))


@dataclass(frozen=True, slots=True)
class CognitiveResultView:
    """Terminal publication shell only; no completeness/fixed-point claim."""

    status: str
    snapshot: ArenaSnapshot

    def canonical_descriptor(self):
        from .types import FailureCode

        statuses = ("PUBLISHED", "ABORTED") + tuple(code.value for code in FailureCode)
        if type(self.status) is not str or self.status not in statuses:
            raise TypeError("unknown CIE terminal status")
        if type(self.snapshot) is not ArenaSnapshot:
            raise TypeError("invalid terminal snapshot")
        return CanonicalDescriptor(
            "CognitiveResultView", (self.status, self.snapshot.canonical_descriptor())
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())
