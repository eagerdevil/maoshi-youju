"""Six reviewable Chinese PDFs, based on actual retained data and first model outputs."""
from pathlib import Path
import hashlib, html, json, shutil, sys
from datetime import datetime,timezone,timedelta
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.vendor'));sys.path.insert(0,str(ROOT))
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Table,TableStyle,Image,KeepTogether
from backend.analysis import Spec,analyse
from backend.diagnostics import diagnose
from backend import services

OUT=ROOT/'output/pdf';FINAL=ROOT/'参赛材料/0.5.0'
pdfmetrics.registerFont(TTFont('CJK','C:/Windows/Fonts/msyh.ttc',subfontIndex=0))
pdfmetrics.registerFont(TTFont('CJKB','C:/Windows/Fonts/msyhbd.ttc',subfontIndex=0))
styles=getSampleStyleSheet()
for name,size,leading,color in [('BodyX',10.5,18,'#334e44'),('TitleX',25,35,'#204c3d'),('HeadX',16,25,'#235b47'),('SubX',12,20,'#44694d'),('SmallX',8.5,14,'#72816c')]:
    styles.add(ParagraphStyle(name,fontName='CJKB' if name in {'TitleX','HeadX','SubX'} else 'CJK',fontSize=size,leading=leading,textColor=colors.HexColor(color),spaceAfter=10,wordWrap='CJK',splitLongWords=True))

def p(text,style='BodyX'):return Paragraph(html.escape(str(text)).replace('\n','<br/>'),styles[style])
def bullet(text):return p('· '+text)
def table(rows,widths):
    t=Table([[p(v,'SmallX') for v in row] for row in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf3e8')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor('#dce5d5')),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    return t

def footer(c,doc):
    c.setStrokeColor(colors.HexColor('#dce5d5'));c.line(48,42,A4[0]-48,42)
    c.setFont('CJK',8);c.setFillColor(colors.HexColor('#819074'))
    c.drawString(48,28,'贸势有据  /  赛道四  /  2026-10-19  /  核验稿')
    c.drawRightString(A4[0]-48,28,str(doc.page))

def write(name,title,pages):
    elements=[]
    for index,page in enumerate(pages):
        if index:elements.append(PageBreak())
        elements.extend([p('TRADE, WITH EVIDENCE','SmallX'),p(title if index==0 else page[0],'TitleX' if index==0 else 'HeadX')])
        content=page if index==0 else page[1:]
        for item in content:elements.append(item if not isinstance(item,str) else p(item))
    path=OUT/name
    SimpleDocTemplate(str(path),pagesize=A4,rightMargin=48,leftMargin=48,topMargin=43,bottomMargin=56,title=title,author='贸势有据项目').build(elements,onFirstPage=footer,onLaterPages=footer)
    return path

def main():
    OUT.mkdir(parents=True,exist_ok=True);FINAL.mkdir(parents=True,exist_ok=True)
    suite=ROOT/'evaluation/deepseek-20261019-v1'
    latest=json.loads((suite/'latest-run.json').read_text(encoding='utf-8'))
    summary=json.loads((ROOT/latest['summary']).read_text(encoding='utf-8'))
    run=(ROOT/latest['summary']).parent
    result=analyse(Spec(products=['8703']));d=diagnose(result)
    by={x['code']:x for x in result['partners']}
    fmt=lambda v:f'{v:,.2f}'
    width=A4[0]-96
    files=[]
    files.append(write('01-作品申报书与项目摘要-核验稿.pdf','贸势有据｜作品申报书与项目摘要',[
      [p('赛道四：数据分析与智能洞察','SubX'),p('来源清晰的数据、可追溯的解释、经得起换窗口核查的结论。','HeadX'),
       table([['申报信息','当前内容'],['团队规模','单人参赛；无指导教师'],['姓名、学号、学院、专业','待参赛者补齐；研究生在读身份须提交前核实'],['作品形态','本地交互应用、分析代码、数据与来源、分析报告、复算包'],['版本与状态','0.5.0核验稿；真实模型小规模试运行完成，独立语义评价与真人试用待完成']],[110,width-110]),
       p('项目摘要','HeadX'),p('经贸分析容易把金额增长误当作份额提高，把某个基期的结论推广到所有时期，或将缺失伙伴认定为退出。贸势有据以保留原始来源的多国贸易数据为基础，提供目标市场、双边贸易和多国表现比较。系统用确定性程序计算指标与分解，借助受限大模型选择工具和解释证据，再通过分析版本、引用与字段绑定约束数字输出。研究诊断固定报告期、比较不同基期，帮助使用者发现方向反转和覆盖不足。研究笔记、离线报告与独立复算包将分析过程转化为可核查成果。'),
       p('当前真实模型试运行仍发现协议与语义问题，已保留首轮失败并补充回归检查。系统定位为辅助研究与复核，不作为自动因果判断、实时贸易监测或经营决策替代。','SmallX')],
      ['问题、用户与创新',p('目标用户与任务','HeadX'),p('主要用户为国际经济贸易相关学生、研究者和案例教学参与者。核心任务是界定国家角色与商品口径，比较金额和份额，核查时间窗口，再形成附证据的研究结论。'),
       p('四项可检验的设计','HeadX'),bullet('角色明确：区分目标市场进口、双边报告流向、各国对世界总额；模型上下文只保留当前模式的有效参数。'),bullet('证据绑定：计算保存公式、输入记录、来源和数据指纹，跨窗口引用使用完整分析ID，模型数字由字段提取。'),bullet('结论核查：展示同一报告期下不同基期的方向，区分反转、方向一致与证据不足，缺失不补零。'),bullet('成果复现：研究笔记与数值快照分别保存，导出包能独立复算全部所选窗口和证据。'),
       p('与现有通用工具的关系','HeadX'),p('本项目强调特定经贸任务的角色、口径和复核流程。没有独立、充分的通用AI对照证据，不能据此宣称优于全部通用AI产品。两流程小规模试运行用于暴露检索和协议问题，尚不构成效果优越性的证明。')],
      ['完成情况与参赛边界',p('已形成的交付','HeadX'),bullet('真实数据：16,496条标准观测，两个数据包；160份WITS原始页面及来源指纹。内置样本覆盖2019至2023年，不能称为当前或全球完整数据。'),bullet('交互应用：三种分析模式、来源追溯、研究诊断、研究笔记、保存恢复、报告和复算导出、模型连接与试用记录。'),bullet('研究案例：美国乘用车进口来源变化，包含金额份额反向、加拿大跨窗口反转、缺失处理和对账残差分析。'),bullet('真实模型：DeepSeek连接和日本开发任务跑通；另按授权完成3题两流程、7次API请求的小规模对照，失败与错误如实保留。'),
       p('提交前必须补齐','HeadX'),bullet('核实参赛者信息及研究生身份；本人核对贡献与AI使用说明并理解核心方法。'),bullet('邀请3至5名真实目标用户，记录实际结果并进行独立观察；当前无正式真人成绩。'),bullet('由独立人员评价模型引用支持与国家角色；修复后模型还需新题验证，不能复用调试题冒充未见测试。'),bullet('参赛者本人录制5至8分钟真实演示MP4；本次提供六分钟讲稿，不把脚本当成已录视频。')]
    ]))
    figure=ROOT/'研究成果/美国乘用车主案例/figures'
    def img(name):
        im=Image(str(figure/name));im.drawHeight=im.imageHeight*width/im.imageWidth;im.drawWidth=width;return im
    files.append(write('02-主案例分析报告.pdf','美国乘用车进口来源变化：金额、份额与基期',[
      [p('研究问题与统计范围','HeadX'),p('以美国报告的HS8703乘用车进口为目标市场，比较2019至2023年的金额、供应伙伴份额及变化分量，并检查结论对基期选择的敏感性。金额为公开发布表换算后的名义美元，不代表数量、实际消费或质量。'),
       table([['指标','程序计算结果'],['2019年世界进口金额',fmt(result['summary']['baseline'])+' USD'],['2023年世界进口金额',fmt(result['summary']['current'])+' USD'],['金额变化',fmt(result['summary']['delta'])+' USD'],['区间增长率',fmt(result['summary']['growth'])+'%（未年化）'],['分类、数据与分析ID','H0；WITS/UN Comtrade；'+result['analysis_id']]],[155,width-155]),p('主要发现','HeadX'),p('韩国供应份额明显上升；日本金额增长但份额下降；加拿大在长窗口下降而在最近一年回升。几类结果说明，金额、相对份额和窗口长度必须分别判断。数据缺失与对账残差同样影响可解释范围。')],
      ['发现一｜金额增长不必然带来份额提高',img('01-金额与份额.png'),p('日本进口金额由'+fmt(by['JPN']['baseline'])+'变为'+fmt(by['JPN']['current'])+'美元，区间增长约'+fmt(by['JPN']['growth'])+'%，份额变化却为'+fmt(by['JPN']['share_change'])+'个百分点。韩国份额变化为+'+fmt(by['KOR']['share_change'])+'个百分点。','BodyX'),p('解释：当某供应国金额增速低于目标市场整体扩张时，金额可以增加而份额下降。这是相对分母的算术关系，不是竞争力的直接测量。证据：根分析E0058、E0061、E0121；完整记录见交互证据抽屉和复算包。','SmallX')],
      ['发现二｜分解变化，不越界解释原因',img('02-对称分解.png'),p('使用对称分解：金额变化 = 平均份额 × 市场总额变化 + 平均市场总额 × 份额变化。韩国金额增加约149.18亿美元，其中市场规模分量约36.87亿美元、份额分量约112.31亿美元。两项精确相加还原金额变化。'),p('该分解是描述性恒等式，不能把“市场分量”认定为实际需求冲击，或把“份额分量”认定为政策、产品质量或企业竞争力的因果效应。若要讨论原因，还需价格、数量、车型构成、汇率、政策事件和识别设计。','SmallX')],
      ['发现三｜换一个基期，方向可能改变',img('03-窗口敏感性.png'),p('固定报告期2023年，加拿大份额变化在2019为基期时约为-4.48个百分点，在2022为基期时约为+0.92个百分点。只挑一个窗口容易产生片面结论。'),p('研究诊断检查所有所选对象，不只检查金额变化前八名。方向依据未格式化值判断，极小非零值以科学计数法展示；窗口可以重叠，不能当作独立样本做显著性结论。单窗口不声明跨窗口稳定。','SmallX')],
      ['缺失、残差与建议',p('缺失与残差是研究内容','HeadX'),p('直布罗陀基期有记录，报告期未列示，因此不能补为零，不能认定退出或下降百分之百。根分析变化对账残差为-2,362,960美元，等于仅报告期有记录伙伴金额1,240,550美元减去仅基期有记录伙伴金额3,603,510美元。各期世界总额与已列示伙伴合计差均约20美元，变化残差不能一概解释为舍入。'),
       p('应用建议','HeadX'),bullet('对学生研究：同时报告金额、份额、窗口和缺失，避免把增长等同于相对表现改善。'),bullet('对案例教学：把“同一数据为何能形成不同表面结论”作为教学问题，要求附分母、公式和来源。'),bullet('对进一步行业研究：补齐数量、价格、车型及潜在影响因素，再提出可验证的机制假说，不能直接据此调整商业或政策决策。'),
       p('AI参与与复现','HeadX'),p('AI协助代码、检查和报告起草；应用内真实DeepSeek负责受限工具规划与证据解释，指标计算由确定性引擎完成。模型可能引用有效但说错国家角色，因此须独立复核。复算包提供原始页面、CSV、参数、代码、全部窗口证据与脚本，模型文本不属于确定性复算承诺。'),p('来源与检索','HeadX'),p('数据来自保留的WITS页面，其底层来源标注为UN Comtrade，H0分类，金额按公开表精度换算。源文件路径、URL、采集记录和SHA256见data/processed/*.manifest.json；主案例证据完整索引见离线HTML和研究诊断包。'),p('数据指纹：'+result['data_sha256'],'SmallX')]
    ]))
    files.append(write('03-AI工具与第三方资源使用说明.pdf','AI工具及第三方资源使用说明',[
      [p('AI的实际参与位置','HeadX'),table([['环节','实际作用与约束'],['开发与文稿','Codex对话助手协助实现代码、测试、数据处理脚本及材料初稿；具体宿主模型以会话记录为准。'],['应用内AI','DeepSeek官方兼容聊天API；请求名与响应模型名deepseek-flash，未锁定不可变权重版本。'],['数值与指标','由Decimal确定性引擎计算；模型只选择证据字段，不自行填写数值。'],['验证','规则测试使用明确的测试替身；真实API试运行另存，不混称为模型准确率。'],['人工复核','参赛者需核对方法、结论和贡献；独立语义评价及真人试用尚未完成。']],[100,width-100]),
       p('真实调用边界','HeadX'),p('本轮按授权仅运行3道题两种流程，实际7次API请求；不自动重试。此前另有连接检测与日本开发示例，首次协议失败和修改后的复测分别保留，不并入新题成绩。当前新增的有效参数筛选和提示修订只完成回归检查，本轮未追加真实调用复测。')],
      ['数据、软件与责任',p('第三方资源','HeadX'),table([['资源','使用方式'],['WITS / UN Comtrade','公开贸易页面、标准数据与来源记录；遵守原站点使用条款，保留归属与检索信息。'],['联合国伙伴参考表','修正公开页面伙伴链接异常、识别实体类型；原始页面不改。'],['Python / FastAPI / Pydantic / httpx','本地后端、参数校验、服务调用。'],['React / TypeScript / Vite / ECharts / Lucide','交互界面、可视化与图标。'],['ReportLab / Poppler','本次PDF生成及页面渲染检查。']],[150,width-150]),p('开源软件具体版本见requirements.txt和frontend/package-lock.json；许可证文件以各上游发行包为准。未声明拥有模型、数据或开源软件的原创权利。'),
       p('凭据、输出与不确定性','HeadX'),p('密钥仅保存于本地config.local.json，接口不返回密钥，源码包、模型日志和PDF不包含密钥。模型调用记录保存实际消息、响应正文、返回模型名、耗时和服务商报告的用量，不保存Authorization头或私有思考内容。引用有效不能保证语义正确。'),
       p('官方接口资料（2026-10-19核对）','HeadX'),p('https://api-docs.deepseek.com/guides/json_mode/\nhttps://api-docs.deepseek.com/api/create-chat-completion/\nhttps://api-docs.deepseek.com/quick_start/pricing/','SmallX')]
    ]))
    files.append(write('04-单人团队成员贡献说明-待补身份.pdf','单人参赛｜成员贡献说明（待本人核验）',[
      [table([['身份项','填写状态'],['参赛者姓名、学号、学院、专业','待本人补齐'],['团队规模','1人'],['指导教师','无'],['研究生在读身份','提交前核实；赛事要求至少包含1名研究生']],[150,width-150]),
       p('已发生的参赛者参与','HeadX'),bullet('提出参赛目标、选择赛道四，并要求支持跨国家与行业分析。'),bullet('确认应用功能方向，试用早期程序并反馈可用，授权继续完善。'),bullet('提供并授权配置DeepSeek服务，限定本轮只进行3题小规模真实评测。'),
       p('AI协助完成的部分','HeadX'),p('代码实现、自动测试、数据整理脚本、交互界面、研究诊断、评测工具与材料初稿由AI协助生成。不能把这些内容全部写为未经AI参与的个人手工开发。技术与研究判断的最终核验责任由参赛者承担。'),
       p('仍需本人完成并确认','HeadX'),p('核对代码与数据口径，理解分解方法与局限；组织真实用户试用及独立评价；核验每项结论、完善申报信息；录制并讲解真实演示。完成前不把上述计划写成已完成贡献。'),
       p('本人确认：________________    日期：________________','SubX'),p('这是依据当前会话整理的贡献核验稿，签署前应按本人实际工作修改。','SmallX')]
    ]))
    totals=summary['totals']
    rows=[['流程','任务数','协议失败','所需数字项命中','独立语义评价']]
    for group,label in [('pipeline','模型自行规划'),('fixed_evidence','预定证据直接解释')]:
        t=totals[group];rows.append([label,str(t['attempts']),str(t['protocol_failures']),f"{t['numeric_items_present_and_correct']} / {t['required_numeric_items']}",'0项完成'])
    files.append(write('05-真实模型试运行与用户试用方案.pdf','真实模型小规模试运行与用户试用方案',[
      [p('本轮实际范围','HeadX'),p('2026-10-19按用户授权，仅运行36道冻结任务中的3题；每题比较模型自行规划与预定证据直接解释两种流程。实际7次API请求，没有自动重试。三个任务是：多国咖啡出口因果边界、中国乘用车市场德国供应数值、以及多国咖啡出口错误前提。'),table(rows,[100,45,65,100,width-310]),
       p('如何解读这些数字','HeadX'),p('数字项命中指回答是否选择了要求的正确证据字段并返回绑定值；无数值要求的题不计入分母。它不是通用算术准确率，更不是语义正确率。基线获得预先确定的证据，跳过规划，属于检索流程消融，不代表普通AI产品的全部能力。模型语义评价尚待独立人员完成。'),
       p('费用与记录','HeadX'),p('API返回用量按已公布Flash高峰价保守估算，本批约'+f"{summary['budget']['estimated_usd']:.6f}"+'美元；未计算缓存折扣，不是实际账单保证。首次输出、失败和冻结指纹都已保留，剩余33题本轮未调用。','SmallX')],
      ['从失败中得到的改进',p('观察到的真实问题','HeadX'),bullet('多国比较的完整Spec带有非当前模式使用的默认reporter和partner，模型把无效默认值当作事实，产生错误澄清、对华或对美流向描述。'),bullet('模型将x0、x1等字段代码写进正文，虽然数字本身由字段绑定，却触发正文数字规则，系统拒绝展示。'),bullet('模型规划仍可能填写不适用的partners或base_years，确定性参数校验能阻止执行，但任务无法完成。'),
       p('本轮修复与未验证之处','HeadX'),p('模型上下文现仅保留当前模式的有效国家角色；增加合法参数示例、模式约束与正文中文表达要求。使用测试替身确认无效角色不再进入规划和解释上下文。按用户限制未再追加真实模型调用，因此修复后的模型成功率未知。原3题转为开发回归题，不能再次充当未见题。'),
       p('下一次独立评价','HeadX'),p('由未参与编写的人员按引用支持、角色准确、缺失处理、澄清充分性和过度因果解释逐项评价；保留分歧。新模型评测需新建版本并冻结未运行题，禁止覆盖本批失败。运行脚本核对冻结代码，当前修复代码与首轮不同，直接重跑旧版本会拒绝，需按版本管理新建题集。')],
      ['真实用户试用：计划，不是成绩',p('对象与标准任务','HeadX'),p('邀请3至5名经贸相关学生，自主参加，以匿名代号记录。每名参与者完成：一、判断日本金额与份额是否反向并找证据；二、比较加拿大两个基期；三、处理直布罗陀缺失并保存、导出结果。'),
       p('实施步骤','HeadX'),bullet('观察者说明仅测试工具使用，不考核参与者；匿名代号不填写姓名、学号或其他个人信息。'),bullet('在“试用与演示”选择真实参与者模式。开始任务后先独立操作，不阅读演示答案；完成后返回提交实际结果、阻碍和费力度。'),bullet('观察者核对数值、引用和实际导出文件，记录需要帮助的地方。系统自报完成不等于观察者验证成功。'),bullet('导出JSON记录，统计任务结果和中断原因；计时为起止墙钟时间，包含等待和中断。小样本只形成可用性反馈，不推断总体效果。'),
       p('当前事实','HeadX'),p('开发排练与真实参与者分别保存，自动浏览器验收属于开发排练。当前没有正式真人任务成绩，也没有独立观察者确认的结果。不能把作者或AI测试填成学生试用数据。')]
    ]))
    files.append(write('06-部署运行与六分钟演示讲稿.pdf','部署运行与六分钟现场演示',[
      [p('开发机与分发包','HeadX'),p('开发机已配置DeepSeek；分发包排除密钥与运行数据库，首次启动需自行配置服务。离线时基础计算、诊断、来源和复算仍可使用；实际AI解释依赖网络和模型服务。'),
       table([['步骤','操作'],['本机启动','双击启动应用.cmd，打开 http://127.0.0.1:8765'],['换机依赖','安装Python 3.11+；python -m pip install --target .vendor -r requirements.txt'],['运行','python -X utf8 run.py --open'],['DeepSeek配置','选择兼容接口；地址https://api.deepseek.com；模型deepseek-flash；密钥在本地密码框填写。'],['真实连接检测','保存配置后检测已保存连接，会产生实际API请求。通过只说明服务与JSON协议可用。'],['复算','解压研究诊断复算包，运行python reproduce_diagnostic.py。'],['参赛者要求','研究生身份、姓名等须核实；本人理解方法并讲解。']],[110,width-110]),
       p('演示前检查','HeadX'),p('先验证8765端口、浏览器、数据包、导出目录与账户余额；关闭无关窗口。不要展示密钥。对模型不可用准备真实错误说明及离线计算路线，不把预先写好的文字假装成实时回答。')],
      ['六分钟讲稿｜发现与核查',p('00:00至00:40｜提出问题','SubX'),p('“贸易额增长，是否就代表供应国表现改善？我们把这个容易误判的问题拆成金额、份额和基期。贸势有据服务于经贸学生和研究者，让每个判断都能追溯到输入与来源。”'),
       p('00:40至01:40｜日本的金额与份额','SubX'),p('载入美国乘用车案例、选择日本。“这里日本金额增长约2.37%，份额却下降约2.81个百分点。因为分母市场总体扩张更快。”点开证据，展示计算输入、分类、原始记录与来源。“这是相对变化，不足以证明竞争力降低。”'),
       p('01:40至02:40｜加拿大的基期反转','SubX'),p('进入研究诊断，搜索CAN。“以2019年为基期，份额下降约4.48个百分点；以2022年为基期，则上升约0.92个百分点。系统把两个窗口放在一起，防止只挑支持某结论的年份。”说明窗口重叠，不是统计显著性检验。'),
       p('02:40至03:20｜缺失不是退出','SubX'),p('选择GIB并展开记录。“基期有记录、报告期缺失，不能直接填零，也就不能声称退出或下降百分之百。系统保留不足，提示研究者补证据。”')],
      ['六分钟讲稿｜AI、交付与边界',p('03:20至04:30｜真实AI参与','SubX'),p('打开AI分析台，现场询问日本的金额与份额变化。展示实际工具、证据字段、模型名和耗时。“模型负责问题到工具、证据到解释；程序负责数值计算与绑定。”若失败，如实展示错误，不反复挑选成功结果掩盖失败。'),
       p('04:30至05:30｜成果可带走、可复算','SubX'),p('把加拿大核查发现加入研究笔记，保存并导出诊断包。“报告不是一段无法追溯的回答。接收者可以拿到参数、数据、证据和脚本，复算全部窗口；模型的自然语言仍需人工复核。”'),
       p('05:30至06:00｜展示验证与下一步','SubX'),p('“工程检查覆盖计算、缺失、接口与导出。真实DeepSeek小规模试运行也暴露了角色和协议问题，我们保留失败并改进。正式语义评价和真人试用仍在准备，不能把这些检查混称为AI准确率。”'),
       p('答辩备忘','HeadX'),bullet('为什么是赛道四？核心成果是有明确问题、数据口径、研究发现、交互核查与分析报告；AI是分析流程中的受限协作者。'),bullet('为什么不直接问通用AI？本项目提供专门的口径约束与证据复现流程，但尚无充分证据证明优于全部通用AI工具。'),bullet('为什么只有历史数据？明确定位为已保留样本的历史分析；更新年份需要完整同口径采集和覆盖校验，不能临时外推。'),
       p('交付状态','HeadX'),p('本次交付的是讲稿和录制路线，不是已完成的MP4。正式5至8分钟演示视频需参赛者本人操作与讲解后录制。')]
    ]))
    manifest={'date':'2026-10-19','version':'0.5.0','status':'核验稿，身份、真人试用、独立语义评价与MP4仍待补齐','files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'evaluation_run':summary['run_id']}
    (OUT/'materials-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    # Copy after generation; visual QA checks these exact bytes before delivery.
    for path in files:shutil.copy2(path,FINAL/path.name)
    shutil.copy2(OUT/'materials-manifest.json',FINAL/'materials-manifest.json')
    md='''# 提交前核验清单

- [ ] 补齐姓名、学号、学院、专业并核实研究生身份。
- [ ] 本人理解并核对代码、数值、研究边界和AI使用说明。
- [ ] 邀请真实目标用户，使用匿名试用入口记录实际结果，另由观察者核实。
- [ ] 由独立人员完成模型语义评价；小规模结果不得外推。
- [ ] 修复后的模型行为使用新题、新版本验证，保留旧失败。
- [ ] 依据六分钟讲稿录制5至8分钟真实MP4。
- [ ] 只提交去除密钥、数据库和个人信息的交付包。

单人参赛，无指导教师；申报书与贡献说明均为核验稿，不能跳过本人确认直接提交。
'''
    (FINAL/'提交前核验清单.md').write_text(md,encoding='utf-8')
    review=ROOT/'研究成果/真实模型试运行';review.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'output/model-smoke/first-failure.json',review/'日本开发例-首次失败.json')
    shutil.copy2(ROOT/'output/model-smoke/retry-01.json',review/'日本开发例-改进后复测.json')
    report_html='<html lang="zh-CN"><meta charset="utf-8"><title>真实模型小规模试运行</title><style>body{max-width:1000px;margin:40px auto;padding:20px;font:16px/1.8 system-ui;color:#284c3e}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7ef;padding:20px}</style><h1>真实模型小规模试运行：首次结果与局限</h1><p>仅3题、两流程、7次API请求；剩余33题未调用。结构合法不代表语义正确。独立语义评价尚未完成。</p><pre>'+html.escape(json.dumps({'totals':summary['totals'],'budget':summary['budget']},ensure_ascii=False,indent=2))+'</pre>'
    for path in sorted(run.glob('*.first.json')):
        payload=json.loads(path.read_text(encoding='utf-8'))
        report_html+='<h2>'+html.escape(payload['task_id']+' / '+payload['group'])+'</h2><p>状态：'+payload['status']+'</p><pre>'+html.escape(json.dumps({'claims':payload['answer'].get('claims'),'first_raw_outputs':[e.get('content') for e in payload['trace']],'number_checks':payload['number_checks']},ensure_ascii=False,indent=2))+'</pre>'
    report_html+='<h2>已发现的局限</h2><p>模型误读非当前模式的默认国家参数；正文出现含数字的字段名；规划参数不适用。有效引用和数值绑定无法自动保证贸易方向描述正确。首轮代码和输出已封存，修复后只做回归检查，本轮未追加真实调用。</p></html>'
    (review/'小规模试运行报告.html').write_text(report_html,encoding='utf-8')
    print(json.dumps({'pdfs':len(files),'output':str(FINAL),'evaluation_requests':summary['budget']['requests']},ensure_ascii=False))

if __name__=='__main__':main()
