# DGCA LITE — Layer 1 Core v0.4

This repository contains the Layer 1 reference implementation governed solely by
[`01_CORE_v0.4.md`](01_CORE_v0.4.md). Earlier Core documents are retained as project
artifacts but are not implementation authorities.

The package implements sparse logical topology, immutable tick snapshots, continuous
activation, reversible mechanical surface projection, bounded temporal provenance,
LLA evidence and Synapse lifecycle, novelty/recruitment/resource arbitration,
event-driven Assembly MAINTAIN → GROW → FORM, atomic commit, deterministic JSON
persistence, and transient diagnostics. It does not implement Layer 2 or later
memory, cognition, reasoning, or generation behavior.

## Closure status

```yaml
Layer 1 Core v0.4: FROZEN
Reviewed implementation commit:
beb10058b09f44e8a1ed737dca81db4d1091473e
```

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
