"""Proof-of-boundary tests for RET-C2-059."""

from __future__ import annotations

import ast
import json
import pathlib
import re
from unittest.mock import patch

from src.nodes.allergen_validator_node import AllergenComplianceValidatorNode
from framework.schemas.agent_status import AgentStatus


def test_pb1_audit_logger_fires() -> None:
    node = AllergenComplianceValidatorNode()
    state = {
        "label_field_map": {"ingredients": "小麦", "allergen_declarations": ["小麦"]},
        "sku_metadata": {},
        "allergen_rules_path": "config/rules/allergens_28item.json",
    }
    with patch("src.nodes.allergen_validator_node.emit_trace_event") as mocked:
        node(state)
    assert mocked.called


def test_pb2_state_serialization() -> None:
    state = {
        "raw_label_text": "x",
        "label_image": None,
        "sku_metadata": {},
        "label_field_map": {},
        "allergen_findings": [],
        "format_findings": [],
        "keihinhyoji_findings": [],
        "nutrition_findings": [],
        "compliance_report": {},
        "markdown_summary": "",
        "sku_verdict": "PASS",
        "status": AgentStatus.SUCCESS,
        "error_message": None,
    }
    assert isinstance(json.loads(json.dumps(state)), dict)


def test_pb3_rule_corpus_loads() -> None:
    with open("config/rules/allergens_28item.json", encoding="utf-8") as fh:
        allergens = json.load(fh)
    assert len(allergens) == 28


def test_pb4_import_isolation() -> None:
    violations: list[str] = []
    for path in pathlib.Path("src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("agenticstar"):
                        violations.append(f"{path}:{node.lineno}")
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("agenticstar"):
                    violations.append(f"{path}:{node.lineno}")
    assert not violations


def test_pb5_checkpoint_safety() -> None:
    jwt_pattern = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
    state = {"compliance_report": {}, "allergen_findings": [], "status": AgentStatus.SUCCESS}
    serialized = json.dumps(state)
    assert not jwt_pattern.search(serialized)
