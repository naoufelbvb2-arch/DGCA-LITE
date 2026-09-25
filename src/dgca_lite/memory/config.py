"""Immutable Layer 2 calibration and administrative capacity limits."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class MemoryConfig:
    """Layer 2 configuration; no field is learned cognitive state."""

    K_C: int = 64
    theta_PC: float = 0.50
    theta_AR: float = 0.50

    # Administrative acquisition limits.  ``None`` means that the canonical
    # session-derived structural bounds are the only limits.  A finite limit
    # can only abort complete acquisition; it never truncates or ranks.
    max_snapshot_cells: int | None = None
    max_snapshot_assemblies: int | None = None
    max_snapshot_synapses: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.K_C, int) or isinstance(self.K_C, bool) or self.K_C <= 0:
            raise ValueError("K_C must be a positive integer")
        for name in ("theta_PC", "theta_AR"):
            value = getattr(self, name)
            if not isfinite(value) or not 0.0 < value <= 1.0:
                raise ValueError(f"{name} must be finite and in (0, 1]")
        for name in (
            "max_snapshot_cells",
            "max_snapshot_assemblies",
            "max_snapshot_synapses",
        ):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value <= 0
            ):
                raise ValueError(f"{name} must be a positive integer or None")
