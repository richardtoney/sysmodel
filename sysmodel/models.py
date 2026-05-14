"""Core Pydantic models for sysmodel.

Imports only from sysmodel.exceptions and sysmodel.registry.
"""

from __future__ import annotations

import json
from collections import deque
from enum import Enum
from typing import Any

from pydantic import BaseModel, field_validator

from sysmodel.exceptions import (
    BlockNotFoundError,
    DuplicateBlockError,
    FlowReferenceError,
    InvalidBlockIdError,
    MetadataValidationError,
    StateMachineReferenceError,
)
from sysmodel.registry import validate_metadata


class BlockType(str, Enum):
    """Enumeration of built-in block types."""

    # Cloud infrastructure
    ACCOUNT = "account"
    VPC = "vpc"
    SUBNET = "subnet"
    EC2 = "ec2"
    RDS = "rds"
    S3 = "s3"
    LAMBDA = "lambda"
    LOAD_BALANCER = "load_balancer"
    # Software and services
    SERVER = "server"
    SERVICE = "service"
    SOFTWARE = "software"
    DATABASE = "database"
    # Logical / organizational
    SYSTEM = "system"
    CLUSTER = "cluster"
    BOUNDARY = "boundary"
    ACTOR = "actor"
    DATASET = "dataset"
    JOB = "job"


class RelType(str, Enum):
    """Enumeration of built-in relationship types."""

    CONTAINS = "contains"
    DEPENDS_ON = "depends_on"
    CONNECTS_TO = "connects_to"
    DEPLOYED_ON = "deployed_on"
    OWNS = "owns"
    AUTHENTICATES_VIA = "authenticates_via"
    MANAGED_BY = "managed_by"


class DataClassification(str, Enum):
    """Data sensitivity classification levels."""

    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    PHI = "phi"
    PII = "pii"
    CONTROLLED = "controlled"


class Block(BaseModel):
    """A typed, labeled node in the system graph.

    Attributes:
        id: Unique identifier within a System. No spaces allowed.
            Use hyphens: "ec2-web-01", "sw-nginx".
        name: Human-readable display name.
        type: BlockType enum value OR a custom string type registered
            via sysmodel.registry.register_schema().
        description: Free-text description of the block's purpose.
        tags: String key/value pairs for filtering and grouping.
            Convention: env, tier, team, role, region, zone.
        metadata: Type-specific supplemental data. Keys are validated
            against METADATA_REGISTRY when validate_model() runs.
    """

    id: str
    name: str
    type: BlockType | str
    description: str = ""
    tags: dict[str, str] = {}
    metadata: dict[str, Any] = {}

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Reject empty ids and ids containing spaces."""
        if not v:
            raise InvalidBlockIdError("Block id must not be empty.")
        if " " in v:
            raise InvalidBlockIdError(
                f"Block id must not contain spaces: '{v}'"
            )
        return v


class Relationship(BaseModel):
    """A directed, typed edge between two Blocks.

    ``source --[type]--> target``

    Attributes:
        source_id: ID of the originating Block.
        target_id: ID of the destination Block.
        type: RelType enum value OR a custom string relationship type.
        metadata: Edge-level attributes (protocol, port, bandwidth, etc.)
    """

    source_id: str
    target_id: str
    type: RelType | str
    metadata: dict[str, Any] = {}


class State(BaseModel):
    """A named state that a Block can occupy.

    Attributes:
        id: Unique within the StateMachine.
        name: Display name.
        description: What this state means for the block.
        invariants: Human-readable conditions that must hold while in
            this state. Not evaluated programmatically.
    """

    id: str
    name: str
    description: str = ""
    invariants: list[str] = []


class Transition(BaseModel):
    """A directed edge between two States within a StateMachine.

    Attributes:
        from_state_id: Source state id.
        to_state_id: Destination state id.
        trigger: Event or condition that fires this transition.
        guard: Optional condition that must be true (human-readable).
        action: What happens when this transition fires (human-readable).
    """

    from_state_id: str
    to_state_id: str
    trigger: str
    guard: str = ""
    action: str = ""


class StateMachine(BaseModel):
    """A set of States and Transitions documenting the lifecycle of a Block.

    Attributes:
        block_id: ID of the Block this state machine belongs to.
        states: Dict of state_id to State.
        transitions: List of Transition edges.
        initial_state: State id of the starting state.
    """

    block_id: str
    states: dict[str, State] = {}
    transitions: list[Transition] = []
    initial_state: str = ""


class FlowHop(BaseModel):
    """One step in a Flow path.

    Attributes:
        block_id: ID of the Block at this hop.
        port_id: Optional identifier for the interface used.
        notes: Human-readable note about this hop.
    """

    block_id: str
    port_id: str = ""
    notes: str = ""


class Flow(BaseModel):
    """An ordered sequence of hops representing a data or control path.

    Example::

        Flow from client -> LB -> web tier -> app tier -> DB

    Attributes:
        id: Unique within the System.
        name: Display name.
        description: Purpose of this flow.
        hops: Ordered list of FlowHop (block_id + optional notes).
        classification: Data sensitivity level of data moving through flow.
        protocol: Primary protocol (HTTPS, gRPC, JDBC, S3, etc.)
        metadata: Additional flow-level attributes.
    """

    id: str
    name: str
    description: str = ""
    hops: list[FlowHop]
    classification: DataClassification = DataClassification.INTERNAL
    protocol: str = ""
    metadata: dict[str, Any] = {}

    @property
    def block_ids(self) -> list[str]:
        """Ordered list of block IDs in this flow."""
        return [h.block_id for h in self.hops]


def _rel_type_str(rel_type: RelType | str) -> str:
    """Normalize a RelType enum or string to its string value."""
    return rel_type.value if isinstance(rel_type, RelType) else rel_type


class System(BaseModel):
    """The root model and registry for a system or collection of systems.

    All cross-references between objects use string IDs resolved here.
    System files instantiate one System and register all their blocks,
    relationships, flows, and state machines into it.

    Usage::

        s = System(name="My System")
        db = s.add(Block(id="db-01", name="postgres", type=BlockType.DATABASE,
                         metadata={"engine": "postgres", "version": "16"}))
        app = s.add(Block(id="app-01", name="api", type=BlockType.SERVICE))
        s.depends_on("app-01", "db-01", protocol="jdbc")
        errors = s.validate_model()
    """

    name: str
    description: str = ""
    blocks: dict[str, Block] = {}
    relationships: list[Relationship] = []
    flows: dict[str, Flow] = {}
    state_machines: dict[str, StateMachine] = {}

    # --- Block management ---

    def add(self, block: Block) -> Block:
        """Register a block. Returns the block for inline assignment.

        Args:
            block: The Block instance to register.

        Returns:
            The same block, enabling ``b = s.add(Block(...))``. 

        Raises:
            DuplicateBlockError: If the block's id is already registered.
        """
        if block.id in self.blocks:
            raise DuplicateBlockError(block.id)
        self.blocks[block.id] = block
        return block

    def resolve(self, block_id: str) -> Block:
        """Resolve a block ID to its Block instance.

        Args:
            block_id: The ID to look up.

        Returns:
            The Block with that ID.

        Raises:
            BlockNotFoundError: If the ID is not registered.
        """
        try:
            return self.blocks[block_id]
        except KeyError:
            raise BlockNotFoundError(block_id)

    def get(self, block_id: str) -> Block | None:
        """Resolve a block ID, returning None if not found.

        Args:
            block_id: The ID to look up.

        Returns:
            The Block, or None.
        """
        return self.blocks.get(block_id)

    # --- Relationship management ---

    def relate(
        self,
        source_id: str,
        rel_type: RelType | str,
        target_id: str,
        **metadata: Any,
    ) -> Relationship:
        """Add a typed relationship between two blocks.

        Args:
            source_id: ID of the source block.
            rel_type: The relationship type.
            target_id: ID of the target block.
            **metadata: Key/value edge attributes (protocol, port, etc.).

        Returns:
            The created Relationship.

        Raises:
            BlockNotFoundError: If either source_id or target_id is not registered.
        """
        self.resolve(source_id)
        self.resolve(target_id)
        rel = Relationship(
            source_id=source_id,
            target_id=target_id,
            type=rel_type,
            metadata=dict(metadata),
        )
        self.relationships.append(rel)
        return rel

    def contains(self, parent_id: str, child_id: str, **metadata: Any) -> Relationship:
        """Add a CONTAINS relationship. Use for structural/ownership hierarchy.

        Args:
            parent_id: ID of the containing block.
            child_id: ID of the contained block.
            **metadata: Optional edge attributes.

        Returns:
            The created Relationship.
        """
        return self.relate(parent_id, RelType.CONTAINS, child_id, **metadata)

    def deployed_on(
        self, software_id: str, host_id: str, **metadata: Any
    ) -> Relationship:
        """Add a DEPLOYED_ON relationship. Use for software placement on a host.

        Args:
            software_id: ID of the software block.
            host_id: ID of the host block.
            **metadata: Optional edge attributes.

        Returns:
            The created Relationship.
        """
        return self.relate(software_id, RelType.DEPLOYED_ON, host_id, **metadata)

    def depends_on(
        self, source_id: str, target_id: str, **metadata: Any
    ) -> Relationship:
        """Add a DEPENDS_ON relationship. Use for runtime dependencies.

        Args:
            source_id: The dependent block.
            target_id: The block being depended upon.
            **metadata: Optional edge attributes (protocol, port, etc.).

        Returns:
            The created Relationship.
        """
        return self.relate(source_id, RelType.DEPENDS_ON, target_id, **metadata)

    def connects_to(
        self, source_id: str, target_id: str, **metadata: Any
    ) -> Relationship:
        """Add a CONNECTS_TO relationship. Use for network/API connections.

        Args:
            source_id: The initiating block.
            target_id: The target block.
            **metadata: Optional edge attributes.

        Returns:
            The created Relationship.
        """
        return self.relate(source_id, RelType.CONNECTS_TO, target_id, **metadata)

    # --- Flow and StateMachine registration ---

    def add_flow(self, flow: Flow) -> Flow:
        """Register a flow after validating all hop block IDs exist.

        Args:
            flow: The Flow to register.

        Returns:
            The same flow.

        Raises:
            FlowReferenceError: If any hop references an unknown block.
        """
        for hop in flow.hops:
            if hop.block_id not in self.blocks:
                raise FlowReferenceError(flow.id, hop.block_id)
        self.flows[flow.id] = flow
        return flow

    def add_state_machine(self, sm: StateMachine) -> StateMachine:
        """Register a state machine after validating its block exists.

        Args:
            sm: The StateMachine to register.

        Returns:
            The same state machine.

        Raises:
            StateMachineReferenceError: If block_id is not registered.
        """
        if sm.block_id not in self.blocks:
            raise StateMachineReferenceError(sm.block_id)
        self.state_machines[sm.block_id] = sm
        return sm

    # --- Traversal ---

    def relationships_from(
        self,
        block_id: str,
        rel_type: RelType | str | None = None,
    ) -> list[Relationship]:
        """All outbound relationships from block_id, optionally filtered by type.

        Args:
            block_id: The source block ID.
            rel_type: Optional filter. If given, only relationships of this
                type are returned.

        Returns:
            List of matching Relationship objects.
        """
        rels = [r for r in self.relationships if r.source_id == block_id]
        if rel_type is not None:
            target_str = _rel_type_str(rel_type)
            rels = [r for r in rels if _rel_type_str(r.type) == target_str]
        return rels

    def relationships_to(
        self,
        block_id: str,
        rel_type: RelType | str | None = None,
    ) -> list[Relationship]:
        """All inbound relationships to block_id, optionally filtered by type.

        Args:
            block_id: The target block ID.
            rel_type: Optional filter.

        Returns:
            List of matching Relationship objects.
        """
        rels = [r for r in self.relationships if r.target_id == block_id]
        if rel_type is not None:
            target_str = _rel_type_str(rel_type)
            rels = [r for r in rels if _rel_type_str(r.type) == target_str]
        return rels

    def direct_children(self, parent_id: str) -> list[Block]:
        """Blocks directly contained by parent_id (CONTAINS edges only).

        Args:
            parent_id: The parent block ID.

        Returns:
            List of directly contained Block objects.
        """
        rels = self.relationships_from(parent_id, RelType.CONTAINS)
        return [self.blocks[r.target_id] for r in rels if r.target_id in self.blocks]

    def descendants(self, root_id: str) -> list[Block]:
        """All blocks reachable from root_id via CONTAINS edges. BFS order.

        Handles cycles without infinite loops.

        Args:
            root_id: The root block ID to start traversal from.

        Returns:
            List of descendant Block objects in BFS order, not including root.
        """
        visited: set[str] = {root_id}
        queue: deque[str] = deque([root_id])
        result: list[Block] = []
        while queue:
            current_id = queue.popleft()
            for rel in self.relationships_from(current_id, RelType.CONTAINS):
                child_id = rel.target_id
                if child_id not in visited:
                    visited.add(child_id)
                    if child_id in self.blocks:
                        result.append(self.blocks[child_id])
                    queue.append(child_id)
        return result

    def ancestors(self, block_id: str) -> list[Block]:
        """Walk up the CONTAINS chain from block_id to the root.

        Args:
            block_id: The block to start from.

        Returns:
            List of ancestor Blocks from immediate parent to root.
        """
        result: list[Block] = []
        visited: set[str] = {block_id}
        current_id = block_id
        while True:
            parents = self.relationships_to(current_id, RelType.CONTAINS)
            if not parents:
                break
            parent_id = parents[0].source_id
            if parent_id in visited:
                break
            visited.add(parent_id)
            if parent_id in self.blocks:
                result.append(self.blocks[parent_id])
            current_id = parent_id
        return result

    def flows_through(self, block_id: str) -> list[Flow]:
        """All flows that include block_id as a hop.

        Args:
            block_id: The block ID to search for.

        Returns:
            List of flows that pass through the block.
        """
        return [f for f in self.flows.values() if block_id in f.block_ids]

    # --- Validation ---

    def validate_model(self, strict: bool = False) -> list[str]:
        """Validate all block metadata against METADATA_REGISTRY.

        Args:
            strict: If True, raises MetadataValidationError on the first
                error found. If False (default), collects and returns all errors.

        Returns:
            List of human-readable error strings. Empty means fully valid.

        Raises:
            MetadataValidationError: If strict=True and any error is found.
        """
        all_errors: list[str] = []
        for block_id, block in self.blocks.items():
            block_type_str = (
                block.type.value if isinstance(block.type, Enum) else block.type
            )
            errors = validate_metadata(block_id, block_type_str, block.metadata)
            if strict and errors:
                raise MetadataValidationError(errors[0])
            all_errors.extend(errors)
        return all_errors

    # --- Serialization ---

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entire system to a plain Python dict.

        All Pydantic models are converted to dicts. Enums become strings.
        The result is JSON-serializable via json.dumps().

        Returns:
            A dict representation of the full system.
        """
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "System":
        """Reconstruct a System from a dict produced by to_dict().

        Args:
            data: A dict as returned by to_dict().

        Returns:
            A fully populated System instance.
        """
        return cls.model_validate(data)

    def to_json(self, indent: int = 2) -> str:
        """Serialize to a JSON string.

        Args:
            indent: JSON indentation level (default 2).

        Returns:
            JSON string representation.
        """
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "System":
        """Reconstruct a System from a JSON string.

        Args:
            json_str: A JSON string as returned by to_json().

        Returns:
            A fully populated System instance.
        """
        return cls.model_validate_json(json_str)
