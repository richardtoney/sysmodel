"""Tests for sysmodel.exceptions."""
import pytest

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


def test_duplicate_block_error_message() -> None:
    err = DuplicateBlockError("db-01")
    assert "db-01" in str(err)
    assert err.block_id == "db-01"


def test_block_not_found_error_message() -> None:
    err = BlockNotFoundError("missing-block")
    assert "missing-block" in str(err)
    assert "Add it before referencing it" in str(err)
    assert err.block_id == "missing-block"


def test_flow_reference_error_message() -> None:
    err = FlowReferenceError("flow-01", "ghost-block")
    assert "flow-01" in str(err)
    assert "ghost-block" in str(err)
    assert err.flow_id == "flow-01"
    assert err.block_id == "ghost-block"


def test_graph_not_available_error_message_contains_install_hint() -> None:
    err = GraphNotAvailableError()
    assert "pip install sysmodel[graph]" in str(err)


def test_state_machine_reference_error_message() -> None:
    err = StateMachineReferenceError("srv-01")
    assert "srv-01" in str(err)
    assert err.block_id == "srv-01"


def test_all_exceptions_inherit_from_sysmodel_error() -> None:
    exceptions = [
        DuplicateBlockError("x"),
        BlockNotFoundError("x"),
        InvalidBlockIdError("bad id"),
        FlowReferenceError("f", "b"),
        StateMachineReferenceError("x"),
        MetadataValidationError("some error"),
        GraphNotAvailableError(),
        GraphLoadError("load failed"),
    ]
    for exc in exceptions:
        assert isinstance(exc, SysmodelError), f"{type(exc).__name__} does not inherit SysmodelError"
        assert isinstance(exc, Exception)
