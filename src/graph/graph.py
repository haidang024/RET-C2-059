"""RET-C2-059 outer graph (Cat 2 nested architecture)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, cast

from framework.graph.agent_base_graph import AgentBaseGraph
from framework.nodes.graph_node import GraphNode
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from framework.utils.config_loader import load_config

from src.nodes.compliance_score_report_node import ComplianceScoreReportNode
from src.nodes.input_parser_node import InputParserNode
from src.schemas.state import State

if TYPE_CHECKING:
    from src.graph.domain_workflow_graph import DomainWorkflowGraph


class DomainWorkflowGraphNode(GraphNode):
    """GraphNode wrapper for the private-label validation workflow."""

    error_strategy: ClassVar[str] = "propagate"
    propagate_hitl: ClassVar[bool] = False

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        llm: Any = None,
        **kwargs: Any,
    ) -> None:
        self._config = config or {}
        self._llm = llm if llm is not None else self._config.get("llm")
        super().__init__(**kwargs)

    def get_subgraph(self) -> DomainWorkflowGraph:
        from src.graph.domain_workflow_graph import DomainWorkflowGraph

        return DomainWorkflowGraph(config=self._parent_config())

    def extract_input(self, state: AgentState) -> str:
        del state
        # Structured label data travels through input_context so framework PII
        # masking of user_input cannot corrupt the validated field map.
        return "Validate the normalized private-label food data."

    @staticmethod
    def _domain_context(state: AgentState) -> dict[str, Any]:
        return {
            "raw_label_text": state.get("raw_label_text", ""),
            "label_field_map": state.get("label_field_map", {}),
            "sku_metadata": state.get("sku_metadata", {}),
        }

    def execute(self, state: AgentState) -> dict[str, Any]:
        """Delegate without placing the structured domain envelope in user_input."""
        if state.get("input_error_message"):
            return {"status": AgentStatus.SUCCESS.value}
        ctx = replace(InvocationContext.from_state(state), hitl_allowed=False)
        subgraph = self.get_subgraph()
        try:
            sub_result = subgraph.invoke(
                self.extract_input(state),
                session_id=ctx.session_id,
                ctx=ctx,
                input_context={"domain": self._domain_context(state)},
            )
        except Exception as exc:
            return cast(dict[str, Any], self._handle_call_error(subgraph, exc, state))
        return self.merge_output(state, sub_result)

    def merge_output(self, state: AgentState, sub_result: dict[str, Any]) -> dict[str, Any]:
        del state
        return {
            "allergen_findings": sub_result.get("allergen_findings", []),
            "format_findings": sub_result.get("format_findings", []),
            "keihinhyoji_findings": sub_result.get("keihinhyoji_findings", []),
            "nutrition_findings": sub_result.get("nutrition_findings", []),
            "status": sub_result.get("status"),
        }

    def _parent_config(self) -> dict[str, Any]:
        """Pass runtime parameters and the in-memory LLM to the inner graph."""
        return {**self._config, "llm": self._llm}


class Graph(AgentBaseGraph):
    """RetailPrivateLabelFoodLabelComplianceAgent outer graph."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    # Harness J2/J4: the Marketplace runner constructs the agent with a bare
    # ``agent_cls()`` on agentcore 1.0.1 and ``agent_cls(config=...)`` on 1.0.3,
    # and it never reads ``config/config.yaml``. The inner DomainWorkflowGraph
    # requires ``legal_text_paths`` and raises at compile time without it, so on
    # the container path every request failed before any node ran. Loading the
    # file here makes both runner generations work; ``**kwargs`` absorbs
    # arguments added by later runner versions.
    def __init__(self, config: dict[str, Any] | None = None, **kwargs: Any) -> None:
        # Load config/config.yaml first, then overlay whatever the runner passed.
        # agentcore 1.0.1 calls agent_cls() (config=None) but 1.0.3 calls
        # agent_cls(config={...}) — often an EMPTY dict. Keying off `is None`
        # alone therefore skipped the file load on 1.0.3 and left required keys
        # missing, which surfaced as a bare
        # "Graph invocation did not succeed: status='error'".
        config_path = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
        file_config = load_config(str(config_path)) if config_path.exists() else {}
        config = {**file_config, **dict(config or {})}
        super().__init__(config=dict(config), **kwargs)

    @property
    def name(self) -> str:
        return "RetailPrivateLabelFoodLabelComplianceAgent"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()
        self._nodes["pre_process"] = InputParserNode()
        self._nodes["main"] = DomainWorkflowGraphNode(
            config=self.config,
            llm=self.config.get("llm"),
        )
        self._nodes["post_process"] = ComplianceScoreReportNode(
            llm=self.config.get("llm"),
            config=self.config,
        )

    def get_output(self, state: AgentState) -> dict[str, Any]:
        """Expose both the framework envelope and structured compliance result."""
        output = {
            "output": state.get("result") or state.get("markdown_summary"),
            "compliance_report": state.get("compliance_report", {}),
            "markdown_summary": state.get("markdown_summary", ""),
            "sku_verdict": state.get("sku_verdict", ""),
            "status": state.get("status"),
            "trace_id": state.get("trace_id"),
            "correlation_id": state.get("correlation_id"),
            "node_history": state.get("node_history", []),
            "generation_mode": state.get("generation_mode"),
            "provider_error_message": state.get("provider_error_message"),
        }
        _set_marketplace_guidance(output, state, "Food-label compliance request")
        return output


def _set_marketplace_guidance(output: dict[str, Any], state: AgentState, subject: str) -> None:
    context = state.get("input_context")
    message = state.get("input_error_message")
    if not (isinstance(context, dict) and "conversation_history" in context and message):
        return
    lines = [f"{subject} could not be processed.", "", f"Reason: {message}"]
    guidance = state.get("input_error_guidance")
    if isinstance(guidance, list) and guidance:
        lines.extend(["", "How to continue:"])
        lines.extend(f"- {item}" for item in guidance)
    output["output"] = "\n".join(lines)
