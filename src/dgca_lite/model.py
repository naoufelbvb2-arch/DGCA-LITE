"""Canonical records and transient proposal types.

Only ``Cell``, ``Synapse`` and ``Assembly`` are canonical learned records.
Everything else in this module is an interface or transaction value.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite


class Territory(str, Enum):
    LANGUAGE = "LANGUAGE"
    AUDIO = "AUDIO"
    VISION = "VISION"


class SynapseState(str, Enum):
    CANDIDATE = "CANDIDATE"
    CONSOLIDATED = "CONSOLIDATED"


class SynapseScope(str, Enum):
    LOCAL = "LOCAL"
    ASSOCIATIVE = "ASSOCIATIVE"
    CROSS_TERRITORY = "CROSS_TERRITORY"

    @property
    def order(self) -> int:
        return {
            SynapseScope.LOCAL: 0,
            SynapseScope.ASSOCIATIVE: 1,
            SynapseScope.CROSS_TERRITORY: 2,
        }[self]


@dataclass(frozen=True, slots=True)
class Cell:
    id: int
    territory: Territory
    committed: bool
    activation: float
    synaptic_budget: int

    def validate(self) -> None:
        if self.id < 0:
            raise ValueError("Cell ID must be nonnegative")
        if not isfinite(self.activation) or not 0 <= self.activation <= 1:
            raise ValueError("Cell activation must be finite and in [0, 1]")
        if self.synaptic_budget <= 0:
            raise ValueError("Cell synaptic_budget must be positive")


@dataclass(frozen=True, slots=True)
class Synapse:
    target_id: int
    strength: float
    evidence_mass: float
    state: SynapseState
    scope: SynapseScope

    def validate(self, source_id: int, e_max: float) -> None:
        if source_id < 0 or self.target_id < 0:
            raise ValueError("Synapse endpoint IDs must be nonnegative")
        if source_id == self.target_id:
            raise ValueError("Self-Synapses are forbidden")
        if not isfinite(self.strength) or not 0 <= self.strength <= 1:
            raise ValueError("Synapse strength must be finite and in [0, 1]")
        if not isfinite(self.evidence_mass) or not 0 <= self.evidence_mass <= e_max:
            raise ValueError("Synapse evidence must be finite and bounded")


@dataclass(frozen=True, slots=True)
class Assembly:
    id: int
    territory: Territory
    members: frozenset[int]

    def validate(self) -> None:
        if self.id < 0:
            raise ValueError("Assembly ID must be nonnegative")
        if not self.members or any(member < 0 for member in self.members):
            raise ValueError("Assembly members must be nonempty valid IDs")


@dataclass(frozen=True, slots=True)
class SurfaceEvent:
    data: bytes

    @classmethod
    def from_text(cls, text: str) -> SurfaceEvent:
        return cls(text.encode("utf-8"))

    def text(self) -> str:
        return self.data.decode("utf-8")


@dataclass(frozen=True, slots=True, order=True)
class SurfaceFeature:
    kind: str
    payload: bytes
    weight: float = field(default=1.0, compare=False)


@dataclass(frozen=True, slots=True)
class SparseSignature:
    chunks: tuple[bytes, ...]
    features: tuple[SurfaceFeature, ...]


@dataclass(frozen=True, slots=True)
class HardBoundary:
    present: bool = True


@dataclass(frozen=True, slots=True)
class TemporalEvent:
    tick: int
    activations: tuple[tuple[int, float], ...]
    signature: SparseSignature
    receptor_drive: tuple[tuple[int, float], ...]


@dataclass(frozen=True, slots=True)
class EvidenceProposal:
    root_id: int
    source_id: int
    target_id: int
    scope: SynapseScope
    q: float
    y: int
    external_origin: bool = True

    @property
    def identity(self) -> tuple[int, int, int, SynapseScope]:
        return (self.root_id, self.source_id, self.target_id, self.scope)


@dataclass(frozen=True, slots=True)
class AdjudicatedEvidence:
    source_id: int
    target_id: int
    scope: SynapseScope
    q: float
    y: int
    external_origin: bool = True


@dataclass(frozen=True, slots=True)
class RecruitmentProposal:
    cell_id: int
    drive: float
    expansion: bool = False


@dataclass(frozen=True, slots=True)
class AssemblyFormProposal:
    members: tuple[int, ...]
    core_coverage: float
    cohesion: float


@dataclass(frozen=True, slots=True)
class AssemblyGrowProposal:
    assembly_id: int
    cell_id: int
    integration: float
    specificity: float
    mean_reciprocal: float


@dataclass(frozen=True, slots=True)
class AssemblyMaintainProposal:
    assembly_id: int
    retained_members: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class TickSnapshot:
    version: int
    tick: int
    cells: Mapping[int, Cell]
    outgoing: Mapping[int, Mapping[tuple[int, SynapseScope], Synapse]]
    incoming: Mapping[int, frozenset[tuple[int, SynapseScope]]]
    assemblies: Mapping[int, Assembly]
    assembly_index: Mapping[frozenset[int], int]
    memberships: Mapping[int, frozenset[int]]
    active_ids: frozenset[int]


@dataclass(slots=True)
class TickTransaction:
    base_version: int
    next_activation: dict[int, float] = field(default_factory=dict)
    cell_commits: set[int] = field(default_factory=set)
    cell_reclaims: set[int] = field(default_factory=set)
    synapse_upserts: dict[tuple[int, int, SynapseScope], Synapse] = field(default_factory=dict)
    synapse_deletes: set[tuple[int, int, SynapseScope]] = field(default_factory=set)
    assembly_upserts: dict[int, Assembly] = field(default_factory=dict)
    assembly_deletes: set[int] = field(default_factory=set)
    touched_pairs: set[tuple[int, int]] = field(default_factory=set)
    references: set[int] = field(default_factory=set)
