from dgca_lite import CoreConfig, CoreEngine
from dgca_lite.model import (
    Assembly,
    Cell,
    Synapse,
    SynapseScope,
    SynapseState,
    Territory,
)


def consolidated(
    target: int,
    scope: SynapseScope = SynapseScope.LOCAL,
    quality: float = 1.0,
) -> Synapse:
    return Synapse(target, quality, 1.0, SynapseState.CONSOLIDATED, scope)


def candidate(
    target: int,
    scope: SynapseScope = SynapseScope.LOCAL,
    quality: float = 1.0,
) -> Synapse:
    return Synapse(target, quality, 1.0, SynapseState.CANDIDATE, scope)


def seed_pair(core: CoreEngine, left: int, right: int, quality: float = 1.0) -> None:
    core.network.seed_synapse(left, consolidated(right, quality=quality))
    core.network.seed_synapse(right, consolidated(left, quality=quality))


def retrieval_core() -> CoreEngine:
    config = CoreConfig(
        logical_capacity=300,
        default_synaptic_budget=32,
        E_max=1.0,
        local_radius=10.0,
        associative_radius=10.0,
        assembly_radius=10.0,
        K_min=3,
        K_max=6,
        M_max=4,
        theta_A=0.1,
    )
    core = CoreEngine(config)
    for cell_id in range(9):
        core.network.seed_cell(
            Cell(cell_id, Territory.LANGUAGE, True, 0.0, 32)
        )
    for members in ((0, 1, 2), (3, 4, 5)):
        for index, left in enumerate(members):
            for right in members[index + 1 :]:
                seed_pair(core, left, right)
    core.network.seed_assembly(
        Assembly(0, Territory.LANGUAGE, frozenset({0, 1, 2}))
    )
    core.network.seed_assembly(
        Assembly(1, Territory.LANGUAGE, frozenset({3, 4, 5}))
    )
    core.network.seed_synapse(
        0, consolidated(3, SynapseScope.ASSOCIATIVE, quality=0.8)
    )
    return core
