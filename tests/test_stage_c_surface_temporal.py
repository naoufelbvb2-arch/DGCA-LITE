import pytest

from dgca_lite.config import CoreConfig
from dgca_lite.model import SparseSignature, SurfaceEvent, SurfaceFeature, TemporalEvent
from dgca_lite.surface import SurfaceCodec
from dgca_lite.temporal import TemporalStream
from dgca_lite.topology import Topology


@pytest.mark.parametrize(
    "text",
    [
        "apple",
        "527",
        "x = x + 1\n",
        "foo_bar <= [3, 7]",
        "🙂 café e\u0301 العربية עברית",
        "    \n\t",
        "C++",
    ],
)
def test_surface_round_trip(text: str) -> None:
    config = CoreConfig(max_event_bytes=8, continuation_bytes=4)
    codec = SurfaceCodec(config, Topology(config))
    event = SurfaceEvent.from_text(text)
    signature = codec.encode(event)
    assert codec.decode(signature) == event
    assert signature == codec.encode(event)


def test_segmentation_is_exact() -> None:
    config = CoreConfig()
    codec = SurfaceCodec(config, Topology(config))
    text = "hello, 世界!\n  x+=1"
    assert b"".join(event.data for event in codec.segment(text)) == text.encode()


def test_unknown_features_need_no_vocabulary_mutation() -> None:
    config = CoreConfig(receptor_fanout=3)
    codec = SurfaceCodec(config, Topology(config))
    feature = SurfaceFeature("POSITIONAL_BYTE", b"never-seen")
    assert codec.project(feature) == codec.project(feature)
    assert len(codec.project(feature)) == 3


def test_projection_collisions_cannot_break_decode() -> None:
    config = CoreConfig(logical_capacity=30, receptor_fanout=2, max_neighborhood=8)
    codec = SurfaceCodec(config, Topology(config))
    left = codec.encode(SurfaceEvent.from_text("ab"))
    right = codec.encode(SurfaceEvent.from_text("ba"))
    assert codec.decode(left).data == b"ab"
    assert codec.decode(right).data == b"ba"
    assert left != right


def test_small_surface_change_retains_controlled_mechanical_overlap() -> None:
    config = CoreConfig()
    codec = SurfaceCodec(config, Topology(config))
    left = codec.encode(SurfaceEvent.from_text("cat"))
    right = codec.encode(SurfaceEvent.from_text("cap"))
    common = set(left.features) & set(right.features)
    assert common
    assert left.features != right.features


def test_receptor_drive_is_sparse_bounded_and_deterministic() -> None:
    config = CoreConfig(receptor_fanout=2)
    codec = SurfaceCodec(config, Topology(config))
    signature = SparseSignature((b"x",), (SurfaceFeature("X", b"x", 0.5),))
    drive = codec.receptor_drive(signature)
    assert drive == codec.receptor_drive(signature)
    assert len(drive) <= 2
    assert all(0 <= value <= 1 for _, value in drive)


def test_root_lifecycle_and_boundary_clear_context() -> None:
    config = CoreConfig(temporal_horizon=2)
    stream = TemporalStream(config)
    root = stream.begin()
    assert root.id == 0 and root.open
    event = TemporalEvent(0, ((1, 0.7),), SparseSignature((b"a",), ()), ((1, 1.0),))
    stream.finalize(event)
    assert len(stream.events) == 1
    assert stream.open_root is None
    stream.clear_boundary()
    assert stream.events == ()
    assert stream.referenced_cells() == frozenset()


def test_temporal_horizon_is_bounded() -> None:
    config = CoreConfig(temporal_horizon=2)
    stream = TemporalStream(config)
    for tick in range(3):
        stream.begin()
        stream.finalize(
            TemporalEvent(tick, (), SparseSignature((bytes((tick,)),), ()), ())
        )
    assert [event.tick for event in stream.events] == [1, 2]
