# Quickstart

Get from `pip install` to a working query in under 30 lines.

## Define a system

```python
from sysmodel import System, Block, BlockType, Flow, FlowHop, DataClassification

# Create the system
s = System(name="Web App", description="Simple three-tier example")

# Add blocks
lb  = s.add(Block(id="lb-01",  name="Load Balancer", type=BlockType.LOAD_BALANCER))
app = s.add(Block(id="app-01", name="API Service",   type=BlockType.SERVICE,
                  tags={"env": "prod"}))
db  = s.add(Block(id="db-01",  name="Database",      type=BlockType.DATABASE,
                  metadata={"engine": "postgres", "version": "16"}))

# Add relationships
s.connects_to("lb-01",  "app-01", protocol="HTTP")
s.depends_on( "app-01", "db-01",  protocol="jdbc", port="5432")

# Add a data flow
s.add_flow(Flow(
    id="flow-01",
    name="Request path",
    hops=[FlowHop(block_id="lb-01"), FlowHop(block_id="app-01"), FlowHop(block_id="db-01")],
    classification=DataClassification.INTERNAL,
    protocol="HTTPS",
))

# Validate metadata
errors = s.validate_model()
for e in errors:
    print(e)
```

## Run Python queries

```python
from sysmodel import queries

# All blocks of a given type
dbs = queries.blocks_of_type(s, BlockType.DATABASE)
print([b.name for b in dbs])   # ['Database']

# What does the API service depend on?
deps = queries.dependencies_of(s, "app-01")
print([b.name for b in deps])  # ['Database']

# All flows through the load balancer
flows = queries.flows_through(s, "lb-01")
print([f.id for f in flows])   # ['flow-01']

# Summarise all blocks
print(queries.summarize_blocks(list(s.blocks.values())))
# [{'id': 'lb-01', 'name': 'Load Balancer', 'type': 'load_balancer', 'tags': {}}, ...]

# Group by type
grouped = queries.group_by_type(list(s.blocks.values()))
print(list(grouped.keys()))    # ['load_balancer', 'service', 'database']
```

## Run Cypher queries (optional)

```bash
pip install sysmodel[graph]
```

```python
from sysmodel.graph import KuzuGraph

with KuzuGraph() as g:
    g.load(s)
    results = g.query(
        "MATCH (a:Block)-[r:Connected]->(b:Block) "
        "WHERE r.rel_type = 'depends_on' "
        "RETURN a.name, b.name"
    )
    print(results)
    # [{'a.name': 'API Service', 'b.name': 'Database'}]
```

## Launch the TUI

```bash
sysmodel systems.example
```
