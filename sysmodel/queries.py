"""Python query helpers for sysmodel System objects.

All public functions take a System as their first argument and return typed
results. Uses glom for collection projection and grouping.
"""

from __future__ import annotations

from typing import Any, cast

from glom import T, glom

from sysmodel.models import (
    Block,
    BlockType,
    DataClassification,
    Flow,
    RelType,
    Relationship,
    System,
)


# ---------------------------------------------------------------------------
# Block queries
# ---------------------------------------------------------------------------


def blocks_of_type(system: System, *types: BlockType | str) -> list[Block]:
    """Return all blocks matching one or more BlockType values.

    Args:
        system: The System to query.
        *types: One or more BlockType values or custom type strings.

    Returns:
        Blocks whose type matches any of the given types.
    """
    type_strs = {t.value if isinstance(t, BlockType) else t for t in types}
    return [
        b
        for b in system.blocks.values()
        if (b.type.value if isinstance(b.type, BlockType) else b.type) in type_strs
    ]


def blocks_with_tag(
    system: System,
    key: str,
    value: str | None = None,
) -> list[Block]:
    """Return blocks that have a tag key present, optionally filtered by value.

    Args:
        system: The System to query.
        key: The tag key to search for.
        value: If given, only blocks where tags[key] == value are returned.

    Returns:
        Matching Block objects.

    Examples::

        blocks_with_tag(s, "env")           # all blocks with any env tag
        blocks_with_tag(s, "env", "prod")   # only env=prod blocks
    """
    result = [b for b in system.blocks.values() if key in b.tags]
    if value is not None:
        result = [b for b in result if b.tags[key] == value]
    return result


def blocks_with_metadata(
    system: System,
    key: str,
    value: Any = None,
) -> list[Block]:
    """Return blocks that have a metadata key present, optionally filtered by value.

    Args:
        system: The System to query.
        key: The metadata key to search for.
        value: If given, only blocks where metadata[key] == value are returned.

    Returns:
        Matching Block objects.
    """
    result = [b for b in system.blocks.values() if key in b.metadata]
    if value is not None:
        result = [b for b in result if b.metadata[key] == value]
    return result


def children_of(
    system: System,
    parent_id: str,
    block_type: BlockType | str | None = None,
) -> list[Block]:
    """Return direct CONTAINS children of parent_id, optionally filtered by type.

    Args:
        system: The System to query.
        parent_id: The parent block's ID.
        block_type: Optional type filter.

    Returns:
        List of directly contained Block objects.
    """
    children = system.direct_children(parent_id)
    if block_type is not None:
        target_str = (
            block_type.value if isinstance(block_type, BlockType) else block_type
        )
        children = [
            b
            for b in children
            if (b.type.value if isinstance(b.type, BlockType) else b.type)
            == target_str
        ]
    return children


def descendants_of(
    system: System,
    root_id: str,
    block_type: BlockType | str | None = None,
) -> list[Block]:
    """Return all CONTAINS descendants of root_id, optionally filtered by type.

    Args:
        system: The System to query.
        root_id: The root block's ID.
        block_type: Optional type filter.

    Returns:
        Descendant Block objects in BFS order.
    """
    all_desc = system.descendants(root_id)
    if block_type is not None:
        target_str = (
            block_type.value if isinstance(block_type, BlockType) else block_type
        )
        all_desc = [
            b
            for b in all_desc
            if (b.type.value if isinstance(b.type, BlockType) else b.type)
            == target_str
        ]
    return all_desc


def software_on(system: System, host_id: str) -> list[Block]:
    """Return software blocks on a host, checking both CONTAINS and DEPLOYED_ON.

    Checks:
    - CONTAINS children of type SOFTWARE
    - Blocks with DEPLOYED_ON pointing at host_id

    Deduplicates results preserving order (CONTAINS first).

    Args:
        system: The System to query.
        host_id: The host block's ID.

    Returns:
        SOFTWARE Block objects on the host, deduplicated.
    """
    seen: set[str] = set()
    result: list[Block] = []

    for child in system.direct_children(host_id):
        type_str = child.type.value if isinstance(child.type, BlockType) else child.type
        if type_str == BlockType.SOFTWARE.value and child.id not in seen:
            seen.add(child.id)
            result.append(child)

    for rel in system.relationships_to(host_id, RelType.DEPLOYED_ON):
        sw = system.blocks.get(rel.source_id)
        if sw is not None and sw.id not in seen:
            seen.add(sw.id)
            result.append(sw)

    return result


def all_software_in(system: System, root_id: str) -> list[Block]:
    """Return all software reachable from root_id.

    Finds all blocks in the subtree via CONTAINS (including root), then calls
    software_on() for each. Deduplicates preserving first-seen order.

    Args:
        system: The System to query.
        root_id: The root block's ID.

    Returns:
        All SOFTWARE blocks reachable from root_id, deduplicated.
    """
    candidates = [system.blocks[root_id]] + system.descendants(root_id)
    seen: set[str] = set()
    result: list[Block] = []
    for host in candidates:
        for sw in software_on(system, host.id):
            if sw.id not in seen:
                seen.add(sw.id)
                result.append(sw)
    return result


def find_by_name(
    system: System,
    name: str,
    exact: bool = True,
) -> list[Block]:
    """Find blocks by name.

    Args:
        system: The System to query.
        name: The name to search for.
        exact: If True (default), matches the full name exactly.
            If False, performs a case-insensitive substring match.

    Returns:
        Matching Block objects.
    """
    if exact:
        return [b for b in system.blocks.values() if b.name == name]
    name_lower = name.lower()
    return [b for b in system.blocks.values() if name_lower in b.name.lower()]


def parent_of(system: System, block_id: str) -> Block | None:
    """Return the direct CONTAINS parent, or None if root-level.

    Args:
        system: The System to query.
        block_id: The block whose parent to find.

    Returns:
        The parent Block, or None.
    """
    parents = system.relationships_to(block_id, RelType.CONTAINS)
    if not parents:
        return None
    return system.blocks.get(parents[0].source_id)


def account_of(system: System, block_id: str) -> Block | None:
    """Walk ancestors to find the nearest ACCOUNT block, or None.

    Args:
        system: The System to query.
        block_id: The starting block's ID.

    Returns:
        The nearest ACCOUNT ancestor Block, or None.
    """
    for ancestor in system.ancestors(block_id):
        type_str = (
            ancestor.type.value
            if isinstance(ancestor.type, BlockType)
            else ancestor.type
        )
        if type_str == BlockType.ACCOUNT.value:
            return ancestor
    return None


# ---------------------------------------------------------------------------
# Relationship queries
# ---------------------------------------------------------------------------


def dependencies_of(system: System, block_id: str) -> list[Block]:
    """Return blocks that block_id depends on (outbound DEPENDS_ON).

    Args:
        system: The System to query.
        block_id: The block whose dependencies to find.

    Returns:
        Blocks that block_id directly depends on.
    """
    rels = system.relationships_from(block_id, RelType.DEPENDS_ON)
    return [system.blocks[r.target_id] for r in rels if r.target_id in system.blocks]


def dependents_of(system: System, block_id: str) -> list[Block]:
    """Return blocks that depend on block_id (inbound DEPENDS_ON).

    Args:
        system: The System to query.
        block_id: The block to find dependents of.

    Returns:
        Blocks that directly depend on block_id.
    """
    rels = system.relationships_to(block_id, RelType.DEPENDS_ON)
    return [system.blocks[r.source_id] for r in rels if r.source_id in system.blocks]


def relationships_between(
    system: System,
    block_a_id: str,
    block_b_id: str,
) -> list[Relationship]:
    """Return all relationships in either direction between two blocks.

    Args:
        system: The System to query.
        block_a_id: One block's ID.
        block_b_id: The other block's ID.

    Returns:
        All Relationship objects connecting the two blocks (either direction).
    """
    return [
        r
        for r in system.relationships
        if (r.source_id == block_a_id and r.target_id == block_b_id)
        or (r.source_id == block_b_id and r.target_id == block_a_id)
    ]


# ---------------------------------------------------------------------------
# Flow queries
# ---------------------------------------------------------------------------


def flows_of_classification(
    system: System,
    classification: DataClassification,
) -> list[Flow]:
    """Return all flows carrying data at the given classification level.

    Args:
        system: The System to query.
        classification: The DataClassification to filter by.

    Returns:
        Matching Flow objects.
    """
    return [
        f
        for f in system.flows.values()
        if f.classification == classification
    ]


def flows_crossing_boundary(
    system: System,
    boundary_id: str,
) -> list[Flow]:
    """Return flows where at least one hop is inside the boundary and one is outside.

    A block is "inside" if it is a CONTAINS descendant of boundary_id.

    Args:
        system: The System to query.
        boundary_id: The boundary block's ID.

    Returns:
        Flows that cross the boundary.
    """
    inside_ids = {b.id for b in system.descendants(boundary_id)}
    result: list[Flow] = []
    for flow in system.flows.values():
        hop_ids = flow.block_ids
        has_inside = any(h in inside_ids for h in hop_ids)
        has_outside = any(h not in inside_ids for h in hop_ids)
        if has_inside and has_outside:
            result.append(flow)
    return result


def lineage_for(
    system: System,
    block_id: str,
) -> dict[str, list[Flow]]:
    """Return flows where block_id appears, split into upstream and downstream.

    Upstream flows are those where block_id is not the first hop (something
    flows into it). Downstream flows are those where block_id is not the
    last hop (something flows out of it).

    Args:
        system: The System to query.
        block_id: The block to find lineage for.

    Returns:
        Dict with keys ``upstream`` and ``downstream``, each a list of Flow.
    """
    upstream: list[Flow] = []
    downstream: list[Flow] = []
    for flow in system.flows.values():
        hop_ids = flow.block_ids
        if block_id not in hop_ids:
            continue
        if hop_ids[0] != block_id:
            upstream.append(flow)
        if hop_ids[-1] != block_id:
            downstream.append(flow)
    return {"upstream": upstream, "downstream": downstream}


# ---------------------------------------------------------------------------
# Projection helpers (glom-based)
# ---------------------------------------------------------------------------


def summarize_blocks(blocks: list[Block]) -> list[dict[str, Any]]:
    """Project blocks to lightweight summary dicts.

    Args:
        blocks: List of Block objects to summarize.

    Returns:
        List of dicts with keys: id, name, type, tags.
    """
    return cast(
        list[dict[str, Any]],
        glom(
            blocks,
            [
                {
                    "id": T.id,
                    "name": T.name,
                    "type": (T.type, str),
                    "tags": T.tags,
                }
            ],
        ),
    )


def group_by_type(
    blocks: list[Block],
) -> dict[str, list[Block]]:
    """Group blocks by their type value string.

    Args:
        blocks: List of Block objects to group.

    Returns:
        Dict mapping type string to list of Blocks.
    """
    result: dict[str, list[Block]] = {}
    for block in blocks:
        key = block.type.value if isinstance(block.type, BlockType) else block.type
        result.setdefault(key, []).append(block)
    return result


def group_by_tag(
    blocks: list[Block],
    tag_key: str,
) -> dict[str, list[Block]]:
    """Group blocks by the value of a tag key.

    Blocks missing the key are grouped under ``__untagged__``.

    Args:
        blocks: List of Block objects to group.
        tag_key: The tag key to group by.

    Returns:
        Dict mapping tag value (or ``__untagged__``) to list of Blocks.
    """
    result: dict[str, list[Block]] = {}
    for block in blocks:
        key = block.tags.get(tag_key, "__untagged__")
        result.setdefault(key, []).append(block)
    return result
