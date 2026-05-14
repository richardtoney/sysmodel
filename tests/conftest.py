"""Shared pytest fixtures for sysmodel tests.

All test fixtures live here. No test file builds its own System from scratch.
"""
from __future__ import annotations

import pytest

from sysmodel.models import (
    Block,
    BlockType,
    DataClassification,
    Flow,
    FlowHop,
    RelType,
    StateMachine,
    State,
    Transition,
    System,
)


@pytest.fixture
def minimal_system() -> System:
    """Two blocks, one relationship. Simplest valid system."""
    s = System(name="Minimal System")
    s.add(Block(id="svc-01", name="API Service", type=BlockType.SERVICE))
    s.add(
        Block(
            id="db-01",
            name="Main DB",
            type=BlockType.DATABASE,
            metadata={"engine": "postgres", "version": "16"},
        )
    )
    s.depends_on("svc-01", "db-01", protocol="jdbc", port="5432")
    return s


@pytest.fixture
def software_system() -> System:
    """Three-layer system for software_on and all_software_in tests.

    account -> subnet -> server -> (SOFTWARE via CONTAINS and DEPLOYED_ON)
    """
    s = System(name="Software System")
    s.add(Block(id="acct-01", name="Primary Account", type=BlockType.ACCOUNT))
    s.add(
        Block(
            id="net-01",
            name="LAN",
            type=BlockType.SUBNET,
            metadata={"cidr": "10.0.0.0/24"},
        )
    )
    s.add(Block(id="srv-01", name="App Server", type=BlockType.SERVER))
    # Software added via CONTAINS
    s.add(
        Block(
            id="sw-nginx",
            name="nginx",
            type=BlockType.SOFTWARE,
            metadata={"version": "1.25"},
        )
    )
    # Software added via DEPLOYED_ON
    s.add(
        Block(
            id="sw-app",
            name="app",
            type=BlockType.SOFTWARE,
            metadata={"version": "2.0"},
        )
    )
    s.contains("acct-01", "net-01")
    s.contains("net-01", "srv-01")
    s.contains("srv-01", "sw-nginx")
    s.deployed_on("sw-app", "srv-01")
    return s


@pytest.fixture
def dependency_system() -> System:
    """A -> B -> C dependency chain for traversal tests.

    Also includes D -> A for dependents_of tests.
    """
    s = System(name="Dependency System")
    s.add(Block(id="svc-a", name="Service A", type=BlockType.SERVICE))
    s.add(Block(id="svc-b", name="Service B", type=BlockType.SERVICE))
    s.add(
        Block(
            id="svc-c",
            name="Service C (DB)",
            type=BlockType.DATABASE,
            metadata={"engine": "postgres", "version": "15"},
        )
    )
    s.add(Block(id="svc-d", name="Service D", type=BlockType.SERVICE))
    s.depends_on("svc-a", "svc-b")
    s.depends_on("svc-b", "svc-c")
    s.depends_on("svc-d", "svc-a")
    return s


@pytest.fixture
def flow_system() -> System:
    """System with a multi-hop flow crossing a boundary.

    Boundary contains node-2 and node-3.
    Flow path: node-1 (outside) -> node-2 (inside) -> node-3 (inside) -> node-4 (outside).
    """
    s = System(name="Flow System")
    s.add(Block(id="node-1", name="External Client", type=BlockType.ACTOR))
    s.add(
        Block(id="boundary-1", name="Internal Network", type=BlockType.BOUNDARY)
    )
    s.add(Block(id="node-2", name="Service A", type=BlockType.SERVICE))
    s.add(Block(id="node-3", name="Service B", type=BlockType.SERVICE))
    s.add(Block(id="node-4", name="External Target", type=BlockType.ACTOR))
    s.contains("boundary-1", "node-2")
    s.contains("boundary-1", "node-3")
    s.add_flow(
        Flow(
            id="flow-01",
            name="Test Flow",
            hops=[
                FlowHop(block_id="node-1"),
                FlowHop(block_id="node-2"),
                FlowHop(block_id="node-3"),
                FlowHop(block_id="node-4"),
            ],
            classification=DataClassification.INTERNAL,
            protocol="HTTPS",
        )
    )
    return s


@pytest.fixture
def kuzu_graph(software_system: System):  # type: ignore[no-untyped-def]
    """In-memory KuzuGraph loaded with software_system. Closes after test."""
    pytest.importorskip("kuzu")
    from sysmodel.graph import KuzuGraph

    g = KuzuGraph()
    g.load(software_system)
    yield g
    g.close()
