"""Local, append-only usability observations. Rehearsals are separated from people."""
import json
import uuid
from datetime import datetime,timezone
from . import services
from .analysis import Spec
from .data import DataError

TASKS=[
    {'id':'amount-share','title':'辨认金额与份额的区别','instruction':'在美国乘用车案例中，判断日本的供应金额与份额是否同向变化，填写两项数值及至少一个证据编号。',
     'focus':'JPN','tab':'markets'},
    {'id':'window','title':'核查基期是否改变结论','instruction':'在研究诊断中搜索CAN，对照2019—2023与2022—2023两个窗口，写出加拿大的份额变化与判断边界。',
     'focus':'CAN','tab':'research'},
    {'id':'export','title':'交付一份可核查的结果','instruction':'检查直布罗陀的缺失情况，保存一条研究笔记并导出报告。填写文件名、证据编号和“能否认定退出”的理由。是否实际成功需观察者核实。',
     'focus':'GIB','tab':'markets'},
]

def database():
    conn=services.db()
    conn.execute('CREATE TABLE IF NOT EXISTS study_sessions(id TEXT PRIMARY KEY,alias TEXT,mode TEXT,created TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS study_events(id INTEGER PRIMARY KEY,session_id TEXT,created TEXT,payload TEXT)')
    return conn

def now():return datetime.now(timezone.utc).isoformat()

def tasks():return [t|{'spec':Spec(products=['8703']).model_dump()} for t in TASKS]

def create(alias,mode):
    sid=uuid.uuid4().hex
    with database() as conn:conn.execute('INSERT INTO study_sessions VALUES (?,?,?,?)',(sid,alias,mode,now()))
    return get(sid)

def get(sid):
    with database() as conn:
        row=conn.execute('SELECT alias,mode,created FROM study_sessions WHERE id=?',(sid,)).fetchone()
        if not row:raise DataError('试用记录不存在')
        events=[json.loads(r[0])|{'created_at':r[1]} for r in conn.execute('SELECT payload,created FROM study_events WHERE session_id=? ORDER BY id',(sid,))]
    return {'id':sid,'alias':row[0],'mode':row[1],'created_at':row[2],'events':events}

def append(sid,payload):
    session=get(sid)
    task_id=payload['task_id']
    if task_id not in {t['id'] for t in TASKS}:raise DataError('未知试用任务')
    events=session['events']
    starts=[e for e in events if e['kind']=='start']
    ends=[e for e in events if e['kind']=='submit']
    active=starts[-1] if starts and (not ends or starts[-1]['created_at']>ends[-1]['created_at']) else None
    if payload['kind']=='start':
        if active:raise DataError('请先提交当前任务结果，再开始下一项')
        if any(e['task_id']==task_id for e in ends):raise DataError('本会话该任务已有首次结果；重试请创建新会话')
    else:
        if not active or active['task_id']!=task_id:raise DataError('须先开始同一任务才能提交')
        elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(active['created_at'])).total_seconds()
        payload=payload|{'elapsed_seconds':round(max(0,elapsed),2),'outcome_source':'participant_self_report',
                         'observer_verified':False}
    with database() as conn:conn.execute('INSERT INTO study_events(session_id,created,payload) VALUES (?,?,?)',(sid,now(),json.dumps(payload,ensure_ascii=False)))
    return get(sid)

def export():
    with database() as conn:ids=[r[0] for r in conn.execute('SELECT id FROM study_sessions ORDER BY created')]
    sessions=[get(sid) for sid in ids]
    people=[s for s in sessions if s['mode']=='participant']
    return {'sessions':sessions,'counts':{'participant_sessions':len(people),'rehearsal_sessions':len(sessions)-len(people),
        'self_reported_task_submissions':sum(e['kind']=='submit' for s in people for e in s['events']),
        'independently_verified_results':0},
        'note':'会话数不等于独立人数；排练不计入真人成绩。耗时为服务器记录的起止墙钟时间，包含中断。自报完成不等于观察者验证成功。'}
