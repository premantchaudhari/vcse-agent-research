# VCSE 0.5.1 — Cross-layout wallpaper capability smoke test

## What this implements

A new **independent** module `vcse.phase5_1` in the existing VCSE 0.5 codebase. Three offline synthetic web pages are loaded into real Chromium via Playwright:

1. **Direct:** visible Download image button.
2. **Menu:** More options → Save to device.
3. **Bookmark decoy:** More → Save (does **not** download) versus Download original (does).

The target is a **real browser download event** of a small generated PNG. The verifier checks the PNG header, CRCs, image dimensions, decoded pixel size and the fixture's known checksum. The file is downloaded into a temporary sandbox directory (not the user's Downloads directory). Every action requires a currently observed button ID. We don't navigate external sites.

The capability library records a successful action sequence, tests it again in a fresh browser context, and stores a verified `download_image` capability. For cross-layout replay, a stored plan from another fixture is *attempted*, but each action is only used if its selector exists in the new page. A simple deterministic semantic fallback (Download → More → Save) handles differences. **This is a deliberately bounded heuristic, not an LLM-generalization result.**

The old Phase 5 invoice benchmark is unchanged and continues to be accessible as `python -m vcse.phase5`.

## Setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m unittest discover -s tests -p test_phase5_1.py -v
python -m vcse.phase5_1 --library artifacts/wallpaper-skills.json --output artifacts/wallpaper-results.json
```

If a nonstandard Chromium installation should be used, set `VCSE_CHROMIUM_PATH` to the exact executable path. Leave it unset if you installed Playwright's Chromium normally.

## Important limitations

- Not an actual online wallpaper downloader. The downloaded file is deliberately synthetic, small (32×24 pixels), and ephemeral; this phase tests the control flow and evidence, not high-resolution media.
- No generative AI inference is used in Phase 5.1. Qwen integration for arbitrary goal/observation → browser action is a future controlled experiment. A successful deterministic test is not evidence of autonomous AI reasoning.
- Matching selectors from another page does **not** establish true transfer of skills. The heuristic fallback implements common labels and must be compared to a no-memory baseline before crediting any learning advantage.
- An unexpected download is never considered valid merely because an event fired: bytes, PNG structure, expected checksum and filename are checked.
- There is no ability to interact with external websites, authentication, copy-protected images, payments, or arbitrary executable tools.
- The original v0.5 invoice benchmark sometimes returned malformed JSON from Ollama. This module does not modify or solve that problem.

## Proposed next experiments

1. Introduce 20+ new, randomized page layouts and compare fresh model planning with and without retrieved capability descriptions.
2. Add a *bounded* model planner with JSON-schema output and one controlled correction retry.
3. Make skill retrieval use semantic preconditions and postconditions, not raw DOM IDs, then measure generalization after UI changes.
4. Expand verification for large, authentic downloads only after real-site permissions and sandbox policies are in place.
