# Phase 3 research notes

**Hypothesis:** structured observations and verification-gated recovery improve task success when a primary browser affordance is broken.

**Test fixtures:** invoice portal A and alternate portal B. Both have a disabled export button, a discoverable receipts link and an accessible invoice table. The alternate changes selectors and navigation path.

**Experiment status:** 17 local tests passed on container Chromium, including the 10 retained from v0.2. The 7 additional tests cover fallback, selector generalization, policy rejection, and no false success. The offline planner uses handcrafted generic rules; it is not a trainable model and the test fixtures are not an independent benchmark. No LLM service was called.

**Threats to validity:** small fixture set; information leakage from matching goal keywords; verifier depends on known expected IDs; DOM-only observations; self-hosted fixture not representative of authenticated or dynamic apps; model prompt injection; concurrent site changes; ambiguous user goals.

**Next experiment design:** 50+ synthetic but novel websites generated from independent templates; benchmark baselines with identical action budgets, multiple seeds, objective verification, no training/test overlap, repeatability and ablations for recovery/skill retrieval.
