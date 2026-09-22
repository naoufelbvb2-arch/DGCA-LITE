"""DGCA LITE Layer 1 Core v0.4.

``01_CORE_v0.4.md`` is the sole architectural authority for this package.
"""

from .config import CoreConfig
from .engine import CoreEngine, TickDiagnostics, TickResult
from .model import (
    Assembly,
    Cell,
    HardBoundary,
    SurfaceEvent,
    Synapse,
    SynapseScope,
    SynapseState,
    Territory,
)

__all__ = [
    "Assembly",
    "Cell",
    "CoreConfig",
    "CoreEngine",
    "HardBoundary",
    "SurfaceEvent",
    "Synapse",
    "SynapseScope",
    "SynapseState",
    "Territory",
    "TickDiagnostics",
    "TickResult",
]
