# DGCA LITE — Layer 1 Core v0.4

This repository contains the Layer 1 reference implementation governed solely by
[`01_CORE_v0.4.md`](01_CORE_v0.4.md). Earlier Core documents are retained as project
artifacts but are not implementation authorities.

The package implements sparse logical topology, immutable tick snapshots, continuous
activation, reversible mechanical surface projection, bounded temporal provenance,
LLA evidence and Synapse lifecycle, novelty/recruitment/resource arbitration,
event-driven Assembly MAINTAIN → GROW → FORM, atomic commit, deterministic JSON
persistence, and transient diagnostics. The frozen Layer 2 implementation adds
memory and retrieval; Layer 3 and later cognitive behavior remain absent.

## Closure status

```yaml
Layer 1 Core v0.4: FROZEN
Reviewed implementation commit:
beb10058b09f44e8a1ed737dca81db4d1091473e
```

### Layer 2 — Memory & Retrieval v0.4

```yaml
Status: FROZEN
Specification: 02_MEMORY_RETRIEVAL.md
Specification SHA-256: 59873de144b811ac3eb8258e9ca8d79a380f2b3d6eda9d79cd60c7b1bd44a7fa
Implementation commit: b039f89e3fd4e0df993f2a9d1bb6bbb10fdb3c3c
Implementation manifest SHA-256: 0d060823d18de9805511b814ca3b0a5a0e4a4d15afa948fb0443fd9efbaf4fc1
Behavioral signature: 504f53062eea6895b6ece2f577fb34f0661d735cd8a75093eda2f0accb84ce28
Verification:
  - 213 repository tests PASS
  - 122 Layer-2 tests PASS
  - A01–A32 PASS
Freeze tag: layer2-memory-retrieval-v0.4-frozen
Layer-2 persistent cognitive state: NONE.
```

Future semantic changes to Layer 2 require a formal revision; higher layers must
not silently patch frozen Layer-2 semantics.

## Requirements and verification

Python 3.12 or newer is required. The runtime package has no third-party dependencies;
the verification suite uses `pytest`.

```powershell
python -m pytest -q
```

## Minimal use

```python
from dgca_lite import CoreEngine, SurfaceEvent

core = CoreEngine()
result = core.process_event(SurfaceEvent.from_text("hello"))
core.save("core-state.json")
restored = CoreEngine.load("core-state.json")
```

`TickResult` and its diagnostics are transient observations. Canonical learned state
is limited to Cells, Synapses, and Assemblies; bounded temporal Surface provenance is
persisted separately to preserve deterministic continuation.
