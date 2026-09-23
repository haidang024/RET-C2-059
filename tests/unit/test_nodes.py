"""Unit tests for RET-C2-059 compliance nodes."""

from __future__ import annotations

from unittest.mock import patch

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.nodes.allergen_validator_node import AllergenComplianceValidatorNode
from src.nodes.compliance_score_report_node import ComplianceScoreReportNode
from src.nodes.input_parser_node import InputParserNode
from src.nodes.keihinhyoji_check_node import KeihinhyojiCheckNode
from src.nodes.label_format_checker_node import LabelFormatCheckerNode
from src.nodes.nutritional_validator_node import NutritionalLabelValidatorNode


_VE = TrustLevel.VERIFIED_EXTERNAL.value


def _base_state() -> dict:
    return {
        "caller_trust_level": _VE,
        "raw_label_text": "品名: クッキー\n原材料名: 小麦粉、卵、砂糖\n内容量: 100g\n賞味期限: 2027-01-01\n保存方法: 常温\n製造者: テスト食品\nアレルゲン: 小麦\nエネルギー: 100 タンパク質: 2 脂質: 4 炭水化物: 12 食塩相当量: 0.2",
        "label_image": None,
        "sku_metadata": {"sku_id": "SKU-001", "product_category": "food", "declared_allergens": ["小麦"]},
    }


def test_tc04_invocation_context_not_in_state() -> None:
    """State must never hold InvocationContext — it travels via config['configurable']."""
    from framework.schemas.agent_state import AgentState
    from src.schemas.state import State

    template_fields = set(State.__annotations__) - set(AgentState.__annotations__)
    prohibited = {"invocation_context", "context", "ctx"}
    violations = prohibited & template_fields
    assert not violations, f"InvocationContext-like fields found in State: {violations}"


def test_tc02_input_parser_length_limit() -> None:
    node = InputParserNode()
    state = {"caller_trust_level": _VE, "raw_label_text": "a" * 8193, "label_image": None, "sku_metadata": {}}
    result = node(state)
    assert result["status"] == AgentStatus.ERROR.value


def test_tc05_emit_trace_called() -> None:
    node = InputParserNode()
    with patch("src.nodes.input_parser_node.emit_trace_event") as mocked:
        node(_base_state())
    assert mocked.called


def test_tc08_required_trust_level() -> None:
    assert InputParserNode.required_trust_level == TrustLevel.VERIFIED_EXTERNAL
    assert AllergenComplianceValidatorNode.required_trust_level == TrustLevel.ANONYMOUS


def test_tc09_missing_allergen_fail() -> None:
    parser = InputParserNode()
    parsed = parser(_base_state())
    state = {
        "label_field_map": parsed.get("label_field_map", {}),
        "sku_metadata": _base_state()["sku_metadata"],
        "allergen_rules_path": "config/rules/allergens_28item.json",
    }
    result = AllergenComplianceValidatorNode()(state)
    assert any(f["allergen"] == "卵" and f["severity"] == "FAIL" for f in result["allergen_findings"])


def test_tc10_allergen_no_findings_when_declared() -> None:
    node = AllergenComplianceValidatorNode()
    state = {
        "label_field_map": {"ingredients": "卵 小麦", "allergen_declarations": ["卵", "小麦"]},
        "allergen_rules_path": "config/rules/allergens_28item.json",
    }
    result = node(state)
    assert result["allergen_findings"] == []


def test_tc11_allergen_non_suppressible_gate(monkeypatch) -> None:
    """S-3 gate rejects allergen findings suppressed in compliance_report."""
    node = AllergenComplianceValidatorNode()
    # execute() returns findings WITH a compliance_report that omits them → suppression detected
    monkeypatch.setattr(
        node,
        "execute",
        lambda state: {
            "allergen_findings": [{"allergen": "卵", "severity": "FAIL"}],
            "compliance_report": {"allergen_findings": []},  # empty → suppression
        },
    )
    state = {
        "label_field_map": {"ingredients": "卵", "allergen_declarations": []},
        "allergen_rules_path": "config/rules/allergens_28item.json",
    }
    result = node(state)
    assert result["status"] == AgentStatus.ERROR.value


def test_tc12_missing_required_field_fail() -> None:
    node = LabelFormatCheckerNode()
    result = node({"label_field_map": {"品名": "x"}})
    assert any(f["severity"] == "FAIL" for f in result["format_findings"])


def test_tc13_keihinhyoji_superiority_fail() -> None:
    node = KeihinhyojiCheckNode()
    result = node({"label_field_map": {"marketing_claims": "日本一", "raw_label_text": ""}})
    assert any(f["type"] == "superiority_claim" and f["severity"] == "FAIL" for f in result["keihinhyoji_findings"])


def test_tc14_keihinhyoji_ambiguous_warn() -> None:
    node = KeihinhyojiCheckNode()
    result = node({"label_field_map": {"marketing_claims": "たっぷり", "raw_label_text": ""}})
    assert any(f["type"] == "ambiguous_quantifier" and f["severity"] == "WARN" for f in result["keihinhyoji_findings"])


def test_tc15_nutrition_missing_fail() -> None:
    node = NutritionalLabelValidatorNode()
    result = node({"label_field_map": {"nutrition_facts": {"エネルギー": {"value": "100"}}}})
    assert any(f["severity"] == "FAIL" for f in result["nutrition_findings"])


def test_tc16_nutrition_arithmetic_warn() -> None:
    node = NutritionalLabelValidatorNode()
    result = node(
        {
            "calorie_tolerance_pct": 0.05,
            "label_field_map": {
                "nutrition_facts": {
                    "エネルギー": {"value": "200"},
                    "タンパク質": {"value": "1"},
                    "脂質": {"value": "1"},
                    "炭水化物": {"value": "1"},
                    "食塩相当量": {"value": "0.1"},
                }
            },
        }
    )
    assert any(f["severity"] == "WARN" for f in result["nutrition_findings"])


def test_tc17_report_fail_verdict() -> None:
    node = ComplianceScoreReportNode()
    result = node(
        {
            "caller_trust_level": _VE,
            "sku_metadata": {"sku_id": "SKU-001"},
            "allergen_findings": [{"severity": "FAIL"}],
            "format_findings": [],
            "keihinhyoji_findings": [],
            "nutrition_findings": [],
        }
    )
    assert result["sku_verdict"] == "FAIL"


def test_tc18_report_pass_verdict() -> None:
    node = ComplianceScoreReportNode()
    result = node(
        {
            "caller_trust_level": _VE,
            "sku_metadata": {"sku_id": "SKU-001"},
            "allergen_findings": [],
            "format_findings": [],
            "keihinhyoji_findings": [],
            "nutrition_findings": [],
        }
    )
    assert result["sku_verdict"] == "PASS"
