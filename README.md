# VCSE — Verified Capability and Skill Execution

**Experimental Python browser-agent research focused on action verification and reusable capability replay.** This repository contains the VCSE v0.5.1 research snapshot and a separate comparison harness using the official Qwen-Agent framework.

> **Research status:** prototype and benchmark code, not a production autonomous agent. No demonstrated superiority to established agents on independently verified real-world tasks.

## Repository overview

**Suggested GitHub About description:** Experimental Python AI agent framework for verified browser automation, skill replay, and benchmarking against Qwen-Agent.

**Suggested topics:** `python` · `ai-agents` · `browser-automation` · `playwright` · `llm` · `agentic-ai` · `benchmarking` · `ollama` · `qwen-agent` · `skill-replay` · `artificial-intelligence`.

The GitHub About description and topics are repository settings and are not automatically populated by this README. The full repository is [public](https://github.com/premantchaudhari/vcse-agent-research), and the original maintainer-owned source is MIT-licensed.

## What is implemented

- Playwright-based constrained browser workflow execution, observation and verification.
- Planner interfaces for local Ollama and HTTPS OpenAI-compatible chat-completions APIs.
- Compact-action planner experiments and verified action-replay research.
- A standalone benchmark comparing official Qwen-Agent with **VCSE-style planner/replay arms** using matched API model, restricted public-web navigation and measured token usage.

**Important distinction:** the VCSE-style benchmark arms are not the complete VCSE engine, and Qwen-Agent is an independent baseline, not a VCSE dependency at runtime.

## Architecture at a glance

```text
Goal -> bounded observation -> planner -> permitted action -> verifier -> outcome
                                      ^
                            optional verified replay

Benchmark: same hosted model -> [Qwen-Agent | VCSE-style planner] -> same browser -> independent verifier
```

## Quick start

Requires a supported Python version and a Playwright Chromium installation.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m unittest discover -s tests -v
```

For API benchmarking, see [comparisons/README.md](comparisons/README.md):

```powershell
python -m pip install -r requirements-benchmark.txt
python -m unittest discover -s comparisons/tests -v
$env:GEMINI_API_KEY = Read-Host 'Gemini API key'
python comparisons/tools/compare_agents.py --provider gemini --model gemini-2.5-flash --ids python-docs --arms qwen-agent vcse-no-memory vcse-memory --repeat 1 --call-timeout 25 --trial-timeout 90
```

These commands are documented configuration examples, not claims that the hosted benchmark has succeeded.

## Evaluation standards

Compare **verified task success first**, then cost per successful task, latency, token usage, model calls and safety. Separate cold planning, warm planning and replay cases. A fast failed task is still a failure. Keep prompts, model configuration, browser capabilities and execution limits matched. External website changes and model-provider behavior can affect reproducibility.

Snapshot validation reported 12/12 comparison offline tests. The full browser suite and hosted-API path were not validated in the snapshot build environment; current CI and live outcomes must be tested separately.

## Continuous validation and release notes

The [research validation workflow](.github/workflows/research-validation.yml) runs synthetic browser tests, comparison harness offline tests, Python compilation, and a history-level Gitleaks check on GitHub Actions. **Live model-provider benchmark experiments are not included in CI** and must be reproduced separately.

The [v0.5.1 research snapshot notes](docs/release-v0.5.1.md) describe release scope and limitations. A GitHub release/tag only exists once separately published; the presence of release notes does not imply an official release.

## Security and responsible use

Use only public read-only evaluation pages or sites you are authorized to automate. Do not provide cookies, authenticated page content, client data or credentials to untrusted model endpoints. Keys belong in environment variables; see [`.env.example`](.env.example). Do not commit runs, session stores or browser artifacts. A public repository is **not** itself approval to execute on third-party services.

## License and public release

Original VCSE research code in this repository is offered under the [MIT License](LICENSE). Third-party frameworks, packages and documentation retain their own licenses; consult their upstream projects. Do not treat the presence of an MIT license as clearance for separately sourced material.

**Publication status:** this repository is public and its maintainer-owned code is provided under the MIT License. Public availability does not certify the code as secure, establish third-party redistribution rights or validate hosted benchmark results. See [SECURITY.md](SECURITY.md) for ongoing security responsibilities.

This research is a portfolio demonstration, not evidence that VCSE outperforms Qwen-Agent or any other agent.
