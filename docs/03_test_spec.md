# Test Specification

## Test Strategy

- Coverage target: 85%+
- Test types: unit, integration, and proof-of-boundary
- Runtime target: published `agenticstar-agentcore[anthropic]==1.0.1` wheel

## Framework Compliance Tests

| TC-ID | Test | Expected Result |
|-------|------|-----------------|
| TC-01 | State is a flat `AgentState` extension | No Pydantic/dataclass fields |
| TC-02 | Label text exceeds 8192 characters | S-2 rejects input |
| TC-03 | Credential-like fields/patterns | CI scans report zero violations |
| TC-04 | Invocation context usage | Nodes use `InvocationContext.from_state()` only |
| TC-05 | Domain tracing | Every FunctionNode path emits a domain event |
| TC-06 | Override `_security_gate_input()` | Framework raises `TypeError` at class definition |
| TC-07 | Override `_security_gate_output()` | Framework raises `TypeError` at class definition |
| TC-08 | Under-privileged caller invokes protected node | S-1 rejects before `execute()` |
| TC-09 | Missing allergen declaration | FAIL finding |
| TC-10 | All allergens declared | No allergen finding |
| TC-11 | Attempt to suppress allergen findings | S-3 rejects output |
| TC-12 | Missing statutory label field | FAIL finding |
| TC-13 | Unsupported superiority claim | FAIL finding |
| TC-14 | Ambiguous quantity claim | WARN finding |
| TC-15 | Missing mandatory nutrient | FAIL finding |
| TC-16 | Calorie arithmetic outside tolerance | WARN finding |
| TC-17 | Any FAIL finding | Final verdict is FAIL |
| TC-18 | No findings | Final verdict is PASS |

## Proof-of-Boundary Tests

| PB-ID | Boundary | Test | Expected Result |
|-------|----------|------|-----------------|
| PB-1 | BaseNode → EventEmitter | Domain trace is emitted | No silent path |
| PB-2 | State serialization | Serialize representative state | Primitive/JSON-safe values only |
| PB-3 | Template → rule corpus | Load shipped allergen corpus | 28 entries |
| PB-4 | Import isolation | AST scan `src/` | No Level-0 or mediator imports |
| PB-5 | Checkpoint safety (conditional) | Apply only when memory/HITL and ingress hooks are enabled | Auto-waived while checkpointing is disabled |
| PB-6 | Node lifecycle | S-1 → start → S-2 → execute → S-3 → complete | Exact order; denial occurs before execute |
| PB-7 | HITL propagation (conditional) | Apply only when `config/config.yaml` enables HITL | Auto-waived as non-HITL |
| PB-8 | Standalone LLM injection | Import server with/without key | Boot without key; same client reaches `main` and report node with key |
| PB-9 | Standalone trust promotion | External and internal bearer tokens | External never becomes INTERNAL; invalid tokens rejected |

## Business Logic Tests

| BL-ID | Scenario | Expected Result |
|-------|----------|-----------------|
| BL-01 | Fully compliant label | PASS |
| BL-02 | Ingredient allergen omitted from declaration | FAIL with allergen finding |
| BL-03 | `日本一` marketing claim | FAIL with 景品表示 finding |
| BL-04 | Calorie mismatch only | WARN |
| BL-05 | Three sequential SKUs | Independent SKU reports |
| BL-06 | LLM absent or provider call fails | Deterministic verdict/report remains available |

## Execution Summary

- Execution date: 2026-08-18
- Scaffold/static gates: PASS
- Supplemental gate regressions: 192 passed, 3 conditional skips
- Lint/format/compile and manual domain pipeline: PASS
- Full runtime/coverage result: blocked before collection because
  `agenticstar-agentcore[anthropic]==1.0.1` is unavailable without a configured
  `AGENTCORE_PYPI_INDEX` or `PIP_EXTRA_INDEX_URL`; rerun after registry access is supplied.
