# Query Reference

All functions are in `sysmodel.queries`. Import as:

```python
from sysmodel import queries
```

## Block queries

### `blocks_of_type(system, *types)`
Return all blocks matching one or more `BlockType` values.
```python
queries.blocks_of_type(s, BlockType.SERVICE)
queries.blocks_of_type(s, BlockType.SERVICE, BlockType.SOFTWARE)
```

### `blocks_with_tag(system, key, value=None)`
Blocks that have a tag key, optionally filtered by value.
```python
queries.blocks_with_tag(s, "env")           # any env tag
queries.blocks_with_tag(s, "env", "prod")   # env=prod only
```

### `blocks_with_metadata(system, key, value=None)`
Blocks that have a metadata key, optionally filtered by value.
```python
queries.blocks_with_metadata(s, "version")
queries.blocks_with_metadata(s, "engine", "postgres")
```

### `children_of(system, parent_id, block_type=None)`
Direct CONTAINS children of `parent_id`, optionally filtered by type.
```python
queries.children_of(s, "vpc-01")
queries.children_of(s, "vpc-01", BlockType.SUBNET)
```

### `descendants_of(system, root_id, block_type=None)`
All CONTAINS descendants of `root_id` in BFS order, optionally filtered by type.
```python
queries.descendants_of(s, "acct-01")
queries.descendants_of(s, "acct-01", BlockType.DATABASE)
```

### `software_on(system, host_id)`
Software blocks on a host. Checks CONTAINS children of type SOFTWARE **and** blocks
with DEPLOYED_ON pointing at the host. Deduplicates.
```python
queries.software_on(s, "srv-01")
```

### `all_software_in(system, root_id)`
All software reachable from `root_id` via CONTAINS traversal, then `software_on()` for
each host found. Deduplicates.
```python
queries.all_software_in(s, "acct-01")
```

### `find_by_name(system, name, exact=True)`
Find blocks by name. `exact=False` performs a case-insensitive substring match.
```python
queries.find_by_name(s, "postgres")
queries.find_by_name(s, "post", exact=False)
```

### `parent_of(system, block_id)`
Direct CONTAINS parent, or `None` if root-level.
```python
queries.parent_of(s, "app-01")  # -> Block(subnet-01)
```

### `account_of(system, block_id)`
Walk ancestors to find the nearest ACCOUNT block, or `None`.
```python
queries.account_of(s, "db-01")  # -> Block(acct-01)
```

## Relationship queries

### `dependencies_of(system, block_id)`
Blocks that `block_id` depends on (outbound DEPENDS_ON).
```python
queries.dependencies_of(s, "app-01")  # -> [Block(db-01)]
```

### `dependents_of(system, block_id)`
Blocks that depend on `block_id` (inbound DEPENDS_ON).
```python
queries.dependents_of(s, "db-01")  # -> [Block(app-01)]
```

### `relationships_between(system, block_a_id, block_b_id)`
All relationships in either direction between two blocks.
```python
queries.relationships_between(s, "app-01", "db-01")
```

## Flow queries

### `flows_of_classification(system, classification)`
All flows carrying data at the given classification level.
```python
queries.flows_of_classification(s, DataClassification.SENSITIVE)
```

### `flows_crossing_boundary(system, boundary_id)`
Flows where at least one hop is inside the boundary and one is outside it.
```python
queries.flows_crossing_boundary(s, "dmz-01")
```

### `lineage_for(system, block_id)`
Flows where `block_id` appears, split into upstream (flows that feed it) and
downstream (flows it feeds into).
```python
lineage = queries.lineage_for(s, "app-01")
print(lineage["upstream"])    # flows where app-01 is not the first hop
print(lineage["downstream"])  # flows where app-01 is not the last hop
```

## Projection helpers

### `summarize_blocks(blocks)`
Project a list of Blocks to lightweight dicts `{id, name, type, tags}`.
```python
queries.summarize_blocks(queries.blocks_of_type(s, BlockType.SERVICE))
```

### `group_by_type(blocks)`
Group blocks by their type string.
```python
grouped = queries.group_by_type(list(s.blocks.values()))
# {"service": [...], "database": [...]}
```

### `group_by_tag(blocks, tag_key)`
Group blocks by the value of a tag key. Blocks missing the key are grouped under
`"__untagged__"`.
```python
queries.group_by_tag(list(s.blocks.values()), "env")
# {"prod": [...], "dev": [...], "__untagged__": [...]}
```
