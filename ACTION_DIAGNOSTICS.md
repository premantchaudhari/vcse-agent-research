# VCSE v0.4.2 – Action diagnostics and safe normalization

This update preserves the CPU-native Ollama adapter. It adds a narrow mapping of equivalent action names (`click_link`, `click_element`, `read_table`, `extract_table_data`) and clearer errors for unsupported ones.

**Important:** This change does not grant additional browser permissions. Unrecognized actions remain blocked; actions must use an exact selector from the observed page, and existing destination/verification rules still apply.

## PowerShell (in the extracted vcse-v0.4.2 folder)

```powershell
$env:VCSE_MODEL_BACKEND = 'ollama'
$env:VCSE_MODEL_ENDPOINT = 'http://127.0.0.1:11434'
$env:VCSE_MODEL_ID = 'qwen3:4b'
$env:VCSE_MODEL_TIMEOUT = '180'
$env:VCSE_MODEL_MAX_TOKENS = '160'
python -m unittest discover -s tests -p test_action_normalization.py -v
python -c "from vcse.phase4 import get_cases,evaluate_case; import json; print(json.dumps(evaluate_case(get_cases()[0], mode='model'), indent=2))"
```

If still blocked, the new `gap` will show `unsupported_action: <action>` instead of hiding the invalid action. If Qwen invents a selector, the engine will continue to reject it.

This patch has not been tested with your actual laptop or Ollama model; local tests validate behavior without live inference.
