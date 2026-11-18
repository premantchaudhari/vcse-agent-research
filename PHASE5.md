# VCSE Phase 5 — Verified Skill Learning (v0.5)

## What this does

Adds a conservative skill library to the v0.4.4 browser agent. After a successful model- or heuristic-planned execution, v0.5 extracts only the successful read-only steps, **replays them in a new Chromium session**, verifies the invoice records against the fixture's independent expected data, and stores the verified workflow. A subsequent task on **the exact same test fixture** retrieves and replays the workflow (including a fresh verification) without calling the planner. Modified or untrusted skills are rejected and the discovery planner is used again.

This is **procedural memory**, not neural weight training. It does not use external websites, persistent login, real invoices, or arbitrary tool creation. It demonstrates reuse on a matching fixture, *not* transfer learning to unseen applications. We intentionally bind each skill to a hash of the complete fixture documents and goal to avoid applying workflows where their validity is unknown.

## Windows setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m unittest discover -s tests -p test_phase5.py -v
```

Run the offline heuristic test before using the model:

```powershell
python -m vcse.phase5 --planner heuristic --split development --repeat --library artifacts/dev-skills.json --output artifacts/dev-phase5.json
```

The initial pass should discover verified skills, and the repeat pass should reuse them with zero planner calls. Use **new library filenames** for clean benchmark runs: existing skills intentionally change the results.

## Test your existing Qwen model on CPU

```powershell
$env:VCSE_MODEL_BACKEND = "ollama"
$env:VCSE_MODEL_ENDPOINT = "http://127.0.0.1:11434"
$env:VCSE_MODEL_ID = "qwen3:4b"
$env:VCSE_MODEL_TIMEOUT = "180"
$env:VCSE_MODEL_MAX_TOKENS = "160"
python -m vcse.phase5 --planner model --split heldout --repeat --library artifacts/model-skills.json --output artifacts/model-phase5.json
```

The first run will use Qwen unless a matching skill already exists. The repeat pass should use verified saved skills, avoiding model calls when the exact fixture is unchanged. The report contains per-task outcomes, planner-call counts, and elapsed times. The new Chromium verification is not instantaneous; reduced planner calls do not guarantee a proportional reduction in total wall-clock time.

## Relevant implementation

- `vcse/phase5.py` — skill extraction, replay, versioned JSON storage, evaluation command.
- `tests/test_phase5.py` — seven targeted tests including storage deduplication, replay, tamper rejection and changed-fixture handling.
- `vcse/phase4.py` — unchanged Qwen model adapter and v0.4.4 tests.

## Safety and experimental limits

- `click` is restricted to observed allowlisted fixture links; `extract_table` to an observed table with expected headers.
- Saves selector sequences and hashes, not invoice contents, cookies, credentials or screenshots.
- Every saved workflow is re-verified before storage and before reuse; unverified output is not marked successful.
- A stored record is not a trusted program and cannot introduce arbitrary code execution.
- The JSON library is a *prototype* for local single-process use: no multi-writer synchronization, signing, per-user isolation or production data retention policy.
- An attacker who can modify the library can alter metadata. The executor still applies the same restrictions and verifier, but this is not a full adversarial-security proof.
- Fixtures intentionally supply expected invoice IDs and totals. A production verifier will need an independent source of truth, not the agent's own output.
- No model fine-tuning has happened. No general browser benchmark improvement is claimed.

## Next research targets

Introduce a principled skill applicability model that generalizes beyond exact document hashes, randomized held-out browser applications, invalidation metrics, adversarial tests, distinct-user separation, and model training data collected only with consent.
