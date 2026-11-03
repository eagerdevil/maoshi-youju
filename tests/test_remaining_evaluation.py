"""The paid batch must exclude exposed tasks and must not silently repeat calls."""
import importlib
import json
from pathlib import Path
import sys

import pytest


@pytest.fixture
def batch(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    runner = importlib.import_module('run_remaining_evaluation')
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    original = tmp_path / 'evaluation/deepseek-20261019-v1'
    suite = tmp_path / 'evaluation/deepseek-20261019-remaining-v3'
    original.mkdir(parents=True)
    suite.mkdir(parents=True)
    tasks = [{'id': f'task-{i}'} for i in range(36)]
    (original / 'tasks.json').write_text(json.dumps(tasks), encoding='utf-8')
    (suite / 'tasks.json').write_text(json.dumps(tasks[3:]), encoding='utf-8')
    (suite / 'protocol.json').write_text(json.dumps({'excluded_exposed_task_ids': [t['id'] for t in tasks[:3]]}), encoding='utf-8')
    return runner, suite


def test_batch_requires_execute_and_refuses_silent_repeat(batch, monkeypatch, capsys):
    runner, suite = batch
    monkeypatch.setattr(sys, 'argv', ['run_remaining_evaluation.py'])
    def no_live_run(*args, **kwargs):
        pytest.fail('Dry run must not call the live runner')
    monkeypatch.setattr(runner, 'run', no_live_run)
    runner.main()
    assert json.loads(capsys.readouterr().out)['live_requests'] == 0
    (suite / 'runs').mkdir()
    with pytest.raises(RuntimeError, match='reruns are forbidden'):
        runner.preflight()


def test_batch_rejects_exposed_task_even_when_count_is_33(batch):
    runner, suite = batch
    tasks = json.loads((suite / 'tasks.json').read_text(encoding='utf-8'))
    tasks[0] = {'id': 'task-0'}
    (suite / 'tasks.json').write_text(json.dumps(tasks), encoding='utf-8')
    with pytest.raises(RuntimeError, match='Only the remaining 33'):
        runner.preflight()
