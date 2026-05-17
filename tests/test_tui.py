"""Smoke tests for sysmodel.tui — CLI parsing and system discovery only.

No Textual app is instantiated. Tests cover the unit-testable helper functions.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from sysmodel.exceptions import SysmodelError
from sysmodel.models import Block, BlockType, System
from sysmodel.tui import (
    discover_system,
    load_module_from_dotted_name,
    load_module_from_path,
)


def _make_module_with_system(name: str = "_test_mod") -> types.ModuleType:
    """Build a synthetic module that contains one System instance."""
    mod = types.ModuleType(name)
    s = System(name="Test System")
    s.add(Block(id="svc-01", name="Service", type=BlockType.SERVICE))
    mod.system = s  # type: ignore[attr-defined]
    return mod


def test_discover_system_finds_system_instance() -> None:
    mod = _make_module_with_system()
    found = discover_system(mod)
    assert isinstance(found, System)
    assert found.name == "Test System"


def test_discover_system_no_system_raises() -> None:
    mod = types.ModuleType("_empty_mod")
    mod.x = 42  # type: ignore[attr-defined]
    with pytest.raises(SysmodelError, match="No System instance"):
        discover_system(mod)


def test_discover_system_multiple_systems_raises() -> None:
    mod = types.ModuleType("_multi_mod")
    mod.s1 = System(name="S1")  # type: ignore[attr-defined]
    mod.s2 = System(name="S2")  # type: ignore[attr-defined]
    with pytest.raises(SysmodelError, match="Multiple System"):
        discover_system(mod)


def test_load_module_by_path(tmp_path: Path) -> None:
    script = tmp_path / "mysystem.py"
    script.write_text(
        "from sysmodel.models import System\n"
        "system = System(name='Path Loaded')\n"
    )
    mod = load_module_from_path(str(script))
    assert hasattr(mod, "system")
    assert isinstance(mod.system, System)
    assert mod.system.name == "Path Loaded"


def test_load_module_by_path_missing_file() -> None:
    with pytest.raises(SysmodelError):
        load_module_from_path("/no/such/file.py")


def test_load_module_by_dotted_name() -> None:
    mod = load_module_from_dotted_name("systems.example")
    assert mod.__name__ == "systems.example"
    system = discover_system(mod)
    assert isinstance(system, System)


def test_load_module_by_dotted_name_missing() -> None:
    with pytest.raises(SysmodelError, match="Cannot import"):
        load_module_from_dotted_name("nonexistent.module.xyz")


def test_cli_entry_help_exits_cleanly() -> None:
    from sysmodel.tui import cli_entry

    old_argv = sys.argv
    sys.argv = ["sysmodel", "--help"]
    try:
        with pytest.raises(SystemExit) as exc_info:
            cli_entry()
        assert exc_info.value.code == 0
    finally:
        sys.argv = old_argv
