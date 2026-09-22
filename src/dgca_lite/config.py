"""Calibration surface and invariant validation for Core v0.4."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any


def _finite(name: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")


def _unit(name: str, value: float) -> None:
    _finite(name, value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class CoreConfig:
    """Numerical calibration; none of these fields are learned state."""

    logical_capacity: int = 1_000_000
    default_synaptic_budget: int = 32

    delta_A: float = 0.25
    gamma_A: float = 0.75
    theta_active: float = 0.10
    theta_emit: float = 0.20

    local_radius: float = 2.0
    associative_radius: float = 4.0
    specificity_radius: float = 4.0
    assembly_radius: float = 6.0
    max_neighborhood: int = 256
    alpha: float = 0.50
    temporal_horizon: int = 4

    theta_R: float = 0.20
    K_R: int = 8

    theta_create: float = 0.01
    E_max: float = 10.0
    theta_S: float = 0.70
    theta_E: float = 0.20
    theta_demote: float = 0.30
    theta_prune: float = 0.10

    theta_A: float = 0.10
    K_min: int = 3
    K_max: int = 16
    d_min: int = 2
    rho: float = 0.70
    rho_G: float = 0.50
    sigma_G: float = 0.30
    rho_keep: float = 0.35
    sigma_keep: float = 0.20
    M_max: int = 4
    epsilon: float = 1e-12

    max_event_bytes: int = 256
    continuation_bytes: int = 128
    receptor_fanout: int = 4
    overlap_ngram_max: int = 3

    def __post_init__(self) -> None:
        if self.logical_capacity < 3:
            raise ValueError("logical_capacity must address all three territories")
        for name in (
            "default_synaptic_budget",
            "max_neighborhood",
            "K_R",
            "K_min",
            "K_max",
            "M_max",
            "max_event_bytes",
            "continuation_bytes",
            "receptor_fanout",
            "overlap_ngram_max",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.temporal_horizon < 1:
            raise ValueError("temporal_horizon must be at least one")
        language_capacity = (self.logical_capacity + 2) // 3
        if self.receptor_fanout > language_capacity:
            raise ValueError(
                "receptor_fanout exceeds addressable LANGUAGE receptor capacity"
            )
        if not 0 < self.theta_active <= self.theta_emit <= 1:
            raise ValueError("0 < theta_active <= theta_emit <= 1 is required")
        for name in (
            "delta_A",
            "gamma_A",
            "theta_R",
            "theta_create",
            "theta_S",
            "theta_E",
            "theta_demote",
            "theta_prune",
            "theta_A",
            "rho",
            "rho_G",
            "sigma_G",
            "rho_keep",
            "sigma_keep",
        ):
            _unit(name, getattr(self, name))
        if self.theta_demote >= self.theta_S:
            raise ValueError("theta_demote must be less than theta_S")
        if self.rho_G <= self.rho_keep:
            raise ValueError("rho_G must be greater than rho_keep")
        if self.sigma_G <= self.sigma_keep:
            raise ValueError("sigma_G must be greater than sigma_keep")
        if self.K_min > self.K_max:
            raise ValueError("K_min must not exceed K_max")
        if not 0 <= self.d_min < self.K_max:
            raise ValueError("d_min must be feasible for an Assembly")
        for name in (
            "local_radius",
            "associative_radius",
            "specificity_radius",
            "assembly_radius",
            "E_max",
            "epsilon",
            "alpha",
        ):
            value = getattr(self, name)
            _finite(name, value)
            if name == "alpha":
                if value < 0:
                    raise ValueError("alpha must be nonnegative")
            elif value <= 0:
                raise ValueError(f"{name} must be positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> CoreConfig:
        return cls(**values)
