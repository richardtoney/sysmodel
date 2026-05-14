"""Tests for sysmodel.graph (Kuzu integration).

All tests in this file require kuzu to be installed.
If kuzu is not available, the entire module is skipped.
"""
from __future__ import annotations

import pytest

kuzu = pytest.importorskip("kuzu")

from sysmodel.exceptions import GraphLoadError, GraphNotAvailableError
from sysmodel.graph import KuzuGraph
from sysmodel.models import (
    Block,
    BlockType,
    Flow,
    FlowHop,
    System,
)


def test_load_block_count_matches(
    kuzu_graph: KuzuGraph, software_system: System
) -> None:
    result = kuzu_graph.query("MATCH (b:Block) RETURN COUNT(b) AS cnt")
    assert result[0]["cnt"] == len(software_system.blocks)


def test_load_relationship_count_matches(
    kuzu_graph: KuzuGraph, software_system: System
) -> None:
    result = kuzu_graph.query("MATCH ()-[r:Connected]->() RETURN COUNT(r) AS cnt")
    assert result[0]["cnt"] == len(software_system.relationships)


def test_load_flow_count_matches(flow_system: System) -> None:
    with KuzuGraph() as g:
        g.load(flow_system)
        result = g.query("MATCH (f:Flow) RETURN COUNT(f) AS cnt")
        assert result[0]["cnt"] == len(flow_system.flows)


def test_load_idempotent(software_system: System) -> None:
    with KuzuGraph() as g:
        g.load(software_system)
        g.load(software_system)  # second load should not duplicate
        result = g.query("MATCH (b:Block) RETURN COUNT(b) AS cnt")
        assert result[0]["cnt"] == len(software_system.blocks)


def test_cypher_all_blocks(kuzu_graph: KuzuGraph) -> None:
    result = kuzu_graph.query("MATCH (b:Block) RETURN b.id")
    assert len(result) > 0


def test_cypher_descendants_via_contains(kuzu_graph: KuzuGraph) -> None:
    result = kuzu_graph.query(
        "MATCH (root:Block {id: 'acct-01'})-[:Connected*]->(b:Block) "
        "RETURN b.id"
    )
    ids = {row["b.id"] for row in result}
    assert "srv-01" in ids
    assert "sw-nginx" in ids


def test_cypher_software_on_host_deployed_on(kuzu_graph: KuzuGraph) -> None:
    result = kuzu_graph.query(
        "MATCH (sw:Block)-[r:Connected]->(host:Block {id: 'srv-01'}) "
        "WHERE r.rel_type = 'deployed_on' "
        "RETURN sw.id"
    )
    ids = {row["sw.id"] for row in result}
    assert "sw-app" in ids


def test_cypher_multi_hop_depends_on(dependency_system: System) -> None:
    with KuzuGraph() as g:
        g.load(dependency_system)
        result = g.query(
            "MATCH (a:Block {id: 'svc-a'})-[r:Connected*]->(dep:Block) "
            "RETURN dep.id"
        )
        ids = {row["dep.id"] for row in result}
        assert "svc-b" in ids
        assert "svc-c" in ids


def test_cypher_no_results_returns_empty_list(kuzu_graph: KuzuGraph) -> None:
    result = kuzu_graph.query(
        "MATCH (b:Block {id: 'does-not-exist-xyz'}) RETURN b.id"
    )
    assert result == []


def test_cypher_flow_hops_ordered(flow_system: System) -> None:
    with KuzuGraph() as g:
        g.load(flow_system)
        result = g.query(
            "MATCH (f:Flow {id: 'flow-01'})-[h:HasHop]->(b:Block) "
            "RETURN b.id, h.position "
            "ORDER BY h.position"
        )
        assert len(result) == 4
        positions = [row["h.position"] for row in result]
        assert positions == sorted(positions)
        assert result[0]["b.id"] == "node-1"
        assert result[-1]["b.id"] == "node-4"


def test_context_manager_closes_cleanly(software_system: System) -> None:
    with KuzuGraph() as g:
        g.load(software_system)
        result = g.query("MATCH (b:Block) RETURN COUNT(b) AS cnt")
        assert result[0]["cnt"] > 0
    # No exception should propagate after close


def test_graph_not_available_error_without_kuzu() -> None:
    import sysmodel.graph as graph_module

    original = graph_module._KUZU_AVAILABLE
    try:
        graph_module._KUZU_AVAILABLE = False
        with pytest.raises(GraphNotAvailableError):
            KuzuGraph()
    finally:
        graph_module._KUZU_AVAILABLE = original
