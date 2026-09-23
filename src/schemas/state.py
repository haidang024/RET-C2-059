"""State schema for RET-C2-059 food label compliance flow."""

from __future__ import annotations

from typing import Any

from framework.schemas.agent_state import AgentState


class State(AgentState):
    """Flat, JSON-serializable state for RET-C2-059."""

    raw_label_text: str
    label_image: str | None

    # Mid-pipeline fields are msgpack-safe and populated incrementally by nodes.
    # TypedDict annotations do not impose runtime presence checks.
    sku_metadata: dict[str, Any]
    label_field_map: dict[str, Any]
    allergen_findings: list[dict[str, Any]]
    keihinhyoji_findings: list[dict[str, Any]]
    nutrition_findings: list[dict[str, Any]]
    compliance_report: dict[str, Any]
    format_findings: list[dict[str, Any]]
    markdown_summary: str
    sku_verdict: str
    result: str
    error_message: str | None
    input_error_message: str | None
    input_error_guidance: list[str]
    generation_mode: str | None
    provider_error_message: str | None
