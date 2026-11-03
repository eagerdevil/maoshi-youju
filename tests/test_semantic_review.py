import copy
import importlib
from pathlib import Path

import pytest


@pytest.fixture
def rubric(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    return importlib.import_module('semantic_review_common')


def all_pass(rubric):
    return {'criteria': {key: {'rating': 'pass', 'reason': '证据支持该项判断。', 'citations': ['A:E1']} for key in rubric.CRITERIA}}


def test_review_does_not_hide_failure_or_uncertainty(rubric):
    result = all_pass(rubric)
    result['criteria']['completeness']['rating'] = 'uncertain'
    assert rubric.validate_review(result, {'A:E1'})['overall'] == 'uncertain'
    result['criteria']['role_correct']['rating'] = 'fail'
    assert rubric.validate_review(result, {'A:E1'})['overall'] == 'fail'


def test_review_rejects_invented_citation_and_skipped_required_check(rubric):
    result = all_pass(rubric)
    with pytest.raises(ValueError, match='outside'):
        rubric.validate_review(result, set())
    result['criteria']['completeness']['rating'] = 'not_applicable'
    with pytest.raises(ValueError, match='cannot be not applicable'):
        rubric.validate_review(result, {'A:E1'})
    result = all_pass(rubric)
    del result['criteria']['role_correct']
    with pytest.raises(ValueError, match='six review criteria'):
        rubric.validate_review(result, {'A:E1'})
