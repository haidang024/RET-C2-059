"""PB-4: template source must not import prohibited platform layers."""

from __future__ import annotations

import ast
from pathlib import Path


SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
PROHIBITED_PREFIXES = ("agenticstar", "agenticstar_agentcore", "mediator")


def _is_prohibited(module_name: str) -> bool:
    return any(module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in PROHIBITED_PREFIXES)


def _scan_file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_prohibited(alias.name):
                    violations.append(f"{path}:{node.lineno} import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if module_name and _is_prohibited(module_name):
                violations.append(f"{path}:{node.lineno} from {module_name} import ...")
    return violations


def test_no_prohibited_imports_in_src() -> None:
    violations: list[str] = []
    for file_path in SRC_ROOT.rglob("*.py"):
        if file_path.is_file():
            violations.extend(_scan_file(file_path))
    assert sorted(violations) == []
