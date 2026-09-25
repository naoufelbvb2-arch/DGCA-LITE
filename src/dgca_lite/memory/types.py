"""Immutable canonical and operational values for Layer 2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from dgca_lite.model import SynapseScope, SynapseState, Territory


class FailureCode(str, Enum):
    INVALID_CUE = "INVALID_CUE"
    EMPTY_CUE = "EMPTY_CUE"
    CUE_CAPACITY_ABORT = "CUE_CAPACITY_ABORT"
    STALE_TRUSTED_ROOT = "STALE_TRUSTED_ROOT"
    SNAPSHOT_ABORTED = "SNAPSHOT_ABORTED"
    SNAPSHOT_CAPACITY_ABORT = "SNAPSHOT_CAPACITY_ABORT"
    INTERNAL_ABORT = "INTERNAL_ABORT"


@dataclass(frozen=True, slots=True)
class RetrievalFailure:
    code: FailureCode
    detail: str = ""


class RetrievalAbort(RuntimeError):
    """Private control flow converted to ``RetrievalFailure`` at publication."""

    def __init__(self, code: FailureCode, detail: str = "") -> None:
        super().__init__(code.value)
        self.code = code
        self.detail = detail


class SourceKind(str, Enum):
    ASSEMBLY = "ASM"
    ATOMIC = "ATOM"

    @property
    def order(self) -> int:
        return 0 if self is SourceKind.ASSEMBLY else 1


@dataclass(frozen=True, slots=True)
class SourceID:
    kind: SourceKind
    numeric_id: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.numeric_id, int)
            or isinstance(self.numeric_id, bool)
            or self.numeric_id < 0
        ):
            raise ValueError("Source numeric ID must be a nonnegative integer")

    @classmethod
    def assembly(cls, assembly_id: int) -> SourceID:
        return cls(SourceKind.ASSEMBLY, assembly_id)

    @classmethod
    def atomic(cls, cell_id: int) -> SourceID:
        return cls(SourceKind.ATOMIC, cell_id)

    def canonical_key(self) -> tuple[int, int]:
        return (self.kind.order, self.numeric_id)

    def as_tuple(self) -> tuple[str, int]:
        return (self.kind.value, self.numeric_id)


@dataclass(frozen=True, slots=True)
class FamilyID:
    assembly_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.assembly_ids:
            raise ValueError("FamilyID must contain at least one Assembly")
        if self.assembly_ids != tuple(sorted(set(self.assembly_ids))):
            raise ValueError("FamilyID Assembly IDs must be sorted and unique")
        if any(item < 0 for item in self.assembly_ids):
            raise ValueError("FamilyID values must be nonnegative")

    def as_tuple(self) -> tuple[str, tuple[int, ...]]:
        return ("FAM", self.assembly_ids)


@dataclass(frozen=True, slots=True)
class BranchID:
    source_id: SourceID
    target_assembly_id: int

    def __post_init__(self) -> None:
        if self.target_assembly_id < 0:
            raise ValueError("target Assembly ID must be nonnegative")

    def canonical_key(self) -> tuple[int, int, int]:
        return (*self.source_id.canonical_key(), self.target_assembly_id)

    def as_tuple(self) -> tuple[tuple[str, int], tuple[str, int]]:
        return (self.source_id.as_tuple(), ("ASM", self.target_assembly_id))


@dataclass(frozen=True, slots=True)
class FrozenFloatMap:
    entries: tuple[tuple[int, float], ...] = ()

    def __post_init__(self) -> None:
        ids = tuple(item[0] for item in self.entries)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("map keys must be sorted and unique")

    @classmethod
    def from_dict(cls, values: dict[int, float]) -> FrozenFloatMap:
        return cls(tuple(sorted(values.items())))

    def to_dict(self) -> dict[int, float]:
        return dict(self.entries)

    def get(self, key: int, default: float | None = None) -> float | None:
        return self.to_dict().get(key, default)

    def __len__(self) -> int:
        return len(self.entries)


@dataclass(frozen=True, slots=True)
class SeedValue:
    drive: float
    exact_one: bool

    def __post_init__(self) -> None:
        if not isfinite(self.drive) or not 0.0 < self.drive <= 1.0:
            raise ValueError("seed drive must be finite and in (0, 1]")
        if self.exact_one and self.drive != 1.0:
            raise ValueError("exact-one seed drive must equal one")


@dataclass(frozen=True, slots=True)
class SeedState:
    entries: tuple[tuple[int, SeedValue], ...]

    def __post_init__(self) -> None:
        if not self.entries:
            raise ValueError("SeedState must be nonempty")
        ids = tuple(item[0] for item in self.entries)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("SeedState keys must be sorted and unique")

    @classmethod
    def from_dict(cls, values: dict[int, SeedValue]) -> SeedState:
        return cls(tuple(sorted(values.items())))

    def to_dict(self) -> dict[int, SeedValue]:
        return dict(self.entries)


@dataclass(frozen=True, slots=True)
class CapturedCell:
    id: int
    territory: Territory
    committed: bool
    activation: float
    synaptic_budget: int


@dataclass(frozen=True, slots=True)
class CapturedSynapse:
    source_id: int
    target_id: int
    strength: float
    evidence_mass: float
    state: SynapseState
    scope: SynapseScope

    def quality(self, e_max: float) -> float:
        return self.strength * self.evidence_mass / e_max

    def canonical_key(self) -> tuple[int, int, int]:
        return (self.source_id, self.target_id, self.scope.order)


@dataclass(frozen=True, slots=True)
class CapturedAssembly:
    id: int
    territory: Territory
    members: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class FrozenParameters:
    core_fingerprint: str
    theta_A: float
    theta_active: float
    K_max: int
    M_max: int
    E_max: float
    K_C: int
    theta_PC: float
    theta_AR: float


@dataclass(frozen=True, slots=True)
class RetrievalSnapshot:
    version: int
    tick: int
    cells: tuple[CapturedCell, ...]
    assemblies: tuple[CapturedAssembly, ...]
    memberships: tuple[tuple[int, tuple[int, ...]], ...]
    local_synapses: tuple[CapturedSynapse, ...]
    associative_synapses: tuple[CapturedSynapse, ...]

    def cell_map(self) -> dict[int, CapturedCell]:
        return {item.id: item for item in self.cells}

    def assembly_map(self) -> dict[int, CapturedAssembly]:
        return {item.id: item for item in self.assemblies}

    def membership_map(self) -> dict[int, tuple[int, ...]]:
        return dict(self.memberships)

    def local_edge_map(self) -> dict[tuple[int, int], CapturedSynapse]:
        return {(item.source_id, item.target_id): item for item in self.local_synapses}

    def associative_by_source(self) -> dict[int, tuple[CapturedSynapse, ...]]:
        result: dict[int, list[CapturedSynapse]] = {}
        for edge in self.associative_synapses:
            result.setdefault(edge.source_id, []).append(edge)
        return {
            source: tuple(sorted(edges, key=lambda item: item.target_id))
            for source, edges in result.items()
        }


@dataclass(frozen=True, slots=True)
class RetrievalUniverse:
    trusted_root_id: int | None
    trusted_cue: FrozenFloatMap
    internal_cue: FrozenFloatMap
    merged_cue: FrozenFloatMap
    seed_ids: tuple[int, ...]
    authorized_ids: tuple[int, ...]
    snapshot: RetrievalSnapshot
    parameters: FrozenParameters


@dataclass(frozen=True, slots=True)
class ReciprocalLink:
    left: int
    right: int
    quality: float

    def __post_init__(self) -> None:
        if self.left >= self.right:
            raise ValueError("reciprocal link endpoints must be canonical and distinct")
        if not isfinite(self.quality) or not 0.0 <= self.quality <= 1.0:
            raise ValueError("reciprocal quality must be finite and in [0, 1]")


@dataclass(frozen=True, slots=True)
class ReconstructionGraph:
    assembly_id: int
    members: tuple[int, ...]
    links: tuple[ReciprocalLink, ...]

    def __post_init__(self) -> None:
        if not self.members or self.members != tuple(sorted(set(self.members))):
            raise ValueError("graph members must be nonempty, sorted, and unique")
        member_set = set(self.members)
        keys: set[tuple[int, int]] = set()
        for link in self.links:
            key = (link.left, link.right)
            if link.left not in member_set or link.right not in member_set or key in keys:
                raise ValueError("invalid or duplicate reciprocal link")
            keys.add(key)


@dataclass(frozen=True, slots=True)
class CompletionStep:
    cell_id: int
    admission_round: int
    supporters: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ReconstructionLane:
    admitted_cells: tuple[int, ...]
    drives: tuple[tuple[int, float], ...]
    exact_one: tuple[tuple[int, bool], ...]
    admission_rounds: tuple[tuple[int, int], ...]
    completion_steps: tuple[CompletionStep, ...]

    def drive_map(self) -> dict[int, float]:
        return dict(self.drives)

    def exact_one_map(self) -> dict[int, bool]:
        return dict(self.exact_one)


class ProvenanceKind(str, Enum):
    SOURCE_COMPLETION = "PC"
    ASSOCIATIVE = "AR"
    TARGET_COMPLETION = "TPC"


@dataclass(frozen=True, slots=True)
class RetrievalProvenance:
    kind: ProvenanceKind
    source_id: SourceID
    cell_id: int
    admission_round: int | None = None
    target_assembly_id: int | None = None
    supporters: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class RootView:
    trusted_root_id: int | None
    merged_cue: FrozenFloatMap
    authorized_witnesses: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class SourceView:
    source_id: SourceID
    seed_state: SeedState
    root_authorized_witnesses: tuple[int, ...]
    reconstructed_cells: tuple[int, ...]
    retrieval_drive: tuple[tuple[int, float], ...]
    exact_one_flags: tuple[tuple[int, bool], ...]
    admission_rounds: tuple[tuple[int, int], ...]
    family_id: FamilyID | None
    dominates: tuple[SourceID, ...]
    dominated_by: tuple[SourceID, ...]
    provenance: tuple[RetrievalProvenance, ...]


@dataclass(frozen=True, slots=True)
class SeparationFamily:
    family_id: FamilyID
    sources: tuple[SourceID, ...]
    undominated: tuple[SourceID, ...]


@dataclass(frozen=True, slots=True)
class SeparationResult:
    families: tuple[SeparationFamily, ...]
    witnesses: tuple[tuple[SourceID, tuple[int, ...]], ...]
    dominance: tuple[tuple[SourceID, SourceID], ...]


@dataclass(frozen=True, slots=True)
class SourceActivity:
    source_id: SourceID
    cells: tuple[int, ...]
    drives: tuple[tuple[int, float], ...]
    exact_one: tuple[tuple[int, bool], ...]


@dataclass(frozen=True, slots=True)
class DirectHit:
    source_id: SourceID
    cell_id: int
    drive: float
    exact_one: bool
    supporters: tuple[int, ...]
    provenance: RetrievalProvenance

    def canonical_key(self) -> tuple[int, int, int]:
        return (*self.source_id.canonical_key(), self.cell_id)


@dataclass(frozen=True, slots=True)
class BranchView:
    branch_id: BranchID
    target_seed_state: SeedState
    reconstructed_target_cells: tuple[int, ...]
    retrieval_drive: tuple[tuple[int, float], ...]
    exact_one_flags: tuple[tuple[int, bool], ...]
    admission_rounds: tuple[tuple[int, int], ...]
    provenance: tuple[RetrievalProvenance, ...]


@dataclass(frozen=True, slots=True)
class AssociationResult:
    direct_hits: tuple[DirectHit, ...]
    branch_seeds: tuple[tuple[BranchID, SeedState], ...]


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    root: RootView
    sources: tuple[SourceView, ...]
    direct_hits: tuple[DirectHit, ...]
    branches: tuple[BranchView, ...]


@dataclass(frozen=True, slots=True)
class RetrievalDiagnostics:
    snapshot_cells: int = 0
    snapshot_assemblies: int = 0
    snapshot_synapses: int = 0
    source_count: int = 0
    branch_count: int = 0
    reconstruction_rounds: int = 0
    cache_hits: int = 0


def canonical_source_key(value: SourceID) -> tuple[int, int]:
    return value.canonical_key()


def immutable_value_tree(value: Any) -> bool:
    """Diagnostic helper used by architecture tests, not retrieval decisions."""
    if isinstance(value, (str, bytes, int, float, bool, type(None), Enum)):
        return True
    if isinstance(value, tuple):
        return all(immutable_value_tree(item) for item in value)
    if hasattr(value, "__dataclass_fields__"):
        return all(
            immutable_value_tree(getattr(value, name))
            for name in value.__dataclass_fields__
        )
    return False
