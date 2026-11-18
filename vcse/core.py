"""Execution-first, verification-gated capability discovery (offline prototype).

No unrestricted shell, networking, browser, or file system access. Only tools
explicitly supplied by the developer run. Users approve sensitive actions in
future adapters; this prototype refuses them.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Callable
import json
from pathlib import Path
import re
import time
import uuid

ToolFn = Callable[[dict[str, Any]], dict[str, Any]]
VerifierFn = Callable[[dict[str, Any], dict[str, Any]], bool]

@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    operation: str
    run: ToolFn
    requires_approval: bool = False

@dataclass(frozen=True)
class Plan:
    goal: str
    operation: str
    inputs: dict[str, Any]
    expected: dict[str, Any]
    allowed_tools: tuple[str, ...] = ()
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])

@dataclass
class Skill:
    operation: str
    tool: str
    times_verified: int = 0
    times_failed: int = 0
    last_verified_at: float = 0.0
    evidence: str = ''

@dataclass
class RunReport:
    goal_id: str
    status: str
    selected_tool: str | None
    attempts: list[dict[str, Any]]
    verified: bool
    gap: str | None = None
    result: dict[str, Any] = field(default_factory=dict)
    user_action: str | None = None

class SkillStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.skills: dict[str, Skill] = {}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding='utf-8'))
            for item in data.get('skills', []):
                skill = Skill(**item)
                self.skills[self._key(skill.operation, skill.tool)] = skill

    @staticmethod
    def _key(operation: str, tool: str) -> str:
        return json.dumps([operation, tool])

    def get(self, operation: str, tool: str) -> Skill | None:
        return self.skills.get(self._key(operation, tool))

    def record(self, operation: str, tool: str, verified: bool, evidence: str = '') -> None:
        key = self._key(operation, tool)
        skill = self.skills.setdefault(key, Skill(operation=operation, tool=tool))
        if verified:
            skill.times_verified += 1
            skill.last_verified_at = time.time()
            skill.evidence = evidence[:200]
        else:
            skill.times_failed += 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps({'schema': 1, 'skills': [asdict(s) for s in self.skills.values()]}, indent=2), encoding='utf-8')
        temp.replace(self.path)

class Engine:
    def __init__(self, tools: list[Tool], verifiers: dict[str, VerifierFn], store: SkillStore, max_attempts: int = 3):
        self.tools = {t.name: t for t in tools}
        self.verifiers = verifiers
        self.store = store
        self.max_attempts = max(1, max_attempts)

    def execute(self, plan: Plan, approved_tools: set[str] | None = None) -> RunReport:
        approved_tools = approved_tools or set()
        attempts: list[dict[str, Any]] = []
        verifier = self.verifiers.get(plan.operation)
        if verifier is None:
            return RunReport(plan.id, 'blocked', None, attempts, False, 'no_verifier', user_action='Developer must define objective success verification for this operation.')
        candidates = [t for t in self.tools.values() if t.operation == plan.operation and (not plan.allowed_tools or t.name in plan.allowed_tools)]
        if not candidates:
            return RunReport(plan.id, 'blocked', None, attempts, False, 'missing_capability', user_action='No authorized adapter is available for this operation.')
        # Prefer previously successful tools but deliberately keep alternate paths.
        candidates.sort(key=lambda t: (-(self.store.get(plan.operation, t.name).times_verified if self.store.get(plan.operation, t.name) else 0), t.name))
        for tool in candidates[:self.max_attempts]:
            if tool.requires_approval and tool.name not in approved_tools:
                attempts.append({'tool': tool.name, 'state': 'approval_required'})
                continue
            try:
                output = tool.run(dict(plan.inputs))
                if not isinstance(output, dict):
                    raise TypeError('Tool must return a dict')
                verified = bool(verifier(output, plan.expected))
                attempts.append({'tool': tool.name, 'state': 'verified' if verified else 'verification_failed', 'output': output})
                self.store.record(plan.operation, tool.name, verified, evidence=str(plan.expected))
                if verified:
                    return RunReport(plan.id, 'completed', tool.name, attempts, True, result=output)
            except Exception as exc:
                attempts.append({'tool': tool.name, 'state': 'tool_error', 'error': str(exc)[:300]})
                self.store.record(plan.operation, tool.name, False)
        needs_approval = any(a['state'] == 'approval_required' for a in attempts)
        return RunReport(plan.id, 'blocked' if needs_approval else 'failed', None, attempts, False, 'approval_required' if needs_approval else 'workarounds_exhausted', user_action='Approval needed for a sensitive tool.' if needs_approval else 'No candidate passed verification; request human review or add another permitted adapter.')


def exact_result(output: dict[str, Any], expected: dict[str, Any]) -> bool:
    """Safe example verifier, not a general correctness oracle."""
    return all(output.get(k) == v for k, v in expected.items())


def numeric_total(output: dict[str, Any], expected: dict[str, Any]) -> bool:
    """Require exact line-item count and totals; not just tool's success flag."""
    amounts = output.get('amounts')
    if not isinstance(amounts, list) or any(not isinstance(x, (float, int)) or isinstance(x, bool) for x in amounts):
        return False
    return len(amounts) == expected['count'] and abs(sum(amounts) - expected['total']) < 1e-8
