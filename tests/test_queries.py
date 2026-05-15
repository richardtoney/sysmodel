"""Tests for sysmodel.queries."""
from __future__ import annotations

from sysmodel import queries
from sysmodel.models import (
    Block,
    BlockType,
    DataClassification,
    Flow,
    FlowHop,
    System,
)


def test_blocks_of_type_single(software_system: System) -> None:
    result = queries.blocks_of_type(software_system, BlockType.SOFTWARE)
    ids = {b.id for b in result}
    assert "sw-nginx" in ids
    assert "sw-app" in ids
    assert "srv-01" not in ids


def test_blocks_of_type_multiple(software_system: System) -> None:
    result = queries.blocks_of_type(software_system, BlockType.SOFTWARE, BlockType.SERVER)
    types = {b.type for b in result}
    assert BlockType.SOFTWARE in types
    assert BlockType.SERVER in types


def test_blocks_with_tag_key_only() -> None:
    s = System(name="Tags")
    s.add(Block(id="a", name="A", type=BlockType.SERVICE, tags={"env": "prod"}))
    s.add(Block(id="b", name="B", type=BlockType.SERVICE, tags={"env": "dev"}))
    s.add(Block(id="c", name="C", type=BlockType.SERVICE, tags={"tier": "web"}))
    result = queries.blocks_with_tag(s, "env")
    ids = {b.id for b in result}
    assert ids == {"a", "b"}


def test_blocks_with_tag_key_and_value() -> None:
    s = System(name="Tags")
    s.add(Block(id="a", name="A", type=BlockType.SERVICE, tags={"env": "prod"}))
    s.add(Block(id="b", name="B", type=BlockType.SERVICE, tags={"env": "dev"}))
    result = queries.blocks_with_tag(s, "env", "prod")
    assert len(result) == 1
    assert result[0].id == "a"


def test_blocks_with_tag_missing_key() -> None:
    s = System(name="Tags")
    s.add(Block(id="a", name="A", type=BlockType.SERVICE, tags={"tier": "web"}))
    result = queries.blocks_with_tag(s, "env")
    assert result == []


def test_blocks_with_metadata_key_only(software_system: System) -> None:
    result = queries.blocks_with_metadata(software_system, "version")
    ids = {b.id for b in result}
    assert "sw-nginx" in ids
    assert "sw-app" in ids


def test_blocks_with_metadata_key_and_value(software_system: System) -> None:
    result = queries.blocks_with_metadata(software_system, "version", "1.25")
    assert len(result) == 1
    assert result[0].id == "sw-nginx"


def test_children_of_all(software_system: System) -> None:
    children = queries.children_of(software_system, "net-01")
    assert len(children) == 1
    assert children[0].id == "srv-01"


def test_children_of_filtered_by_type(software_system: System) -> None:
tml    sw_children = queries.children_of(software_system, "srv-01", BlockType.SOFTWARE)
    assert len(sw_children) == 1
    assert sw_children[0].id == "sw-nginx"

    server_children = queries.children_of(software_system, "srv-01", BlockType.SERVER)
    assert server_children == []


def test_descendants_of_filtered(software_system: System) -> None:
    sw = queries.descendants_of(software_system, "acct-01", BlockType.SOFTWARE)
    ids = {b.id for b in sw}
    assert "sw-nginx" in ids
    assert "srv-01" not in ids


def test_software_on_via_contains(software_system: System) -> None:
    result = queries.software_on(software_system, "srv-01")
    ids = {b.id for b in result}
    assert "sw-nginx" in ids


def test_software_on_via_deployed_on(software_system: System) -> None:
    result = queries.software_on(software_system, "srv-01")
    ids = {b.id for b in result}
    assert "sw-app" in ids


def test_software_on_deduplicates_both_edges() -> None:
    s = System(name="Dedup")
    s.add(Block(id="host", name="Host", type=BlockType.SERVER))
    s.add(Block(id="sw", name="SW", type=BlockType.SOFTWARE, metadata={"version": "1"}))
    s.contains("host", "sw")
    s.deployed_on("sw", "host")
    result = queries.software_on(s, "host")
    assert len(result) == 1
    assert result[0].id == "sw"


def test_all_software_in_root(software_system: System) -> None:
    result = queries.all_software_in(software_system, "acct-01")
    ids = {b.id for b in result}
    assert "sw-nginx" in ids
    assert "sw-app" in ids


def test_find_by_name_exact(software_system: System) -> None:
    result = queries.find_by_name(software_system, "nginx")
    assert len(result) == 1
    assert result[0].id == "sw-nginx"


def test_find_by_name_substring(software_system: System) -> None:
    result = queries.find_by_name(software_system, "app", exact=False)
    ids = {b.id for b in result}
    assert "sw-app" in ids


def test_parent_of_returns_parent(software_system: System) -> None:
    parent = queries.parent_of(software_system, "srv-01")
    assert parent is not None
    assert parent.id == "net-01"


def test_parent_of_root_returns_none(software_system: System) -> None:
    parent = queries.parent_of(software_system, "acct-01")
    assert parent is None


def test_account_of_deep_block(software_system: System) -> None:
    acct = queries.account_of(software_system, "sw-nginx")
    assert acct is not None
    assert acct.id == "acct-01"


def test_account_of_no_account_returns_none(dependency_system: System) -> None:
    result = queries.account_of(dependency_system, "svc-a")
    assert result is None


def test_dependencies_of(dependency_system: System) -> None:
    deps = queries.dependencies_of(dependency_system, "svc-a")
    ids = {b.id for b in deps}
    assert "svc-b" in ids


def test_dependents_of(dependency_system: System) -> None:
    deps = queries.dependents_of(dependency_system, "svc-a")
    ids = {b.id for b in deps}
    assert "svc-d" in ids


def test_relationships_between_both_directions(minimal_system: System) -> None:
    rels = queries.relationships_between(minimal_system, "svc-01", "db-01")
    assert len(rels) == 1
    rels_reversed = queries.relationships_between(minimal_system, "db-01", "svc-01")
    assert len(rels_reversed) == 1


def test_flows_of_classification(flow_system: System) -> None:
    result = queries.flows_of_classification(flow_system, DataClassification.INTERNAL)
    assert len(result) == 1
    assert result[0].id == "flow-01"


def test_flows_crossing_boundary_detects_crossing(flow_system: System) -> None:
    result = queries.flows_crossing_boundary(flow_system, "boundary-1")
    assert len(result) == 1
    assert result[0].id == "flow-01"


def test_flows_crossing_boundary_no_false_positives(flow_system: System) -> None:
    flow_system.add_flow(
        Flow(
            id="flow-inside",
            name="Inside Only",
            hops=[FlowHop(block_id="node-2"), FlowHop(block_id="node-3")],
        )
    )
    result = queries.flows_crossing_boundary(flow_system, "boundary-1")
    ids = {f.id for f in result}
    assert "flow-inside" not in ids


def test_lineage_for_upstream(flow_system: System) -> None:
    lineage = queries.lineage_for(flow_system, "node-2")
    assert len(lineage["upstream"]) == 1


def test_lineage_for_downstream(flow_system: System) -> None:
    lineage = queries.lineage_for(flow_system, "node-3")
    assert len(lineage["downstream"]) == 1


def test_lineage_for_source_node_no_upstream(flow_system: System) -> None:
    lineage = queries.lineage_for(flow_system, "node-1")
    assert lineage["upstream"] == []


def test_lineage_for_sink_node_no_downstream(flow_system: System) -> None:
    lineage = queries.lineage_for(flow_system, "node-4")
    assert lineage["downstream"] == []


def test_summarize_blocks_shape(software_system: System) -> None:
    blocks = list(software_system.blocks.values())
    summaries = queries.summarize_blocks(blocks)
    assert len(summaries) == len(blocks)
    for s in summaries:
        assert set(s.keys()) == {"id", "name", "type", "tags"}


def test_group_by_type(software_system: System) -> None:
    blocks = list(software_system.blocks.values())
    grouped = queries.group_by_type(blocks)
    assert "software" in grouped
    assert len(grouped["software"]) == 2


def test_group_by_tag_with_untagged() -> None:
    s = System(name="Tagged")
    s.add(Block(id="a", name="A", type=BlockType.SERVICE, tags={"env": "prod"}))
    s.add(Block(id="b", name="B", type=BlockType.SERVICE, tags={"env": "dev"}))
    s.add(Block(id="c", name="C", type=BlockType.SERVICE))
    blocks = list(s.blocks.values())
    grouped = queries.group_by_tag(blocks, "env")
    assert "prod" in grouped
    assert "dev" in grouped
    assert "__untagged__" in grouped
    assert grouped["__untagged__"][0].id == "c"
