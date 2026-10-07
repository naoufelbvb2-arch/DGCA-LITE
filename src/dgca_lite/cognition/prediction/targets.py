"""Closed, source-specific prediction targets. These values confer no authority."""

from dataclasses import dataclass

from ..identity import CanonicalDescriptor
from ..serialization import canonical_identity_bytes


def d(kind, *values):
    return CanonicalDescriptor(kind, values)


def cell_id(value):
    if type(value) is not int or not 0 <= value < 2**63:
        raise ValueError("exact nonnegative bounded Cell/Assembly identity required")
    return value


def cell_set(values, *, maximum=256, nonempty=True):
    if type(values) is not tuple or len(values) > maximum:
        raise ValueError("Cell set outer bound")
    if nonempty and not values:
        raise ValueError("empty target Cell set")
    for value in values:
        cell_id(value)
    if values != tuple(sorted(set(values))):
        raise ValueError("canonical unique ascending Cell set required")
    return values


def source_id(source):
    if (
        type(source) is not CanonicalDescriptor
        or source.kind != "PredictionSourceIdentity"
        or type(source.values) is not tuple
        or len(source.values) != 2
    ):
        raise TypeError("closed typed source identity required")
    kind, number = source.values
    if type(kind) is not str or kind not in ("ASM", "ATOM"):
        raise ValueError("unknown source class")
    cell_id(number)
    return source


@dataclass(frozen=True, slots=True)
class BranchPattern:
    target_assembly_id: int
    anchor_carriers: tuple[int, ...]
    pattern_cells: tuple[int, ...]
    source_identity: CanonicalDescriptor

    def canonical_descriptor(self):
        # Both outer bounds precede traversal of either member set.
        if any(
            type(v) is not tuple or len(v) > 256
            for v in (self.anchor_carriers, self.pattern_cells)
        ):
            raise ValueError("target outer bound")
        cell_id(self.target_assembly_id)
        cell_set(self.anchor_carriers)
        cell_set(self.pattern_cells)
        source_id(self.source_identity)
        if not set(self.anchor_carriers) <= set(self.pattern_cells):
            raise ValueError("anchors must belong to the sealed pattern")
        return d(
            "BranchPattern",
            self.target_assembly_id,
            self.anchor_carriers,
            self.pattern_cells,
            self.source_identity,
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


@dataclass(frozen=True, slots=True)
class AtomicCarrier:
    carrier_id: int
    source_identity: CanonicalDescriptor

    def canonical_descriptor(self):
        cell_id(self.carrier_id)
        source_id(self.source_identity)
        return d("AtomicCarrier", self.carrier_id, self.source_identity)

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


def target_from_data(data):
    if type(data) is not CanonicalDescriptor or type(data.values) is not tuple:
        raise TypeError("closed target descriptor required")
    if data.kind == "BranchPattern" and len(data.values) == 4:
        return BranchPattern(*data.values)
    if data.kind == "AtomicCarrier" and len(data.values) == 2:
        return AtomicCarrier(*data.values)
    raise ValueError("unknown target shape")


@dataclass(frozen=True, slots=True)
class TargetGuard:
    target: CanonicalDescriptor
    construction_policy_revision: CanonicalDescriptor

    def canonical_descriptor(self):
        target_from_data(self.target)
        if type(self.construction_policy_revision) is not CanonicalDescriptor:
            raise TypeError("closed construction policy identity required")
        return d("TargetGuard", self.target, self.construction_policy_revision)

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())
