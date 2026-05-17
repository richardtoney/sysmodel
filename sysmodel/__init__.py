"""sysmodel — model and query software systems and cloud infrastructure as Python.

Public API::

    from sysmodel import System, Block, BlockType, RelType, Flow, FlowHop
    from sysmodel import queries
    from sysmodel.graph import KuzuGraph   # optional: pip install sysmodel[graph]
"""

from sysmodel import queries
from sysmodel._version import __version__
from sysmodel.exceptions import (
    BlockNotFoundError,
    DuplicateBlockError,
    FlowReferenceError,
    GraphLoadError,
    GraphNotAvailableError,
    InvalidBlockIdError,
    MetadataValidationError,
    StateMachineReferenceError,
    SysmodelError,
)
from sysmodel.models import (
    Block,
    BlockType,
    DataClassification,
    Flow,
    FlowHop,
    Relationship,
    RelType,
    State,
    StateMachine,
    System,
    Transition,
)
from sysmodel.registry import (
    METADATA_REGISTRY,
    MetadataSchema,
    get_schema,
    register_schema,
)

__all__ = [
    "__version__",
    # Exceptions
    "SysmodelError",
    "DuplicateBlockError",
    "BlockNotFoundError",
    "InvalidBlockIdError",
    "FlowReferenceError",
    "StateMachineReferenceError",
    "MetadataValidationError",
    "GraphNotAvailableError",
    "GraphLoadError",
    # Models
    "Block",
    "BlockType",
    "DataClassification",
    "Flow",
    "FlowHop",
    "Relationship",
    "RelType",
    "State",
    "StateMachine",
    "System",
    "Transition",
    # Registry
    "MetadataSchema",
    "METADATA_REGISTRY",
    "register_schema",
    "get_schema",
    # Queries module
    "queries",
]
