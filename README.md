# sysmodel

`sysmodel` is a Python library for modeling software systems and cloud infrastructure
as plain Python files. Define blocks, connect them with typed relationships, trace data
flows, and query everything with Python helpers or Cypher via an embedded graph database.

[![CI](https://github.com/richardtoney/sysmodel/actions/workflows/ci.yml/badge.svg)](https://github.com/richardtoney/sysmodel/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/sysmodel)](https://pypi.org/project/sysmodel/)
[![Python](https://img.shields.io/pypi/pyversions/sysmodel)](https://pypi.org/project/sysmodel/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## What this is

`sysmodel` lets engineering teams document living system architecture as code.
Models are plain `.py` files that import the library and instantiate objects.
They can be queried, visualised in a TUI, loaded into a graph database, and
kept in version control alongside the systems they describe.

## Install

```bash
pip install sysmodel
```

To enable Cypher queries via the embedded Kuzu graph database:

```bash
pip install sysmodel[graph]
```

## Define a system

```python
from sysmodel import (
    System, Block, BlockType,
    Flow, FlowHop, DataClassification,
)

s = System(name="Web App", description="Three-tier web application")

# Add blocks with types and metadata
lb  = s.add(Block(id="lb-01",  name="Load Balancer", type=BlockType.LOAD_BALANCER,
                  tags={"env": "prod"}))
app = s.add(Block(id="app-01", name="API Service",   type=BlockType.SERVICE,
                  metadata={"port": "8080", "language": "python"},
                  tags={"env": "prod", "tier": "app"}))
db  = s.add(Block(id="db-01",  name="Database",      type=BlockType.DATABASE,
                  metadata={"engine": "postgres", "version": "16"}))

# Add typed relationships
s.connects_to("lb-01",  "app-01", protocol="HTTP", port="8080")
s.depends_on( "app-01", "db-01",  protocol="jdbc", port="5432")

# Add a data flow with classification
s.add_flow(Flow(
    id="req-01", name="Request path",
    classification=DataClassification.INTERNAL,
    hops=[
        FlowHop(block_id="lb-01",  notes="Routing"),
        FlowHop(block_id="app-01", notes="Business logic"),
        FlowHop(block_id="db-01",  notes="Data retrieval"),
    ],
))

# Validate all metadata against the registry
errors = s.validate_model()
for e in errors:
    print(e)
```

## Query with Python

```python
from sysmodel import queries, DataClassification

# What does the API service depend on?
deps = queries.dependencies_of(s, "app-01")
print([b.name for b in deps])
# ['Database']

# What depends on the database?
rev = queries.dependents_of(s, "db-01")
print([b.name for b in rev])
# ['API Service']

# All blocks with the env=prod tag
prod = queries.blocks_with_tag(s, "env", "prod")
print([b.id for b in prod])
# ['lb-01', 'app-01']

# Find by name (exact or substring)
print(queries.find_by_name(s, "API Service")[0].id)       # 'app-01'
print(queries.find_by_name(s, "api", exact=False)[0].id)  # 'app-01'

# Flows through the load balancer (System method)
flows = s.flows_through("lb-01")
print([f.name for f in flows])
# ['Request path']

# Flows carrying internal data
internal = queries.flows_of_classification(s, DataClassification.INTERNAL)
print([f.name for f in internal])
# ['Request path']

# Data lineage for a block
lineage = queries.lineage_for(s, "app-01")
print([f.name for f in lineage["upstream"]])    # flows arriving at app-01
print([f.name for f in lineage["downstream"]])  # flows leaving app-01

# Group all blocks by type
grouped = queries.group_by_type(list(s.blocks.values()))
print({t: len(bs) for t, bs in grouped.items()})
# {'load_balancer': 1, 'service': 1, 'database': 1}

# Group by tag value
by_env = queries.group_by_tag(list(s.blocks.values()), "env")
print({k: [b.id for b in v] for k, v in by_env.items()})
# {'prod': ['lb-01', 'app-01'], '__untagged__': ['db-01']}

# Summarise blocks to lightweight dicts
print(queries.summarize_blocks(list(s.blocks.values())))
# [{'id': 'lb-01', 'name': 'Load Balancer', 'type': 'load_balancer', 'tags': {...}}, ...]
```

## Query with Cypher

```python
from sysmodel.graph import KuzuGraph

with KuzuGraph() as g:
    g.load(s)

    # Direct dependencies
    print(g.query(
        "MATCH (a:Block)-[r:Connected]->(b:Block) "
        "WHERE r.rel_type = 'depends_on' "
        "RETURN a.name, b.name"
    ))
    # [{'a.name': 'API Service', 'b.name': 'Database'}]

    # All reachable blocks from root (explicit hop bounds recommended)
    print(g.query(
        "MATCH (root:Block {id: 'lb-01'})-[:Connected*1..10]->(b:Block) "
        "RETURN b.name, b.type"
    ))

    # Blocks that nothing depends on (leaf nodes)
    print(g.query(
        "MATCH (b:Block) WHERE NOT (b)-[:Connected]->(:Block) "
        "RETURN b.name, b.type"
    ))

    # Blocks appearing in more than one flow (shared infrastructure)
    print(g.query(
        "MATCH (f:Flow)-[:HasHop]->(b:Block) "
        "WITH b, COUNT(DISTINCT f) AS flow_count "
        "WHERE flow_count > 1 "
        "RETURN b.name, b.type, flow_count "
        "ORDER BY flow_count DESC"
    ))
```

## Model state machines

Document the lifecycle of any block with named states and typed transitions:

```python
from sysmodel import StateMachine, State, Transition

sm = StateMachine(
    block_id="app-01",
    initial_state="starting",
    states={
        "starting": State(id="starting", name="Starting",
                          invariants=["Health check returns 503"]),
        "running":  State(id="running",  name="Running",
                          invariants=["Health check returns 200"]),
        "stopped":  State(id="stopped",  name="Stopped"),
    },
    transitions=[
        Transition(
            from_state_id="starting", to_state_id="running",
            trigger="Health check passes",
            action="Register with load balancer",
        ),
        Transition(
            from_state_id="running", to_state_id="stopped",
            trigger="Shutdown signal",
            guard="All in-flight requests complete",
            action="Deregister from load balancer",
        ),
    ],
)
s.add_state_machine(sm)
```

## Serialize and reload

```python
# JSON round-trip
json_str = s.to_json()
restored = System.from_json(json_str)

# Dict round-trip (for custom storage or diffing)
d = s.to_dict()
restored = System.from_dict(d)
```

## Run the TUI

```bash
sysmodel systems.example
```

```
┌────────────────────────────────────────────────────────────┐
│  sysmodel — Sample Web Application   [● kuzu]   │
├──────────────┬─────────────────────────────────────────────┤
│  INVENTORY   │  id      name         type          tags        │
│  CONTAINMENT │  ──────  ────────────  ────────────  ────────    │
│  SOFTWARE    │  lb-01   Load Balancer load_balancer tier=public │
│  DEPS        │  app-01  API Service   service       tier=app    │
│  FLOWS       │  db-01   Database      database      tier=data   │
│  CYPHER      │                                                  │
├──────────────┴─────────────────────────────────────────────┤
│  >                                                    [Run ⏎]  │
└────────────────────────────────────────────────────────────┘
```

Load from a file path: `sysmodel myproject/arch.py`

Keybindings: `q` quit • `ctrl+e` export CSV • `ctrl+l` clear • `ctrl+r` reload • `?` help

## Extend the registry

Add custom block types and their metadata schemas without modifying sysmodel:

```python
from sysmodel import System, Block
from sysmodel.registry import register_schema, MetadataSchema

register_schema(
    "firewall",
    MetadataSchema(
        required={"vendor"},
        allowed={"model", "firmware_version"},
    ),
)

s = System(name="Network")
s.add(Block(id="fw-01", name="Edge Firewall", type="firewall",
           metadata={"vendor": "OpenBSD", "model": "pf"}))

print(s.validate_model())  # []
```

Pass `strict=True` to raise on the first error instead of collecting:

```python
s.validate_model(strict=True)  # raises MetadataValidationError
```

## Run tests

```bash
pip install -e ".[graph,dev]"
pytest
```

Expected output includes:

```
---------- coverage: platform linux, python 3.11 ----------
Name                    Stmts   Miss  Cover
-------------------------------------------
sysmodel/exceptions.py     28      0   100%
sysmodel/graph.py          89      4    96%
sysmodel/models.py        162      3    98%
sysmodel/queries.py       102      2    98%
sysmodel/registry.py       42      0   100%
-------------------------------------------
TOTAL                     423     9    98%

90 passed in 4.21s
```

To run tests without the Kuzu optional dependency:

```bash
pip install -e ".[dev]"
pytest -k "not test_graph"
```
