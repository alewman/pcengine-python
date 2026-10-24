"""Import boundaries (Aubrey's rule): cpu_io, vdc and psg are modules that can move out into a
core or a repository of their own, so they may import only the shared constants and Protocols
and themselves; and nothing in the package reads module-level mutable state (a second VDC is a
second instance)."""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src" / "pcengine_python"

ALLOWED = {
    "cpu_io": {"pcengine_python.cpu_io", "pcengine_python.sockets"},
    "vdc": {"pcengine_python.vdc", "pcengine_python.machine"},
    "psg": {"pcengine_python.psg"},
}


def imports_of(path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module


@pytest.mark.parametrize("package", sorted(ALLOWED))
def test_package_imports_only_what_its_boundary_allows(package):
    files = sorted((SRC / package).glob("*.py"))
    assert files
    for path in files:
        for name in imports_of(path):
            if not name.startswith("pcengine_python"):
                continue
            assert any(name == ok or name.startswith(ok + ".") for ok in ALLOWED[package]), (
                f"{path.name} imports {name}"
            )


def test_nothing_in_the_chip_packages_imports_the_cpu_core():
    for path in SRC.rglob("*.py"):
        for name in imports_of(path):
            assert not name.startswith("huc6280"), f"{path} imports {name}"


def test_no_module_level_mutable_state_in_the_chip_packages():
    """Instances, not modules: no top-level list/dict/set/bytearray/array assignments."""
    for package in ALLOWED:
        for path in (SRC / package).glob("*.py"):
            tree = ast.parse(path.read_text())
            for node in tree.body:
                if isinstance(node, ast.Assign | ast.AnnAssign):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    if any(getattr(t, "id", "") == "__all__" for t in targets):
                        continue
                    value = node.value
                    mutable = isinstance(value, ast.List | ast.Dict | ast.Set) or (
                        isinstance(value, ast.Call)
                        and getattr(value.func, "id", "") in {"bytearray", "array", "list"}
                    )
                    assert not mutable, f"{path.name}:{node.lineno} has module-level state"
