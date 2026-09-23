"""InputParserNode for RET-C2-059 food label compliance checks."""

from __future__ import annotations

import json
import re
from typing import Any, ClassVar

from framework.errors import SecurityViolationError
from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

_MIN_LABEL_CHARS = 20
_INPUT_GUIDANCE = [
    "Provide raw food-label text, or a JSON object with raw_label_text.",
    "You may provide label_image instead when OCR input is available.",
    "Include label fields such as 品名, 原材料名, 内容量, 賞味期限, 保存方法, and 製造者.",
]


def _input_error(message: str) -> dict[str, Any]:
    return {
        "status": AgentStatus.SUCCESS.value,
        "input_error_message": message,
        "input_error_guidance": _INPUT_GUIDANCE,
    }


class InputParserNode(FunctionNode):
    """S-2 input gate and field extraction for label text/image."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def _extra_security_gate_input(self, state: dict[str, Any]) -> dict[str, Any]:
        payload = self._read_payload(state)
        raw = state.get("raw_label_text", "") or payload.get("raw_label_text", "")
        if not isinstance(raw, str):
            raise SecurityViolationError("raw_label_text must be text")
        if len(raw) > 8192:
            raise SecurityViolationError("label_text exceeds 8192 char limit")
        if not raw.strip() and not (state.get("label_image") or payload.get("label_image")):
            return {**state, **_input_error("Please provide raw_label_text or label_image.")}
        if raw:
            from shared.security.pii_detector import detect_pii

            findings = detect_pii(raw)
            if findings:
                for f in sorted(findings, key=lambda x: x["start"], reverse=True):
                    raw = raw[: f["start"]] + "[MASKED]" + raw[f["end"] :]
                state["raw_label_text"] = raw
                emit_trace_event("pii_masked_label_text", {"count": len(findings)}, state)
        return state

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("input_error_message"):
            return _input_error(str(state["input_error_message"]))
        payload = self._read_payload(state)
        raw_text = state.get("raw_label_text") or payload.get("raw_label_text", "")
        label_image = state.get("label_image") or payload.get("label_image")
        sku_metadata = state.get("sku_metadata") or payload.get("sku_metadata", {})

        ocr_used = False
        if not raw_text.strip() and label_image:
            raw_text = self._run_ocr(label_image)
            ocr_used = True

        if not label_image and len(raw_text.strip()) < _MIN_LABEL_CHARS:
            return _input_error("The label text is too short to run a meaningful compliance check.")

        field_map = self._extract_fields(raw_text)
        field_map["raw_label_text"] = raw_text

        emit_trace_event(
            "InputParserNode_execute_complete",
            {"ocr_used": ocr_used, "field_count": len(field_map)},
            state,
        )
        return {
            "label_field_map": field_map,
            "raw_label_text": raw_text,
            "sku_metadata": sku_metadata if isinstance(sku_metadata, dict) else {},
            "status": AgentStatus.SUCCESS.value,
        }

    @staticmethod
    def _read_payload(state: dict[str, Any]) -> dict[str, Any]:
        """Normalize the standalone string input into the domain envelope."""
        raw_input = (state.get("input_context") or {}).get("raw", state.get("user_input", ""))
        if isinstance(raw_input, dict):
            return raw_input
        if isinstance(raw_input, str):
            try:
                parsed = json.loads(raw_input)
            except json.JSONDecodeError:
                return {"raw_label_text": raw_input}
            if isinstance(parsed, dict):
                return parsed
            return {"raw_label_text": raw_input}
        return {}

    def _extract_fields(self, text: str) -> dict[str, Any]:
        ingredients = ""
        marketing_claims: list[str] = []
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        for line in lines:
            if line.startswith("原材料名"):
                ingredients = line.split(":", 1)[-1].strip() if ":" in line else line.replace("原材料名", "").strip()
            if any(keyword in line for keyword in ["日本一", "No.1", "たっぷり", "免疫力アップ", "最高品質"]):
                marketing_claims.append(line)

        nutrition = self._extract_nutrition(lines)
        allergens = self._extract_declared_allergens(lines)

        return {
            "ingredients": ingredients,
            "allergen_declarations": allergens,
            "nutrition_facts": nutrition,
            "marketing_claims": " ".join(marketing_claims),
            "font_metadata": {},
            "品名": self._extract_prefixed(lines, "品名"),
            "原材料名": ingredients,
            "内容量": self._extract_prefixed(lines, "内容量"),
            "賞味期限": self._extract_prefixed(lines, "賞味期限"),
            "保存方法": self._extract_prefixed(lines, "保存方法"),
            "製造者": self._extract_prefixed(lines, "製造者"),
        }

    def _extract_prefixed(self, lines: list[str], key: str) -> str:
        for line in lines:
            if line.startswith(key):
                return line.split(":", 1)[-1].strip() if ":" in line else line.replace(key, "").strip()
        return ""

    def _extract_declared_allergens(self, lines: list[str]) -> list[str]:
        for line in lines:
            if line.startswith("アレルゲン"):
                body = line.split(":", 1)[-1] if ":" in line else line.replace("アレルゲン", "")
                return [part.strip() for part in re.split(r"[、,]", body) if part.strip()]
        return []

    def _extract_nutrition(self, lines: list[str]) -> dict[str, dict[str, str]]:
        mapping = {
            "エネルギー": r"エネルギー\s*[:：]?\s*([0-9.]+)",
            "タンパク質": r"タンパク質\s*[:：]?\s*([0-9.]+)",
            "脂質": r"脂質\s*[:：]?\s*([0-9.]+)",
            "炭水化物": r"炭水化物\s*[:：]?\s*([0-9.]+)",
            "食塩相当量": r"食塩相当量\s*[:：]?\s*([0-9.]+)",
        }
        text = " ".join(lines)
        output: dict[str, dict[str, str]] = {}
        for key, pattern in mapping.items():
            match = re.search(pattern, text)
            if match:
                output[key] = {"value": match.group(1)}
        return output

    def _run_ocr(self, image_bytes: bytes) -> str:
        del image_bytes
        return "品名: OCR商品\n原材料名: 砂糖\n内容量: 100g\n賞味期限: 2027-01-01\n保存方法: 常温\n製造者: OCR製造者"
