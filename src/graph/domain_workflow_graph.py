"""Inner DomainWorkflowGraph for RET-C2-059 compliance pipeline."""

from __future__ import annotations

from typing import Any

from framework.graph.base_graph import BaseGraph
from framework.schemas.agent_status import AgentStatus
from langgraph.graph import END, START

from src.nodes.allergen_validator_node import AllergenComplianceValidatorNode
from src.nodes.keihinhyoji_check_node import KeihinhyojiCheckNode
from src.nodes.label_format_checker_node import LabelFormatCheckerNode
from src.nodes.nutritional_validator_node import NutritionalLabelValidatorNode
from src.schemas.state import State


class DomainWorkflowGraph(BaseGraph):
    """Inner domain workflow graph for RET-C2-059."""

    @property
    def name(self) -> str:
        return "ret_c2_059_compliance_workflow"

    @property
    def state_schema(self) -> type:
        return State

    def _validate_config(self) -> None:
        legal = self.config.get("legal_text_paths", {})
        required = ["food_labeling_act", "allergen_rules", "premium_display_rules"]
        for key in required:
            if not legal.get(key):
                raise ValueError(f"DomainWorkflowGraph: missing required legal_text_paths key: {key}")

    def register_nodes(self) -> None:
        """Register all domain nodes. Do NOT call super()."""
        legal_paths = self.config.get("legal_text_paths", {})
        self._nodes["allergen"] = AllergenComplianceValidatorNode(
            rules_path=legal_paths.get("allergen_rules", "config/rules/allergens_28item.json")
        )
        self._nodes["format"] = LabelFormatCheckerNode()
        self._nodes["keihinhyoji"] = KeihinhyojiCheckNode()
        self._nodes["nutrition"] = NutritionalLabelValidatorNode(
            calorie_tolerance_pct=float(self.config.get("calorie_tolerance_pct", 0.05))
        )

    def add_edges(self) -> None:
        self._sg.add_edge(START, "allergen")
        self._sg.add_edge("allergen", "format")
        self._sg.add_edge("format", "keihinhyoji")
        self._sg.add_edge("keihinhyoji", "nutrition")
        self._sg.add_edge("nutrition", END)

    def route(self, state: dict[str, Any]) -> str:
        del state
        return "allergen"

    def get_output(self, state: dict[str, Any]) -> dict[str, Any]:
        """Keys MUST match DomainWorkflowGraphNode.merge_output() keys."""
        return {
            "allergen_findings": state.get("allergen_findings", []),
            "format_findings": state.get("format_findings", []),
            "keihinhyoji_findings": state.get("keihinhyoji_findings", []),
            "nutrition_findings": state.get("nutrition_findings", []),
            "status": (
                AgentStatus.SUCCESS.value if state.get("status") != AgentStatus.ERROR.value else AgentStatus.ERROR.value
            ),
        }
