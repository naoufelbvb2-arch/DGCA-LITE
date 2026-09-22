import ast
import inspect
from dataclasses import replace
from pathlib import Path

from dgca_lite.activation import compute_activation
from dgca_lite.assemblies import process_assemblies
from dgca_lite.config import CoreConfig
from dgca_lite.learning import RootEvidenceLedger, aggregate_evidence, apply_learning
from dgca_lite.model import (
    Assembly,
    Cell,
    EvidenceProposal,
    Synapse,
    SynapseScope,
    SynapseState,
    Territory,
    TickTransaction,
)
from dgca_lite.network import SparseNetwork


def test_directional_learning_never_mutates_reverse_edge() -> None:
    config = CoreConfig(E_max=1, local_radius=3)
    network = SparseNetwork(config)
    source = 0
    target = network.topology.neighborhood(source, SynapseScope.LOCAL)[0]
    for cell_id in (source, target):
        network.seed_cell(Cell(cell_id, Territory.LANGUAGE, True, 0, 4))
    proposal = EvidenceProposal(0, source, target, SynapseScope.LOCAL, 1, 1)
    aggregated, conflicts = aggregate_evidence((proposal,), RootEvidenceLedger(0))
    result = apply_learning(network.snapshot(), aggregated, conflicts, network.topology, config)
    assert [item.key for item in result.new_edges] == [
        (source, target, SynapseScope.LOCAL)
    ]
    assert network.edge(target, source, SynapseScope.LOCAL) is None


def test_inactivity_changes_activation_but_not_persistent_synapse() -> None:
    config = CoreConfig(E_max=1, local_radius=3)
    network = SparseNetwork(config)
    source = 0
    target = network.topology.neighborhood(source, SynapseScope.LOCAL)[0]
    network.seed_cell(Cell(source, Territory.LANGUAGE, True, 0.8, 4))
    network.seed_cell(Cell(target, Territory.LANGUAGE, True, 0, 4))
    edge = Synapse(target, 0.8, 1, SynapseState.CONSOLIDATED, SynapseScope.LOCAL)
    network.seed_synapse(source, edge)
    compute_activation(network.snapshot(), {}, config)
    assert network.edge(source, target, SynapseScope.LOCAL) == edge


def test_high_evidence_resists_one_contradiction_but_remains_correctable() -> None:
    config = CoreConfig(E_max=10, theta_demote=0.3, local_radius=3)
    network = SparseNetwork(config)
    source = 0
    target = network.topology.neighborhood(source, SynapseScope.LOCAL)[0]
    for cell_id in (source, target):
        network.seed_cell(Cell(cell_id, Territory.LANGUAGE, True, 0, 4))
    network.seed_synapse(
        source,
        Synapse(target, 1, 10, SynapseState.CONSOLIDATED, SynapseScope.LOCAL),
    )
    first_strength = None
    for root in range(20):
        proposal = EvidenceProposal(root, source, target, SynapseScope.LOCAL, 1, 0)
        aggregated, conflicts = aggregate_evidence((proposal,), RootEvidenceLedger(root))
        result = apply_learning(
            network.snapshot(), aggregated, conflicts, network.topology, config
        )
        updated = result.existing_updates[(source, target, SynapseScope.LOCAL)]
        if first_strength is None:
            first_strength = updated.strength
        network.commit(
            TickTransaction(
                base_version=network.version,
                synapse_upserts={(source, target, SynapseScope.LOCAL): updated},
            )
        )
    assert first_strength is not None and first_strength > 0.9
    assert network.edge(source, target, SynapseScope.LOCAL).state is SynapseState.CANDIDATE


def test_assemblies_overlap_within_membership_bound() -> None:
    config = CoreConfig(E_max=1, K_min=3, M_max=2, local_radius=5, assembly_radius=5)
    network = SparseNetwork(config)
    for cell_id in range(5):
        network.seed_cell(Cell(cell_id, Territory.LANGUAGE, True, 0, 4))
    for left, right in ((0, 1), (0, 2), (1, 2), (2, 3), (2, 4), (3, 4)):
        network.seed_synapse(left, Synapse(right, 1, 1, SynapseState.CONSOLIDATED, SynapseScope.LOCAL))
        network.seed_synapse(right, Synapse(left, 1, 1, SynapseState.CONSOLIDATED, SynapseScope.LOCAL))
    network.seed_assembly(Assembly(0, Territory.LANGUAGE, frozenset({0, 1, 2})))
    network.seed_assembly(Assembly(1, Territory.LANGUAGE, frozenset({2, 3, 4})))
    assert network.memberships[2] == frozenset({0, 1})


def test_inactivity_alone_does_not_trigger_assembly_maintenance() -> None:
    config = CoreConfig(E_max=1, K_min=3, local_radius=5, assembly_radius=5)
    network = SparseNetwork(config)
    for cell_id in range(3):
        network.seed_cell(Cell(cell_id, Territory.LANGUAGE, True, 0, 4))
    for left, right in ((0, 1), (0, 2), (1, 2)):
        network.seed_synapse(left, Synapse(right, 1, 1, SynapseState.CONSOLIDATED, SynapseScope.LOCAL))
        network.seed_synapse(right, Synapse(left, 1, 1, SynapseState.CONSOLIDATED, SynapseScope.LOCAL))
    assembly = Assembly(0, Territory.LANGUAGE, frozenset({0, 1, 2}))
    network.seed_assembly(assembly)
    result = process_assemblies(
        network.snapshot(), {}, frozenset(), frozenset(), network.topology, config, 1
    )
    assert result.maintain_workset == ()
    assert result.upserts == {} and result.deletes == frozenset()
    assert network.assemblies[0] == assembly


class _NoGlobalAssemblyIteration(dict):
    def __iter__(self):
        raise AssertionError("normal assembly path attempted a global scan")

    def values(self):
        raise AssertionError("normal assembly path attempted a global scan")

    def items(self):
        raise AssertionError("normal assembly path attempted a global scan")


def test_assembly_runtime_does_not_iterate_all_assemblies() -> None:
    config = CoreConfig()
    network = SparseNetwork(config)
    snapshot = replace(snapshot := network.snapshot(), assemblies=_NoGlobalAssemblyIteration(snapshot.assemblies))
    result = process_assemblies(
        snapshot, {}, frozenset(), frozenset(), network.topology, config, 0
    )
    assert result.maintain_workset == ()


def test_production_modules_have_no_future_layer_imports_or_capacity_loops() -> None:
    package = Path(inspect.getfile(SparseNetwork)).parent
    forbidden = {"memory", "cognition", "reasoning", "generation"}
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = {
            alias.name.split(".")[0].lower()
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert not imported & forbidden
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
                assert not any(
                    isinstance(arg, ast.Attribute) and arg.attr == "logical_capacity"
                    for arg in node.args
                )


def test_persistent_knowledge_records_contain_no_time_decay_fields() -> None:
    forbidden = {"age", "last_seen", "timestamp", "decay", "semantic", "label"}
    for record in (Cell, Synapse, Assembly):
        assert not ({field.lower() for field in record.__dataclass_fields__} & forbidden)
