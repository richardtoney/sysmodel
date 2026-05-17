# Concepts

## The five core objects

| Object | Role |
|---|---|
| `Block` | A typed, labeled node: server, service, database, actor, etc. |
| `Relationship` | A directed, typed edge between two Blocks |
| `Flow` | An ordered list of hops representing a data or control path |
| `StateMachine` | States and transitions documenting a Block's lifecycle |
| `System` | The registry that owns all of the above via string IDs |

## The flat registry design

All blocks live in `System.blocks` — a plain `dict[str, Block]`. There are no nested
object trees. Children are found via `CONTAINS` relationships, not via object references:

```
System.blocks
  ├── "vpc-01"     Block(type=VPC)
  ├── "subnet-01" Block(type=SUBNET)
  ├── "app-01"    Block(type=SERVICE)
  └── "db-01"     Block(type=DATABASE)

System.relationships
  vpc-01   ──[CONTAINS]→── subnet-01
  subnet-01──[CONTAINS]→── app-01
  subnet-01──[CONTAINS]→── db-01
  app-01   ──[DEPENDS_ON]→─ db-01
```

This makes the entire model serializable to a flat JSON object and loadable into a
graph database without any structural translation.

## Why metadata validation is a registry, not subclasses

Each block type has different required/allowed metadata keys. Using subclasses would
force you to either import a different class per type or rely on runtime `isinstance`
checks. The registry approach lets you:

- Extend the schema for any type without modifying sysmodel source
- Add entirely new block type strings without touching the `BlockType` enum
- Validate all metadata in a single pass via `System.validate_model()`

## CONTAINS vs DEPLOYED_ON

`CONTAINS` models structural ownership: a VPC contains subnets, a subnet contains
instances. `DEPLOYED_ON` models software placement on a host without implying structural
ownership. Both are first-class relationship types.

The `software_on()` query helper checks both: it returns software found as CONTAINS
children of type SOFTWARE **and** software pointing at the host via DEPLOYED_ON.

## Pydantic for authoring; Kuzu for traversal

Pydantic validates your model at definition time — it catches misspelled field names and
missing required metadata before a single query runs. Kuzu provides expressive
variable-length path queries over the same data. They do not overlap.
