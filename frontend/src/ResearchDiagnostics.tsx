import React, { useEffect, useState } from "react";
import {
  Download,
  RefreshCw,
  Search,
  ShieldCheck,
  ArrowUpRight,
  BookOpen,
} from "lucide-react";

type Obj = Record<string, any>;
const format = (v: string | number | null | undefined, digits = 3) => {
  if (v == null) return "数据不足";
  const value = Number(v);
  if (value !== 0 && Math.abs(value) < 0.5 * 10 ** -digits)
    return value.toExponential(2);
  return value.toLocaleString("zh-CN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
};
const stateClass = (state: string) =>
  state === "reversal"
    ? "amber"
    : state === "insufficient"
      ? "neutral"
      : "green";
const quadrantNames: Record<string, string> = {
  both_up: "金额与份额均上升",
  both_down: "金额与份额均下降",
  amount_up_share_down: "金额上升、份额下降",
  amount_down_share_up: "金额下降、份额上升",
  flat: "含持平",
  insufficient: "证据不足",
};
async function request(path: string, body: Obj) {
  const response = await fetch("/api/diagnostics" + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "诊断请求失败" }));
    throw Error(
      typeof error.detail === "string"
        ? error.detail
        : "诊断参数无效，请重新选择",
    );
  }
  return response;
}

export default function ResearchDiagnostics({
  result,
  Chart,
  nameOf,
  onEvidence,
  onAddNote,
  documentBody,
}: {
  result: Obj;
  Chart: React.ComponentType<any>;
  nameOf: (row: Obj) => string;
  onEvidence: (evidence: Obj) => void;
  onAddNote: (note: string) => void;
  documentBody: () => Obj;
}) {
  const [data, setData] = useState<Obj | null>(null);
  const [years, setYears] = useState<number[]>([]);
  const [working, setWorking] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [page, setPage] = useState(0);
  const [chosen, setChosen] = useState("");
  const [notice, setNotice] = useState("");
  const scope = {
    spec: result.spec,
    expected_analysis_id: result.analysis_id,
    source_saved_id: result.saved_record?.id || null,
  };
  useEffect(() => {
    let active = true;
    request("", scope)
      .then((r) => r.json())
      .then((d) => {
        if (!active) return;
        setData(d);
        setYears(d.base_years);
        setChosen(
          d.rows.find((r: Obj) => r.direction === "reversal")?.code ||
            d.rows[0]?.code ||
            "",
        );
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setWorking(false);
      });
    return () => {
      active = false;
    };
  }, [result.analysis_id]);
  async function calculate() {
    setWorking(true);
    setError("");
    setNotice("");
    try {
      const d = await (
        await request("", {
          ...scope,
          ...(years.length ? { base_years: years } : {}),
        })
      ).json();
      setData(d);
      setYears(d.base_years);
      setPage(0);
      if (!d.rows.some((r: Obj) => r.code === chosen))
        setChosen(d.rows[0]?.code || "");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setWorking(false);
    }
  }
  async function download(kind: string) {
    if (!data) return;
    setExporting(true);
    setError("");
    try {
      const response = await request("/" + kind, {
        ...documentBody(),
        base_years: data.base_years,
      });
      const url = URL.createObjectURL(await response.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download =
        kind === "bundle"
          ? "贸势有据-研究诊断复算包.zip"
          : "贸势有据-研究诊断报告.html";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
      setNotice("已导出当前诊断，包含全部对象和所选窗口。");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setExporting(false);
    }
  }
  function open(ref: string | null) {
    const e = data?.evidence.find((e: Obj) => e.id === ref);
    if (e) onEvidence(e);
  }
  if (!data)
    return (
      <section className="panel research-loading">
        <ShieldCheck size={26} />
        <h2>{working ? "正在核查各个时间窗口…" : "诊断暂不可用"}</h2>
        <p>计算沿用当前国家、商品、流向与分类，不调用模型。</p>
        {error && <div className="alert error">{error}</div>}
        {!working && (
          <button className="button" onClick={calculate}>
            重试诊断
          </button>
        )}
      </section>
    );
  const dirty = JSON.stringify(years) !== JSON.stringify(data.base_years);
  const query = search.trim().toLowerCase();
  const exactCode = data.rows.some((r: Obj) => r.code.toLowerCase() === query);
  const filtered = data.rows.filter(
    (r: Obj) =>
      (exactCode
        ? r.code.toLowerCase() === query
        : (nameOf(r) + r.name + r.code).toLowerCase().includes(query)) &&
      (filter === "all" ||
        (filter === "reversal" && r.direction === "reversal") ||
        (filter === "incomplete" && !r.complete) ||
        (filter === "consistent" &&
          ["positive", "negative", "flat"].includes(r.direction)) ||
        (filter === "divergent" &&
          ["amount_up_share_down", "amount_down_share_up"].includes(
            r.quadrant,
          ))),
  );
  const pages = Math.max(1, Math.ceil(filtered.length / 12));
  const visible = filtered.slice(page * 12, (page + 1) * 12);
  const selected = data.rows.find((r: Obj) => r.code === chosen);
  const competition = result.spec.mode === "competition";
  const chartValues = visible.flatMap((r: Obj) =>
    r.points.map((p: Obj) =>
      p.metric == null ? 0 : Math.abs(Number(p.metric)),
    ),
  );
  const range = Math.max(...chartValues, 0.01);
  const option = {
    aria: {
      enabled: true,
      description:
        "各对象在不同基期下的" +
        data.metric_label +
        "，灰色表示证据不足。表格提供相同数据及证据按钮。",
    },
    grid: { left: 98, right: 18, top: 12, bottom: 75 },
    tooltip: {
      renderMode: "richText",
      formatter: (params: Obj) => params.data.description,
    },
    xAxis: {
      type: "category",
      data: data.base_years.map((y: number) => y + "—" + result.spec.end_year),
      axisLabel: { fontSize: 11, color: "#657a77" },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    yAxis: {
      type: "category",
      inverse: true,
      data: visible.map(nameOf),
      axisLabel: { width: 85, overflow: "truncate", color: "#315649" },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    visualMap: {
      min: -range,
      max: range,
      calculable: false,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      itemWidth: 12,
      itemHeight: 160,
      text: ["上升", "下降"],
      inRange: { color: ["#c88960", "#f5f4ea", "#287b66"] },
      precision: 2,
    },
    series: [
      {
        type: "heatmap",
        data: visible.flatMap((r: Obj, y: number) =>
          r.points.map((p: Obj, x: number) => ({
            value: [x, y, p.metric == null ? 0 : Number(p.metric)],
            evidence_id: p.evidence_id,
            metric: p.metric,
            description: `${nameOf(r)}\n${p.base_year}—${p.end_year}\n${data.metric_label}：${format(p.metric)} ${data.unit}${p.metric == null ? "\n缺失或分母不可用，不补零" : ""}`,
            itemStyle: {
              borderColor: "#fff",
              borderWidth: 4,
              ...(p.metric == null ? { color: "#e5e8e4" } : {}),
            },
          })),
        ),
        label: {
          show: true,
          fontSize: 11,
          color: "#183b38",
          formatter: (p: Obj) =>
            p.data.metric == null ? "—" : format(p.data.metric, 2),
        },
        emphasis: { itemStyle: { borderColor: "#365c4d", borderWidth: 2 } },
      },
    ],
  };
  function addFinding() {
    if (!selected || !data) return;
    const refs = selected.points
      .filter((p: Obj) => p.evidence_id)
      .map((p: Obj) => p.evidence_id);
    onAddNote(`【研究诊断】${nameOf(selected)}（${selected.code}）：固定报告期${result.spec.end_year}，基期选择${data.base_years.join("、")}；${data.metric_label}判断为“${selected.direction_label}”，可计算窗口${selected.observed_windows}/${data.base_years.length}。${competition ? "当前分析窗口的金额与份额对照为“" + quadrantNames[selected.quadrant] + "”。" : "区间增长率未年化。"}窗口重叠，方向诊断不证明统计显著、因果关系或竞争力。
诊断ID：${data.diagnostic_id}
证据：${refs.join("；")}`);
  }
  return (
    <div className="research-diagnostics">
      <section className="panel diagnostic-intro">
        <div>
          <span className="eyebrow">CHECK THE CONCLUSION</span>
          <h2>换一个基期，结论还成立吗？</h2>
          <p>
            固定报告期，系统检查{data.metric_label}
            的方向。先核查，再形成研究判断。
          </p>
        </div>
        <span className="badge">
          <ShieldCheck size={14} />
          确定性诊断 · 无需模型
        </span>
      </section>
      <section className="panel diagnostic-controls">
        <div className="panel-heading">
          <div>
            <h2>选择比较窗口</h2>
            <p>
              最多六个基期，仅在当前分析区间内比较。报告期固定为{" "}
              {result.spec.end_year} 年。
            </p>
          </div>
          <button
            className="button primary"
            disabled={working || !years.length}
            onClick={calculate}
          >
            <RefreshCw size={15} className={working ? "spin" : ""} />
            {working ? "重新核查中…" : "更新诊断"}
          </button>
        </div>
        <div className="window-options" role="group" aria-label="研究诊断基期">
          {data.available_years.map((year: number) => (
            <label key={year}>
              <input
                type="checkbox"
                checked={years.includes(year)}
                disabled={
                  working || (!years.includes(year) && years.length >= 6)
                }
                onChange={(e) =>
                  setYears(
                    e.target.checked
                      ? [...years, year].sort((a, b) => a - b)
                      : years.filter((y) => y !== year),
                  )
                }
              />
              {year}—{result.spec.end_year}
            </label>
          ))}
        </div>
        {dirty && (
          <p className="diagnostic-pending" role="status">
            窗口选择已修改，点击“更新诊断”后查看和导出。
          </p>
        )}
        <small>
          以下结果对应基期 {data.base_years.join("、")}
          ；分类计数可能交叉，不能相加为总数。
        </small>
      </section>
      {error && (
        <div className="alert error" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="scope-box" role="status">
          {notice}
        </div>
      )}
      <div className="metric-grid diagnostic-counts">
        {[
          [
            "reversal",
            "窗口方向反转",
            data.counts.reversal,
            "不同基期出现正负两个方向",
          ],
          [
            "consistent",
            "所选窗口方向一致",
            data.counts.consistent,
            "全部可算且同升、同降或全持平",
          ],
          [
            "incomplete",
            "窗口覆盖不足",
            data.counts.incomplete,
            "缺失或指标分母不可用",
          ],
          [
            competition ? "divergent" : "all",
            competition ? "金额与份额反向" : "诊断对象",
            competition ? data.counts.divergent : data.counts.entities,
            competition ? "使用当前分析窗口" : "各国或所选商品分别核查",
          ],
        ].map(([key, title, value, note]) => (
          <button
            key={key}
            className={
              "metric-card " + (filter === key ? "diagnostic-selected" : "")
            }
            disabled={working || dirty}
            onClick={() => {
              setFilter(filter === key ? "all" : String(key));
              setPage(0);
            }}
          >
            <div className="metric-label">
              {title}
              <ArrowUpRight size={15} />
            </div>
            <strong>{value}</strong>
            <small>{note}</small>
          </button>
        ))}
      </div>
      <section className="panel diagnostic-matrix" aria-busy={working}>
        <div className="panel-heading">
          <div>
            <h2>
              窗口对照矩阵 <span className="count">{filtered.length}</span>
            </h2>
            <p>
              {data.metric_label} / {data.unit}
              。灰色表示证据不足；点击色块或证据编号可追溯计算。
            </p>
          </div>
          <div className="diagnostic-filter">
            <label>
              <Search size={15} />
              <input
                aria-label="搜索诊断对象"
                value={search}
                placeholder="国家、地区或商品"
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(0);
                }}
              />
            </label>
            <select
              aria-label="筛选诊断类型"
              value={filter}
              onChange={(e) => {
                setFilter(e.target.value);
                setPage(0);
              }}
            >
              <option value="all">全部对象</option>
              <option value="reversal">方向反转</option>
              <option value="consistent">方向一致</option>
              <option value="incomplete">覆盖不足</option>
              {competition && <option value="divergent">金额与份额反向</option>}
            </select>
          </div>
        </div>
        {visible.length ? (
          <>
            <Chart
              option={option}
              height={Math.max(220, visible.length * 38 + 100)}
              onClick={(p: Obj) => open(p.data?.evidence_id)}
            />
            <div className="diagnostic-table">
              <table>
                <thead>
                  <tr>
                    <th>对象</th>
                    {data.base_years.map((y: number) => (
                      <th key={y}>
                        {y}—{result.spec.end_year}
                      </th>
                    ))}
                    <th>方向诊断</th>
                    <th>可计算窗口</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((row: Obj) => (
                    <tr
                      key={row.code}
                      className={chosen === row.code ? "chosen" : ""}
                    >
                      <td>
                        <button
                          className="diagnostic-name"
                          onClick={() => setChosen(row.code)}
                        >
                          {nameOf(row)}
                          <small>{row.code}</small>
                        </button>
                      </td>
                      {row.points.map((point: Obj) => (
                        <td key={point.base_year}>
                          <span title={point.metric ?? "缺失或分母不可用"}>
                            {format(point.metric)}
                          </span>
                          <button
                            className="evidence-link"
                            disabled={!point.evidence_id}
                            aria-label={`${row.code} ${point.base_year}窗口证据`}
                            onClick={() => open(point.evidence_id)}
                          >
                            {point.evidence_id?.split(":")[1] || "未列示"}
                          </button>
                        </td>
                      ))}
                      <td>
                        <span
                          className={
                            "diagnostic-status " + stateClass(row.direction)
                          }
                        >
                          {row.direction_label}
                        </span>
                      </td>
                      <td>
                        {row.observed_windows} / {data.base_years.length}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <p className="diagnostic-empty">
            没有符合条件的对象，可以更换筛选或搜索词。
          </p>
        )}
        <div className="diagnostic-pagination">
          <small>
            共 {filtered.length}{" "}
            个对象，图表与表格显示同一页，每页十二项。宽表可左右滚动。
          </small>
          <div>
            <button
              className="button"
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
            >
              上一页
            </button>
            <span>
              {page + 1} / {pages}
            </span>
            <button
              className="button"
              disabled={page + 1 >= pages}
              onClick={() => setPage(page + 1)}
            >
              下一页
            </button>
          </div>
        </div>
      </section>
      {selected && (
        <section className="panel diagnostic-detail">
          <div className="panel-heading">
            <div>
              <h2>{nameOf(selected)} · 判断核查</h2>
              <p>点击上方表格的对象名称，查看对应发现。</p>
            </div>
            <button
              className="button"
              disabled={working || dirty}
              onClick={addFinding}
            >
              <BookOpen size={16} />
              加入研究笔记
            </button>
          </div>
          <p>
            <span
              className={"diagnostic-status " + stateClass(selected.direction)}
            >
              {selected.direction_label}
            </span>{" "}
            固定报告期为{result.spec.end_year}年，{selected.observed_windows} /{" "}
            {data.base_years.length}个所选窗口可计算{data.metric_label}。
          </p>
          {competition && (
            <div className="scope-box">
              当前分析基期 {result.spec.base_year}：
              {quadrantNames[selected.quadrant]}。
              {["amount_up_share_down", "amount_down_share_up"].includes(
                selected.quadrant,
              )
                ? "金额方向不能代替份额判断。"
                : "金额与份额须分别理解。"}
              {selected.primary?.evidence_id && (
                <button
                  className="evidence-link"
                  onClick={() => open(selected.primary.evidence_id)}
                >
                  核查依据
                </button>
              )}
            </div>
          )}
          <div className="diagnostic-point-grid">
            {selected.points.map((p: Obj) => (
              <button
                key={p.base_year}
                className="diagnostic-point"
                disabled={!p.evidence_id}
                onClick={() => open(p.evidence_id)}
              >
                <small>
                  {p.base_year}—{p.end_year} · {data.unit}
                </small>
                <strong>{format(p.metric)}</strong>
                <span>金额变化 {format(p.delta, 0)} USD</span>
              </button>
            ))}
          </div>
          <p className="muted">
            方向依据未格式化的计算值。诊断反映所选窗口的描述性差异，不能据此识别原因。
          </p>
        </section>
      )}
      <section className="panel diagnostic-export">
        <div>
          <h2>把核查过程带走</h2>
          <p>
            导出包含全部对象的离线报告，或附原始数据、窗口证据与复算脚本的资料包。搜索和分页不改变导出范围。
          </p>
        </div>
        <div>
          <button
            className="button"
            disabled={working || dirty || exporting}
            onClick={() => download("report")}
          >
            <Download size={16} />
            导出诊断报告
          </button>
          <button
            className="button primary"
            disabled={working || dirty || exporting}
            onClick={() => download("bundle")}
          >
            <Download size={16} />
            {exporting ? "正在导出…" : "导出诊断复算包"}
          </button>
        </div>
      </section>
      <section className="panel diagnostic-boundaries">
        <h2>如何理解这些结果</h2>
        <ul>
          {data.notes.map((note: string) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
        <small>
          诊断版本 {data.version} · 诊断ID {data.diagnostic_id} · 根分析{" "}
          {data.analysis_id}
        </small>
      </section>
    </div>
  );
}
