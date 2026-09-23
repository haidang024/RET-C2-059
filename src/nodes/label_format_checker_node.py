"""Label format checker node for RET-C2-059."""

from __future__ import annotations

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


REQUIRED_FIELDS = ["品名", "原材料名", "内容量", "賞味期限", "保存方法", "製造者"]
MIN_FONT_SIZE_PT = 8


class LabelFormatCheckerNode(FunctionNode):
    """Validate required field presence and font-size thresholds."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        field_map = state.get("label_field_map", {})
        findings: list[dict[str, Any]] = []

        for field in REQUIRED_FIELDS:
            if not field_map.get(field):
                findings.append(
                    {
                        "field": field,
                        "severity": "FAIL",
                        "citation": "食品表示法施行規則 第3条",
                        "remediation": f"必須表示項目 {field} が欠落しています",
                    }
                )

        font_metadata = field_map.get("font_metadata", {})
        for field, font_pt in font_metadata.items():
            try:
                if float(font_pt) < MIN_FONT_SIZE_PT:
                    findings.append(
                        {
                            "field": field,
                            "severity": "FAIL",
                            "citation": "食品表示法施行規則 別表第19",
                            "remediation": f"フォントサイズを {MIN_FONT_SIZE_PT}pt 以上にしてください",
                        }
                    )
            except (ValueError, TypeError):
                continue

        emit_trace_event(
            "LabelFormatCheckerNode_execute_complete",
            {"findings_count": len(findings)},
            state,
        )
        return {"format_findings": findings}
