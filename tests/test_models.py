"""Tests for sysmodel.models — Block, Relationship, Flow, StateMachine, System."""
from __future__ import annotations

import pytest

from sysmodel.exceptions import (
    BlockNotFoundError,
    DuplicateBlockError,
    FlowReferenceError,
    InvalidBlockIdError,
    MetadataValidationError,
    StateMachineReferenceError,
)
from sysmodel.models import (
    Block,
    BlockType,
    DataClassification,
    Flow,
    FlowHop,
    RelType,
    State,
    StateMachine,
    System,
    Transition,
)


# --- Block validation ---

def test_block_id_rejects_spaces() -> None:
    with pytest.raises(InvalidBlockIdError):
        Block(id="bad id", name="Bad", type=BlockType.SERVICE)


def test_block_id_rejects_empty() -> None:
    with pytest.raises(InvalidBlockIdError):
        Block(id="", name="Bad", type=BlockType.SERVICE)


def test_block_custom_type_string_allowed() -> None:
    b = Block(id="fw-01", name="Firewall", type="firewall")
    assert b.type == "firewall"


# --- System.add ---

def test_add_block_returns_block(minimal_system: System) -> None:
    s = System(name="Test")
    b = Block(id="x-01", name="X", type=BlockType.SERVICE)
    result = s.add(b)
    assert result is b


def test_add_duplicate_raises_duplicate_block_error() -> None:
    s = System(name="Test")
    s.add(Block(id="dup-01", name="First", type=BlockType.SERVICE))
    with pytest.raises(DuplicateBlockError) as exc_info:
        s.add(Block(id="dup-01", name="Second", type=BlockType.SERVICE))
    assert exc_info.value.block_id == "dup-01"


# --- System.resolve / get ---

def test_resolve_existing_block(minimal_system: System) -> None:
    block = minimal_system.resolve("svc-01")
    assert block.id == "svc-01"


def test_resolve_missing_raises_block_not_found_error(minimal_system: System) -> None:
    with pytest.raises(BlockNotFoundError) as exc_info:
        minimal_system.resolve("ghost-block")
    assert exc_info.value.block_id == "ghost-block"


def test_get_missing_returns_none(minimal_system: System) -> None:
    assert minimal_system.get("no-such-block") is None


# --- Relationship management ---

def test_relate_missing_source_raises() -> None:
    s = System(name="Test")
    s.add(Block(id="b-01", name="B", type=BlockType.SERVICE))
    with pytest.raises(BlockNotFoundError):
        s.relate("missing", RelType.DEPENDS_ON, "b-01")


def test_relate_missing_target_raises() -> None:
    s = System(name="Test")
    s.add(Block(id="a-01", name="A", type=BlockType.SERVICE))
    with pytest.raises(BlockNotFoundError):
        s.relate("a-01", RelType.DEPENDS_ON, "missing")


def test_contains_shorthand() -> None:
    s = System(name="Test")
    s.add(Block(id="parent", name="Parent", type=BlockType.BOUNDARY))
    s.add(Block(id="child", name="Child", type=BlockType.SERVICE))
    rel = s.contains("parent", "child")
    assert rel.type == RelType.CONTAINS
    assert rel.source_id == "parent"
    assert rel.target_id == "child"


def test_deployed_on_shorthand() -> None:
    s = System(name="Test")
    s.add(Block(id="sw", name="App", type=BlockType.SOFTWARE, metadata={"version": "1.0"}))
    s.add(Block(id="host", name="Host", type=BlockType.SERVER))
    rel = s.deployed_on("sw", "host")
    assert rel.type == RelType.DEPLOYED_ON


def test_depends_on_shorthand(minimal_system: System) -> None:
    rels = minimal_system.relationships_from("svc-01", RelType.DEPENDS_ON)
    assert len(rels) == 1
    assert rels[0].target_id == "db-01"


def test_connects_to_shorthand() -> None:
    s = System(name="Test")
    s.add(Block(id="a", name="A", type=BlockType.SERVICE))
    s.add(Block(id="b", name="B", type=BlockType.SERVICE))
    rel = s.connects_to("a", "b", protocol="HTTPS")
    assert rel.type == RelType.CONNECTS_TO
    assert rel.metadata["protocol"] == "HTTPS"


# --- Flow registration ---

def test_add_flow_valid(flow_system: System) -> None:
    assert "flow-01" in flow_system.flows
    assert len(flow_system.flows["flow-01"].hops) == 4


def test_add_flow_missing_hop_raises_flow_reference_error() -> None:
    s = System(name="Test")
    s.add(Block(id="n1", name="N1", type=BlockType.SERVICE))
    with pytest.raises(FlowReferenceError) as exc_info:
        s.add_flow(
            Flow(
                id="bad-flow",
                name="Bad",
                hops=[FlowHop(block_id="n1"), FlowHop(block_id="ghost")],
            )
        )
    assert exc_info.value.flow_id == "bad-flow"
    assert exc_info.value.block_id == "ghost"


# --- StateMachine registration ---

def test_add_state_machine_valid() -> None:
    s = System(name="Test")
    s.add(Block(id="svc", name="Service", type=BlockType.SERVICE))
    sm = StateMachine(
        block_id="svc",
        states={"running": State(id="running", name="Running")},
        initial_state="running",
    )
    result = s.add_state_machine(sm)
    assert result is sm
    assert "svc" in s.state_machines


def test_add_state_machine_missing_block_raises() -> None:
    s = System(name="Test")
    sm = StateMachine(block_id="ghost")
    with pytest.raises(StateMachineReferenceError):
        s.add_state_machine(sm)


# --- Traversal ---

def test_descendants_bfs_order(software_system: System) -> None:
    descendants = software_system.descendants("acct-01")
    ids = [b.id for b in descendants]
    # BFS: net-01 before srv-01, srv-01 before sw-nginx
    assert "net-01" in ids
    assert "srv-01" in ids
    assert "sw-nginx" in ids
    assert ids.index("net-01") < ids.index("srv-01")
    assert ids.index("srv-01") < ids.index("sw-nginx")


def test_descendants_no_duplicates_on_diamond_graph() -> None:
    s = System(name="Diamond")
    s.add(Block(id="root", name="Root", type=BlockType.BOUNDARY))
    s.add(Block(id="left", name="Left", type=BlockType.SERVICE))
    s.add(Block(id="right", name="Right", type=BlockType.SERVICE))
    s.add(Block(id="bottom", name="Bottom", type=BlockType.DATABASE,
                metadata={"engine": "pg", "version": "16"}))
    s.contains("root", "left")
    s.contains("root", "right")
    s.contains("left", "bottom")
    s.contains("right", "bottom")
    descendants = s.descendants("root")
    ids = [b.id for b in descendants]
    assert ids.count("bottom") == 1


def test_ancestors_root_to_leaf(software_system: System) -> None:
    ancestors = software_system.ancestors("sw-nginx")
    ids = [b.id for b in ancestors]
    assert ids[0] == "srv-01"
    assert "net-01" in ids
    assert "acct-01" in ids


def test_direct_children_empty() -> None:
    s = System(name="Test")
    s.add(Block(id="lone", name="Lone", type=BlockType.SERVICE))
    assert s.direct_children("lone") == []


def test_flows_through(flow_system: System) -> None:
    flows = flow_system.flows_through("node-2")
    assert len(flows) == 1
    assert flows[0].id == "flow-01"


# --- Validation ---

def test_validate_model_clean_returns_empty_list(minimal_system: System) -> None:
    errors = minimal_system.validate_model()
    assert errors == []


def test_validate_model_missing_required_key() -> None:
    s = System(name="Test")
    s.add(Block(id="ec2-01", name="Web", type=BlockType.EC2, metadata={}))
    errors = s.validate_model()
    assert any("instance_type" in e for e in errors)


def test_validate_model_unknown_key() -> None:
    s = System(name="Test")
    s.add(
        Block(
            id="ec2-01",
            name="Web",
            type=BlockType.EC2,
            metadata={"instance_type": "t3.micro", "bogus": "value"},
        )
    )
    errors = s.validate_model()
    assert any("bogus" in e for e in errors)


def test_validate_model_strict_raises_metadata_validation_error() -> None:
    s = System(name="Test")
    s.add(Block(id="ec2-01", name="Web", type=BlockType.EC2, metadata={}))
    with pytest.raises(MetadataValidationError):
        s.validate_model(strict=True)


def test_validate_model_collects_all_errors() -> None:
    s = System(name="Test")
    # Two blocks each missing required metadata
    s.add(Block(id="ec2-01", name="Web", type=BlockType.EC2, metadata={}))
    s.add(Block(id="rds-01", name="DB", type=BlockType.RDS, metadata={}))
    errors = s.validate_model()
    assert len(errors) >= 3  # ec2 needs instance_type; rds needs engine + version


# --- Serialization ---

def test_to_dict_round_trip(minimal_system: System) -> None:
    data = minimal_system.to_dict()
    restored = System.from_dict(data)
    assert restored.name == minimal_system.name
    assert set(restored.blocks.keys()) == set(minimal_system.blocks.keys())
    assert len(restored.relationships) == len(minimal_system.relationships)


def test_to_json_round_trip(minimal_system: System) -> None:
    json_str = minimal_system.to_json()
    restored = System.from_json(json_str)
    assert restored.name == minimal_system.name
    assert set(restored.blocks.keys()) == set(minimal_system.blocks.keys())


def test_from_dict_validates_blocks(minimal_system: System) -> None:
    data = minimal_system.to_dict()
    restored = System.from_dict(data)
    assert restored.blocks["svc-01"].type == BlockType.SERVICE
    assert restored.blocks["db-01"].metadata["engine"] == "postgres"
