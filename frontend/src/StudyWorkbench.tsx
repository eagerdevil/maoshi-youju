import { useEffect, useState } from "react";
type Obj = Record<string, any>;
async function api(path: string, body?: Obj) {
  const r = await fetch(
    "/api/study" + path,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {},
  );
  const d = await r.json();
  if (!r.ok) throw Error(typeof d.detail === "string" ? d.detail : "参数无效");
  return d;
}
export default function StudyWorkbench({
  onLaunch,
}: {
  onLaunch: (c: Obj) => Promise<void>;
}) {
  const [tasks, setTasks] = useState<Obj[]>([]),
    [session, setSession] = useState<Obj | null>(null);
  const [alias, setAlias] = useState("P001"),
    [mode, setMode] = useState("rehearsal"),
    [error, setError] = useState(""),
    [working, setWorking] = useState(false);
  const [answer, setAnswer] = useState(""),
    [outcome, setOutcome] = useState("completed"),
    [difficulty, setDifficulty] = useState(""),
    [effort, setEffort] = useState("3");
  const [materials, setMaterials] = useState<Obj[]>([]),
    [readiness, setReadiness] = useState<Obj | null>(null);
  useEffect(() => {
    fetch("/api/materials")
      .then((r) => r.json())
      .then(setMaterials)
      .catch(() => {});
    fetch("/api/release-status")
      .then((r) => r.json())
      .then(setReadiness)
      .catch(() => {});
    api("/tasks")
      .then(setTasks)
      .catch((e) => setError(e.message));
    const sid = localStorage.getItem("trade-study-session");
    if (sid)
      api("/sessions/" + sid)
        .then(setSession)
        .catch(() => localStorage.removeItem("trade-study-session"));
  }, []);
  async function act(action: () => Promise<void>) {
    setWorking(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setWorking(false);
    }
  }
  const starts = session?.events.filter((e: Obj) => e.kind === "start") || [],
    ends = session?.events.filter((e: Obj) => e.kind === "submit") || [];
  const last = starts.at(-1),
    end = ends.at(-1);
  const active =
    last && (!end || last.created_at > end.created_at) ? last : null;
  function launch(task: Obj) {
    return onLaunch({
      id: "study-" + task.id,
      title: task.title,
      spec: task.spec,
      focus: task.focus,
      tab: task.tab,
      question: "",
    });
  }
  return (
    <div className="study-workbench">
      <section className="panel">
        <h2>目前有哪些真实验证？</h2>
        {readiness?.answer_safeguards && <p className="muted">{readiness.answer_safeguards.note}</p>}
        {readiness?.targeted_retest && <div>
          <p>
            {readiness.targeted_retest.version}针对性复测：
            {readiness.targeted_retest.totals.mechanical_pass}/{readiness.targeted_retest.cases}份机械检查通过；
            规则答复{readiness.targeted_retest.totals.rule_answers}份，模型答复{readiness.targeted_retest.totals.live_model_answers}份，
            实际请求{readiness.targeted_retest.requests}次，自动重试{readiness.targeted_retest.automatic_retries}次。
            要求数值匹配{readiness.targeted_retest.totals.numeric_items_present_and_correct}/{readiness.targeted_retest.totals.required_numeric_items}。
          </p>
          <p className="muted">针对已见问题的开发复测；仍有百分比与百分点措辞混用，独立人工语义评价待完成。</p>
          {readiness.targeted_retest.report_url && <a className="button" href={readiness.targeted_retest.report_url} target="_blank" rel="noreferrer">查看0.5.3针对性复测报告</a>}
        </div>}
        <p className="muted">
          模型已配置不等于回答正确，开发排练不等于真人试用。
        </p>
        {readiness?.real_evaluation && (
          <p>
            真实模型小规模试运行：{readiness.real_evaluation.tasks}题，
            {readiness.real_evaluation.requests}次API请求，自动重试
            {readiness.real_evaluation.automatic_retries}
            次。独立语义评价尚未完成。
          </p>
        )}
        {readiness?.model_regression && (
          <p>
            修复后已见题回归：{readiness.model_regression.tasks}题、
            {readiness.model_regression.requests}次API请求，无自动重试。
            {Object.entries(readiness.model_regression.totals).map(([group, value]) => {
              const t = value as Obj;
              return <span key={group}> {group === "pipeline" ? "自动规划" : "固定证据"}：协议失败{t.protocol_failures}/{t.attempts}，要求数值匹配{t.numeric_items_present_and_correct}/{t.required_numeric_items}。</span>;
            })}
            <span className="muted">已见题结果不能代表泛化准确率；正文仍需人工核查。</span>
          </p>
        )}
        {readiness?.remaining_evaluation && (
          <div>
            <p>
              剩余题目首次真实测试：{readiness.remaining_evaluation.tasks}题、
              {readiness.remaining_evaluation.requests}次API请求，无自动重试。
              自动规划预期状态匹配{readiness.remaining_evaluation.pipeline_expected_status_matches}/{readiness.remaining_evaluation.tasks}。
            </p>
            {Object.entries(readiness.remaining_evaluation.totals).map(([group, value]) => {
              const t = value as Obj;
              const s = readiness.remaining_evaluation.statuses[group];
              return <p key={group}>
                {group === "pipeline" ? "自动规划" : "固定证据"}：正常回答{s.answered}、澄清{s.clarification}、失败{s.failed}；
                要求数值匹配{t.numeric_items_present_and_correct}/{t.required_numeric_items}。
              </p>;
            })}
            <p className="muted">越界题预期澄清；有效数值不代表正文完全正确。独立语义评价待完成。</p>
            {readiness.remaining_evaluation.report_url && <a className="button" href={readiness.remaining_evaluation.report_url} target="_blank" rel="noreferrer">查看33题完整报告与首次回答</a>}
          </div>
        )}
        {readiness?.ai_semantic_review && (
          <div>
            <p>
              AI辅助语义复核：{readiness.ai_semantic_review.responses}份记录、
              {readiness.ai_semantic_review.requests}次请求。
              AI判通过{readiness.ai_semantic_review.ai_verdicts.pass ?? 0}、
              不通过{readiness.ai_semantic_review.ai_verdicts.fail ?? 0}、
              不确定{readiness.ai_semantic_review.ai_verdicts.uncertain ?? 0}；
              原回答不可用{readiness.ai_semantic_review.statuses.no_usable_answer ?? 0}、
              评价协议失败{readiness.ai_semantic_review.statuses.reviewer_failed ?? 0}。
            </p>
            <p className="muted">同模型辅助评价已观察到漏判，不能代替独立人工评价；人工评价仍待完成。</p>
            {readiness.ai_semantic_review.report_url && <a className="button" href={readiness.ai_semantic_review.report_url} target="_blank" rel="noreferrer">查看AI辅助评价与分歧记录</a>}
          </div>
        )}
        <p className="muted">
          当前记录的参与者会话：{readiness?.study?.participant_sessions ?? "—"}
          ；独立核实结果：
          {readiness?.study?.independently_verified_results ?? "—"}
          。会话数不代表独立人数。
        </p>
        <div className="material-links">
          {materials.map((m) => (
            <a
              className="button"
              key={m.id}
              href={m.url}
              target="_blank"
              rel="noreferrer"
            >
              {m.name.replace(/\.pdf$/, "")}
            </a>
          ))}
        </div>
      </section>
      <section className="panel">
        <div className="eyebrow">OBSERVE THE ACTUAL WORK</div>
        <h2>记录真实使用过程</h2>
        <p className="muted">
          三个标准任务，保留实际答案、卡点与起止耗时。匿名代号仅用于本机记录，请勿填写姓名或其他个人信息。排练与参与者试用分别保存。
        </p>
        {error && (
          <div className="alert error" role="alert">
            {error}
          </div>
        )}
        {!session ? (
          <div className="study-create">
            <label>
              匿名代号
              <input
                aria-label="试用匿名代号"
                maxLength={20}
                value={alias}
                onChange={(e) => setAlias(e.target.value)}
              />
            </label>
            <label>
              记录类型
              <select
                aria-label="试用记录类型"
                value={mode}
                onChange={(e) => setMode(e.target.value)}
              >
                <option value="rehearsal">开发排练（不算真人成绩）</option>
                <option value="participant">真实参与者试用</option>
              </select>
            </label>
            <button
              className="button primary"
              disabled={working || !alias.trim()}
              onClick={() =>
                act(async () => {
                  const s = await api("/sessions", { alias, mode });
                  setSession(s);
                  localStorage.setItem("trade-study-session", s.id);
                })
              }
            >
              建立试用会话
            </button>
          </div>
        ) : (
          <div className="scope-box">
            {session.alias} ·{" "}
            {session.mode === "rehearsal" ? "开发排练" : "真实参与者试用"} ·
            已提交 {ends.length} / 3 项
            <button
              className="text-button"
              disabled={!!active || working}
              onClick={() => {
                setSession(null);
                localStorage.removeItem("trade-study-session");
              }}
            >
              新建另一会话
            </button>
          </div>
        )}
        <div className="study-tasks">
          {tasks.map((task: Obj) => {
            const done = ends.some((e: Obj) => e.task_id === task.id);
            return (
              <article key={task.id}>
                <span className="eyebrow">任务 {tasks.indexOf(task) + 1}</span>
                <h3>{task.title}</h3>
                <p>{task.instruction}</p>
                <button
                  className="button"
                  disabled={!session || !!active || done || working}
                  onClick={() =>
                    act(async () => {
                      setSession(
                        await api("/sessions/" + session!.id + "/events", {
                          kind: "start",
                          task_id: task.id,
                        }),
                      );
                      setAnswer("");
                      setDifficulty("");
                      await launch(task);
                    })
                  }
                >
                  {done ? "已保存首次结果" : "开始计时并打开任务"}
                </button>
              </article>
            );
          })}
        </div>
        <p className="muted">
          开始后会打开分析页面；完成操作后返回“试用与演示”填写实际结果。计时包含离开页面、中断和等待，不能直接称为净操作时间。
        </p>
        {active && (
          <div className="study-submit">
            <h3>
              当前任务：{tasks.find((t) => t.id === active.task_id)?.title}
            </h3>
            <p>
              开始于{" "}
              {new Date(active.created_at).toLocaleString("zh-CN", {
                timeZone: "Asia/Shanghai",
              })}
            </p>
            <label>
              实际答案或未完成原因
              <textarea
                aria-label="试用实际答案"
                value={answer}
                maxLength={2400}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="填写你实际得到的数值、证据和判断；不要复制演示讲稿。"
              />
            </label>
            <div className="study-create">
              <label>
                自报完成情况
                <select
                  aria-label="试用完成情况"
                  value={outcome}
                  onChange={(e) => setOutcome(e.target.value)}
                >
                  <option value="completed">自报已完成，待观察者核实</option>
                  <option value="blocked">未完成或遇到阻碍</option>
                </select>
              </label>
              <label>
                操作费力度
                <select
                  aria-label="操作费力度"
                  value={effort}
                  onChange={(e) => setEffort(e.target.value)}
                >
                  {[1, 2, 3, 4, 5].map((n) => (
                    <option key={n} value={n}>
                      {n}
                      {n === 1 ? " · 很轻松" : n === 5 ? " · 很费力" : ""}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              卡点与建议
              <textarea
                aria-label="试用卡点与建议"
                value={difficulty}
                maxLength={1200}
                onChange={(e) => setDifficulty(e.target.value)}
              />
            </label>
            <button
              className="button primary"
              disabled={working || !answer.trim()}
              onClick={() =>
                act(async () => {
                  setSession(
                    await api("/sessions/" + session!.id + "/events", {
                      kind: "submit",
                      task_id: active.task_id,
                      answer,
                      outcome,
                      difficulty,
                      effort: Number(effort),
                    }),
                  );
                  setAnswer("");
                  setDifficulty("");
                })
              }
            >
              提交本次实际结果
            </button>
          </div>
        )}
        {ends.length > 0 && (
          <div className="study-results">
            <h3>已记录的首次结果</h3>
            {ends.map((event: Obj) => (
              <div key={event.created_at}>
                <b>{tasks.find((t) => t.id === event.task_id)?.title}</b>
                <p>{event.answer}</p>
                <small>
                  {event.elapsed_seconds} 秒墙钟时间 ·{" "}
                  {event.outcome === "completed" ? "自报完成" : "遇到阻碍"} ·
                  未经独立观察者核实
                </small>
              </div>
            ))}
          </div>
        )}
        <a className="button" href="/api/study/export" download>
          导出本机匿名试用记录
        </a>
      </section>
      <section className="panel">
        <div className="eyebrow">A SIX-MINUTE STORY</div>
        <h2>六分钟现场演示路线</h2>
        <p className="muted">
          先展示发现与证据，再展示AI如何调用工具。演示内容不作为参与者试用答案或评测成绩。
        </p>
        <ol className="demo-route">
          <li>
            <b>00:00—00:40 · 一个容易误判的问题</b>
            <p>
              进口金额增长是否意味着供应份额提高？说明用户是经贸学生与研究者。
            </p>
          </li>
          <li>
            <b>00:40—01:40 · 日本：金额与份额反向</b>
            <p>
              打开美国乘用车案例，选择日本，查看金额、份额和两种变化分量，并展开来源证据。
            </p>
          </li>
          <li>
            <b>01:40—02:40 · 加拿大：换基期后结论反转</b>
            <p>
              进入研究诊断，搜索CAN，对照长窗口与最近一年。明确窗口重叠，不解释为显著性。
            </p>
          </li>
          <li>
            <b>02:40—03:20 · 缺失不是退出</b>
            <p>查看GIB缺失记录，解释为何系统拒绝补零。</p>
          </li>
          <li>
            <b>03:20—04:30 · 真实AI调用</b>
            <p>
              在AI分析台现场提问，展示实际模型、工具参数、绑定数值和引用。若服务失败，展示实际错误并继续确定性分析。
            </p>
          </li>
          <li>
            <b>04:30—05:30 · 把结论变成可核查成果</b>
            <p>
              加入研究笔记，保存并导出诊断复算包；解释对方能独立复算哪些内容。
            </p>
          </li>
          <li>
            <b>05:30—06:00 · 验证与边界</b>
            <p>
              区分自动测试、真实模型试运行与真人试用，准确说明尚未完成的独立语义评价。
            </p>
          </li>
        </ol>
        <p className="muted">
          单人参赛、无指导教师。申报材料已按本人信息填写，演示视频已提供；请在平台提交前由本人核对材料和视频。
        </p>
      </section>
    </div>
  );
}
