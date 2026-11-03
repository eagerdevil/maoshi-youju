"""Per-request model tracing, with no credentials or private reasoning content."""
from contextvars import ContextVar
from contextlib import contextmanager
import json

_trace = ContextVar('model_trace', default=None)
_budget = ContextVar('model_budget', default=None)

class BudgetExceeded(ValueError):pass

@contextmanager
def budget(limit_usd):
    ledger={'limit_usd':limit_usd,'estimated_usd':0.0,'requests':0,
            'input_usd_per_million':0.3,'output_usd_per_million':1.2,
            'price_source':'https://api-docs.deepseek.com/quick_start/pricing/',
            'note':'按2026-10-19 Flash高峰公布价估算；不是服务商账单保证。未知用量按保守预留值计入。'}
    token=_budget.set(ledger)
    try:yield ledger
    finally:_budget.reset(token)

def reserve(body):
    ledger=_budget.get()
    if ledger is None:return None
    # Conservative byte count plus message framing; no request is made if reserve does not fit.
    inputs=len(json.dumps(body,ensure_ascii=False).encode('utf-8'))+1024
    outputs=body.get('max_tokens',4096)
    amount=(inputs*ledger['input_usd_per_million']+outputs*ledger['output_usd_per_million'])/1_000_000
    if ledger['estimated_usd']+amount>ledger['limit_usd']:raise BudgetExceeded('模型评测达到保守估算预算上限，已停止后续请求')
    ledger['estimated_usd']+=amount;ledger['requests']+=1
    return amount

def settle(reserved,usage):
    ledger=_budget.get()
    if ledger is None or reserved is None or not isinstance(usage,dict):return
    if not all(type(usage.get(k)) is int and usage[k]>=0 for k in ['prompt_tokens','completion_tokens']):return
    actual=(usage['prompt_tokens']*ledger['input_usd_per_million']+usage['completion_tokens']*ledger['output_usd_per_million'])/1_000_000
    ledger['estimated_usd']+=actual-reserved


@contextmanager
def capture():
    events=[]
    token=_trace.set(events)
    try: yield events
    finally: _trace.reset(token)


def record(event):
    events=_trace.get()
    if events is not None: events.append(event)
