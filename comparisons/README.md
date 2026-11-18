# VCSE ↔ Official Qwen-Agent comparison

This benchmark compares **the official Qwen-Agent Python framework** with compact VCSE-style planning and verified terminal-success action replay. **The benchmark VCSE-style arms are not the full VCSE engine.**

All arms use the same API model, metering proxy and restricted public-web Playwright navigator; task verification is independent. Timeout is 90 seconds per subprocess and 25 seconds per upstream call by default. The API key never enters Git or result artifacts.

Supported hosted APIs: Gemini, OpenAI, Groq, OpenRouter (OpenAI-compatible endpoints). A selected model must support compatible chat-completion and Qwen-Agent tool-call behavior; some models do not. Reasoning disabled automatically only on Gemini 2.5 where supported; other models may have different reasoning modes, so comparisons must use identical provider+model for all arms.

On Windows PowerShell, from the repository root:

```powershell
python -m pip install -r requirements-benchmark.txt
python -m playwright install chromium
$env:GEMINI_API_KEY = Read-Host 'Gemini API key'
python comparisons/tools/compare_agents.py --provider gemini --model gemini-2.5-flash --repeat 1 --ids python-docs --arms qwen-agent vcse-no-memory vcse-memory --call-timeout 25 --trial-timeout 90
```

For Groq example (use a compatible model supported by your account; set pricing explicitly):

```powershell
$env:GROQ_API_KEY = Read-Host 'Groq API key'
python comparisons/tools/compare_agents.py --provider groq --model YOUR_GROQ_MODEL --ids python-docs --input-rate YOUR_INPUT_USD_PER_MILLION --output-rate YOUR_OUTPUT_USD_PER_MILLION
```

For other providers, choose `--provider openai` / `openrouter`, set the corresponding API key and a valid model ID. The default model is Gemini-specific; change it when changing providers. Model provider pricing must be verified independently and entered using `--input-rate` and `--output-rate`, other providers require these rates so the estimated spending guard remains enabled.

Never treat a task failure as a speed victory. No claims of live tests are made; the local offline suite only checks source behavior. See original README in the project history for research limitations.
