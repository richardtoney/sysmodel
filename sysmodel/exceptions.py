"""Exception hierarchy for sysmodel. All public exceptions inherit from SysmodelError."""


class SysmodelError(Exception):
    """Base class for all sysmodel exceptions."""


class DuplicateBlockError(SysmodelError):
    """Raised when a block ID is registered more than once."""

    def __init__(self, block_id: str) -> None:
        super().__init__(f"Block id '{block_id}' already exists in this system.")
        self.block_id = block_id


class BlockNotFoundError(SysmodelError):
    """Raised when a block ID cannot be resolved."""

    def __init__(self, block_id: str) -> None:
        super().__init__(
            f"Block '{block_id}' not found. Add it before referencing it."
        )
        self.block_id = block_id


class InvalidBlockIdError(SysmodelError):
    """Raised when a block ID contains illegal characters or is empty."""


class FlowReferenceError(SysmodelError):
    """Raised when a Flow hop references a block ID not in the system."""

    def __init__(self, flow_id: str, block_id: str) -> None:
        super().__init__(
            f"Flow '{flow_id}' references unknown block '{block_id}'."
        )
        self.flow_id = flow_id
        self.block_id = block_id


class StateMachineReferenceError(SysmodelError):
    """Raised when a StateMachine references an unknown block."""

    def __init__(self, block_id: str) -> None:
        super().__init__(
            f"StateMachine references unknown block '{block_id}'. "
            "Add the block before attaching a state machine."
        )
        self.block_id = block_id


class MetadataValidationError(SysmodelError):
    """Raised by validate_model(strict=True) on the first metadata error found."""


class GraphNotAvailableError(SysmodelError):
    """Raised when Kuzu is accessed but not installed."""

    def __init__(self) -> None:
        super().__init__(
            "Graph queries require kuzu. Install it with: "
            "pip install sysmodel[graph]"
        )


class GraphLoadError(SysmodelError):
    """Raised when loading a System into Kuzu fails."""
