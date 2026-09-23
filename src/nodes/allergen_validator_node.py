"""Allergen validator node for RET-C2-059."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

from framework.errors import SecurityViolationError
from framework.nodes.function_node import FunctionNode
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class AllergenComplianceValidatorNode(FunctionNode):
    """Validate allergen declarations against the 28-item mandatory list."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, rules_path: str = "config/rules/allergens_28item.json") -> None:
        super().__init__()
        self._rules_path = rules_path

    def _extra_security_gate_output(self, result: dict[str, Any]) -> dict[str, Any]:
        findings = result.get("allergen_findings", [])
        if findings:
            report = result.get("compliance_report")
            # Only raise if a compliance_report is explicitly present but omits the allergen findings
            if report is not None and not report.get("allergen_findings"):
                raise SecurityViolationError("Allergen findings suppressed - consumer safety violation")
        return result

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        domain = (state.get("input_context") or {}).get("domain", {})
        if not isinstance(domain, dict):
            domain = {}
        field_map = state.get("label_field_map") or domain.get("label_field_map", {})
        declared = field_map.get("allergen_declarations", [])
        ingredients = str(field_map.get("ingredients", ""))
        rules_path = state.get("allergen_rules_path", self._rules_path)
        allergens = self._load_allergen_rules(rules_path)

        findings: list[dict[str, Any]] = []
        for allergen in allergens:
            if allergen in ingredients and allergen not in declared:
                findings.append(
                    {
                        "allergen": allergen,
                        "severity": "FAIL",
                        "citation": "食品表示法 第4次改正 別表 第1項",
                        "remediation": f"アレルゲン {allergen} を表示欄に追加してください",
                    }
                )

        emit_trace_event(
            "AllergenComplianceValidatorNode_execute_complete",
            {"findings_count": len(findings)},
            state,
        )
        return {
            "raw_label_text": state.get("raw_label_text") or domain.get("raw_label_text", ""),
            "label_field_map": field_map,
            "sku_metadata": state.get("sku_metadata") or domain.get("sku_metadata", {}),
            "allergen_findings": findings,
        }

    def _load_allergen_rules(self, rules_path: str = "config/rules/allergens_28item.json") -> list[str]:
        path = Path(rules_path)
        if path.exists():
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                return [str(x) for x in data]
        return []
