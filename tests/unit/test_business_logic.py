"""Business-logic tests for RET-C2-059 end-to-end flow."""

from __future__ import annotations

import json

from framework.schemas.invocation_context import InvocationContext
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.graph.graph import Graph


def _config() -> dict:
    return {
        "legal_text_paths": {
            "food_labeling_act": "config/rules/label_format_rules.json",
            "allergen_rules": "config/rules/allergens_28item.json",
            "premium_display_rules": "config/rules/keihinhyoji_blocklist.json",
        },
        "calorie_tolerance_pct": 0.05,
    }


def _invoke(agent: Graph, state: dict) -> dict:
    raw = json.dumps(state, ensure_ascii=False)
    ctx = InvocationContext(caller_trust_level=TrustLevel.VERIFIED_EXTERNAL)
    return agent.invoke(raw, ctx=ctx, input_context={"raw": raw})


def test_bl01_compliant_label_pass() -> None:
    agent = Graph(config=_config())
    state = {
        "raw_label_text": (
            "品名: ヨーグルト\n原材料名: 乳、砂糖\n内容量: 100g\n賞味期限: 2027-01-01\n"
            "保存方法: 要冷蔵\n製造者: テスト乳業\nアレルゲン: 乳\n"
            "エネルギー: 100 タンパク質: 4 脂質: 5 炭水化物: 10 食塩相当量: 0.1"
        ),
        "label_image": None,
        "sku_metadata": {"sku_id": "SKU-100", "product_category": "food", "declared_allergens": ["乳"]},
    }
    result = _invoke(agent, state)
    assert result["sku_verdict"] == "PASS"


def test_bl02_missing_allergen_fail() -> None:
    agent = Graph(config=_config())
    state = {
        "raw_label_text": (
            "品名: クッキー\n原材料名: 小麦粉、卵、砂糖\n内容量: 100g\n賞味期限: 2027-01-01\n"
            "保存方法: 常温\n製造者: テスト食品\nアレルゲン: 小麦\n"
            "エネルギー: 100 タンパク質: 2 脂質: 4 炭水化物: 12 食塩相当量: 0.2"
        ),
        "label_image": None,
        "sku_metadata": {"sku_id": "SKU-101", "product_category": "food", "declared_allergens": ["小麦"]},
    }
    result = _invoke(agent, state)
    assert result["sku_verdict"] == "FAIL"
    assert len(result["compliance_report"]["allergen_findings"]) > 0


def test_bl03_keihinhyoji_fail() -> None:
    agent = Graph(config=_config())
    state = {
        "raw_label_text": (
            "品名: ドリンク\n原材料名: 水、砂糖\n内容量: 500ml\n賞味期限: 2027-01-01\n"
            "保存方法: 常温\n製造者: テスト飲料\nアレルゲン: \n"
            "日本一の品質\nエネルギー: 100 タンパク質: 1 脂質: 1 炭水化物: 22 食塩相当量: 0.1"
        ),
        "label_image": None,
        "sku_metadata": {"sku_id": "SKU-102", "product_category": "drink", "declared_allergens": []},
    }
    result = _invoke(agent, state)
    assert result["sku_verdict"] == "FAIL"
    assert len(result["compliance_report"]["keihinhyoji_findings"]) > 0


def test_bl04_nutrition_warn() -> None:
    agent = Graph(config=_config())
    state = {
        "raw_label_text": (
            "品名: スープ\n原材料名: 水、塩\n内容量: 200ml\n賞味期限: 2027-01-01\n"
            "保存方法: 常温\n製造者: テスト食品\nアレルゲン: \n"
            "エネルギー: 200 タンパク質: 1 脂質: 1 炭水化物: 1 食塩相当量: 0.1"
        ),
        "label_image": None,
        "sku_metadata": {"sku_id": "SKU-103", "product_category": "soup", "declared_allergens": []},
    }
    result = _invoke(agent, state)
    assert result["sku_verdict"] == "WARN"


def test_bl_status_is_plain_string_not_enum() -> None:
    """Regression for RET-C2-059-CR-R3-01: get_output() must return AgentStatus.*.value (str), not the enum member."""
    from src.graph.domain_workflow_graph import DomainWorkflowGraph

    graph = DomainWorkflowGraph(
        config={
            "legal_text_paths": {
                "food_labeling_act": "x",
                "allergen_rules": "x",
                "premium_display_rules": "x",
            }
        }
    )

    # Success path: state has no error status
    out_success = graph.get_output({})
    assert isinstance(out_success["status"], str), "status must be a plain str, not an enum member"
    assert out_success["status"] == AgentStatus.SUCCESS.value

    # Error path: state carries error status
    out_error = graph.get_output({"status": AgentStatus.ERROR.value})
    assert isinstance(out_error["status"], str), "status must be a plain str, not an enum member"
    assert out_error["status"] == AgentStatus.ERROR.value


def test_bl05_batch_three_skus_independent() -> None:
    agent = Graph(config=_config())
    sku_states = [
        {
            "raw_label_text": "品名: A\n原材料名: 乳\n内容量: 1\n賞味期限: 2027\n保存方法: 常温\n製造者: X\nアレルゲン: 乳\nエネルギー: 100 タンパク質: 1 脂質: 1 炭水化物: 22 食塩相当量: 0.1",
            "label_image": None,
            "sku_metadata": {"sku_id": "SKU-A", "product_category": "food", "declared_allergens": ["乳"]},
        },
        {
            "raw_label_text": "品名: B\n原材料名: 卵\n内容量: 1\n賞味期限: 2027\n保存方法: 常温\n製造者: X\nアレルゲン: \nエネルギー: 100 タンパク質: 1 脂質: 1 炭水化物: 22 食塩相当量: 0.1",
            "label_image": None,
            "sku_metadata": {"sku_id": "SKU-B", "product_category": "food", "declared_allergens": []},
        },
        {
            "raw_label_text": "品名: C\n原材料名: 水\n内容量: 1\n賞味期限: 2027\n保存方法: 常温\n製造者: X\nアレルゲン: \n日本一\nエネルギー: 100 タンパク質: 1 脂質: 1 炭水化物: 22 食塩相当量: 0.1",
            "label_image": None,
            "sku_metadata": {"sku_id": "SKU-C", "product_category": "food", "declared_allergens": []},
        },
    ]
    results = [_invoke(agent, state)["compliance_report"] for state in sku_states]
    assert len(results) == 3
    assert {report["sku_id"] for report in results} == {"SKU-A", "SKU-B", "SKU-C"}
