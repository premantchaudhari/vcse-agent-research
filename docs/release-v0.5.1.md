# VCSE v0.5.1 — Research snapshot

**Status:** Experimental / pre-release. This is a research snapshot, not a production autonomous agent.

## Included

- Constrained Playwright browser observations, actions and independent verification
- Local Ollama and configurable hosted model adapter experiments
- Verified capability recording/replay on **synthetic** browser fixtures
- Dedicated Qwen-Agent versus VCSE-style planner/replay comparison harness with offline tests

## Evidence boundaries

- The benchmark's VCSE-style arms are **not the complete VCSE engine**.
- Offline synthetic fixture success does not establish real-world generalization.
- No claim of independently demonstrated superiority over Qwen-Agent or other frameworks.
- API-based benchmark outcomes require comparable model settings, repeat trials, and published traces before making performance claims.

## Reproduce

Use Python 3.12, install `requirements.txt` and `requirements-benchmark.txt`, run `python -m playwright install chromium`, then:

```bash
python -m unittest discover -s tests -v
python -m unittest discover -s comparisons/tests -v
```

See [README](../README.md), [Phase 5.1](../PHASE5_1.md) and [comparison instructions](../comparisons/README.md).

**License:** [MIT](../LICENSE) for original maintainer-owned code. Third-party packages retain their own licenses.

A GitHub release may be tagged `v0.5.1` **after** confirming the final snapshot revision and passing checks. This file is release-note source, not proof that a GitHub release exists.
