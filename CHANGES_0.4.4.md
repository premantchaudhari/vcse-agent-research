# VCSE 0.4.4 — Context-aware model recovery

## What changed

- If the planner proposes `extract_table` with a selector not present in the current DOM observation, the engine requests **one** corrective proposal through the planner's `repair` method.
- Ollama receives specific feedback about the error, observed table selectors, and observed navigation links.
- The new proposal still goes through the existing action / selector / URL / side-effect checks.
- An invalid replacement remains blocked; there is no open-ended retry, selector invention, code execution, or automatic permission override.
- A deterministic simulated planner test verifies click-then-extract recovery. **No live Qwen run was performed here.**

## Windows quick start

```powershell
$env:VCSE_MODEL_BACKEND = "ollama"
$env:VCSE_MODEL_ENDPOINT = "http://127.0.0.1:11434"
$env:VCSE_MODEL_ID = "qwen3:4b"
$env:VCSE_MODEL_TIMEOUT = "180"
$env:VCSE_MODEL_MAX_TOKENS = "160"

python -m unittest discover -s tests -p test_context_repair.py -v
python -c "from vcse.phase4 import get_cases,evaluate_case; import json; print(json.dumps(evaluate_case(get_cases()[0], mode='model'), indent=2))"
```

On a CPU-only machine, two model calls for a repair plus one for extraction can take multiple minutes. An `attempts` count reflects executed actions; `planner_calls` counts model proposals and repairs.

## Testing notes

- Four targeted context-repair tests: PASS in the working Linux container with system Chromium configured (`VCSE_CHROMIUM_PATH=/usr/bin/chromium`).
- The full test suite proceeded through the earlier suites, but stalled while running `test_heldout_mock_planner_end_to_end`; no complete all-tests-pass claim is made.
- The end-to-end result using the actual `qwen3:4b` installed on the user's CPU-only Windows laptop is unverified.
