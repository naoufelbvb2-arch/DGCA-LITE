"""Transient projection data and frozen finite mechanical Prediction policy."""

from dataclasses import dataclass

from ..identity import CanonicalDescriptor, SnapshotBinding
from ..ingress import _snapshot
from ..serialization import canonical_identity_bytes
from .targets import d, target_from_data


@dataclass(frozen=True, slots=True)
class PredictionPolicy:
    max_live_forecasts: int = 16
    max_horizon: int = 8
    max_targets: int = 64
    max_capture_cells: int = 128
    max_capture_assemblies: int = 32
    max_capture_synapses: int = 512

    def __post_init__(self):
        for value, ceiling in (
            (self.max_live_forecasts, 64),
            (self.max_horizon, 64),
            (self.max_targets, 256),
            (self.max_capture_cells, 512),
            (self.max_capture_assemblies, 128),
            (self.max_capture_synapses, 2048),
        ):
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError("finite exact Prediction policy bound required")

    def canonical_descriptor(self):
        self.__post_init__()
        return d(
            "PredictionPolicy",
            self.max_live_forecasts,
            self.max_horizon,
            self.max_targets,
            self.max_capture_cells,
            self.max_capture_assemblies,
            self.max_capture_synapses,
            "ROOT_SEEDED_SOURCE_VIEW_ONLY_V1",
            "TERMINATE_ON_HARD_BOUNDARY_V1",
        )


@dataclass(frozen=True, slots=True)
class ConditionalProjectionView:
    origin_class: str
    snapshot: SnapshotBinding
    targets: tuple[CanonicalDescriptor, ...]
    input_provenance: CanonicalDescriptor

    def canonical_descriptor(self):
        if type(self.targets) is not tuple or len(self.targets) > 256:
            raise ValueError("projection outer bound")
        if type(self.origin_class) is not str or self.origin_class not in (
            "TRUSTED_ONLY",
            "MIXED",
            "INTERNAL_ONLY",
        ):
            raise ValueError("closed origin class required")
        if type(self.snapshot) is not SnapshotBinding:
            raise TypeError("exact historical snapshot binding required")
        if type(self.input_provenance) is not CanonicalDescriptor:
            raise TypeError("closed provenance descriptor required")
        for target in self.targets:
            target_from_data(target)
        keys = tuple(canonical_identity_bytes(t) for t in self.targets)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("unique canonical target order required")
        return d(
            "ConditionalProjectionView",
            self.origin_class,
            self.snapshot,
            self.targets,
            self.input_provenance,
        )

    def __post_init__(self):
        canonical_identity_bytes(self.canonical_descriptor())


def freeze_projection(view):
    data = _snapshot(view.canonical_descriptor())
    return ConditionalProjectionView(*data.values)
