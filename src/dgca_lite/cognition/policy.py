"""Frozen mechanical bounds; no learned thresholds or semantic ranking."""

from dataclasses import dataclass, fields


@dataclass(frozen=True, slots=True)
class ValueLimits:
    """Bounds for one complete closed-value validation/serialization.

    These administrative defaults bound data representation, not truth,
    confidence, inference, or forecast acceptance. Runtime policy bindings must
    retain the exact limits used by charged work.
    """

    max_nodes: int = 4096
    max_depth: int = 64
    max_scalar_bytes: int = 65536

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{field.name} must be a positive integer")


DEFAULT_VALUE_LIMITS = ValueLimits()
