"""Compliance score report node for RET-C2-059."""

from __future__ import annotations

import re
from typing import Any, ClassVar

from framework.errors import SecurityViolationError
from framework.nodes.function_node import FunctionNode
from framework.schemas.trust_level import TrustLevel
from framework.schemas.agent_status import AgentStatus
from shared.utils.audit_logger import emit_trace_event
from src.services.llm_runtime import complete_text, provider_metadata


class ComplianceScoreReportNode(FunctionNode):
    """Aggregate findings into SKU-level verdict and report."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self, llm: Any = None, config: dict[str, Any] | None = None) -> None:
        super().__init__()
        # Runtime clients are injected through Graph and never persisted in State.
        # Verdicts and citations remain deterministic when no key is configured.
        self._llm = llm
        self._config = dict(config or {})

    def _extra_security_gate_output(self, result: dict[str, Any]) -> dict[str, Any]:
        """S-3: enforce compliance report integrity and redact obvious PII markers."""
        if result.get("input_error_message"):
            return result
        report = result.get("compliance_report", {}) if isinstance(result, dict) else {}
        output = str(result.get("markdown_summary", "")) if isinstance(result, dict) else str(result)

        required_keys = {"verdict", "fail_count", "warn_count", "total_findings"}
        if not isinstance(report, dict) or not required_keys.issubset(set(report.keys())):
            raise SecurityViolationError("Compliance report missing required fields")

        verdict = str(report.get("verdict", "")).upper()
        if verdict not in {"PASS", "WARN", "FAIL"}:
            raise SecurityViolationError("Invalid compliance verdict")

        findings_total = (
            len(report.get("allergen_findings", []))
            + len(report.get("format_findings", []))
            + len(report.get("keihinhyoji_findings", []))
            + len(report.get("nutrition_findings", []))
        )
        if int(report.get("total_findings", 0)) != findings_total:
            raise SecurityViolationError("Compliance findings total mismatch")

        if not output.strip():
            raise SecurityViolationError("Output is empty - blocked by S-3 gate")
        if "Compliance Report" not in output:
            raise SecurityViolationError("Compliance markdown summary header missing")
        if re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", output):
            raise SecurityViolationError("PII detected in output (email address)")
        return result

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("input_error_message"):
            message = str(state["input_error_message"])
            return {
                "status": AgentStatus.SUCCESS.value,
                "result": message,
                "markdown_summary": message,
                "input_error_message": message,
            }
        allergen_findings: list[dict[str, Any]] = state.get("allergen_findings", [])
        format_findings: list[dict[str, Any]] = state.get("format_findings", [])
        keihinhyoji_findings: list[dict[str, Any]] = state.get("keihinhyoji_findings", [])
        nutrition_findings: list[dict[str, Any]] = state.get("nutrition_findings", [])

        all_findings = allergen_findings + format_findings + keihinhyoji_findings + nutrition_findings
        fail_count = sum(1 for finding in all_findings if finding.get("severity") == "FAIL")
        warn_count = sum(1 for finding in all_findings if finding.get("severity") == "WARN")

        if fail_count > 0:
            verdict = "FAIL"
        elif warn_count > 0:
            verdict = "WARN"
        else:
            verdict = "PASS"

        report: dict[str, Any] = {
            "sku_id": state.get("sku_metadata", {}).get("sku_id", "unknown"),
            "verdict": verdict,
            "fail_count": fail_count,
            "warn_count": warn_count,
            "allergen_findings": allergen_findings,
            "format_findings": format_findings,
            "keihinhyoji_findings": keihinhyoji_findings,
            "nutrition_findings": nutrition_findings,
            "total_findings": len(all_findings),
        }

        ai_note = self._generate_ai_note(state, report)
        metadata = provider_metadata(state)
        markdown = self._build_markdown_summary(report, ai_note=ai_note)
        emit_trace_event(
            "ComplianceScoreReportNode_execute_complete",
            {
                "verdict": verdict,
                "fail_count": fail_count,
                "warn_count": warn_count,
                "llm_used": bool(ai_note),
            },
            state,
        )
        return {
            "compliance_report": report,
            "markdown_summary": markdown,
            "sku_verdict": verdict,
            "result": markdown,
            "status": AgentStatus.SUCCESS.value,
            **metadata,
        }

    def _generate_ai_note(self, state: dict[str, Any], report: dict[str, Any]) -> str:
        """Generate optional wording from aggregate counts, never raw label text."""
        messages = [
            {
                "role": "system",
                "content": (
                    "Write one concise Japanese operational follow-up sentence for a food-label review. "
                    "Do not change the verdict, invent findings, or give a new legal conclusion."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"verdict={report.get('verdict', 'UNKNOWN')}; "
                    f"fail_count={int(report.get('fail_count', 0))}; "
                    f"warn_count={int(report.get('warn_count', 0))}"
                ),
            },
        ]
        try:
            return complete_text(
                state,
                messages,
                self._llm,
                max_tokens=256,
                timeout_s=float(self._config.get("timeout_s", 30.0)),
                max_retry=int(self._config.get("max_retry", 3)),
            )
        except Exception:
            return ""

    def _build_markdown_summary(self, report: dict[str, Any], ai_note: str = "") -> str:
        lines: list[str] = [
            f"# Compliance Report: {report.get('sku_id', 'unknown')}",
            f"- Verdict: {report.get('verdict', 'UNKNOWN')}",
            f"- FAIL: {report.get('fail_count', 0)}",
            f"- WARN: {report.get('warn_count', 0)}",
            "",
            "## Findings",
        ]
        for section in [
            "allergen_findings",
            "format_findings",
            "keihinhyoji_findings",
            "nutrition_findings",
        ]:
            lines.append(f"### {section}")
            findings = report.get(section, [])
            if not findings:
                lines.append("- none")
                continue
            for finding in findings:
                lines.append(
                    f"- [{finding.get('severity', 'INFO')}] {finding.get('citation', '')} :: {finding.get('remediation', '')}"
                )
            lines.append("")
        if ai_note:
            lines.extend(["## AI Operational Note", ai_note])
        return "\n".join(lines)
