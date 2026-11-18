"""A controlled simulation: website export unavailable; an allowed fallback works."""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
import argparse
import json
from vcse.core import Engine, Plan, SkillStore, Tool, numeric_total


def primary_export(_: dict) -> dict:
    raise RuntimeError('Website export UI unavailable')


def public_receipts(_: dict) -> dict:
    # Demonstration-only fixture, not a real user's bills or live site.
    return {'amounts': [350.0, 150.0, 200.0], 'source': 'fixture-receipt-view'}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--store', default='run/skills.json')
    args = parser.parse_args()
    tools = [
        Tool('a_website_export', 'Use official export UI', 'invoice_totals', primary_export),
        Tool('b_receipt_view', 'Use an allowed read-only receipt view', 'invoice_totals', public_receipts),
    ]
    plan = Plan('Collect invoice totals even if normal export is unavailable', 'invoice_totals', {}, {'count': 3, 'total': 700.0})
    result = Engine(tools, {'invoice_totals': numeric_total}, SkillStore(Path(args.store))).execute(plan)
    print(json.dumps(asdict(result), indent=2))

if __name__ == '__main__':
    main()
