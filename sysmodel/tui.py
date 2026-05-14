"""Textual TUI for sysmodel — interactive query interface.

Launch with:  sysmodel systems.example
              sysmodel path/to/system.py
              sysmodel --help

The TUI loads a System and lets you run queries against it.
It does not write back to the source file.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import logging
import sys
import types
from pathlib import Path
from typing import Any

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Collapsible,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

from sysmodel import queries
from sysmodel.exceptions import SysmodelError
from sysmodel.models import Block, BlockType, DataClassification, Flow, System

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Kuzu availability (optional)
# ---------------------------------------------------------------------------

try:
    from sysmodel.graph import KuzuGraph
    from sysmodel.graph import _KUZU_AVAILABLE as _GRAPH_AVAILABLE
except Exception:  # noqa: BLE001 — broad catch: graph import failure must not crash TUI
    _GRAPH_AVAILABLE = False
    KuzuGraph = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Module loading and system discovery (unit-testable, no Textual)
# ---------------------------------------------------------------------------


def load_module_from_path(file_path: str) -> types.ModuleType:
    """Load a Python source file as a module.

    Args:
        file_path: Absolute or relative path to a .py file.

    Returns:
        The loaded module object.

    Raises:
        SysmodelError: If the file cannot be loaded.
    """
    path = Path(file_path).resolve()
    module_name = path.stem
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise SysmodelError(f"Cannot load module from path: {file_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception as exc:
        raise SysmodelError(f"Error executing {file_path}: {exc}") from exc
    return module


def load_module_from_dotted_name(dotted_name: str) -> types.ModuleType:
    """Import a module by its dotted Python name.

    Args:
        dotted_name: A dotted module path such as ``systems.example``.

    Returns:
        The imported module object.

    Raises:
        SysmodelError: If the module cannot be imported.
    """
    try:
        return importlib.import_module(dotted_name)
    except ImportError as exc:
        raise SysmodelError(
            f"Cannot import module '{dotted_name}': {exc}. "
            "Check that the module is on sys.path."
        ) from exc


def discover_system(module: types.ModuleType) -> System:
    """Find the single System instance in a module's namespace.

    Args:
        module: An imported Python module.

    Returns:
        The System instance found in the module.

    Raises:
        SysmodelError: If zero or more than one System instance is found.
    """
    found = [
        obj for obj in vars(module).values() if isinstance(obj, System)
    ]
    if not found:
        raise SysmodelError(
            f"No System instance found in '{module.__name__}'. "
            "Define a System at module level, e.g.: system = System(name='My App')"
        )
    if len(found) > 1:
        raise SysmodelError(
            f"Multiple System instances found in '{module.__name__}'. "
            "Define exactly one System at module level."
        )
    return found[0]


def _resolve_module(target: str) -> types.ModuleType:
    """Load a module from either a file path or dotted name."""
    if target.endswith(".py") or "/" in target or "\\" in target:
        return load_module_from_path(target)
    return load_module_from_dotted_name(target)


# ---------------------------------------------------------------------------
# Result formatters
# ---------------------------------------------------------------------------


def _blocks_table(blocks: list[Block]) -> list[dict[str, str]]:
    return [
        {
            "id": b.id,
            "name": b.name,
            "type": str(b.type.value if hasattr(b.type, "value") else b.type),
            "tags": ", ".join(f"{k}={v}" for k, v in b.tags.items()),
        }
        for b in blocks
    ]


def _flows_table(flows: list[Flow]) -> list[dict[str, str]]:
    return [
        {
            "id": f.id,
            "name": f.name,
            "classification": str(f.classification.value if hasattr(f.classification, "value") else f.classification),
            "hops": " -> ".join(f.block_ids),
        }
        for f in flows
    ]


def _count_summary(system: System) -> list[dict[str, str]]:
    counts: dict[str, int] = {}
    for block in system.blocks.values():
        type_str = str(block.type.value if hasattr(block.type, "value") else block.type)
        counts[type_str] = counts.get(type_str, 0) + 1
    return [{"type": t, "count": str(c)} for t, c in sorted(counts.items())]


# ---------------------------------------------------------------------------
# Query tab helpers
# ---------------------------------------------------------------------------


def _query_blocks_tag(system: System, param: str) -> list[dict[str, str]]:
    if "=" in param:
        key, _, val = param.partition("=")
        blocks = queries.blocks_with_tag(system, key.strip(), val.strip())
    else:
        blocks = queries.blocks_with_tag(system, param.strip())
    return _blocks_table(blocks)


def _query_blocks_meta(system: System, param: str) -> list[dict[str, str]]:
    return _blocks_table(queries.blocks_with_metadata(system, param.strip()))


def _query_rels_between(system: System, param: str) -> list[dict[str, str]]:
    parts = param.split()
    if len(parts) < 2:
        return [{"error": "Provide two block IDs separated by a space"}]
    rels = queries.relationships_between(system, parts[0], parts[1])
    return [
        {
            "source": r.source_id,
            "type": str(r.type.value if hasattr(r.type, "value") else r.type),
            "target": r.target_id,
            "metadata": str(r.metadata),
        }
        for r in rels
    ]


def _query_flows_class(system: System, param: str) -> list[dict[str, str]]:
    try:
        cls = DataClassification(param.strip().lower())
    except ValueError:
        return [{"error": f"Unknown classification: {param}. Valid: {[c.value for c in DataClassification]}"}]
    return _flows_table(queries.flows_of_classification(system, cls))


def _query_lineage(system: System, param: str) -> list[dict[str, str]]:
    lineage = queries.lineage_for(system, param.strip())
    rows: list[dict[str, str]] = []
    for direction, flows in lineage.items():
        for flow in flows:
            rows.append({"direction": direction, "flow_id": flow.id, "name": flow.name})
    return rows


# ---------------------------------------------------------------------------
# Query tab definitions (must appear after all referenced callables)
# ---------------------------------------------------------------------------

# Each entry: (display_label, param_prompt_or_None, callable_taking(system, param))
_TABS: dict[str, list[tuple[str, str | None, Any]]] = {
    "INVENTORY": [
        ("All blocks by type", None, lambda s, _: _blocks_table(list(s.blocks.values()))),
        ("Block count summary", None, lambda s, _: _count_summary(s)),
        ("Blocks with tag [key]=[value]", "tag key=value", _query_blocks_tag),
        ("Blocks with metadata key [key]", "metadata key", _query_blocks_meta),
    ],
    "CONTAINMENT": [
        ("Children of [block id]", "block id", lambda s, p: _blocks_table(queries.children_of(s, p))),
        ("All descendants of [block id]", "block id", lambda s, p: _blocks_table(queries.descendants_of(s, p))),
        ("Full ancestry of [block id]", "block id", lambda s, p: _blocks_table(s.ancestors(p))),
    ],
    "SOFTWARE": [
        ("All software in system", None, lambda s, _: _blocks_table(queries.blocks_of_type(s, BlockType.SOFTWARE))),
        ("Software on [host id]", "host id", lambda s, p: _blocks_table(queries.software_on(s, p))),
        ("All software with version", None, lambda s, _: _blocks_table(queries.blocks_with_metadata(s, "version"))),
    ],
    "DEPS": [
        ("Dependencies of [block id]", "block id", lambda s, p: _blocks_table(queries.dependencies_of(s, p))),
        ("Dependents of [block id]", "block id", lambda s, p: _blocks_table(queries.dependents_of(s, p))),
        ("Relationships between [id] and [id]", "id1 id2 (space-separated)", _query_rels_between),
    ],
    "FLOWS": [
        ("All flows", None, lambda s, _: _flows_table(list(s.flows.values()))),
        ("Flows through [block id]", "block id", lambda s, p: _flows_table(s.flows_through(p))),
        ("Flows crossing boundary [id]", "boundary id", lambda s, p: _flows_table(queries.flows_crossing_boundary(s, p))),
        ("Flows by classification [level]", "classification level", _query_flows_class),
        ("Lineage for [block id]", "block id", _query_lineage),
    ],
    "CYPHER": [],
}


# ---------------------------------------------------------------------------
# Textual App
# ---------------------------------------------------------------------------


class SysmodelApp(App[None]):
    """Textual TUI for querying a sysmodel System."""

    CSS = """
    #sidebar {
        width: 28;
        border-right: solid $primary-darken-2;
        background: $surface;
    }
    #sidebar-tabs {
        height: auto;
    }
    #query-list {
        height: 1fr;
        background: $surface;
    }
    #main-area {
        width: 1fr;
    }
    #validation-warnings {
        height: auto;
        background: $warning 20%;
        color: $warning-darken-3;
        padding: 0 1;
    }
    #results-scroll {
        height: 1fr;
    }
    #results-table {
        height: 1fr;
    }
    #input-area {
        height: 3;
        background: $surface;
        border-top: solid $primary-darken-2;
        padding: 0 1;
    }
    #kuzu-status {
        dock: right;
        width: 18;
        content-align: right middle;
        padding: 0 1;
    }
    .kuzu-ok   { color: $success; }
    .kuzu-warn { color: $warning; }
    .kuzu-err  { color: $error; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("tab", "focus_next", "Next", show=False),
        Binding("ctrl+e", "export_csv", "Export CSV"),
        Binding("ctrl+l", "clear_results", "Clear"),
        Binding("ctrl+r", "reload", "Reload"),
        Binding("question_mark", "toggle_help", "Help"),
    ]

    _current_rows: reactive[list[dict[str, str]]] = reactive([])

    def __init__(self, system: System, source: str) -> None:
        super().__init__()
        self._system = system
        self._source = source
        self._graph: Any = None
        self._graph_status = "unavailable"
        self._selected_tab = "INVENTORY"
        self._pending_query: tuple[str | None, Any] | None = None  # (prompt, fn)
        self._validation_errors: list[str] = system.validate_model()

    def on_mount(self) -> None:
        self._init_graph()
        self._populate_sidebar(self._selected_tab)
        self._run_query("All blocks by type", None, _TABS["INVENTORY"][0][2])

    def _init_graph(self) -> None:
        if not _GRAPH_AVAILABLE:
            self._graph_status = "unavailable"
            return
        try:
            self._graph = KuzuGraph()
            self._graph.load(self._system)
            self._graph_status = "ok"
        except Exception as exc:  # noqa: BLE001
            logger.warning("KuzuGraph load failed: %s", exc)
            self._graph_status = "error"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal():
            with Vertical(id="sidebar"):
                yield ListView(id="query-list")
            with Vertical(id="main-area"):
                if self._validation_errors:
                    yield Collapsible(
                        Static(
                            "Model validation warnings — queries may return incomplete results.\n"
                            + "\n".join(self._validation_errors[:5])
                        ),
                        title="⚠ Validation warnings",
                        id="validation-warnings",
                    )
                with ScrollableContainer(id="results-scroll"):
                    yield DataTable(id="results-table", show_cursor=True)
        with Horizontal(id="input-area"):
            yield Input(placeholder="Cypher (CYPHER tab) or query parameter", id="query-input")
            yield Button("Run ⏎", id="run-btn", variant="primary")
        yield Footer()

    def on_ready(self) -> None:
        self._update_title()
        self._populate_sidebar(self._selected_tab)

    def _update_title(self) -> None:
        status_icons = {"ok": "● kuzu", "unavailable": "○ kuzu", "error": "● kuzu"}
        status = status_icons.get(self._graph_status, "")
        self.title = f"sysmodel — {self._system.name}  [{status}]"
        self.sub_title = self._source

    def _populate_sidebar(self, tab_name: str) -> None:
        lv = self.query_one("#query-list", ListView)
        lv.clear()
        items = _TABS.get(tab_name, [])
        if tab_name == "CYPHER":
            if self._graph_status == "ok":
                lv.append(ListItem(Label("Enter Cypher in the input bar below")))
            else:
                lv.append(
                    ListItem(
                        Label(
                            "Kuzu unavailable.\n"
                            "Install with: pip install sysmodel[graph]"
                        )
                    )
                )
        else:
            for label, prompt, fn in items:
                lv.append(ListItem(Label(label), name=label))

    @on(ListView.Selected)
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        tab = self._selected_tab
        items = _TABS.get(tab, [])
        label = str(event.item.query_one(Label).renderable)
        for item_label, prompt, fn in items:
            if item_label == label:
                if prompt is not None:
                    self._pending_query = (prompt, fn)
                    self.query_one("#query-input", Input).placeholder = f"Enter: {prompt}"
                    self.query_one("#query-input", Input).focus()
                else:
                    self._run_query(label, None, fn)
                return

    @on(Button.Pressed, "#run-btn")
    def on_run_pressed(self, _: Button.Pressed) -> None:
        self._handle_input_submit()

    @on(Input.Submitted, "#query-input")
    def on_input_submitted(self, _: Input.Submitted) -> None:
        self._handle_input_submit()

    def _handle_input_submit(self) -> None:
        inp = self.query_one("#query-input", Input)
        value = inp.value.strip()

        if self._selected_tab == "CYPHER":
            if value and self._graph_status == "ok":
                self._run_cypher(value)
            return

        if self._pending_query is not None:
            _prompt, fn = self._pending_query
            self._pending_query = None
            inp.value = ""
            inp.placeholder = "Cypher (CYPHER tab) or query parameter"
            self._run_query("Query result", value, fn)

    def _run_query(self, title: str, param: str | None, fn: Any) -> None:
        try:
            rows = fn(self._system, param)
        except SysmodelError as exc:
            rows = [{"error": str(exc)}]
        except Exception as exc:  # noqa: BLE001
            rows = [{"error": f"Unexpected error: {exc}"}]
        self._display_rows(title, rows)

    def _run_cypher(self, cypher: str) -> None:
        if self._graph is None:
            self._display_rows("Cypher", [{"error": "Kuzu not loaded"}])
            return
        try:
            rows = self._graph.query(cypher)
            if not rows:
                rows = [{"info": "(no results)"}]
        except Exception as exc:  # noqa: BLE001
            rows = [{"error": str(exc)}]
        self._display_rows("Cypher result", [{k: str(v) for k, v in r.items()} for r in rows])

    def _display_rows(self, title: str, rows: list[dict[str, str]]) -> None:
        self._current_rows = rows
        table = self.query_one("#results-table", DataTable)
        table.clear(columns=True)
        if not rows:
            table.add_column("info")
            table.add_row("(no results)")
            return
        columns = list(rows[0].keys())
        for col in columns:
            table.add_column(col)
        for row in rows:
            table.add_row(*[str(row.get(c, "")) for c in columns])

    def action_export_csv(self) -> None:
        import csv
        import io

        rows = self._current_rows
        if not rows:
            return
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        path = Path("sysmodel_export.csv")
        path.write_text(buf.getvalue())
        self.notify(f"Exported {len(rows)} rows to {path}")

    def action_clear_results(self) -> None:
        self._display_rows("Cleared", [])

    def action_reload(self) -> None:
        try:
            module = _resolve_module(self._source)
            self._system = discover_system(module)
            self._validation_errors = self._system.validate_model()
            if self._graph is not None:
                try:
                    self._graph.load(self._system)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Graph reload failed: %s", exc)
            self.notify("System reloaded.")
        except SysmodelError as exc:
            self.notify(f"Reload failed: {exc}", severity="error")

    def action_toggle_help(self) -> None:
        self.notify(
            "Keybindings: q=quit, tab=next, ctrl+e=export CSV, "
            "ctrl+l=clear, ctrl+r=reload, ?=help"
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def cli_entry() -> None:
    """Entry point registered as the ``sysmodel`` console script.

    Usage::

        sysmodel systems.example
        sysmodel path/to/system_file.py
        sysmodel --help
    """
    parser = argparse.ArgumentParser(
        prog="sysmodel",
        description="Interactive query interface for sysmodel System definitions.",
        epilog="Examples:\n  sysmodel systems.example\n  sysmodel myproject/arch.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Python module path (systems.example) or file path (arch.py)",
    )
    args = parser.parse_args()

    if not args.target:
        parser.print_help()
        sys.exit(0)

    try:
        module = _resolve_module(args.target)
        system = discover_system(module)
    except SysmodelError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    app = SysmodelApp(system=system, source=args.target)
    app.run()
