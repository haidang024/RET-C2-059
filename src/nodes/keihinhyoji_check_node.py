"""Keihinhyoji check node for RET-C2-059."""

from __future__ import annotations

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


SUPERIORITY_CLAIMS_BLOCKLIST = [
    "No.1",
    "ナンバーワン",
    "日本一",
    "最高品質",
    "最高級",
    "業界初",
    "世界初",
    "唯一",
    "最強",
    "完全無欠",
    "他を圧倒",
]
AMBIGUOUS_QUANTIFIERS = ["たっぷり", "ふんだん", "豊富", "大量"]
UNSUBSTANTIATED_HEALTH_CLAIMS = ["免疫力アップ", "体に良い", "健康増進", "アンチエイジング"]


class KeihinhyojiCheckNode(FunctionNode):
    """Detect potential 景品表示法 violations in marketing claims."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        field_map = state.get("label_field_map", {})
        claims_text = " ".join(
            [
                str(field_map.get("marketing_claims", "")),
                str(field_map.get("raw_label_text", "")),
            ]
        )
        findings: list[dict[str, Any]] = []

        for claim in SUPERIORITY_CLAIMS_BLOCKLIST:
            if claim in claims_text:
                findings.append(
                    {
                        "term": claim,
                        "type": "superiority_claim",
                        "severity": "FAIL",
                        "citation": "景品表示法 第5条第1号",
                        "remediation": f"表現 {claim} は根拠のない優良誤認表示です。削除または根拠を明示してください",
                    }
                )

        for term in AMBIGUOUS_QUANTIFIERS:
            if term in claims_text:
                findings.append(
                    {
                        "term": term,
                        "type": "ambiguous_quantifier",
                        "severity": "WARN",
                        "citation": "景品表示法 第5条第1号",
                        "remediation": f"表現 {term} は曖昧な数量表現です。具体的な数値に置き換えてください",
                    }
                )

        for claim in UNSUBSTANTIATED_HEALTH_CLAIMS:
            if claim in claims_text:
                findings.append(
                    {
                        "term": claim,
                        "type": "health_claim",
                        "severity": "FAIL",
                        "citation": "景品表示法 第5条第1号 / 健康増進法第31条",
                        "remediation": f"健康効能表示 {claim} は科学的根拠の提示が必要です",
                    }
                )

        emit_trace_event(
            "KeihinhyojiCheckNode_execute_complete",
            {"findings_count": len(findings)},
            state,
        )
        return {"keihinhyoji_findings": findings}
