"""Example system: a generic three-tier web application.

Demonstrates the full sysmodel feature set:
- Multiple block types (account, vpc, subnet, load balancer, service, database)
- Containment hierarchy via CONTAINS relationships
- Runtime dependencies via DEPENDS_ON
- Network connections via CONNECTS_TO
- A multi-hop data flow with classification
- A state machine on the application service

This file is the primary demonstration vehicle for the TUI and docs.
Run with:  sysmodel systems.example
"""
from __future__ import annotations

import sys

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

# ---------------------------------------------------------------------------
# System root
# ---------------------------------------------------------------------------

system = System(
    name="Sample Web Application",
    description="Generic three-tier web application illustrating sysmodel features.",
)

# ---------------------------------------------------------------------------
# Infrastructure blocks
# ---------------------------------------------------------------------------

acct = system.add(
    Block(
        id="acct-01",
        name="Primary Account",
        type=BlockType.ACCOUNT,
        tags={"env": "prod", "team": "platform"},
    )
)

vpc = system.add(
    Block(
        id="vpc-01",
        name="Application VPC",
        type=BlockType.VPC,
        metadata={"cidr": "10.0.0.0/16"},
        tags={"env": "prod"},
    )
)

subnet_pub = system.add(
    Block(
        id="subnet-pub",
        name="Public Subnet",
        type=BlockType.SUBNET,
        metadata={"cidr": "10.0.1.0/24", "public": "true"},
        tags={"tier": "public", "env": "prod"},
    )
)

subnet_priv = system.add(
    Block(
        id="subnet-priv",
        name="Private Subnet",
        type=BlockType.SUBNET,
        metadata={"cidr": "10.0.2.0/24", "public": "false"},
        tags={"tier": "private", "env": "prod"},
    )
)

# ---------------------------------------------------------------------------
# Compute and application blocks
# ---------------------------------------------------------------------------

lb = system.add(
    Block(
        id="lb-01",
        name="Application Load Balancer",
        type=BlockType.LOAD_BALANCER,
        metadata={"scheme": "internet-facing", "protocol": "HTTPS", "port": "443"},
        tags={"tier": "public", "env": "prod"},
    )
)

app = system.add(
    Block(
        id="app-01",
        name="API Service",
        type=BlockType.SERVICE,
        description="Core REST API backend.",
        metadata={"port": "8080", "protocol": "HTTP", "language": "python"},
        tags={"tier": "app", "env": "prod", "team": "backend"},
    )
)

db = system.add(
    Block(
        id="db-01",
        name="Primary Database",
        type=BlockType.DATABASE,
        description="Relational database backing the API.",
        metadata={"engine": "postgres", "version": "16", "port": "5432"},
        tags={"tier": "data", "env": "prod"},
    )
)

cache = system.add(
    Block(
        id="cache-01",
        name="Response Cache",
        type=BlockType.SERVICE,
        description="In-memory cache for frequently read data.",
        metadata={"port": "6379", "protocol": "TCP"},
        tags={"tier": "app", "env": "prod"},
    )
)

external_client = system.add(
    Block(
        id="client-01",
        name="External Client",
        type=BlockType.ACTOR,
        description="End-user browser or API consumer.",
    )
)

# ---------------------------------------------------------------------------
# Containment hierarchy
# ---------------------------------------------------------------------------

system.contains("acct-01", "vpc-01")
system.contains("vpc-01", "subnet-pub")
system.contains("vpc-01", "subnet-priv")
system.contains("subnet-pub", "lb-01")
system.contains("subnet-priv", "app-01")
system.contains("subnet-priv", "db-01")
system.contains("subnet-priv", "cache-01")

# ---------------------------------------------------------------------------
# Runtime relationships
# ---------------------------------------------------------------------------

system.connects_to("client-01", "lb-01", protocol="HTTPS", port="443")
system.connects_to("lb-01", "app-01", protocol="HTTP", port="8080")
system.depends_on("app-01", "db-01", protocol="jdbc", port="5432")
system.depends_on("app-01", "cache-01", protocol="TCP", port="6379")

# ---------------------------------------------------------------------------
# Data flow
# ---------------------------------------------------------------------------

system.add_flow(
    Flow(
        id="flow-request",
        name="Inbound Request Flow",
        description="Path of an API request from an external client to the database.",
        hops=[
            FlowHop(block_id="client-01", notes="Originates request"),
            FlowHop(block_id="lb-01", notes="TLS termination and routing"),
            FlowHop(block_id="app-01", notes="Business logic and query"),
            FlowHop(block_id="db-01", notes="Data retrieval"),
        ],
        classification=DataClassification.INTERNAL,
        protocol="HTTPS",
    )
)

# ---------------------------------------------------------------------------
# State machine on the API service
# ---------------------------------------------------------------------------

system.add_state_machine(
    StateMachine(
        block_id="app-01",
        states={
            "starting": State(
                id="starting",
                name="Starting",
                description="Service initialising; not yet accepting traffic.",
                invariants=["Health check endpoint returns 503"],
            ),
            "running": State(
                id="running",
                name="Running",
                description="Service healthy and processing requests.",
                invariants=[
                    "Health check endpoint returns 200",
                    "Database connection pool active",
                ],
            ),
            "degraded": State(
                id="degraded",
                name="Degraded",
                description="Serving requests but with reduced functionality.",
                invariants=["Cache unavailable; reads fall through to database"],
            ),
            "stopped": State(
                id="stopped",
                name="Stopped",
                description="Service offline; not accepting traffic.",
                invariants=["No active connections"],
            ),
        },
        transitions=[
            Transition(
                from_state_id="starting",
                to_state_id="running",
                trigger="Health check passes",
                action="Register with load balancer",
            ),
            Transition(
                from_state_id="running",
                to_state_id="degraded",
                trigger="Cache connection lost",
                action="Switch to direct database reads",
            ),
            Transition(
                from_state_id="degraded",
                to_state_id="running",
                trigger="Cache connection restored",
                action="Resume cached reads",
            ),
            Transition(
                from_state_id="running",
                to_state_id="stopped",
                trigger="Shutdown signal received",
                guard="All in-flight requests complete",
                action="Deregister from load balancer",
            ),
            Transition(
                from_state_id="stopped",
                to_state_id="starting",
                trigger="Start command issued",
            ),
        ],
        initial_state="starting",
    )
)

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_errors = system.validate_model()
if _errors:
    for _err in _errors:
        print(f"[sysmodel validation] {_err}", file=sys.stderr)
