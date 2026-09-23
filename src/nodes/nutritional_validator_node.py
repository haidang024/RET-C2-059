"""Nutritional label validator node for RET-C2-059."""

from __future__ import annotations

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


REQUIRED_NUTRIENTS = ["エネルギー", "タンパク質", "脂質", "炭水化物", "食塩相当量"]
CALORIE_TOLERANCE = 0.05


class NutritionalLabelValidatorNode(FunctionNode):
    """Validate nutrient panel completeness and calorie arithmetic."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, calorie_tolerance_pct: float = CALORIE_TOLERANCE) -> None:
        super().__init__()
        self._calorie_tolerance_pct = calorie_tolerance_pct

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        tolerance = float(state.get("calorie_tolerance_pct", self._calorie_tolerance_pct))
        field_map = state.get("label_field_map", {})
        nutrition = field_map.get("nutrition_facts", {})
        findings: list[dict[str, Any]] = []

        for nutrient in REQUIRED_NUTRIENTS:
            if nutrient not in nutrition:
                findings.append(
                    {
                        "nutrient": nutrient,
                        "severity": "FAIL",
                        "citation": "食品表示法施行規則 第3条 別表第9",
                        "remediation": f"5大栄養素 {nutrient} の表示が不足しています",
                    }
                )

        try:
            declared_kcal = float(nutrition.get("エネルギー", {}).get("value", 0))
            carb = float(nutrition.get("炭水化物", {}).get("value", 0))
            protein = float(nutrition.get("タンパク質", {}).get("value", 0))
            fat = float(nutrition.get("脂質", {}).get("value", 0))
            calc_kcal = carb * 4 + protein * 4 + fat * 9
            if declared_kcal > 0 and abs(declared_kcal - calc_kcal) / declared_kcal > tolerance:
                findings.append(
                    {
                        "field": "エネルギー",
                        "severity": "WARN",
                        "citation": "食品表示法施行規則 別表第9 注",
                        "remediation": (
                            f"申告カロリー ({declared_kcal}kcal) と計算値 ({calc_kcal:.1f}kcal) "
                            f"の差が ±{int(tolerance * 100)}% を超えています"
                        ),
                    }
                )
        except (ValueError, TypeError):
            pass

        emit_trace_event(
            "NutritionalLabelValidatorNode_execute_complete",
            {"findings_count": len(findings)},
            state,
        )
        return {"nutrition_findings": findings}
