# Kroki MCP stress-test reporting rules

Use this addendum with `tests/prompts/kroki_full_catalog_stress_test.md` when an agent executes the full tool-only stress test.

These rules are intentionally strict. They prevent a successful render run from hiding validation defects or under-counting tool invocations.

## Execution accounting

Initialize these counters to zero before the first MCP call:

- `list_diagram_types_calls`
- `validate_uml_calls`
- `generate_uml_calls`
- `generate_uml_batch_calls`

Increment the relevant counter for **every attempted MCP tool invocation**, before evaluating whether the call succeeded or returned a controlled error.

Controlled-error calls still count. In particular:

- the invalid `generate_uml` call from Negative 2 counts;
- the empty `generate_uml_batch` call from Negative 3 counts;
- the mixed valid/invalid `generate_uml_batch` call from Negative 4 counts.

Do not infer counts from successful artifacts. Count actual tool invocations.

For the current full stress-test specification, if every phase executes exactly once, the expected totals are:

- `list_diagram_types_calls = 2`
  - initial catalog discovery;
  - post-negative-test health check.
- `validate_uml_calls = 17`
  - 7 complex Mermaid validations;
  - 9 PlantUML-family validations;
  - 1 malformed-Mermaid negative validation.
- `generate_uml_calls = 3`
  - 2 identical stateless repeatability renders;
  - 1 invalid-diagram-type negative call.
- `generate_uml_batch_calls = 6`
  - 1 complex Mermaid batch;
  - 1 PlantUML-family batch;
  - 2 full-catalog batches;
  - 1 empty-batch negative call;
  - 1 mixed valid/invalid negative batch.
- `total_mcp_tool_calls = 28`.

If a validation failure causes a complex-case render to be omitted as required by the main prompt, report both the actual counters and the expected baseline, and explain the delta. Never fabricate a call just to match the baseline.

## Strict Mermaid negative-test semantics

Negative 1 uses:

```text
sequenceDiagram
A->>
```

with `diagram_type="mermaid"`, `output_format="svg"`, and `strict=true`.

This negative test passes **only** when `validate_uml` returns `valid: false` or an equivalent controlled validation failure.

The test does **not** pass merely because the MCP connection remains healthy.

If the validator returns `valid: true` for that malformed sequence message:

- record `NEGATIVE 1: FAIL`;
- count the `validate_uml` invocation normally;
- continue the remaining safe tests;
- force the overall stress-test verdict to FAIL.

After the strict validator fix, the expected result is a validation error explaining that the sequence message has an arrow but no target actor.

## Final report requirements

The final report must include a tool-call accounting table:

| MCP tool | Actual calls | Expected baseline | Status |
| --- | ---: | ---: | --- |
| `list_diagram_types` | N | 2 | PASS/EXPLAIN |
| `validate_uml` | N | 17 | PASS/EXPLAIN |
| `generate_uml` | N | 3 | PASS/EXPLAIN |
| `generate_uml_batch` | N | 6 | PASS/EXPLAIN |
| **Total** | N | **28** | PASS/EXPLAIN |

Also report the four negative tests individually. Do not collapse them into `4/4` unless each expected error condition was actually satisfied.

Overall PASS requires all conditions from the main stress-test prompt plus:

- malformed Mermaid is rejected by strict validation;
- the tool-call ledger includes failed/negative invocations;
- the reported counters reconcile with the actual transcript.

If any of those conditions fail, finish with:

`MCP_KROKI_TOOL_ONLY_STRESS_TEST: FAIL - <short reason>`
