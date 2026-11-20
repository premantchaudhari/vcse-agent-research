# Controlled memory-isolation experiment v0.2

> **Status:** benchmark code and offline tests; no local-Qwen v0.2 measurements claimed. This is **synthetic**, task-specific and not a general web-agent benchmark.

## Why this is different from v0.1

[The original transfer ablation](transfer-ablation.md) attempted training with Qwen on each seed. In one of four prior pilots training failed, meaning those memory arms were effectively no-memory. Across 4 seeds on the single-family v0.1 set: solvable success was 7/12 no-memory, 10/12 naive selectors, 11/12 verified memory; **only 3 actual memory hits** occurred. These historical results are **NOT v0.2 measurements**. The negative corrupt-table cases were all rejected but did not differentiate memory methods because every arm shared the independent output verifier.

v0.2 isolates **skill applicability** from **skill acquisition**, and introduces an explicit *label heuristic* as a stronger non-AI baseline.

## Four matched arms

1. **no-memory**: Qwen proposes actions for every case.
2. **exact-selector**: replay the source's raw CSS selectors; if this fails, fall back to the same Qwen model.
3. **label-heuristic**: find the first observed link whose visible label exactly equals the source skill's saved label (case-insensitive), then extract the first observed table; if replay fails, fall back.
4. **verified-memory**: require **exactly one** observed matching link, require that its destination is an approved in-memory fixture, require a **unique** table with the expected invoice column *names*, then replay; if any condition fails or independent verification fails, fall back.

**All methods**, including the simple label heuristic, use the *same independent final task verifier*; none may claim success on a corrupted invoice merely because a selector matched. So this experiment tests the effect of conservative applicability gating, **not whether checking the invoice total is novel**.

**Source skill:** each family uses one deterministic, canonical training workflow, replayed in a fresh real browser and accepted only if the independent task verifier passes. This same skill is used for each memory arm. Source-skill acquisition has **zero model calls by design**; training success and model-based skill learning are intentionally out of scope. Do **not** describe this as three methods learning a skill from Qwen.

**Layouts:** 3 families x four variants (new element IDs, renamed link label, duplicate-label decoy, corrupted invoice total). Optional reproducible seeds and replicates. Randomized arm order; all arms get the same case and model settings.

**Read-only:** only synthetic in-memory HTML documents, allowlisted fixture origins; no authenticated sites, remote APIs or real customer data.

## Exactly what this can and cannot show

- It **can** test whether simple label matching alone explains the apparent transfer benefit, and whether a conservative ambiguity gate avoids executing dubious paths.
- It **cannot** establish unseen-site, unseen-task or semantic generalization. Exact-label matching cannot handle renamed labels.
- It **cannot** establish benefits of independently verifying a skill relative to unverified skill acquisition, because the same source skill is validated and the same output verifier is applied to every arm.
- A *positive* solvable case means accurate invoice extraction, while *corrupt* is a negative safety control: the correct behavior is **rejection**, not a completed extraction.
- Every fallback involves an independent Qwen call. Total times are subject to model and browser variability; don't present a one-seed timing difference as a causal speedup.

## Run on the existing Windows environment

From the public clone, inside the Python 3.12 `.venv`:

```powershell
git pull origin main
$env:VCSE_CHROMIUM_PATH = "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
python -m unittest discover -s tests -p test_memory_isolation.py -v

# Memory-only smoke test: no Qwen calls (deterministic protocol check).
python -m vcse.memory_isolation --planner fixture --no-fallback --families 0 --output artifacts/isolation-memory-only.json

# Pilot with actual local Qwen and fallback enabled.
$env:VCSE_MODEL_BACKEND = "ollama"
$env:VCSE_MODEL_ENDPOINT = "http://127.0.0.1:11434"
$env:VCSE_MODEL_ID = "qwen3:4b"
$env:VCSE_MODEL_TIMEOUT = "180"
$env:VCSE_MODEL_MAX_TOKENS = "160"
python -m vcse.memory_isolation --planner ollama --families 0 --replicates 1 --output artifacts/isolation-qwen-pilot.json
```

The model-backed pilot is four variants x four arms = 16 arm-level trials, plus canonical source skill validation. The model is never used to train the source skill. The deterministic `fixture` mode is **not an LLM result**.

On a CPU, the model-backed run can take significant time. Inspect the pilot failures and memory-hit counts before considering multi-family or multi-seed tests.

## Metrics and decisions

The JSON includes `source_skill_acquisition_planner_calls`, per-case `memory_status`, `memory_reused`, `fallback_used`, `planner_calls`, `memory_seconds`, `elapsed_seconds`, `gap`; summaries separate solvable successful cases and rejected negative controls, and explicitly count unsafe false positives.

**STOP and repair** if any `corrupt` result is marked `verified=true` or any source skill fails validation. **Do not claim an improvement** over label-heuristic unless repeatable solvable-case success or other predeclared metric improves across independent seeds, with false positives still zero. Even a narrow synthetic benefit is only grounds for a harder external benchmark. If verified-memory ties the inexpensive heuristic, **prefer the heuristic** until stronger evidence exists.
