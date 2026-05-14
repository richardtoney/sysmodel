# sysmodel

`sysmodel` is a Python library for modeling the structure and behavior of software
systems and cloud infrastructure as plain Python files. Teams define blocks (servers,
services, databases, networks), connect them with typed relationships, define data flows,
and query the resulting model using either Python helper functions or Cypher via an
embedded Kuzu graph database.

## Install

```bash
pip install sysmodel
```

To enable Cypher/graph queries:

```bash
pip install sysmodel[graph]
```

## Hello World

```python
from sysmodel import System, Block, BlockType

s = System(name="My App")
db  = s.add(Block(id="db-01",  name="postgres", type=BlockType.DATABASE,
                  metadata={"engine": "postgres", "version": "16"}))
app = s.add(Block(id="app-01", name="api",      type=BlockType.SERVICE))
s.depends_on("app-01", "db-01", protocol="jdbc")

errors = s.validate_model()
print(errors)  # []
```

## Key Features

- **Plain Python files** are the source of truth — no YAML, no special DSL
- **Pydantic-validated models** catch errors at definition time
- **20 Python query helpers** for blocks, relationships, flows, and projections
- **Optional Kuzu integration** for expressive graph traversal with Cypher
- **Textual TUI** for interactive exploration of any system model
- **Registry-based metadata validation** — extensible without subclassing
- **Typed exception hierarchy** for precise error handling
