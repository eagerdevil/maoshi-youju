"""Run at most 60 same-model AI-assisted reviews, never claiming human review."""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.vendor'))
sys.path.insert(0, str(ROOT))
from backend import services, model_runtime
from semantic_review_common import validate_review

SUITE = ROOT / 'evaluation/ai-semantic-review-20261019-v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


async def run(args):
    if (SUITE / 'runs').exists():
        raise RuntimeError('A review run already started; automatic reruns are forbidden')
    for name, digest in read(SUITE / 'freeze.json')['files'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Frozen review input changed: ' + name)
    inputs = read(SUITE / 'inputs.json')
    protocol = read(SUITE / 'protocol.json')
    if len(inputs) != 66 or sum(e['availability'] == 'reviewable' for e in inputs) != 60:
        raise RuntimeError('Unexpected scope for authorized review')
    config = services.config()
    if urlparse(config['base_url']).hostname != 'api.deepseek.com' or config['model'] != 'deepseek-flash':
        raise RuntimeError('Budget estimate applies to the saved official DeepSeek Flash setup')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = SUITE / 'runs' / run_id
    out.mkdir(parents=True)
    with model_runtime.budget(args.budget_usd) as ledger:
        summary = {'run_id': run_id, 'review_type': 'same_model_ai_assisted_not_independent_human',
                   'started_at': datetime.now(timezone.utc).isoformat(), 'model': services.public_config(),
                   'automatic_retries': 0, 'human_semantic_reviews_completed': 0, 'budget': ledger, 'results': []}
        for index, entry in enumerate(inputs, 1):
            if services.config() != config:
                raise RuntimeError('Model configuration changed during review')
            started = perf_counter()
            trace, evaluation, error = [], None, None
            if entry['availability'] == 'no_usable_answer':
                status = 'no_usable_answer'
            else:
                try:
                    with model_runtime.capture() as trace:
                        raw = await services.complete([{'role': 'system', 'content': protocol['prompt']},
                            {'role': 'user', 'content': json.dumps(entry['packet'], ensure_ascii=False)}])
                    evaluation = validate_review(json.loads(raw), {e['id'] for e in entry['packet']['evidence']})
                    status = 'reviewed'
                except Exception as exc:
                    if isinstance(exc, model_runtime.BudgetExceeded):
                        raise
                    status = 'reviewer_failed'
                    error = {'type': type(exc).__name__, 'message': str(exc)[:1200]}
            payload = {'review_id': entry['review_id'], 'status': status, 'evaluation': evaluation, 'trace': trace,
                       'elapsed_ms': round((perf_counter() - started) * 1000), 'error': error}
            with (out / (entry['review_id'] + '.first.json')).open('x', encoding='utf-8') as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
            summary['results'].append({k: payload[k] for k in ['review_id', 'status', 'evaluation', 'elapsed_ms']})
            (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'{index:02d}/66 {entry["review_id"]}: {status}' + (' / ' + evaluation['overall'] if evaluation else ''), flush=True)
        summary['finished_at'] = datetime.now(timezone.utc).isoformat()
        summary['statuses'] = dict(Counter(r['status'] for r in summary['results']))
        summary['ai_verdicts'] = dict(Counter(r['evaluation']['overall'] for r in summary['results'] if r['evaluation']))
        (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        (SUITE / 'latest-run.json').write_text(json.dumps({'run_id': run_id, 'summary': (out / 'summary.json').relative_to(ROOT).as_posix()}, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'run_id': run_id, 'statuses': summary['statuses'], 'ai_verdicts': summary['ai_verdicts'], 'budget': ledger, 'human_reviews': 0}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--budget-usd', type=float, default=2.0)
    args = parser.parse_args()
    if not 0 < args.budget_usd <= 2.0:
        parser.error('Budget must be above zero and at most USD 2.00')
    if args.execute:
        asyncio.run(run(args))
    else:
        print('Dry run only. --execute is required for the authorized AI-assisted review.')
