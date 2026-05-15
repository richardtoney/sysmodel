"""Kuzu graph database integration for sysmodel.

This module is an optional dependency. If kuzu is not installed,
every public class raises GraphNotAvailableError.

Install the graph extra to enable::

    pip install sysmodel[graph]
"""

from __future__ import annotations

import contextlib
import json
import logging
import shutil
import tempfile
from enum import Enum
from typing import TYPE_CHECKING, Any

from sysmodel.exceptions import GraphLoadError, GraphNotAvailableError

if TYPE_CHECKING:
    from sysmodel.models import System

try:
    import kuzu

    _KUZU_AVAILABLE = True
except ImportError:
    _KUZU_AVAILABLE = False

logger = logging.getLogger(__name__)

# DDL executed in order — relationship tables must be dropped before node tables.
_DROP_STMTS = [
    "DROP TABLE IF EXISTS HasHop",
    "DROP TABLE IF EXISTS Connected",
    "DROP TABLE IF EXISTS Flow",
    "DROP TABLE IF EXISTS Block",
]

_CREATE_STMTS = [
    (
        "CREATE NODE TABLE Block("
        "id STRING, name STRING, type STRING, "
        "description STRING, tags STRING, metadata STRING, "
        "PRIMARY KEY (id))"
    ),
    (
        "CREATE NODE TABLE Flow("
        "id STRING, name STRING, description STRING, "
        "classification STRING, protocol STRING, "
        "PRIMARY KEY (id))"
    ),
    "CREATE REL TABLE Connected(FROM Block TO Block, rel_type STRING, metadata STRING)",
    "CREATE REL TABLE HasHop(FROM Flow TO Block, position INT64, notes STRING)",
]


class KuzuGraph:
    """Kuzu-backed graph query interface for a System.

    Requires ``sysmodel[graph]`` to be installed.

    Usage::

        from sysmodel.graph import KuzuGraph
        g = KuzuGraph()          # in-memory (uses temp directory)
        g = KuzuGraph("/tmp/db") # file-backed (persists across sessions)
        g.load(system)
        results = g.query(
            "MATCH (a:Block)-[r:Connected]->(b:Block) "
            "WHERE r.rel_type = 'depends_on' "
            "RETURN a.name, b.name"
        )
        g.close()

    Context manager usage::

        with KuzuGraph() as g:
            g.load(system)
            g.query(...)

    Verified Cypher patterns::

        -- All descendants (variable-length path, explicit hop bounds)
        MATCH (root:Block {id: 'subnet-lan'})-[:Connected*1..20]->(b:Block)
        WHERE b.type <> 'account'
        RETURN b.name, b.type

        -- Software on a host (DEPLOYED_ON)
        MATCH (sw:Block)-[:Connected {rel_type: 'deployed_on'}]->(host:Block {id: 'srv-01'})
        RETURN sw.name, sw.metadata

        -- Multi-hop transitive dependency
        MATCH (a:Block {id: 'svc-a'})-[:Connected*1..20]->(dep:Block)
        RETURN dep.name, dep.type

        -- Leaf nodes: blocks with no outbound DEPENDS_ON
        MATCH (b:Block)
        WHERE NOT (b)-[:Connected {rel_type: 'depends_on'}]->(:Block)
        RETURN b.name, b.type

        -- Full hop-by-hop flow path
        MATCH (f:Flow {id: 'flow-01'})-[h:HasHop]->(b:Block)
        RETURN b.name, b.type, h.notes
        ORDER BY h.position

        -- Blocks appearing in more than one flow (shared infrastructure)
        MATCH (f:Flow)-[:HasHop]->(b:Block)
        WITH b, COUNT(DISTINCT f) AS flow_count
        WHERE flow_count > 1
        RETURN b.name, b.type, flow_count
        ORDER BY flow_count DESC
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        """Create a KuzuGraph instance.

        Args:
            db_path: Path to a Kuzu database directory, or ":memory:" for
                an in-process temporary database (default).

        Raises:
            GraphNotAvailableError: If kuzu is not installed.
            GraphLoadError: If the database cannot be opened.
        """
        if not _KUZU_AVAILABLE:
            raise GraphNotAvailableError()

        self._temp_dir: str | None = None
        if db_path == ":memory:":
            # kuzu>=0.11 rejects an existing directory; use a non-existent subdirectory
            self._temp_dir = tempfile.mkdtemp(prefix="sysmodel_kuzu_")
            actual_path = self._temp_dir + "/db"
        else:
            actual_path = db_path

        try:
            self._db = kuzu.Database(actual_path)
            self._conn = kuzu.Connection(self._db)
        except Exception as exc:
            self._cleanup_temp()
            raise GraphLoadError(str(exc)) from exc

    def _cleanup_temp(self) -> None:
        """Remove the temp directory if one was created."""
        if self._temp_dir is not None:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None

    def _run(self, query: str, params: dict[str, Any] | None = None) -> Any:
        """Execute a Kuzu statement, wrapping exceptions as GraphLoadError."""
        try:
            if params:
                return self._conn.execute(query, params)
            return self._conn.execute(query)
        except Exception as exc:
            logger.error("Kuzu operation failed: %s", exc)
            raise GraphLoadError(str(exc)) from exc

    def _setup_schema(self) -> None:
        """Drop all tables and recreate the schema."""
        for stmt in _DROP_STMTS + _CREATE_STMTS:
            self._run(stmt)

    def load(self, system: System) -> None:
        """Export a System into Kuzu.

        Idempotent — clears all data before loading so calling load() twice
        with the same system is safe.

        Load order:

        1. Drop and recreate all tables (idempotent reset)
        2. Insert Block nodes
        3. Insert Connected edges (from system.relationships)
        4. Insert Flow nodes
        5. Insert HasHop edges (from flow.hops with position index)
        6. Assert: kuzu block count == len(system.blocks)

        Args:
            system: The System to load.

        Raises:
            GraphLoadError: If any Kuzu operation fails.
        """
        self._setup_schema()

        # 2. Insert Block nodes
        for block in system.blocks.values():
            type_str = (
                block.type.value if isinstance(block.type, Enum) else block.type
            )
            self._run(
                "CREATE (:Block {id: $id, name: $name, type: $type, "
                "description: $blk_desc, tags: $tags, metadata: $meta})",
                {
                    "id": block.id,
                    "name": block.name,
                    "type": type_str,
                    "blk_desc": block.description,
                    "tags": json.dumps(block.tags),
                    "meta": json.dumps(block.metadata),
                },
            )

        # 3. Insert Connected edges
        for rel in system.relationships:
            rel_type_str = (
                rel.type.value if isinstance(rel.type, Enum) else rel.type
            )
            self._run(
                "MATCH (src:Block {id: $src}), (tgt:Block {id: $tgt}) "
                "CREATE (src)-[:Connected {rel_type: $rel_type, metadata: $meta}]->(tgt)",
                {
                    "src": rel.source_id,
                    "tgt": rel.target_id,
                    "rel_type": rel_type_str,
                    "meta": json.dumps(rel.metadata),
                },
            )

        # 4. Insert Flow nodes
        for flow in system.flows.values():
            classification_str = (
                flow.classification.value
                if isinstance(flow.classification, Enum)
                else flow.classification
            )
            self._run(
                "CREATE (:Flow {id: $id, name: $name, description: $flow_desc, "
                "classification: $cls, protocol: $proto})",
                {
                    "id": flow.id,
                    "name": flow.name,
                    "flow_desc": flow.description,
                    "cls": classification_str,
                    "proto": flow.protocol,
                },
            )

        # 5. Insert HasHop edges
        for flow in system.flows.values():
            for position, hop in enumerate(flow.hops):
                self._run(
                    "MATCH (f:Flow {id: $fid}), (b:Block {id: $bid}) "
                    "CREATE (f)-[:HasHop {position: $pos, notes: $notes}]->(b)",
                    {
                        "fid": flow.id,
                        "bid": hop.block_id,
                        "pos": position,
                        "notes": hop.notes,
                    },
                )

        # 6. Assert count using the public query() method (handles API compat)
        count_result = self.query("MATCH (b:Block) RETURN COUNT(b) AS cnt")
        loaded_count = int(count_result[0]["cnt"]) if count_result else 0
        expected_count = len(system.blocks)
        if loaded_count != expected_count:
            raise GraphLoadError(
                f"Block count mismatch after load: "
                f"expected {expected_count}, got {loaded_count}"
            )

    def query(self, cypher: str) -> list[dict[str, Any]]:
        """Execute a Cypher query against the loaded graph.

        Tags and metadata fields are automatically deserialized from JSON
        strings back to dicts in the result.

        Args:
            cypher: A Cypher query string.

        Returns:
            List of result row dicts. Empty list if no results.

        Raises:
            GraphLoadError: If the query fails.
            GraphNotAvailableError: If kuzu is not installed.
        """
        if not _KUZU_AVAILABLE:
            raise GraphNotAvailableError()

        result = self._run(cypher)

        # Handle kuzu>=0.5 (column_names property) and kuzu 0.4.x (get_column_names method)
        columns: list[str] = (
            result.column_names
            if hasattr(result, "column_names")
            else result.get_column_names()
        )

        rows: list[dict[str, Any]] = []
        while result.has_next():
            raw_row = result.get_next()
            row: dict[str, Any] = {}
            for col, val in zip(columns, raw_row, strict=False):
                if isinstance(val, str) and col in ("tags", "metadata"):
                    with contextlib.suppress(json.JSONDecodeError, ValueError):
                        val = json.loads(val)
                row[col] = val
            rows.append(row)
        return rows

    def close(self) -> None:
        """Close the Kuzu connection and release resources."""
        with contextlib.suppress(AttributeError):
            del self._conn
        with contextlib.suppress(AttributeError):
            del self._db
        self._cleanup_temp()

    def __enter__(self) -> KuzuGraph:
        """Support use as a context manager."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Close the graph on context manager exit."""
        self.close()
