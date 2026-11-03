"""One authorized run of all 33 remaining tasks; no retries or old-task repeats."""
import argparse
import asyncio
import json
from types import SimpleNamespace

from run_model_evaluation import ROOT, run


def preflight():
    suite = ROOT / 'evaluation/deepseek-20261019-remaining-v3'
    tasks = json.loads((suite / 'tasks.json').read_text(encoding='utf-8'))
    protocol = json.loads((suite / 'protocol.json').read_text(encoding='utf-8'))
    old_tasks = json.loads((ROOT / 'evaluation/deepseek-20261019-v1/tasks.json').read_text(encoding='utf-8'))
    excluded = set(protocol['excluded_exposed_task_ids'])
    ids = {t['id'] for t in tasks}
    if len(tasks) != 33 or len(ids) != 33 or ids & excluded or ids | excluded != {t['id'] for t in old_tasks}:
        raise RuntimeError('Only the remaining 33 tasks are authorized in this run')
    if (suite / 'runs').exists() or (suite / 'latest-run.json').exists():
        raise RuntimeError('A run already started; automatic reruns are forbidden')
    return suite.name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true', help='Explicitly enable the authorized live API batch')
    parser.add_argument('--budget-usd', type=float, default=2.0)
    args = parser.parse_args()
    if not 0 < args.budget_usd <= 2.0:
        parser.error('Budget must be above zero and at most USD 2.00')
    suite = preflight()
    if not args.execute:
        print(json.dumps({'suite': suite, 'tasks': 33, 'maximum_requests': 99, 'live_requests': 0}))
        return
    asyncio.run(run(SimpleNamespace(suite=suite, limit=33, budget_usd=args.budget_usd)))


if __name__ == '__main__':
    main()
