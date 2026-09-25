from dataclasses import replace

from dgca_lite.memory.config import MemoryConfig
from dgca_lite.memory.serialization import behavioral_signature, canonical_result_bytes
from dgca_lite.memory.session import retrieve_internal
from dgca_lite.memory.types import RetrievalResult

from .helpers import retrieval_core


def result(*, use_cache: bool = False, diagnostics_sink=None) -> RetrievalResult:
    value = retrieve_internal(
        retrieval_core(),
        {0: 1.0},
        MemoryConfig(),
        use_cache=use_cache,
        diagnostics_sink=diagnostics_sink,
    )
    assert isinstance(value, RetrievalResult)
    return value


def test_same_result_produces_bit_identical_bytes_and_signature() -> None:
    left = result()
    right = result()
    assert canonical_result_bytes(left) == canonical_result_bytes(right)
    assert behavioral_signature(left) == behavioral_signature(right)
    assert len(behavioral_signature(left)) == 64


def test_cache_and_no_cache_are_canonically_identical() -> None:
    uncached = result(use_cache=False)
    cached = result(use_cache=True)
    assert canonical_result_bytes(uncached) == canonical_result_bytes(cached)
    assert behavioral_signature(uncached) == behavioral_signature(cached)


def test_diagnostics_on_and_off_are_canonically_identical() -> None:
    diagnostics = []
    without = result()
    with_diagnostics = result(diagnostics_sink=diagnostics.append)
    assert diagnostics
    assert canonical_result_bytes(without) == canonical_result_bytes(with_diagnostics)


def test_binary64_payload_is_lossless() -> None:
    base = result()
    hit = base.direct_hits[0]
    changed = replace(base, direct_hits=(replace(hit),))
    assert canonical_result_bytes(base) == canonical_result_bytes(changed)
    adjacent = replace(
        base,
        direct_hits=(replace(hit, drive=float.fromhex("0x1.999999999999bp-1")),),
    )
    assert canonical_result_bytes(base) != canonical_result_bytes(adjacent)


def test_typed_identities_and_provenance_are_in_canonical_bytes() -> None:
    value = result()
    encoded = canonical_result_bytes(value)
    assert b"SourceID" in encoded
    assert b"BranchID" in encoded
    assert b"RetrievalProvenance" in encoded
    assert b"uuid" not in encoded.lower()
    assert b"session" not in encoded.lower()
