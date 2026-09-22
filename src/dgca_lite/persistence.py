"""Deterministic JSON persistence for canonical state and bounded provenance."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .config import CoreConfig
from .model import (
    Assembly,
    Cell,
    SparseSignature,
    SurfaceFeature,
    Synapse,
    SynapseScope,
    SynapseState,
    TemporalEvent,
    Territory,
)

if TYPE_CHECKING:
    from .engine import CoreEngine


def _signature_to_dict(signature: SparseSignature) -> dict[str, Any]:
    return {
        "chunks": [chunk.hex() for chunk in signature.chunks],
        "features": [
            {"kind": feature.kind, "payload": feature.payload.hex(), "weight": feature.weight}
            for feature in signature.features
        ],
    }


def _signature_from_dict(value: dict[str, Any]) -> SparseSignature:
    return SparseSignature(
        tuple(bytes.fromhex(chunk) for chunk in value["chunks"]),
        tuple(
            SurfaceFeature(
                feature["kind"], bytes.fromhex(feature["payload"]), feature["weight"]
            )
            for feature in value["features"]
        ),
    )


def engine_state(engine: CoreEngine) -> dict[str, Any]:
    return {
        "format": "DGCA-LITE-Core-v0.4",
        "config": engine.config.to_dict(),
        "network": engine.network.canonical_state(),
        "temporal": {
            "next_root_id": engine.temporal.next_root_id,
            "events": [
                {
                    "tick": event.tick,
                    "activations": [list(item) for item in event.activations],
                    "signature": _signature_to_dict(event.signature),
                    "receptor_drive": [list(item) for item in event.receptor_drive],
                }
                for event in engine.temporal.events
            ],
        },
    }


def save_engine(engine: CoreEngine, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(engine_state(engine), sort_keys=True, separators=(",", ":"))
    temporary = destination.with_name(destination.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, destination)


def load_engine(path: str | Path) -> CoreEngine:
    from .engine import CoreEngine

    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if value.get("format") != "DGCA-LITE-Core-v0.4":
        raise ValueError("unsupported persistence format")
    engine = CoreEngine(CoreConfig.from_dict(value["config"]))
    network_state = value["network"]
    for item in network_state["cells"]:
        engine.network.seed_cell(
            Cell(
                item["id"],
                Territory(item["territory"]),
                item["committed"],
                item["activation"],
                item["synaptic_budget"],
            )
        )
    for item in network_state["synapses"]:
        engine.network.seed_synapse(
            item["source_id"],
            Synapse(
                item["target_id"],
                item["strength"],
                item["evidence_mass"],
                SynapseState(item["state"]),
                SynapseScope(item["scope"]),
            ),
        )
    for item in network_state["assemblies"]:
        engine.network.seed_assembly(
            Assembly(
                item["id"], Territory(item["territory"]), frozenset(item["members"])
            )
        )
    engine.network.version = network_state["version"]
    engine.network.tick = network_state["tick"]
    engine.network.next_assembly_id = network_state["next_assembly_id"]
    temporal = value["temporal"]
    events = (
        TemporalEvent(
            item["tick"],
            tuple((cell_id, activation) for cell_id, activation in item["activations"]),
            _signature_from_dict(item["signature"]),
            tuple((cell_id, drive) for cell_id, drive in item["receptor_drive"]),
        )
        for item in temporal["events"]
    )
    engine.temporal.load(events, temporal["next_root_id"])
    return engine
