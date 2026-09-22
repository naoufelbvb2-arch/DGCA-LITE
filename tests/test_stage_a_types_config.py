from dataclasses import fields
from math import inf, nan

import pytest

from dgca_lite.config import CoreConfig
from dgca_lite.model import (
    Assembly,
    Cell,
    Synapse,
    SynapseScope,
    SynapseState,
    Territory,
)


def test_canonical_schema_purity() -> None:
    assert [f.name for f in fields(Cell)] == [
        "id", "territory", "committed", "activation", "synaptic_budget"
    ]
    assert [f.name for f in fields(Synapse)] == [
        "target_id", "strength", "evidence_mass", "state", "scope"
    ]
    assert [f.name for f in fields(Assembly)] == ["id", "territory", "members"]


@pytest.mark.parametrize("bad", [nan, inf, -inf])
def test_config_rejects_nonfinite_values(bad: float) -> None:
    with pytest.raises(ValueError):
        CoreConfig(E_max=bad)


def test_config_relationships() -> None:
    with pytest.raises(ValueError):
        CoreConfig(theta_active=0.3, theta_emit=0.2)
    with pytest.raises(ValueError):
        CoreConfig(theta_demote=0.8, theta_S=0.7)
    with pytest.raises(ValueError):
        CoreConfig(rho_G=0.2, rho_keep=0.2)
    with pytest.raises(ValueError):
        CoreConfig(K_min=5, K_max=4)


def test_self_synapse_rejected() -> None:
    edge = Synapse(1, 1.0, 1.0, SynapseState.CANDIDATE, SynapseScope.LOCAL)
    with pytest.raises(ValueError):
        edge.validate(1, 10.0)


def test_primitive_validation() -> None:
    cell = Cell(1, Territory.LANGUAGE, True, 0.5, 3)
    cell.validate()
    assembly = Assembly(0, Territory.LANGUAGE, frozenset({1, 2}))
    assembly.validate()


def test_config_round_trip_is_deterministic() -> None:
    config = CoreConfig()
    assert CoreConfig.from_dict(config.to_dict()) == config
