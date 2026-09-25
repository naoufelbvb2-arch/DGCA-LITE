"""DGCA LITE Layer 2 transient memory and retrieval.

Layer 2 reconstructs immutable retrieval views from frozen Layer 1 state.  It
owns no persistent cognitive state and never mutates Core.
"""

from .config import MemoryConfig
from .types import (
    BranchID,
    FailureCode,
    FamilyID,
    RetrievalFailure,
    RetrievalResult,
    SourceID,
)

__all__ = [
    "BranchID",
    "FailureCode",
    "FamilyID",
    "MemoryConfig",
    "RetrievalFailure",
    "RetrievalResult",
    "SourceID",
]
