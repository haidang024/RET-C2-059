# Template Design Specification

## Position in AgentCore Architecture

- **Agent Class**: `Graph` (registry name: `RetailPrivateLabelFoodLabelComplianceAgent`)
- **L1 Base**: `AgentBaseGraph`
- **Three-Layer Separation**:
  - State: flat `State(AgentState)` with JSON-serializable values only
  - Nodes: `FunctionNode` validators plus a `GraphNode` composition wrapper
  - Graph: outer `AgentBaseGraph` and inner `BaseGraph`

## Architecture Overview

### Node Configuration

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| initialize | Framework bootstrap | framework state | initialized state | default `InitializeNode` |
| pre_process | Validate input, parse JSON/plain text, normalize label fields | `user_input`, `input_context` | `raw_label_text`, `label_field_map`, `sku_metadata` | `InputParserNode(FunctionNode)` / `execute` + S-2 hook |
| main | Invoke the four-stage domain subgraph | normalized label fields | four findings lists | `DomainWorkflowGraphNode(GraphNode)` / composition hooks |
| post_process | Compute verdict and render report; optionally add constrained AI wording | findings lists | `compliance_report`, `markdown_summary`, `result` | `ComplianceScoreReportNode(FunctionNode)` / `execute` + S-3 hook |
| finalize | Framework output envelope | final state | response | default `FinalizeNode` |

The inner `DomainWorkflowGraph` runs:

```text
allergen → format → keihinhyoji → nutrition
```

The complete data flow is:

```text
START → initialize → pre_process → main/subgraph → post_process → finalize → END
```

### State Definition

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| `raw_label_text` | `str` | Normalized label or OCR text | after pre-process |
| `label_image` | `str` | Optional image reference | no |
| `sku_metadata` | `dict` | SKU identifier and retail metadata | no |
| `label_field_map` | `dict` | Parsed statutory and nutrition fields | after pre-process |
| `allergen_findings` | `list` | Missing allergen declarations | after main |
| `format_findings` | `list` | Required-field/font violations | after main |
| `keihinhyoji_findings` | `list` | Advertising claim findings | after main |
| `nutrition_findings` | `list` | Nutrition completeness/arithmetic findings | after main |
| `compliance_report` | `dict` | Machine-readable deterministic report | after post-process |
| `markdown_summary` / `result` | `str` | Human-readable output | after post-process |
| `sku_verdict` | `str` | `PASS`, `WARN`, or `FAIL` | after post-process |

State contains no secrets, SDK clients, Pydantic models, dataclasses, or
`InvocationContext`. Context is recovered with `InvocationContext.from_state()`;
the inner domain envelope travels through non-persisted `input_context`.

## Runtime Configuration and LLM Injection

`config/agent.yaml` contains registry identity only. `config/config.yaml` contains
runtime controls, the three shipped rule paths, tolerance values, and Azure OpenAI
settings. The node resolves the Azure client from invocation-scoped secrets;
provider failure falls back to the deterministic statutory report.

`Graph.register_nodes()` injects the same client into `main` and
`ComplianceScoreReportNode`. The rule corpus alone determines findings and the
verdict. The LLM sees aggregate verdict/count values only; provider absence,
errors, or unsupported responses fall back to the deterministic markdown report.

## Rule Corpus

- `config/rules/allergens_28item.json`
- `config/rules/label_format_rules.json`
- `config/rules/keihinhyoji_blocklist.json`

All paths are configured in `config/config.yaml` and resolve to committed files.

## Framework Utilization

- [x] `InvocationContext.from_state()` at the composite-node boundary
- [x] `SecurityViolationError`
- [x] S-2 domain validation via `_extra_security_gate_input()`
- [x] S-3 report preservation via `_extra_security_gate_output()`
- [x] S-4 domain events from every `FunctionNode.execute()`
- [x] No override of final framework `_security_gate_input/_output` methods
- [x] No Level-0 or mediator imports from `src/`

## EU AI Act Art.13 Design-Time Evidence

Not applicable because `docs/01_proposal.md` declares this intended purpose out
of Annex III scope. The report nevertheless exposes findings, citations, the
deterministic verdict, and whether an optional AI note was used.

## Design Decision Record

| Decision | Options | Chosen | Rationale |
|----------|---------|--------|-----------|
| L1 base | AgentBaseGraph / AutonomousBaseGraph | AgentBaseGraph | Linear bounded compliance workflow |
| Composition | flat outer chain / inner subgraph | GraphNode + BaseGraph | Keeps the use-case workflow cohesive and reusable |
| Provider absence | fail boot / deterministic fallback | deterministic fallback | Core statutory checks do not require generation |
| AI authority | generate verdict / wording only | aggregate-count wording only | Prevents AI output from changing findings or legal conclusions |
| HITL | interrupt / non-HITL | non-HITL | No interrupt requirement or autonomous decision path |
