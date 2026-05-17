# TUI Guide

The `sysmodel` command launches an interactive query interface for any system definition.

## Starting the TUI

```bash
# Load by dotted module name
sysmodel systems.example

# Load by file path
sysmodel path/to/my_system.py

# Show help
sysmodel --help
```

## Layout

```
┌────────────────────────────────────────────────────────────┐
│  sysmodel — Sample Web Application   [● kuzu]   │
├──────────────┬─────────────────────────────────────────────────┤
│              │                                              │
│  INVENTORY   │  id        name       type    tags          │
│  CONTAINMENT │  ────────  ─────────  ──────  ──────────     │
│  SOFTWARE    │  lb-01     Load Bal   load_b  tier=public  │
│  DEPS        │  app-01    API Svc    service  tier=app     │
│  FLOWS       │  db-01     Database   databas  tier=data    │
│  CYPHER      │                                              │
├──────────────┴─────────────────────────────────────────────────┤
│  > Enter Cypher or parameter here                  [Run ⏎]  │
└────────────────────────────────────────────────────────────┘
```

## Kuzu status indicator

The `[● kuzu]` indicator in the title bar shows the graph database status:

| Symbol | Meaning |
|---|---|
| `● kuzu` (green) | Kuzu loaded and ready for Cypher queries |
| `○ kuzu` (yellow) | Kuzu not installed; Python queries still work |
| `● kuzu` (red) | Kuzu installed but load failed; see log for details |

## Query tabs

| Tab | Queries available |
|---|---|
| INVENTORY | All blocks, count summary, by tag, by metadata key |
| CONTAINMENT | Children, descendants, ancestors of a block |
| SOFTWARE | All software, software on a host, software with version |
| DEPS | Dependencies, dependents, relationships between two blocks |
| FLOWS | All flows, through a block, crossing a boundary, by classification, lineage |
| CYPHER | Free-form Kuzu Cypher (requires `sysmodel[graph]`) |

Click a query item to run it. Items that require a block ID or other parameter will
place focus on the input bar and show a prompt.

## Keybindings

| Key | Action |
|---|---|
| `q` or `ctrl+c` | Quit |
| `tab` | Cycle focus |
| `enter` | Run selected query or submit input |
| `ctrl+e` | Export current results to `sysmodel_export.csv` |
| `ctrl+l` | Clear results panel |
| `ctrl+r` | Reload system from source module |
| `?` | Show keybinding help notification |

## Validation warnings

If `validate_model()` returns errors, a collapsible warning panel appears above the
results area with the message:

> Model validation warnings — queries may return incomplete results.

Queries still run. Fix the metadata errors in your system file and press `ctrl+r` to
reload.
