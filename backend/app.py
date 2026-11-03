from __future__ import annotations
import csv, io, json
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
import httpx
from .data import ROOT, DataError, datasets, catalogue
from .analysis import Spec, analyse
from . import services
from . import APP_VERSION
from .cases import cases
from .evidence_tools import ToolPlan, execute
from . import diagnostics
from . import study
from typing import Literal

app=FastAPI(title='贸势有据',version=APP_VERSION)

@app.middleware('http')
async def fresh_application_shell(request,call_next):
    response=await call_next(request)
    if request.url.path in {'/','/index.html'}:
        response.headers['Cache-Control']='no-store'
    return response

class ClientError(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:Literal['react','window','promise','chart']
    build:str=Field(max_length=32)
    message:str=Field(max_length=1200)
    stack:str=Field(default='',max_length=6000)
    component_stack:str=Field(default='',max_length=6000)

@app.post('/api/client-errors')
def client_error(body:ClientError):
    import re
    payload=body.model_dump()
    for key in ['message','stack','component_stack']:
        payload[key]=re.sub(r'sk-[A-Za-z0-9_-]{12,}','[credential removed]',payload[key])
    payload['created_at']=services.now()
    directory=ROOT/'output';directory.mkdir(exist_ok=True)
    with (directory/'client-errors.jsonl').open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(payload,ensure_ascii=False)+'\n')
    return {'recorded':True}

@app.exception_handler(DataError)
async def data_error(request,exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=422,content={'detail':str(exc)})

@app.get('/api/health')
def health(): return {'status':'ok','version':APP_VERSION,'ai':services.public_config()}

@app.get('/api/datasets')
def list_datasets(): return [{'id':m['dataset_id'],'name':m['name'],'records':m['records']} for m in datasets()]

@app.get('/api/cases')
def list_cases():
    available={m['dataset_id'] for m in datasets()}
    return [case for case in cases() if case['spec']['dataset_id'] in available]

@app.get('/api/datasets/{dataset_id}')
def dataset(dataset_id:str): return catalogue(dataset_id)

@app.post('/api/analyse')
def analysis(spec:Spec): return analyse(spec)

class SaveRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    spec:Spec
    title:str=Field(default='',max_length=160)
    note:str=Field(default='',max_length=5000)
    source_saved_id:str|None=Field(default=None,max_length=64)
    expected_analysis_id:str|None=Field(default=None,max_length=64)

class DiagnosticRequest(SaveRequest):
    base_years:list[int]|None=Field(default=None,min_length=1,max_length=6)

def document_result(body:SaveRequest):
    result=services.saved_get(body.source_saved_id) if body.source_saved_id else analyse(body.spec)
    if result['spec']!=body.spec.model_dump():raise DataError('保存记录与分析条件不一致')
    if body.expected_analysis_id and result['analysis_id']!=body.expected_analysis_id:raise DataError('数据或计算版本已变化，请重新分析后保存或导出')
    return result|{'saved_record':{'title':body.title.strip() or result.get('saved_record',{}).get('title') or result['title']+' · '+result['product_label'],'note':body.note}}

@app.post('/api/diagnostics')
def research_diagnostic(body:DiagnosticRequest):
    return diagnostics.diagnose(document_result(body),body.base_years)

@app.post('/api/diagnostics/{kind}')
def diagnostic_document(kind:str,body:DiagnosticRequest):
    if kind not in {'report','bundle'}:raise HTTPException(404,'不支持此导出类型')
    result=document_result(body)
    diagnostic=diagnostics.diagnose(result,body.base_years)
    if kind=='report':return HTMLResponse(diagnostics.report(diagnostic),headers={'Content-Disposition':'attachment; filename="research-diagnostic.html"'})
    return Response(services.export_diagnostic_zip(result,diagnostic),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="research-diagnostic.zip"'})

@app.post('/api/saved')
def save(body:SaveRequest): return services.save_analysis(document_result(body),body.title,body.note)

@app.get('/api/saved')
def saved(): return services.saved_list()

@app.get('/api/saved/{aid}')
def saved_one(aid:str): return services.saved_get(aid)

@app.post('/api/document/{kind}')
def document(kind:str,body:SaveRequest):
    result=document_result(body)
    if kind=='report':return HTMLResponse(services.report(result),headers={'Content-Disposition':'attachment; filename="trade-report.html"'})
    if kind=='bundle':return Response(services.export_zip(result),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="trade-reproduction.zip"'})
    raise HTTPException(404,'不支持此导出类型')

@app.post('/api/export/report')
def report(spec:Spec):
    return HTMLResponse(services.report(analyse(spec)),headers={'Content-Disposition':'attachment; filename="trade-report.html"'})

@app.post('/api/export/bundle')
def bundle(spec:Spec):
    return Response(services.export_zip(analyse(spec)),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="trade-reproduction.zip"'})

@app.get('/api/import/template')
def template():
    header='reporter,reporter_name,partner,partner_name,year,flow,product,product_name,classification,value_usd,status\n'
    return Response('\ufeff'+header,media_type='text/csv',headers={'Content-Disposition':'attachment; filename="trade-template.csv"'})

@app.post('/api/import')
async def import_data(file:UploadFile=File(...),name:str=Form(...),source_url:str=Form(...)):
    content=await file.read(12*1024*1024+1)
    return services.import_csv(content,name,source_url)

class ModelConfig(BaseModel):
    model_config=ConfigDict(extra='forbid')
    provider:str='none'
    base_url:str=Field(default='http://127.0.0.1:11434',max_length=500)
    model:str=Field(default='',max_length=200)
    api_key:str|None=Field(default=None,max_length=1000)

@app.get('/api/model')
def model(): return services.public_config()

@app.post('/api/model')
def set_model(body:ModelConfig): return services.set_config(body.model_dump())

@app.post('/api/model/test')
async def test_model():return await services.test_model_connection()

class StudyCreate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    alias:str=Field(pattern=r'^[A-Za-z0-9_-]{1,20}$')
    mode:Literal['rehearsal','participant']='rehearsal'

class StudyEvent(BaseModel):
    model_config=ConfigDict(extra='forbid')
    task_id:str=Field(max_length=40)
    kind:Literal['start','submit']
    answer:str=Field(default='',max_length=2400)
    outcome:Literal['completed','blocked','not_attempted']='not_attempted'
    difficulty:str=Field(default='',max_length=1200)
    effort:int|None=Field(default=None,ge=1,le=5)

@app.get('/api/study/tasks')
def study_tasks():return study.tasks()

MATERIALS={
    'submission':'01-作品申报书与项目摘要.pdf',
    'analysis':'02-主案例分析报告.pdf',
    'ai-use':'03-AI工具与第三方资源使用说明.pdf',
    'contribution':'04-单人团队成员贡献说明.pdf',
    'evaluation':'05-测试结果与评价边界.pdf',
    'demo':'06-数据来源运行说明与演示讲稿.pdf',
}
MATERIALS_DIRECTORY = '参赛材料/0.5.4-提交版-20261103'

@app.get('/api/materials')
def materials():
    return [{'id':key,'name':name,'url':'/api/materials/'+key} for key,name in MATERIALS.items() if (ROOT/MATERIALS_DIRECTORY/name).is_file()]

@app.get('/api/materials/{key}')
def material(key:str):
    if key not in MATERIALS:raise HTTPException(404,'材料不存在')
    path=ROOT/MATERIALS_DIRECTORY/MATERIALS[key]
    if not path.is_file():raise HTTPException(404,'材料尚未生成')
    return FileResponse(path,media_type='application/pdf')

@app.get('/api/release-status')
def release_status():
    result={'version':APP_VERSION,'model':services.public_config(),'study':study.export()['counts'],
            'independent_semantic_review':'pending','materials':len(materials()),'real_evaluation':None,
            'answer_safeguards':{'version':'0.5.3','verification':'offline_regression_only','live_model_retest':'pending',
                'note':'四类回答约束已修复；下列真实模型评测来自旧冻结版本，不代表0.5.3的真实模型表现。'}}
    latest=ROOT/'evaluation/deepseek-20261019-v1/latest-run.json'
    if latest.exists():
        pointer=json.loads(latest.read_text(encoding='utf-8'))
        path=(ROOT/pointer['summary']).resolve()
        if not path.is_relative_to((ROOT/'evaluation').resolve()):raise DataError('评测结果路径无效')
        summary=json.loads(path.read_text(encoding='utf-8'))
        result['real_evaluation']={'tasks':summary['tasks_planned'],'requests':summary['budget']['requests'],
            'automatic_retries':summary['automatic_retries'],'totals':summary['totals'],'run_id':summary['run_id'],
            'note':'原始小规模首次结果，失败保留；修复后已见题回归另列，不证明语义正确率或优于通用AI。'}
    result['model_regression']=None
    latest=ROOT/'evaluation/deepseek-20261019-regression-v2/latest-run.json'
    if latest.exists():
        pointer=json.loads(latest.read_text(encoding='utf-8'))
        path=(ROOT/pointer['summary']).resolve()
        if not path.is_relative_to((ROOT/'evaluation').resolve()):raise DataError('评测结果路径无效')
        summary=json.loads(path.read_text(encoding='utf-8'))
        result['model_regression']={'tasks':summary['tasks_planned'],'requests':summary['budget']['requests'],
            'automatic_retries':summary['automatic_retries'],'totals':summary['totals'],'run_id':summary['run_id'],
            'note':'修复后原三题真实回归，属于已见题；正文仍有措辞问题，独立语义评价待完成。'}
    result['remaining_evaluation']=None
    latest=ROOT/'evaluation/deepseek-20261019-remaining-v3/latest-run.json'
    if latest.exists():
        pointer=json.loads(latest.read_text(encoding='utf-8'))
        path=(ROOT/pointer['summary']).resolve()
        if not path.is_relative_to((ROOT/'evaluation').resolve()):raise DataError('评测结果路径无效')
        summary=json.loads(path.read_text(encoding='utf-8'))
        if summary.get('finished_at'):
            rows=summary['results']
            result['remaining_evaluation']={'tasks':summary['tasks_planned'],'requests':summary['budget']['requests'],
                'automatic_retries':summary['automatic_retries'],'totals':summary['totals'],'run_id':summary['run_id'],
                'statuses':{group:{status:sum(r['group']==group and r['status']==status for r in rows)
                    for status in ['answered','clarification','failed']} for group in summary['groups']},
                'pipeline_expected_status_matches':sum(r['group']=='pipeline' and r['clarification_status_matches'] is True for r in rows),
                'report_url':'/api/evaluation-report/remaining' if (ROOT/'研究成果/真实模型试运行/剩余三十三题测试报告.html').is_file() else None,
                'note':'剩余33题首次真实运行；与开发题共享模板，不是独立盲测。独立语义评价待完成。'}
    result['ai_semantic_review']=None
    latest=ROOT/'evaluation/ai-semantic-review-20261019-v1/latest-run.json'
    if latest.exists():
        pointer=json.loads(latest.read_text(encoding='utf-8'))
        path=(ROOT/pointer['summary']).resolve()
        if not path.is_relative_to((ROOT/'evaluation').resolve()):raise DataError('评测结果路径无效')
        summary=json.loads(path.read_text(encoding='utf-8'))
        if summary.get('finished_at'):
            result['ai_semantic_review']={'responses':len(summary['results']),'requests':summary['budget']['requests'],
                'statuses':summary['statuses'],'ai_verdicts':summary['ai_verdicts'],
                'review_type':summary['review_type'],'human_semantic_reviews_completed':0,
                'report_url':'/api/evaluation-report/ai-semantic' if (ROOT/'研究成果/真实模型试运行/AI辅助语义评价报告.html').is_file() else None,
                'note':'同模型AI辅助复核，已观察到漏判；AI通过不代表人工确认。独立人工语义评价仍待完成。'}
    result['targeted_retest']=None
    latest=ROOT/'evaluation/deepseek-20261019-targeted-v4/latest-run.json'
    if latest.exists():
        pointer=json.loads(latest.read_text(encoding='utf-8'))
        path=(ROOT/pointer['summary']).resolve()
        if not path.is_relative_to((ROOT/'evaluation').resolve()):raise DataError('评测结果路径无效')
        summary=json.loads(path.read_text(encoding='utf-8'))
        if summary.get('finished_at'):
            result['targeted_retest']={'version':summary['app_version'],'cases':summary['cases_planned'],
                'requests':summary['budget']['requests'],'totals':summary['totals'],'statuses':summary['statuses'],
                'automatic_retries':summary['automatic_retries'],'run_id':summary['run_id'],
                'report_url':'/api/evaluation-report/targeted' if (ROOT/'研究成果/真实模型试运行/0.5.3针对性复测报告.html').is_file() else None,
                'semantic_review':'pending','note':'已见问题定向复测，规则答复与模型答复分别统计；机械通过不代表语义正确，正文仍有措辞问题。'}
            result['answer_safeguards'].update(verification='targeted_live_retest_completed',live_model_retest='completed_targeted',
                note='0.5.3已完成13份已见问题针对性复测，规则答复与模型答复分开；较早试运行仍为旧冻结版本。机械通过不等于语义正确，独立人工评价仍待完成。')
    result['wording_and_presentation']={'version':'0.5.4','verification':'offline_replay',
        'live_model_retest':'not_run','note':'新增单位混用提示和补充分析折叠；保留原始文本。0.5.3定向真实复测属于历史冻结版本。'}
    return result

@app.get('/api/evaluation-report/{key}')
def evaluation_report(key:str):
    reports={'remaining':'剩余三十三题测试报告.html','ai-semantic':'AI辅助语义评价报告.html','targeted':'0.5.3针对性复测报告.html'}
    if key not in reports:raise HTTPException(404,'评测报告不存在')
    path=ROOT/'研究成果/真实模型试运行'/reports[key]
    if not path.is_file():raise HTTPException(404,'评测报告尚未生成')
    return FileResponse(path,media_type='text/html; charset=utf-8')

@app.post('/api/study/sessions')
def create_study(body:StudyCreate):return study.create(body.alias,body.mode)

@app.get('/api/study/export')
def export_study():
    return Response(json.dumps(study.export(),ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':'attachment; filename="usability-records.json"'})

@app.get('/api/study/sessions/{sid}')
def get_study(sid:str):return study.get(sid)

@app.post('/api/study/sessions/{sid}/events')
def add_study_event(sid:str,body:StudyEvent):
    if body.kind=='submit' and not body.answer.strip():raise DataError('请填写实际结果或未完成的原因')
    if body.kind=='submit' and body.outcome=='not_attempted':raise DataError('提交时请选择实际完成状态')
    return study.append(sid,body.model_dump())

class AskRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    question:str=Field(min_length=1,max_length=1600)
    spec:Spec
    expected_analysis_id:str|None=Field(default=None,max_length=64)

class ToolRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    spec:Spec
    plan:ToolPlan
    expected_analysis_id:str|None=Field(default=None,max_length=64)

def current_result(body):
    result=analyse(body.spec)
    if body.expected_analysis_id and body.expected_analysis_id!=result['analysis_id']:
        raise DataError('数据或计算版本已变化，请重新分析')
    return result

@app.post('/api/tools/execute')
def calculation_tool(body:ToolRequest):
    return execute(current_result(body),body.plan)

@app.post('/api/ai/ask')
async def ask(body:AskRequest):
    try: return await services.ask_ai(body.question,current_result(body))
    except DataError: raise
    except httpx.HTTPError: raise HTTPException(502,'模型服务连接或调用失败，请检查地址、模型和凭据。')
    except (ValueError,KeyError,TypeError,IndexError): raise HTTPException(502,'模型返回格式无效，未展示未经校验的回答。')

dist=ROOT/'frontend/dist'
if dist.exists(): app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')
else:
    @app.get('/')
    def missing_build(): return HTMLResponse('<h1>贸势有据</h1><p>请先构建frontend，再启动应用。</p>',status_code=503)
