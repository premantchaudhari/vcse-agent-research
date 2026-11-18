# VCSE research charter, v0.1

## Question
Can a capability-gap detector and independently verified workaround registry improve *held-out* autonomous task completion with fewer user interruptions and no increase in unsafe actions?

## Hypotheses
- H1: Explicit evidence-checked fallbacks raise verified completion over one-shot execution on tasks with recoverable tool failures.
- H2: Reusing previously validated scoped skills lowers cost without reducing success on changed environments.
- H3: A capability-gap classifier can distinguish missing tool, missing knowledge, denied permission, invalid goal and transient error more accurately than blind retries.

## Experimental arms
A. Same base model, regular planning and tools, no persistent skills.
B. Same model, same tools/budgets, persistent verified skill memory.
C. Same model, budgets and permissions, capability-gap diagnosis + sandboxed alternative synthesis and verification.

## Guardrails
- User grants scopes for tools and accounts; higher-impact actions require approval.
- Treat websites, repos, PDFs and tool outputs as untrusted instructions.
- Restrict time/steps/cost and repeat attempts; never bypass access control.
- Keep private memories distinct from global reusable methods; redact or omit user content in model-training exports.
- Verify with test oracles distinct from the tool's self-report; record actual provenance.
- Store skill applicability conditions and degradation signals, re-evaluate after page/environment changes.

## Benchmark protocol
- Gather >=100 consented, reproducible real tasks and >=50 held-out variants across websites, code projects and local workflows.
- Log full traces with redaction, permissions, tool failures, time, latency and costs.
- Run each arm on identical tasks, model versions and budgets. Use multiple seeds/repeats.
- Primary outcome: independently verified task completion.
- Secondary: intervention count, cost, step count, time, recovery rate, regressions and policy violations.
- No evaluation data may enter LoRA training. Publish confidence intervals and failure cases.

## V0.2 tasks
1. Add model-agnostic planner using typed JSON plans and strict schemas, with prompt-injection controls.
2. Add sandboxed Playwright adapter with limited site allowlist and read-only modes.
3. Develop classification of failure causes, including explicit permission-denied terminal state.
4. Implement declarative executable skill recipes and environmental preconditions.
5. Add browser-backed verifier oracles and a manual review queue for ambiguous successes.
6. Add costs, timeouts, dry runs, cancellation, durable audit/event log and rollback.
7. Collect curated trajectories for SFT/LoRA and evaluate new model adapters in shadow mode.

## Novelty caution
Many constituent mechanisms are prior art: planners, browser-use agents, retries, skill memory, online learning, and verifiers. Claims of novelty require a targeted survey of papers, patents and implementations, plus a reproducible new algorithm and evidence. This repository is a prototype to test hypotheses, not a patent filing.
