# Transfer ablation v0.1 — reproducible synthetic experiment

> **Status: protocol implementation only. Local Qwen3/Ollama results have NOT yet been produced.** Do not repost the historical exact-fixture 4/4 replay result as transfer evidence. This benchmark is intentionally synthetic; it does not prove real-world website generalization or research novelty.

## Research question

On layouts withheld from skill creation, does a **verified semantic-label memory** preserve independently checked task success and reduce local LLM planner calls compared with (a) no memory and (b) naive CSS-selector memory?

This test is deliberately a stepping stone, **not a novel memory algorithm**. An exact visible-label match is a simplistic applicability test; changing labels, ambiguous labels or corrupted results cause rejection or fallback.

## Related prior art

- [Voyager (2023)](https://arxiv.org/abs/2305.16291) — a skill library with iterative prompting and environment feedback.
- [BrowserGym](https://github.com/ServiceNow/BrowserGym) — infrastructure for web-agent benchmark experiments.
- [WebArena (ICLR 2024)](https://arxiv.org/abs/2307.13854) — realistic long-horizon web-agent evaluation.

The above make it inappropriate to claim novelty from verified memory or replay alone.

## Controlled design

Training: one source layout for each of **three navigation-label families**, with skills obtained by the *same selected planner* and stored only after successful independent browser verification. The training planner call count is reported separately rather than hidden.

Test variants per family:
1. **ids:** fresh randomized element IDs with unchanged visible link label
2. **renamed:** changed element IDs and paraphrased visible link label
3. **decoy:** additional identical-label link leading to an invalid invoice table
4. **corrupt:** correct navigation but wrong invoice total (verifier must reject)

Each variant is generated from a deterministic seed. Use **4 replicates** for 48 withheld synthetic layouts (3 families × 4 variants × 4 replicates); results are paired by case across all arms and arm execution order is randomized deterministically. Training source HTML is separate from all test HTML.

Arms:
- **no-memory:** always plan with the selected local model.
- **naive-memory:** attempt raw source CSS selectors, then use the same model if replay fails.
- **verified-memory:** match exactly one observed link with the stored visible label, re-observe the target page, locate a unique invoice table by column headings, execute, independently verify all invoice IDs and the exact sum; otherwise fall back to the same model.

All arms use the same tool allowlist, task oracle, model interface, maximum five action attempts, and task set. Every success is checked with the existing independent invoice-table verifier; raw replay failure is **never** silently recorded as task success. The verifier's expected IDs/amounts are not included in model or memory applicability observations. Model settings apply identically across arms.

**Important limitations:** this is a tiny generated domain with one goal and three visible-label families. The verified-memory arm has a hard-coded table-header expectation and exact-label applicability heuristic. It is therefore a narrow known-domain baseline, **not learned semantic transfer**. Live performance is likely sensitive to label changes and ambiguous links. The naive-memory arm receives the same fallback model as verified-memory, so call and success comparisons account for recovery. Per-arm learning/training cost is not included in test time, but is reported separately.

## Windows PowerShell

From the cloned `vcse-agent-research` directory, using Python 3.12 and an active venv:

```powershell
python -m pip install -r requirements.txt

# Use installed Edge if Playwright Chromium download is unavailable.
$env:VCSE_CHROMIUM_PATH = "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"

python -m unittest discover -s tests -p test_transfer_benchmark.py -v

# Smoke test: offline deterministic planner. These are not LLM results.
python -m vcse.transfer_benchmark --planner fixture --families 0 --replicates 1 --output artifacts/transfer-smoke.json

# Genuine local-model run, small pilot first.
$env:VCSE_MODEL_BACKEND = "ollama"
$env:VCSE_MODEL_ENDPOINT = "http://127.0.0.1:11434"
$env:VCSE_MODEL_ID = "qwen3:4b"
$env:VCSE_MODEL_TIMEOUT = "180"
$env:VCSE_MODEL_MAX_TOKENS = "160"

python -m vcse.transfer_benchmark --planner ollama --families 0 --replicates 1 --output artifacts/transfer-qwen-pilot.json
```

Only after the pilot works, consider the **full 48-layout experiment**. On a CPU this may require many model calls and be expensive in wall-clock time. There is no need to run the full suite without checking pilot outcomes:

```powershell
python -m vcse.transfer_benchmark --planner ollama --replicates 4 --output artifacts/transfer-qwen-48.json
```

`--planner fixture` is a deterministic fake planner for protocol testing; never report it as a local Qwen result. The model-backed run requires the local Ollama service and model preinstalled. No remote sites or credentials are used.

## What to publish

Along with the sanitized JSON report, publish:
- Model name, **Ollama digest**, Ollama and Playwright versions, browser version, CPU/GPU/RAM, source commit and random seed
- Per-variant per-arm verified success **and failures**, total model calls, total time and retry/fallback counts
- The source training calls and any skipped or failed training cases
- At least 3 seeds / repeated runs if making statistical claims; one run is an exploratory case study
- Explain all synthetic fixtures and heuristic applicability rules
- Distinguish model-planning time from browser-verification overhead where possible

## Stop/go decision

**Stop or redesign** the memory method if the verified arm does not improve verified completion relative to no-memory, or if it causes false-positive outcomes on decoys/corrupted tables. **Go to broader external benchmarks** only after stable reproducible results on randomized unseen synthetic layouts. Even a synthetic win only justifies trying real evaluations; it does not prove real-world performance.

## Scope safety

All browser fixtures are in-memory HTML, allowlisted to `https://vcse.fixture.test`. No real invoice accounts, external website access, cookies, browser profiles or API keys are required.

## Analyze repeated runs before changing the algorithm

After a set of local-model runs, aggregate all original reports with the new
**audit command**. This is a descriptive post-processing step; it does not
rerun Ollama or the browser:

```powershell
python -m vcse.transfer_audit `
  artifacts/transfer-qwen-pilot.json `
  artifacts/transfer-qwen-seed-2027.json `
  artifacts/transfer-qwen-seed-3049.json `
  artifacts/transfer-qwen-seed-4093.json `
  --output artifacts/transfer-audit.json
```

The audit reports *solvable positive cases* separately from the deliberately
corrupted invoice **negative safety controls**. It flags any unsafe false
positive where a corrupted invoice was marked verified. It also distinguishes
runs where training failed, counts actual memory reuse, and displays
paired outcomes against no-memory on the same case. Failure messages are
bucketed into planner errors, browser/timeout errors, missing selectors,
missing tables and exhausted budgets. These are **failure-message categories,
not verified root-cause diagnoses**.

Do **not** interpret the four corrupted cases as solved tasks or omit the
seed where skill training failed. Likewise, a fixture with a changed ID but
the same visible label is not evidence of semantic generalization across
renamed links. Predeclare rules before a larger experiment.
