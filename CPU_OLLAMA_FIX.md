# CPU-only Ollama planner fix

The original `OpenAICompatiblePlanner` uses `/v1/chat/completions` with a JSON response format but does not request `think: false`. This can make Qwen thinking models take a long time on CPU. The new `OllamaNativePlanner` uses `/api/chat` with `think: false`, `format: json`, a small `num_predict`, and `keep_alive: 10m`.

## Windows PowerShell

```powershell
$env:VCSE_MODEL_BACKEND = "ollama"
$env:VCSE_MODEL_ENDPOINT = "http://127.0.0.1:11434"
$env:VCSE_MODEL_ID = "qwen3:4b"
$env:VCSE_MODEL_TIMEOUT = "180"
$env:VCSE_MODEL_MAX_TOKENS = "160"

python -m unittest discover -s tests -p test_ollama_native.py -v
python -c "from vcse.phase4 import get_cases,evaluate_case; import json; print(json.dumps(evaluate_case(get_cases()[0], mode='model'), indent=2))"
python -m vcse.phase4 --planner model --split heldout --output artifacts/model-heldout.json
```

### Notes

- This is an incremental update of VCSE v0.4. Run from the extracted `vcse-v0.4` project directory and don't merge folders incorrectly.
- The test suite checks request shape and browser-fixture behavior. It does **not** perform live Ollama inference: you must test with your own local Ollama process.
- `num_predict=160` may be too short for verbose model outputs, but concise action JSON should fit. Increase to 256 if Ollama returns incomplete JSON.
- CPU inference can still be slow; native mode doesn't guarantee a certain speed or success rate. To diagnose, run `ollama ps` and compare response times.
- The model is only allowed to suggest actions. The browser executor enforces permitted actions and independently checks the result.
