# VCSE — Verified Capability and Skill Execution

Private repository-ready snapshot of VCSE **v0.5.1** with a separate **official Qwen-Agent comparison harness**. Existing VCSE execution code is retained; the compact-planner patch is applied to `vcse/discovery.py`. This does **not** mean VCSE's runtime is implemented using Qwen-Agent. Qwen-Agent is an independent benchmark arm.

## APIs and models

VCSE's `OpenAICompatiblePlanner` in `vcse/discovery.py` accepts any valid HTTPS OpenAI-compatible chat-completions endpoint, including Google Gemini, OpenAI, Groq and OpenRouter. `OllamaNativePlanner` supports local Ollama. Configure keys only through environment variables. **Qwen-Agent** supports model backend configuration separately in `comparisons/tools/compare_agents.py`. The comparison harness supports `--provider gemini|openai|groq|openrouter` and one common model across both arms.

See [comparisons/README.md](comparisons/README.md) to run a bounded benchmark. Both arms use the same model, browser and tools; estimated API spend is calculated from reported usage and user-supplied model rates. Qwen-Agent must support the chosen model's tool-calling compatibility. This code has not been verified with live API credentials.

## Usage

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m unittest discover -s comparisons/tests -v
```

## Publishing

Create a **new empty PRIVATE repo** at https://github.com/new (`vcse-agent-research` suggested), with no README or license initialized. Then from the extracted folder:

```powershell
git init -b main
git add .
git diff --cached --check
git diff --cached --name-only
git commit -m 'Import VCSE v0.5.1 with provider-neutral API and official Qwen-Agent benchmark'
git remote add origin https://github.com/premantchaudhari/vcse-agent-research.git
git push -u origin main
```

**Do not push until checking `git diff --cached --name-only` for secrets, local logs, private data or credentials.** License is intentionally not added; absent a license, permission to reuse is not granted.

## Scientific status

This repository contains experimental research code. Synthetic benchmark success, fixture results and tests do not establish real-world agent superiority. The API comparison is independent and is not a full engine-to-engine comparison.

### Validation status of this snapshot

On the package builder, `python -m unittest discover -s comparisons/tests -v` passed 12/12 offline tests. The full VCSE browser-based suite could not pass here because Playwright's Chromium executable was absent; install `python -m playwright install chromium` before rerunning. No hosted API or browser live task was executed on the builder. Local Windows and hosted-provider behavior remain unverified.
