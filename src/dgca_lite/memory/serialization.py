"""Canonical deterministic Layer 2 result serialization and signatures."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import fields, is_dataclass
from enum import Enum
from math import isfinite

from .types import RetrievalResult

_MAGIC = b"DGCA-LITE-L2-R1\x00"


def _length(value: int) -> bytes:
    return value.to_bytes(8, "big", signed=False)


def _encode(value: object) -> bytes:
    if value is None:
        return b"N"
    if isinstance(value, bool):
        return b"T" if value else b"F"
    if isinstance(value, Enum):
        return b"E" + _encode(type(value).__qualname__) + _encode(value.value)
    if isinstance(value, int):
        payload = str(value).encode("ascii")
        return b"I" + _length(len(payload)) + payload
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("canonical results cannot contain nonfinite floats")
        return b"D" + struct.pack(">d", value)
    if isinstance(value, str):
        payload = value.encode("utf-8")
        return b"S" + _length(len(payload)) + payload
    if isinstance(value, bytes):
        return b"B" + _length(len(value)) + value
    if isinstance(value, tuple):
        return b"A" + _length(len(value)) + b"".join(_encode(item) for item in value)
    if is_dataclass(value) and not isinstance(value, type):
        encoded_fields = tuple(
            (field.name, getattr(value, field.name)) for field in fields(value)
        )
        return b"R" + _encode(type(value).__qualname__) + _encode(encoded_fields)
    raise TypeError(f"unsupported canonical value: {type(value).__qualname__}")


def canonical_result_bytes(result: RetrievalResult) -> bytes:
    return _MAGIC + _encode(result)


def behavioral_signature(result: RetrievalResult) -> str:
    return hashlib.sha256(canonical_result_bytes(result)).hexdigest()
