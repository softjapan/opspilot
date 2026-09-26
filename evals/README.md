# OpsPilot Evals

Run with:

```bash
uv run opspilot evals run                                    # detection only, no API key needed
uv run opspilot evals run --provider anthropic --check-diagnosis   # real diagnosis accuracy
```

## Two accuracy layers

- **Detection accuracy**: did the analyzers produce (or correctly avoid) the
  expected `Finding`s? This is deterministic and measured the same way
  regardless of LLM provider.
- **Diagnosis accuracy** (`--check-diagnosis`): did the explanation's root
  cause mention the expected keywords? Only meaningful with a real provider
  (`--provider anthropic|openai`) — the `mock` provider doesn't reason, it
  just echoes the most recent finding's title, so diagnosis results under
  `mock` are not a real accuracy measurement (the report says so explicitly).

## Scope: only what the analyzers actually detect

Every scenario here corresponds to a real detection rule in
`src/opspilot/analyzers/`:

- **mysql**: `type == 'ALL' and key IS NULL` → missing index (one rule)
- **nginx**: 5xx responses, upstream connection failures
- **linux**: CPU/memory/disk threshold breaches

There is intentionally no `lock-contention`, `disk-full` (as distinct from
the generic threshold), or `docker` category — OpsPilot doesn't detect those
yet. **Add analyzer capability first, then add the matching eval scenario.**
Shipping a scenario for a detection rule that doesn't exist would just be
evaluating a fiction.

Each category also ships one `*-no-false-positive.yaml` scenario, so the
benchmark catches over-eager detection, not just missed detection.

## Publishing results

Detection-mode numbers are real and reproducible (no LLM involved) — see
`tests/evals/test_runner.py::test_all_shipped_scenarios_pass_in_detection_mode`
for the regression guard. Diagnosis-mode numbers depend on which model you
run with. Don't paste either into the README until you've actually run them
with the setup you're claiming — see `plan.md` for why.
