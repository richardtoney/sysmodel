# Cypher Queries

The optional Kuzu integration enables expressive graph traversal with Cypher.

```bash
pip install sysmodel[graph]
```

```python
from sysmodel.graph import KuzuGraph

with KuzuGraph() as g:
    g.load(system)
    results = g.query("MATCH (b:Block) RETURN b.name, b.type")
```

## The Connected table pattern

All relationships — CONTAINS, DEPENDS_ON, CONNECTS_TO, DEPLOYED_ON, and custom types
— share a single `Connected` relationship table. The actual type is stored as a `rel_type`
property on each edge.

This allows variable-length traversal across all relationship types while keeping the
Kuzu schema simple. To filter by a specific relationship type, add a `WHERE` clause on
`rel_type`:

```cypher
MATCH (a:Block)-[r:Connected]->(b:Block)
WHERE r.rel_type = 'depends_on'
RETURN a.name, b.name
```

## Kuzu variable-length path syntax

Kuzu supports `[:RelTable*]` for variable-length traversal. The `{property: value}`
filter on relationship tables works in variable-length patterns:

```cypher
MATCH (root:Block {id: 'acct-01'})-[:Connected*]->(b:Block)
RETURN b.name, b.type
```

This returns all descendants reachable by any relationship. Combine with a `rel_type`
filter via a regular pattern if you need type-specific traversal.

## Verified Cypher patterns

### All descendants via CONTAINS (variable-length path)

```cypher
MATCH (root:Block {id: 'acct-01'})-[:Connected*]->(b:Block)
RETURN b.name, b.type
```

Traverses all outbound `Connected` edges from `acct-01` to any depth.

### Software on a host (DEPLOYED_ON)

```cypher
MATCH (sw:Block)-[r:Connected]->(host:Block {id: 'srv-01'})
WHERE r.rel_type = 'deployed_on'
RETURN sw.name, sw.metadata
```

Finds all blocks that are deployed on a specific host.

### Multi-hop transitive dependency

```cypher
MATCH (a:Block {id: 'app-01'})-[r:Connected*]->(dep:Block)
RETURN dep.name, dep.type
```

Walks all outbound edges from `app-01` to find everything it transitively reaches.

### Leaf nodes: blocks with no outbound DEPENDS_ON

```cypher
MATCH (b:Block)
WHERE NOT (b)-[:Connected]->(:Block)
RETURN b.name, b.type
```

Finds blocks with no outbound relationships — typically databases or external services.

### Full hop-by-hop flow path (ordered)

```cypher
MATCH (f:Flow {id: 'flow-01'})-[h:HasHop]->(b:Block)
RETURN b.name, b.type, h.notes
ORDER BY h.position
```

Returns each hop in the flow in order, with notes.

### Blocks appearing in more than one flow (shared infrastructure)

```cypher
MATCH (f:Flow)-[:HasHop]->(b:Block)
WITH b, COUNT(DISTINCT f) AS flow_count
WHERE flow_count > 1
RETURN b.name, b.type, flow_count
ORDER BY flow_count DESC
```

Identifies blocks that are critical to multiple flows.
