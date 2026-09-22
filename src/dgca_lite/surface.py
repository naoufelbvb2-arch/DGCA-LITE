"""Deterministic, reversible, non-semantic Surface interface."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from .config import CoreConfig
from .model import SparseSignature, SurfaceEvent, SurfaceFeature, Territory
from .topology import Topology

_SEGMENTS = re.compile(r"\w+|\s+|[^\w\s]", re.UNICODE)


class SurfaceCodec:
    def __init__(self, config: CoreConfig, topology: Topology) -> None:
        self.config = config
        self.topology = topology

    def segment(self, text: str) -> tuple[SurfaceEvent, ...]:
        """Mechanical segmentation whose concatenation exactly recovers ``text``."""
        return tuple(SurfaceEvent.from_text(match.group(0)) for match in _SEGMENTS.finditer(text))

    def encode(self, event: SurfaceEvent) -> SparseSignature:
        raw = event.data
        chunk_size = min(self.config.max_event_bytes, self.config.continuation_bytes)
        chunks = tuple(raw[index : index + chunk_size] for index in range(0, len(raw), chunk_size))
        if not chunks:
            chunks = (b"",)

        features: list[SurfaceFeature] = [
            SurfaceFeature("BOUNDARY", b"START"),
            SurfaceFeature("LENGTH", len(raw).to_bytes(8, "big")),
        ]
        for chunk_index, chunk in enumerate(chunks):
            features.append(
                SurfaceFeature(
                    "CHUNK",
                    chunk_index.to_bytes(4, "big") + len(chunk).to_bytes(4, "big"),
                )
            )
        for position, byte in enumerate(raw):
            features.append(
                SurfaceFeature("POSITIONAL_BYTE", position.to_bytes(8, "big") + bytes((byte,)))
            )
        maximum = min(self.config.overlap_ngram_max, len(raw))
        for size in range(1, maximum + 1):
            for start in range(len(raw) - size + 1):
                features.append(SurfaceFeature(f"BYTE_NGRAM_{size}", raw[start : start + size]))
        features.append(SurfaceFeature("BOUNDARY", b"END"))
        return SparseSignature(chunks=chunks, features=tuple(features))

    def decode(self, signature: SparseSignature) -> SurfaceEvent:
        return SurfaceEvent(b"".join(signature.chunks))

    def _feature_digest(self, feature: SurfaceFeature, salt: int) -> int:
        digest = hashlib.blake2b(
            feature.kind.encode("ascii")
            + b"\0"
            + feature.payload
            + salt.to_bytes(4, "big"),
            digest_size=16,
            person=b"DGCA-v0.3-entry",
        ).digest()
        return int.from_bytes(digest, "big")

    def project(self, feature: SurfaceFeature) -> tuple[int, ...]:
        """Mechanical Entry Projection Pi(feature)."""
        start, end = self.topology.bounds(Territory.LANGUAGE)
        size = end - start
        anchor = start + self._feature_digest(feature, 0) % size
        receptors: list[int] = [anchor]
        for neighbor in self.topology.neighborhood(anchor, scope=self._local_scope()):
            if neighbor not in receptors:
                receptors.append(neighbor)
            if len(receptors) >= self.config.receptor_fanout:
                return tuple(receptors)
        salt = 1
        while len(receptors) < self.config.receptor_fanout:
            candidate = start + self._feature_digest(feature, salt) % size
            if candidate not in receptors:
                receptors.append(candidate)
            salt += 1
        return tuple(receptors)

    @staticmethod
    def _local_scope():
        # Local import keeps the mechanical feature type independent of Synapses.
        from .model import SynapseScope

        return SynapseScope.LOCAL

    def receptor_drive(
        self, signature: SparseSignature
    ) -> tuple[tuple[int, float], ...]:
        factors: dict[int, list[float]] = defaultdict(list)
        for feature in signature.features:
            if not 0 <= feature.weight <= 1:
                raise ValueError("Surface feature drive must be in [0, 1]")
            for receptor in self.project(feature):
                factors[receptor].append(feature.weight)
        result: list[tuple[int, float]] = []
        for receptor in sorted(factors):
            remaining = 1.0
            for weight in factors[receptor]:
                remaining *= 1.0 - weight
            result.append((receptor, 1.0 - remaining))
        return tuple(result)

