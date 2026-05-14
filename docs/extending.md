# Extending sysmodel

## Adding a custom block type

The `BlockType` enum lists the built-in types, but you can use **any string** as a block
type without modifying sysmodel source:

```python
from sysmodel.models import Block, System

s = System(name="My Network")
fw = s.add(Block(id="fw-01", name="Edge Firewall", type="firewall"))
```

Custom type strings are fully supported everywhere: queries, graph loading, and the TUI.

## Registering a metadata schema

Call `register_schema()` before defining any blocks of the custom type. This lets
`validate_model()` enforce required and allowed metadata keys:

```python
from sysmodel import System, Block
from sysmodel.registry import register_schema, MetadataSchema

# Register the schema for your custom type
register_schema(
    "firewall",
    MetadataSchema(
        required={"vendor"},
        allowed={"model", "firmware_version", "management_ip"},
    ),
)

s = System(name="Network")

# This block will pass validation
fw_ok = s.add(Block(
    id="fw-01",
    name="Edge Firewall",
    type="firewall",
    metadata={"vendor": "OpenBSD", "model": "pf"},
))

# This block will produce a validation error (missing required 'vendor')
fw_bad = s.add(Block(
    id="fw-02",
    name="Bad Firewall",
    type="firewall",
    metadata={"firmware_version": "7.4"},
))

errors = s.validate_model()
for e in errors:
    print(e)
# Block 'fw-02' (firewall): missing required metadata key 'vendor'
```

## Where to call register_schema()

Call it at the top of your system file, before any `Block()` definitions, or in a
shared configuration module that your system files import:

```python
# shared_schemas.py
from sysmodel.registry import register_schema, MetadataSchema

register_schema("firewall", MetadataSchema(required={"vendor"}))
register_schema("switch",   MetadataSchema(required={"vendor"}, allowed={"ports"}))
```

```python
# my_system.py
import shared_schemas  # registers the schemas
from sysmodel.models import Block, System

s = System(name="My Network")
s.add(Block(id="fw-01", name="Firewall", type="firewall", metadata={"vendor": "OpenBSD"}))
```

## Inspecting the registry

```python
from sysmodel.registry import get_schema, METADATA_REGISTRY

# Get the schema for a specific type
schema = get_schema("firewall")
print(schema.required)   # {'vendor'}
print(schema.allowed)    # {'model', 'firmware_version', 'management_ip'}
print(schema.all_known)  # {'vendor', 'model', 'firmware_version', 'management_ip'}

# List all registered types
print(list(METADATA_REGISTRY.keys()))
```
