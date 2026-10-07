"""Pure B01/B02 rules; future BranchViews are never observation lanes (§32.1)."""

from ..types import CaptureState, ForecastStatus
from .targets import (
    AtomicCarrier,
    BranchPattern,
    cell_set,
    d,
    source_id,
    target_from_data,
)


def match(target, sources, root_witnesses):
    """Consume only closed extracted root-seeded SourceView data."""
    if type(sources) is not tuple or len(sources) > 640:
        raise ValueError("future source outer bound")
    if type(root_witnesses) is not tuple or len(root_witnesses) > 512:
        raise ValueError("root witness outer bound")
    for row in sources:
        if type(row) is not tuple or len(row) != 3:
            raise ValueError("closed source row required")
        sid, witnesses, cells = row
        if type(sid) is not tuple or len(sid) != 2:
            raise ValueError("closed source identity required")
        if any(type(v) is not tuple or len(v) > 512 for v in (witnesses, cells)):
            raise ValueError("future source lane outer bound")
    cell_set(root_witnesses, maximum=512, nonempty=False)
    identities = set()
    for sid, witnesses, cells in sources:
        source_id(d("PredictionSourceIdentity", *sid))
        if sid in identities:
            raise ValueError("duplicate future SourceView identity")
        identities.add(sid)
        cell_set(witnesses, maximum=512, nonempty=False)
        cell_set(cells, maximum=512, nonempty=False)
    target = target_from_data(target)
    if type(target) is AtomicCarrier:
        return target.carrier_id in root_witnesses
    if type(target) is not BranchPattern:
        raise TypeError("unknown prediction target")
    lane = next(
        (s for s in sources if s[0] == ("ASM", target.target_assembly_id)),
        None,
    )
    witnesses, cells = ((), ()) if lane is None else (lane[1], lane[2])
    return bool(set(target.anchor_carriers) & set(witnesses)) and set(
        target.pattern_cells
    ) <= set(cells)


def status_after(horizon, states, matched):
    if type(horizon) is not int or not 1 <= horizon <= 64:
        raise ValueError("exact bounded logical horizon required")
    if type(states) is not tuple or len(states) > horizon:
        raise ValueError("coverage state outer bound")
    if type(matched) is not bool or any(type(s) is not CaptureState for s in states):
        raise ValueError("closed capture/match classifications required")
    if matched:
        return ForecastStatus.MATCHED
    if len(states) < horizon:
        return ForecastStatus.PENDING
    if any(state is CaptureState.OBSERVATION_GAP for state in states):
        return ForecastStatus.INCONCLUSIVE_OBSERVATION_GAP
    return ForecastStatus.WINDOW_ELAPSED_WITHOUT_MATCH
