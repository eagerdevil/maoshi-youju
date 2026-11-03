import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import * as echarts from "echarts/core";
import { LineChart, BarChart, HeatmapChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  AriaComponent,
  VisualMapContinuousComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronRight,
  CircleHelp,
  Database,
  Download,
  ExternalLink,
  FileText,
  FolderOpen,
  Globe2,
  Layers3,
  LoaderCircle,
  PanelRightClose,
  Plus,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  X,
} from "lucide-react";
import "./style.css";
import ResearchDiagnostics from "./ResearchDiagnostics";
import StudyWorkbench from "./StudyWorkbench";
import DisplayBoundary from "./DisplayBoundary";
import {
  UI_BUILD,
  installDisplayErrorReporting,
  reportDisplayError,
} from "./displayErrors";

echarts.use([
  LineChart,
  BarChart,
  HeatmapChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  AriaComponent,
  VisualMapContinuousComponent,
  CanvasRenderer,
]);

type Spec = {
  dataset_id: string;
  mode: "competition" | "bilateral" | "comparison";
  reporter: string;
  reporters: string[];
  partner: string;
  flow: "M" | "X";
  products: string[];
  base_year: number;
  end_year: number;
};
type Obj = Record<string, any>;
const defaults: Spec = {
  dataset_id: "wits-core",
  mode: "competition",
  reporter: "USA",
  reporters: ["CHN", "DEU", "JPN"],
  partner: "CHN",
  flow: "M",
  products: ["0902"],
  base_year: 2019,
  end_year: 2023,
};
const modeNames = {
  competition: "目标市场竞争",
  bilateral: "双边贸易分析",
  comparison: "多国表现比较",
};
const palette = [
  "#27796b",
  "#c98258",
  "#4e7396",
  "#9a81a8",
  "#b29d58",
  "#718c7c",
];
const cnNames: Record<string, string> = {
  CHN: "中国",
  USA: "美国",
  DEU: "德国",
  JPN: "日本",
  GBR: "英国",
  IND: "印度",
  BRA: "巴西",
  CAN: "加拿大",
  FRA: "法国",
  ARG: "阿根廷",
  LKA: "斯里兰卡",
  VNM: "越南",
  IDN: "印度尼西亚",
  KEN: "肯尼亚",
  ITA: "意大利",
  KOR: "韩国",
  MEX: "墨西哥",
  ARE: "阿联酋",
  PAK: "巴基斯坦",
  MWI: "马拉维",
  POL: "波兰",
  NLD: "荷兰",
  AUS: "澳大利亚",
  CHE: "瑞士",
  BEL: "比利时",
  ESP: "西班牙",
  THA: "泰国",
  CIV: "科特迪瓦",
  COL: "哥伦比亚",
  TUR: "土耳其",
  ZAF: "南非",
  AUT: "奥地利",
  SWE: "瑞典",
  CZE: "捷克",
  HUN: "匈牙利",
  PRT: "葡萄牙",
  NZL: "新西兰",
};
const operandNames: Record<string, string> = {
  base: "基期金额 / USD",
  end: "报告期金额 / USD",
  M0: "基期市场总额 / USD",
  M1: "报告期市场总额 / USD",
  x0: "基期伙伴金额 / USD",
  x1: "报告期伙伴金额 / USD",
  s0: "基期伙伴份额 / %",
  s1: "报告期伙伴份额 / %",
  market_component: "市场规模变化分量 / USD",
  share_component: "供应份额变化分量 / USD",
  growth_percent: "区间增长率 / %",
  share_change_pp: "份额变化 / 百分点",
  contribution_pp: "对总增长的贡献 / 百分点",
  world: "世界总额 / USD",
  listed_sum: "列示伙伴合计 / USD",
  total_delta: "总额变化 / USD",
  comparable_delta: "可比伙伴变化合计 / USD",
  value: "金额合计 / USD",
};
const label = (p: Obj) => cnNames[p.code] || p.name;
const num = (v: number | null | undefined, d = 2) =>
  v == null
    ? "—"
    : v.toLocaleString("zh-CN", {
        maximumFractionDigits: d,
        minimumFractionDigits: d,
      });
function money(v: number | null | undefined) {
  if (v == null) return "—";
  const a = Math.abs(v);
  return a >= 1e8
    ? num(v / 1e8) + " 亿"
    : a >= 1e4
      ? num(v / 1e4) + " 万"
      : num(v);
}
const axisMoney = (v: number) =>
  Math.abs(v) >= 1e8
    ? num(v / 1e8, 1) + "亿"
    : Math.abs(v) >= 1e4
      ? num(v / 1e4, 0) + "万"
      : num(v, 0);
const signed = (v: number | null | undefined, d = 2) =>
  v == null ? "—" : (v > 0 ? "+" : "") + num(v, d);
async function api(path: string, body?: unknown) {
  const r = await fetch(
    "/api" + path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: "请求失败" }));
    throw Error(
      typeof e.detail === "string" ? e.detail : JSON.stringify(e.detail),
    );
  }
  return r.json();
}
function Chart({
  option,
  height = 280,
  onClick,
}: {
  option: Obj;
  height?: number;
  onClick?: (e: any) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [chartError, setChartError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    let c: ReturnType<typeof echarts.init> | undefined;
    let ro: ResizeObserver | undefined;
    const failed = (error: unknown) => {
      setChartError(true);
      reportDisplayError("chart", error);
    };
    const resize = () => {
      try {
        if (c && !c.isDisposed()) c.resize();
      } catch (error) {
        failed(error);
      }
    };
    try {
      const probe = document.createElement("canvas");
      try {
        if (!probe.getContext("2d"))
          throw new Error("浏览器未提供二维图表绘图能力");
      } finally {
        probe.width = 0;
        probe.height = 0;
      }
      c = echarts.init(ref.current);
      c.setOption(option);
      if (onClick) c.on("click", onClick);
      if (typeof ResizeObserver !== "undefined") {
        ro = new ResizeObserver(resize);
        ro.observe(ref.current);
      } else window.addEventListener("resize", resize);
      setChartError(false);
    } catch (error) {
      failed(error);
    }
    return () => {
      ro?.disconnect();
      window.removeEventListener("resize", resize);
      try {
        if (c && !c.isDisposed()) c.dispose();
      } catch (error) {
        reportDisplayError("chart", error);
      }
    };
  }, [option, retry]);
  return (
    <>
      <div
        ref={ref}
        style={{
          height,
          width: "100%",
          display: chartError ? "none" : undefined,
        }}
        role="img"
        aria-label={option.aria?.description || "贸易分析交互图表"}
      />
      {chartError && (
        <div className="chart-recovery" role="status">
          <p>图表暂时无法显示，数值明细和证据仍可查看。</p>
          <button
            className="button"
            onClick={() => {
              setChartError(false);
              setRetry((n) => n + 1);
            }}
          >
            重试图表
          </button>
        </div>
      )}
    </>
  );
}
function Button({ children, onClick, primary = false, disabled = false }: any) {
  return (
    <button
      className={"button " + (primary ? "primary" : "")}
      onClick={onClick}
      disabled={disabled}
    >
      {React.Children.map(children, (child, index) => (
        <span
          key={index}
          className={
            React.isValidElement(child) ? "button-part" : "button-label"
          }
        >
          {child}
        </span>
      ))}
    </button>
  );
}
function EvidenceTools({
  result,
  years,
  onEvidence,
}: {
  result: Obj;
  years: number[];
  onEvidence: (e: Obj) => void;
}) {
  const [partners, setPartners] = useState<string[]>([]);
  const [bases, setBases] = useState<number[]>([result.spec.base_year]);
  const [packet, setPacket] = useState<Obj | null>(null);
  const [working, setWorking] = useState(false);
  const [failure, setFailure] = useState("");
  async function calculate() {
    setWorking(true);
    setFailure("");
    setPacket(null);
    try {
      setPacket(
        await api("/tools/execute", {
          spec: result.spec,
          expected_analysis_id: result.analysis_id,
          plan: { tool: "window_compare", partners, base_years: bases },
        }),
      );
    } catch (e) {
      setFailure((e as Error).message);
    } finally {
      setWorking(false);
    }
  }
  return (
    <section className="tool-workbench">
      <h3>伙伴与时间窗口核查</h3>
      <p className="muted">
        直接调用计算工具，无需连接模型。报告期固定为 {result.spec.end_year}{" "}
        年；缺失保留为空。
      </p>
      {result.spec.mode === "competition" && (
        <label>
          指定供应伙伴（最多六个，可多选；留空显示变化最大的八个）
          <select
            aria-label="指定供应伙伴"
            multiple
            value={partners}
            onChange={(e) =>
              setPartners(
                Array.from(e.target.selectedOptions, (o) => o.value).slice(
                  0,
                  6,
                ),
              )
            }
          >
            {[...result.partners]
              .sort((a: Obj, b: Obj) => a.code.localeCompare(b.code))
              .map((p: Obj) => (
                <option key={p.code} value={p.code}>
                  {p.code} · {p.name}
                </option>
              ))}
          </select>
        </label>
      )}
      <p className="muted">
        已选伙伴：{partners.length ? partners.join("、") : "按金额变化排序"}
        ；宽表可左右滚动查看证据。
      </p>
      <div className="window-options" role="group" aria-label="比较窗口基期">
        {years
          .filter((y) => y < result.spec.end_year)
          .map((y) => (
            <label key={y}>
              <input
                type="checkbox"
                checked={bases.includes(y)}
                onChange={(e) =>
                  setBases(
                    e.target.checked
                      ? [...bases, y].sort().slice(0, 4)
                      : bases.filter((b) => b !== y),
                  )
                }
              />
              {y}—{result.spec.end_year}
            </label>
          ))}
      </div>
      <Button disabled={working || !bases.length} onClick={calculate}>
        {working ? "计算中…" : "核查所选窗口"}
      </Button>
      {failure && <div className="alert error">{failure}</div>}
      {packet?.windows.map((w: Obj) => (
        <div className="window-result" key={w.analysis_id}>
          <h4>
            {w.spec.base_year}—{w.spec.end_year}
          </h4>
          <small>分析版本 {w.analysis_id}</small>
          <div className="tool-table">
            <table>
              <thead>
                <tr>
                  <th>对象</th>
                  <th>基期 / USD</th>
                  <th>报告期 / USD</th>
                  <th>份额变化 / 百分点</th>
                  <th>证据</th>
                </tr>
              </thead>
              <tbody>
                {(w.comparisons.length ? w.comparisons : w.partners).map(
                  (p: Obj) => (
                    <tr key={p.code}>
                      <td>{p.name}</td>
                      <td>{num(p.baseline)}</td>
                      <td>{num(p.current)}</td>
                      <td>{num(p.share_change)}</td>
                      <td>
                        <button
                          className="evidence-link"
                          onClick={() =>
                            onEvidence(
                              packet.evidence.find(
                                (e: Obj) => e.id === p.evidence_id,
                              ),
                            )
                          }
                        >
                          {p.evidence_id.split(":")[1]}
                        </button>
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
          {w.unavailable_partners.length > 0 && (
            <p className="muted">
              该窗口未列示：{w.unavailable_partners.join("、")}
              。无法判断进入或退出。
            </p>
          )}
        </div>
      ))}
    </section>
  );
}

function App() {
  const [datasets, setDatasets] = useState<Obj[]>([]),
    [catalog, setCatalog] = useState<Obj | null>(null),
    [draft, setDraft] = useState<Spec>(defaults),
    [result, setResult] = useState<Obj | null>(null);
  const [busy, setBusy] = useState(true),
    [error, setError] = useState(""),
    [toast, setToast] = useState(""),
    [tab, setTab] = useState("overview"),
    [modal, setModal] = useState("");
  const [evidence, setEvidence] = useState<Obj | null>(null),
    [chosen, setChosen] = useState(""),
    [search, setSearch] = useState(""),
    [page, setPage] = useState(0),
    [indexed, setIndexed] = useState(false);
  const [model, setModel] = useState<Obj>({
      provider: "none",
      base_url: "http://127.0.0.1:11434",
      model: "",
      configured: false,
    }),
    [settings, setSettings] = useState<Obj>({});
  const [question, setQuestion] = useState(""),
    [answer, setAnswer] = useState<Obj | null>(null),
    [aiBusy, setAiBusy] = useState(false),
    [aiError, setAiError] = useState("");
  const [saved, setSaved] = useState<Obj[]>([]),
    [saveTitle, setSaveTitle] = useState(""),
    [analysisNote, setAnalysisNote] = useState(""),
    [caseStudies, setCaseStudies] = useState<Obj[]>([]),
    [uploadName, setUploadName] = useState(""),
    [sourceUrl, setSourceUrl] = useState(""),
    [file, setFile] = useState<File | null>(null);
  const [modelCheck, setModelCheck] = useState<Obj | null>(null);
  const [checkingModel, setCheckingModel] = useState(false);
  const activeAnalysis = useRef<string | null>(null);
  function restoreNotebook(r: Obj) {
    const annotation = r.saved_record;
    let cached: Obj = {};
    if (!annotation) {
      try {
        const parsed = JSON.parse(
          localStorage.getItem("trade-notebook:" + r.analysis_id) || "{}",
        );
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          if (typeof parsed.title === "string") cached.title = parsed.title;
          if (typeof parsed.note === "string") cached.note = parsed.note;
        }
      } catch {}
    }
    setSaveTitle(
      annotation?.title || cached.title || r.title + " · " + r.product_label,
    );
    setAnalysisNote(annotation?.note ?? cached.note ?? "");
    activeAnalysis.current = r.analysis_id;
  }
  function editNotebook(note: string, title = saveTitle) {
    setAnalysisNote(note);
    setSaveTitle(title);
    if (result) {
      try {
        localStorage.setItem(
          "trade-notebook:" + result.analysis_id,
          JSON.stringify({ title, note }),
        );
      } catch {}
    }
  }
  const dirty =
    !!result && JSON.stringify(draft) !== JSON.stringify(result.spec);
  const update = (patch: Partial<Spec>) =>
    setDraft((p) => ({ ...p, ...patch }));
  const notify = (t: string) => {
    setToast(t);
    setTimeout(() => setToast(""), 4500);
  };
  async function run(s = draft) {
    setBusy(true);
    setError("");
    try {
      const r = await api("/analyse", s);
      setResult(r);
      restoreNotebook(r);
      setChosen(
        r.partners.find((p: Obj) => p.code === "CHN")?.code ||
          r.partners[0]?.code ||
          "",
      );
      setEvidence(null);
      setPage(0);
      setSearch("");
      setAnswer(null);
      setAiError("");
      return r;
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    (async () => {
      try {
        const ds = await api("/datasets");
        setDatasets(ds);
        const id = ds.find((d: Obj) => d.id === "wits-core")?.id || ds[0]?.id;
        if (!id) throw Error("尚未导入数据，请先添加数据包。");
        const c = await api("/datasets/" + id);
        setCatalog(c);
        const s = {
          ...defaults,
          dataset_id: id,
          base_year: c.years[0],
          end_year: c.years.at(-1),
        };
        setDraft(s);
        await run(s);
      } catch (e) {
        setError((e as Error).message);
        setBusy(false);
      }
      try {
        setModel(await api("/model"));
      } catch {}
      try {
        setCaseStudies(await api("/cases"));
      } catch {}
    })();
  }, []);
  async function changeDataset(id: string) {
    try {
      setBusy(true);
      const c = await api("/datasets/" + id);
      setCatalog(c);
      const reps = c.reporters.map((r: Obj) => r.code);
      const s: Spec = {
        ...draft,
        dataset_id: id,
        reporter: reps[0],
        reporters: reps.slice(0, 3),
        partner: c.partners.find((p: Obj) => p.code !== reps[0])?.code || "CHN",
        products: [c.products[0].code],
        base_year: c.years[0],
        end_year: c.years.at(-1),
      };
      setDraft(s);
      await run(s);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function openEv(id: string) {
    const e =
      answer?.evidence?.find((e: Obj) => e.id === id) ||
      result?.evidence.find((e: Obj) => e.id === id);
    if (e) setEvidence(e);
  }
  async function openCase(c: Obj) {
    setBusy(true);
    setError("");
    try {
      const cat = await api("/datasets/" + c.spec.dataset_id);
      setCatalog(cat);
      setDraft(c.spec);
      const calculated = await run(c.spec);
      if (calculated) {
        if (c.focus) setChosen(c.focus);
        setTab(c.tab);
        setQuestion(c.question);
        notify("案例已加载；可继续修改条件探索");
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function documentBody() {
    return {
      spec: result!.spec,
      title: saveTitle,
      note: analysisNote,
      expected_analysis_id: result!.analysis_id,
      source_saved_id: result!.saved_record?.id || null,
    };
  }
  async function download(kind: string) {
    if (!result) return;
    setBusy(true);
    try {
      const r = await fetch("/api/document/" + kind, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(documentBody()),
      });
      if (!r.ok) {
        const e = await r.json();
        throw Error(e.detail);
      }
      const url = URL.createObjectURL(await r.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download =
        kind === "bundle" ? "贸势有据-复算包.zip" : "贸势有据-分析报告.html";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
      notify("已导出当前分析");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function ask(q = question) {
    if (!result || !q.trim()) return;
    setQuestion(q);
    setAiBusy(true);
    setAiError("");
    setAnswer(null);
    const requestedId = result.analysis_id;
    try {
      const response = await api("/ai/ask", {
        question: q,
        spec: result.spec,
        expected_analysis_id: requestedId,
      });
      if (activeAnalysis.current === requestedId) {
        if (response.analysis_id === requestedId) setAnswer(response);
        else setAiError("数据版本已变化，请重新分析后提问。");
      }
    } catch (e) {
      if (activeAnalysis.current === requestedId)
        setAiError((e as Error).message);
    } finally {
      setAiBusy(false);
    }
  }
  const r = result;
  const rows: Obj[] = r
    ? r.comparisons.length
      ? r.comparisons
      : r.partners
    : [];
  const selected = r?.partners.find((p: Obj) => p.code === chosen);
  const filtered = rows.filter((p) =>
    (p.name + p.code + (cnNames[p.code] || ""))
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const chartBase = {
    color: palette,
    animationDuration: 400,
    textStyle: { fontFamily: "Microsoft YaHei, sans-serif", color: "#667b75" },
    tooltip: { trigger: "axis", renderMode: "richText" },
    grid: { left: 63, right: 25, top: 25, bottom: 38 },
    xAxis: {
      type: "category",
      axisLine: { lineStyle: { color: "#dce6e0" } },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: "#edf1ed", type: "dashed" } },
      axisLabel: { color: "#85958e" },
    },
  };
  let lineOption: Obj = {};
  if (r) {
    const reps =
      r.spec.mode === "comparison" ? r.spec.reporters : [r.spec.reporter];
    lineOption = {
      ...chartBase,
      aria: { description: "按年份显示名义美元贸易金额；可切换为基期指数" },
      legend:
        reps.length > 1
          ? { bottom: 0, icon: "circle", itemWidth: 8 }
          : undefined,
      grid: { ...chartBase.grid, bottom: reps.length > 1 ? 56 : 35 },
      xAxis: { ...chartBase.xAxis, data: r.series.map((s: Obj) => s.year) },
      yAxis: {
        ...chartBase.yAxis,
        axisLabel: {
          formatter: (v: number) => (indexed ? num(v, 0) : axisMoney(v)),
        },
      },
      series: reps.map((code: string, i: number) => ({
        name: cnNames[code] || r.names[code] || code,
        type: "line",
        smooth: 0.25,
        symbol: "circle",
        symbolSize: 7,
        connectNulls: false,
        lineStyle: { width: 3 },
        itemStyle: { color: palette[i] },
        areaStyle:
          reps.length === 1
            ? {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                  { offset: 0, color: "#27796b26" },
                  { offset: 1, color: "#27796b00" },
                ]),
              }
            : undefined,
        data: r.series.map((s: Obj) => {
          const v = s.values[code];
          const base = r.series[0].values[code];
          return indexed
            ? v != null && base > 0
              ? (v / base) * 100
              : null
            : v;
        }),
      })),
    };
  }
  const ranked = [...rows]
    .filter((p) => p.delta != null)
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
    .slice(0, 8)
    .reverse();
  const barOption = {
    ...chartBase,
    aria: { description: "所选范围内金额变化最大的可比对象，按绝对变化选取" },
    grid: { left: 95, right: 28, top: 10, bottom: 35 },
    xAxis: {
      type: "value",
      splitLine: { lineStyle: { color: "#edf1ed" } },
      splitNumber: 3,
      axisLabel: { hideOverlap: true, formatter: axisMoney },
    },
    yAxis: {
      type: "category",
      data: ranked.map((p) => label(p)),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { width: 85, overflow: "truncate" },
    },
    series: [
      {
        type: "bar",
        barMaxWidth: 17,
        data: ranked.map((p) => ({
          value: p.delta,
          code: p.code,
          itemStyle: {
            color: p.delta >= 0 ? "#428977" : "#cc9273",
            borderRadius: [0, 3, 3, 0],
          },
        })),
      },
    ],
  };
  const decompOption = selected
    ? {
        ...chartBase,
        aria: { description: "所选供应国金额变化的市场规模与供应份额对称分解" },
        grid: { left: 112, right: 30, top: 10, bottom: 30 },
        xAxis: {
          type: "value",
          splitNumber: 3,
          axisLabel: { hideOverlap: true, formatter: axisMoney },
          splitLine: { lineStyle: { color: "#edf1ed" } },
        },
        yAxis: {
          type: "category",
          data: ["金额总变化", "市场规模分量", "供应份额分量"],
          axisLine: { show: false },
          axisTick: { show: false },
        },
        series: [
          {
            type: "bar",
            barMaxWidth: 22,
            data: [
              selected.delta,
              selected.market_component,
              selected.share_component,
            ].map((v, i) => ({
              value: v,
              itemStyle: {
                color: i === 0 ? "#183f36" : i === 1 ? "#6e9e86" : "#cf9c70",
                borderRadius: 3,
              },
            })),
          },
        ],
      }
    : {};
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setTab("overview");
          }}
        >
          <span className="brand-mark">
            <Activity size={22} />
          </span>
          <div>
            贸势有据<small>TRADE, WITH EVIDENCE</small>
          </div>
        </a>
        <div className="workspace-label">
          研究工作台 <span>LOCAL</span>
        </div>
        <nav>
          {[
            ["overview", TrendingUp, "分析总览"],
            ["markets", Globe2, "市场与结构"],
            ["research", ShieldCheck, "研究诊断"],
            ["study", Check, "试用与演示"],
            ["ai", Sparkles, "AI 分析台"],
            ["data", Database, "数据与来源"],
            ["methods", BookOpen, "方法与边界"],
          ].map(([key, Icon, text]: any) => (
            <button
              key={key}
              className={tab === key ? "nav-item active" : "nav-item"}
              onClick={() => setTab(key)}
            >
              <Icon size={18} />
              {text}
              {tab === key && <ChevronRight size={14} />}
            </button>
          ))}
        </nav>
        <div className="sidebar-line" />
        <button
          className="nav-item"
          onClick={async () => {
            try {
              setSaved(await api("/saved"));
              setModal("saved");
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          <FolderOpen size={18} />
          我的分析记录
        </button>
        <div className="sidebar-bottom">
          <div className="evidence-promise">
            <ShieldCheck size={22} />
            <strong>让每个结论，有据可查</strong>
            <p>
              真实数据 · 明确口径
              <br />
              证据追溯 · 分析复现
            </p>
          </div>
          <button
            className="nav-item"
            onClick={() => {
              setSettings({ ...model, api_key: undefined });
              setModal("model");
            }}
          >
            <Settings2 size={17} />
            模型连接{" "}
            <span className={"dot " + (model.configured ? "online" : "")} />
          </button>
          <div className="local-label">
            本地工作空间 <span>v{UI_BUILD}</span>
          </div>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div>
            <span>研究工作台</span>
            <ChevronRight size={13} />
            <b>
              {tab === "overview"
                ? "分析总览"
                : tab === "markets"
                  ? "市场与结构"
                  : tab === "study"
                    ? "试用与演示"
                    : tab === "research"
                      ? "研究诊断"
                      : tab === "ai"
                        ? "AI 分析台"
                        : tab === "data"
                          ? "数据与来源"
                          : "方法与边界"}
            </b>
          </div>
          <div>
            <span className="status-pill">
              <span className="dot online" />
              本地运行
            </span>
            <button
              className="icon-button"
              title="方法说明"
              onClick={() => setTab("methods")}
            >
              <CircleHelp size={19} />
            </button>
          </div>
        </header>
        <div className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                EXPLORE THE PATTERNS. TRACE THE EVIDENCE.
              </div>
              <h1>
                {tab === "data"
                  ? "可信分析，从数据开始"
                  : tab === "study"
                    ? "让价值，在实际使用中被看见"
                    : tab === "research"
                      ? "让结论，经得起核查"
                      : tab === "ai"
                        ? "带着问题，寻找证据"
                        : tab === "methods"
                          ? "清楚的方法，可信的解释"
                          : "看见贸易变化，理解市场格局"}
              </h1>
              <p>连接国家、行业与时间，让数据探索走向有依据的判断。</p>
            </div>
            <div className="heading-actions">
              <Button
                disabled={!r || busy}
                onClick={() => {
                  setModal("save");
                }}
              >
                <Plus size={16} />
                保存分析
              </Button>
              <Button
                primary
                disabled={!r || busy}
                onClick={() => download("report")}
              >
                <Download size={16} />
                导出报告
              </Button>
            </div>
          </div>
          {error && (
            <div className="alert error" role="alert">
              <span>{error}</span>
              <button onClick={() => setError("")} aria-label="关闭错误">
                <X size={16} />
              </button>
            </div>
          )}
          {tab === "overview" && caseStudies.length > 0 && (
            <section className="case-studies" aria-label="研究案例">
              <div className="case-heading">
                <span className="eyebrow">START WITH A QUESTION</span>
                <small>从一个真实问题开始，也可以在下方自由选择条件</small>
              </div>
              <div className="case-grid">
                {caseStudies.map((c, i) => (
                  <button
                    key={c.id}
                    disabled={busy}
                    onClick={() => openCase(c)}
                    className="case-card"
                  >
                    <span className="case-number">0{i + 1}</span>
                    <strong>{c.title}</strong>
                    <p>{c.description}</p>
                    <span className="case-action">
                      打开案例 <ArrowRight size={13} />
                    </span>
                  </button>
                ))}
              </div>
            </section>
          )}
          <section className="configuration">
            <div className="config-top">
              <div className="segmented">
                {(Object.keys(modeNames) as (keyof typeof modeNames)[]).map(
                  (m) => (
                    <button
                      key={m}
                      className={draft.mode === m ? "selected" : ""}
                      onClick={() =>
                        update({
                          mode: m,
                          flow: m === "competition" ? "M" : draft.flow,
                        })
                      }
                    >
                      {modeNames[m]}
                    </button>
                  ),
                )}
              </div>
              <span className="tiny">
                <Database size={13} />
                {catalog?.rows?.toLocaleString() || "—"} 条真实观测
              </span>
            </div>
            <div className="config-fields">
              <label>
                数据包
                <select
                  value={draft.dataset_id}
                  onChange={(e) => changeDataset(e.target.value)}
                  disabled={busy}
                >
                  {datasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </label>
              {draft.mode !== "comparison" && (
                <label>
                  {draft.mode === "competition" ? "目标进口市场" : "报告国"}
                  <select
                    value={draft.reporter}
                    onChange={(e) => update({ reporter: e.target.value })}
                  >
                    {catalog?.reporters.map((c: Obj) => (
                      <option key={c.code} value={c.code}>
                        {label(c)} · {c.code}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {draft.mode === "bilateral" && (
                <label>
                  贸易伙伴
                  <select
                    value={draft.partner}
                    onChange={(e) => update({ partner: e.target.value })}
                  >
                    {catalog?.partners
                      .filter((c: Obj) => c.code !== draft.reporter)
                      .map((c: Obj) => (
                        <option key={c.code} value={c.code}>
                          {label(c)} · {c.code}
                        </option>
                      ))}
                  </select>
                </label>
              )}
              {draft.mode !== "competition" && (
                <label>
                  贸易流向
                  <select
                    value={draft.flow}
                    onChange={(e) =>
                      update({ flow: e.target.value as "M" | "X" })
                    }
                  >
                    <option value="X">报告国出口</option>
                    <option value="M">报告国进口</option>
                  </select>
                </label>
              )}
              <label>
                基期
                <select
                  value={draft.base_year}
                  onChange={(e) => update({ base_year: +e.target.value })}
                >
                  {catalog?.years.map((y: number) => (
                    <option key={y}>{y}</option>
                  ))}
                </select>
              </label>
              <span className="year-arrow">
                <ArrowRight size={15} />
              </span>
              <label>
                报告期
                <select
                  value={draft.end_year}
                  onChange={(e) => update({ end_year: +e.target.value })}
                >
                  {catalog?.years.map((y: number) => (
                    <option key={y}>{y}</option>
                  ))}
                </select>
              </label>
              <Button primary disabled={busy || !catalog} onClick={() => run()}>
                {busy ? (
                  <LoaderCircle size={16} className="spin" />
                ) : (
                  <Search size={16} />
                )}
                开始分析
              </Button>
            </div>
            <div className="config-bottom">
              <span className="field-caption">商品范围</span>
              {catalog?.products.map((p: Obj) => (
                <button
                  className={
                    "chip " +
                    (draft.products.includes(p.code) ? "selected" : "")
                  }
                  key={p.code}
                  onClick={() =>
                    update({
                      products: draft.products.includes(p.code)
                        ? draft.products.filter((c) => c !== p.code)
                        : [...draft.products, p.code],
                    })
                  }
                >
                  {draft.products.includes(p.code) && <Check size={12} />}{" "}
                  <span className="chip-label">{p.name}</span>
                  <span>HS {p.code}</span>
                </button>
              ))}
              {draft.mode === "comparison" && (
                <>
                  <span className="config-divider" />
                  <span className="field-caption">比较国家</span>
                  {catalog?.reporters.map((p: Obj) => (
                    <button
                      key={p.code}
                      className={
                        "chip " +
                        (draft.reporters.includes(p.code) ? "selected" : "")
                      }
                      onClick={() =>
                        update({
                          reporters: draft.reporters.includes(p.code)
                            ? draft.reporters.filter((c) => c !== p.code)
                            : [...draft.reporters, p.code],
                        })
                      }
                    >
                      {label(p)}
                    </button>
                  ))}
                </>
              )}
            </div>
          </section>
          {dirty && (
            <div className="alert warning">
              筛选条件已修改。下方仍显示上一次分析，请点击“开始分析”更新。
            </div>
          )}
          {busy && !r && (
            <div className="empty">
              <LoaderCircle className="spin" />
              正在读取数据并计算…
            </div>
          )}
          {r && (
            <>
              <div className="analysis-context">
                <span className="section-label">
                  {modeNames[r.spec.mode as keyof typeof modeNames]}
                </span>
                <span>
                  {r.title} <span className="slash">/</span> {r.product_label}{" "}
                  <span className="slash">/</span> {r.spec.base_year}—
                  {r.spec.end_year}
                </span>
                <span className="verified">
                  <ShieldCheck size={13} />
                  {r.classification} · 名义美元
                </span>
              </div>
              {(tab === "overview" || tab === "markets") && (
                <>
                  <div className="metric-grid">
                    {(r.spec.mode === "comparison"
                      ? [
                          [
                            "比较报告国",
                            r.comparisons.length + " 个",
                            "各国分别计算，不作为全球总额",
                          ],
                          [
                            "商品范围",
                            r.spec.products.length + " 类",
                            r.product_label,
                          ],
                          [
                            "比较窗口",
                            r.spec.end_year - r.spec.base_year + " 年",
                            `${r.spec.base_year} → ${r.spec.end_year}`,
                          ],
                          [
                            "计算证据",
                            r.evidence.length + " 条",
                            "点击表格中的证据编号查看",
                          ],
                        ]
                      : [
                          [
                            "基期贸易金额",
                            money(r.summary.baseline),
                            r.spec.base_year + " 年 · USD",
                          ],
                          [
                            "报告期贸易金额",
                            money(r.summary.current),
                            r.spec.end_year + " 年 · USD",
                          ],
                          [
                            "金额变化",
                            r.summary.delta == null
                              ? "—"
                              : (r.summary.delta > 0 ? "+" : "") +
                                money(r.summary.delta),
                            "报告期 − 基期 · USD",
                          ],
                          [
                            "区间增长率",
                            r.summary.growth == null
                              ? "—"
                              : signed(r.summary.growth) + "%",
                            "基期为零或缺失时不计算",
                          ],
                        ]
                    ).map(([k, v, note], i) => (
                      <button
                        className={"metric-card " + (i === 1 ? "featured" : "")}
                        key={k}
                        onClick={() =>
                          r.summary.evidence_id && openEv(r.summary.evidence_id)
                        }
                      >
                        <div className="metric-label">
                          {k}
                          {i === 1 ? (
                            <ArrowUpRight size={17} />
                          ) : (
                            <span className="metric-index">0{i + 1}</span>
                          )}
                        </div>
                        <strong>{v}</strong>
                        <small>{note}</small>
                      </button>
                    ))}
                  </div>
                  <div className="chart-grid">
                    <section className="panel">
                      <div className="panel-heading">
                        <div>
                          <h2>时间里的变化</h2>
                          <p>
                            {indexed
                              ? "基期 = 100；基期为零或缺失时不生成指数"
                              : "贸易金额 / USD · 缺失年份保留断点"}
                          </p>
                        </div>
                        <div className="mini-toggle">
                          <button
                            className={!indexed ? "active" : ""}
                            onClick={() => setIndexed(false)}
                          >
                            金额
                          </button>
                          <button
                            className={indexed ? "active" : ""}
                            onClick={() => setIndexed(true)}
                          >
                            指数
                          </button>
                        </div>
                      </div>
                      <Chart option={lineOption} />
                    </section>
                    <section className="panel">
                      <div className="panel-heading">
                        <div>
                          <h2>
                            {r.spec.mode === "comparison"
                              ? "哪些国家变化更大？"
                              : r.spec.mode === "bilateral"
                                ? "哪些商品推动变化？"
                                : "哪些供应市场变化最大？"}
                          </h2>
                          <p>按金额变动绝对值选取前八项 · USD</p>
                        </div>
                        <span className="legend-dot" />
                      </div>
                      <Chart
                        option={barOption}
                        onClick={(e) => {
                          if (e.data?.code) {
                            setChosen(e.data.code);
                            setTab("markets");
                          }
                        }}
                      />
                    </section>
                  </div>
                  {r.spec.mode === "competition" && (
                    <section className="panel decomposition">
                      <div className="decomp-copy">
                        <span className="eyebrow">
                          BEYOND THE HEADLINE NUMBER
                        </span>
                        <h2>
                          增长来自市场，
                          <br />
                          还是供应份额？
                        </h2>
                        <p>
                          用对称分解拆开金额变化。两项精确相加，帮助区分市场扩张与份额调整。
                        </p>
                        <select
                          aria-label="选择供应国"
                          value={chosen}
                          onChange={(e) => setChosen(e.target.value)}
                        >
                          {r.partners.map((p: Obj) => (
                            <option key={p.code} value={p.code}>
                              {label(p)}
                            </option>
                          ))}
                        </select>
                        <button
                          className="text-button"
                          onClick={() =>
                            selected && openEv(selected.evidence_id)
                          }
                        >
                          查看计算依据 <ArrowRight size={14} />
                        </button>
                      </div>
                      <div className="decomp-chart">
                        {selected?.delta != null &&
                        selected?.market_component != null ? (
                          <>
                            <Chart option={decompOption} height={195} />
                            <div className="formula-note">
                              市场规模变化分量 + 供应份额变化分量 = 金额变化{" "}
                              <span>描述性分解，不代表因果影响</span>
                            </div>
                          </>
                        ) : (
                          <div className="empty">
                            该伙伴两期记录或分母不完整，无法分解；未将缺失当作零。
                          </div>
                        )}
                      </div>
                    </section>
                  )}
                  {tab === "markets" && r.structure && (
                    <section className="panel">
                      <div className="panel-heading">
                        <div>
                          <h2>市场结构与覆盖</h2>
                          <p>头部份额以世界总额为分母；整体HHI暂不输出</p>
                        </div>
                      </div>
                      <div className="structure-grid">
                        {["baseline", "current"].map((k) => {
                          const s = r.structure[k];
                          return (
                            <div key={k}>
                              <h3>{s.year} 年</h3>
                              <p>
                                已列示前三伙伴份额{" "}
                                <b>{num(s.listed_top3_share)}%</b>
                              </p>
                              <p>
                                已列示前五伙伴份额{" "}
                                <b>{num(s.listed_top5_share)}%</b>
                              </p>
                              <p>
                                伙伴合计 / 世界总额{" "}
                                <b>{num(s.coverage_pct)}%</b>
                              </p>
                              <p>
                                统计残差 / USD <b>{money(s.residual)}</b>
                              </p>
                              <button
                                className="text-button"
                                onClick={() => openEv(s.evidence_id)}
                              >
                                查看覆盖证据 <ArrowRight size={14} />
                              </button>
                            </div>
                          );
                        })}
                        <div>
                          <h3>为什么保留残差？</h3>
                          <p>
                            公开表存在舍入、未列示和特殊伙伴。两期可比伙伴变化合计与总变化的差额为{" "}
                            <b>{money(r.structure.change_residual)} USD</b>。
                          </p>
                          <p>{r.structure.current.hhi_reason}</p>
                          <button
                            className="text-button"
                            onClick={() =>
                              openEv(r.structure.residual_evidence_id)
                            }
                          >
                            查看变化对账 <ArrowRight size={14} />
                          </button>
                        </div>
                      </div>
                    </section>
                  )}
                  <section className="panel table-panel">
                    <div className="panel-heading">
                      <div>
                        <h2>
                          {r.spec.mode === "comparison"
                            ? "国家比较明细"
                            : r.spec.mode === "bilateral"
                              ? "商品构成明细"
                              : "供应市场明细"}{" "}
                          <span className="count">{rows.length}</span>
                        </h2>
                        <p>所有数值均由程序计算，证据编号可点击。</p>
                      </div>
                      <div className="table-search">
                        <Search size={15} />
                        <input
                          placeholder="搜索名称或代码"
                          value={search}
                          onChange={(e) => {
                            setSearch(e.target.value);
                            setPage(0);
                          }}
                        />
                      </div>
                    </div>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>对象 / 代码</th>
                            <th>{r.spec.base_year} 金额</th>
                            <th>{r.spec.end_year} 金额</th>
                            <th>金额变化</th>
                            <th>区间增长率</th>
                            {r.spec.mode === "competition" && (
                              <>
                                <th>份额变化 / pp</th>
                                <th>状态</th>
                              </>
                            )}
                            <th>证据</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filtered
                            .slice(page * 10, page * 10 + 10)
                            .map((p) => (
                              <tr
                                key={p.code}
                                className={
                                  chosen === p.code ? "highlight-row" : ""
                                }
                                onClick={() => setChosen(p.code)}
                              >
                                <td>
                                  <strong>{label(p)}</strong>
                                  <small>{p.code}</small>
                                </td>
                                <td>{money(p.baseline)}</td>
                                <td>{money(p.current)}</td>
                                <td
                                  className={
                                    p.delta > 0
                                      ? "positive"
                                      : p.delta < 0
                                        ? "negative"
                                        : ""
                                  }
                                >
                                  {p.delta == null
                                    ? "—"
                                    : (p.delta > 0 ? "+" : "") + money(p.delta)}
                                </td>
                                <td>
                                  {p.growth == null
                                    ? "—"
                                    : signed(p.growth) + "%"}
                                </td>
                                {r.spec.mode === "competition" && (
                                  <>
                                    <td>{signed(p.share_change)}</td>
                                    <td>
                                      <span className="row-status">
                                        {p.status === "unknown"
                                          ? "记录不完整"
                                          : p.status === "entry"
                                            ? "明确进入"
                                            : p.status === "exit"
                                              ? "明确退出"
                                              : "两期有记录"}
                                      </span>
                                    </td>
                                  </>
                                )}
                                <td>
                                  <button
                                    className="evidence-link"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      openEv(p.evidence_id);
                                    }}
                                  >
                                    {p.evidence_id}
                                    <ExternalLink size={11} />
                                  </button>
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                      {!filtered.length && (
                        <div className="empty">没有匹配的记录</div>
                      )}
                    </div>
                    <div className="table-footer">
                      <span>
                        金额单位：USD · 万 / 亿为中文缩写 · — 表示无法计算
                      </span>
                      <div>
                        <button
                          disabled={page === 0}
                          onClick={() => setPage((p) => p - 1)}
                        >
                          上一页
                        </button>
                        <span>
                          {page + 1} /{" "}
                          {Math.max(1, Math.ceil(filtered.length / 10))}
                        </span>
                        <button
                          disabled={(page + 1) * 10 >= filtered.length}
                          onClick={() => setPage((p) => p + 1)}
                        >
                          下一页
                        </button>
                      </div>
                    </div>
                  </section>
                  <div className="bottom-grid">
                    <section className="panel insight-panel">
                      <div className="panel-heading">
                        <h2>
                          <Layers3 size={17} />
                          计算摘要
                        </h2>
                        <span className="badge">程序生成</span>
                      </div>
                      {r.insights.length ? (
                        r.insights.map((i: Obj, j: number) => (
                          <div className="insight" key={j}>
                            <span>0{j + 1}</span>
                            <div>
                              <p>{i.text}</p>
                              {i.evidence_ids.map((id: string) => (
                                <button
                                  key={id}
                                  className="evidence-link"
                                  onClick={() => openEv(id)}
                                >
                                  {id}
                                  <ArrowRight size={12} />
                                </button>
                              ))}
                            </div>
                          </div>
                        ))
                      ) : (
                        <p>
                          各国分别展示，请结合比较明细和证据判断；缺失不作零值处理。
                        </p>
                      )}
                    </section>
                    <section className="panel ai-invite">
                      <Sparkles size={23} />
                      <h2>把下一步探索交给问题</h2>
                      <p>在当前分析范围内，调用工具、解释变化、追溯证据。</p>
                      <button className="button" onClick={() => setTab("ai")}>
                        进入 AI 分析台 <ArrowRight size={15} />
                      </button>
                      <small>
                        {model.configured
                          ? "模型已配置，调用状态以实际请求为准"
                          : "模型尚未连接 · 基础分析已可使用"}
                      </small>
                    </section>
                  </div>
                </>
              )}
              {tab === "study" && <StudyWorkbench onLaunch={openCase} />}
              {tab === "research" && (
                <fieldset className="diagnostic-fieldset" disabled={busy}>
                  <ResearchDiagnostics
                    key={r.analysis_id}
                    result={r}
                    Chart={Chart}
                    nameOf={label}
                    onEvidence={setEvidence}
                    documentBody={documentBody}
                    onAddNote={(note) => {
                      if (busy) return;
                      const next = analysisNote
                        ? analysisNote + "\n\n" + note
                        : note;
                      if (next.length > 5000) {
                        notify("研究笔记超过五千字，请先精简原有内容。");
                        return;
                      }
                      editNotebook(next);
                      notify("核查发现已加入下方研究笔记，可编辑后保存。");
                    }}
                  />
                </fieldset>
              )}
              {tab === "ai" && (
                <div className="ai-layout">
                  <section className="panel ai-work">
                    <div className="panel-heading">
                      <div>
                        <h2>
                          <Sparkles size={19} />
                          用问题连接分析
                        </h2>
                        <p>
                          回答固定在当前分析条件上。更换条件后，请重新发起问题。
                        </p>
                      </div>
                      <span className="badge">
                        {model.configured ? "模型已配置" : "模型未连接"}
                      </span>
                    </div>
                    <div className="scope-box">
                      {r.title} · {r.product_label} · {r.spec.base_year}—
                      {r.spec.end_year}
                    </div>
                    {!model.configured && (
                      <div className="model-notice">
                        <Settings2 size={23} />
                        <div>
                          <h3>连接模型后启用自然语言分析</h3>
                          <p>
                            支持本地 Ollama
                            或兼容聊天接口。当前没有运行大模型，不将计算摘要伪装为AI回答。
                          </p>
                          <Button
                            onClick={() => {
                              setSettings({ ...model, api_key: undefined });
                              setModal("model");
                            }}
                          >
                            配置模型连接
                          </Button>
                        </div>
                      </div>
                    )}
                    <EvidenceTools
                      key={r.analysis_id}
                      result={r}
                      years={catalog?.years || []}
                      onEvidence={setEvidence}
                    />
                    <div className="suggestions">
                      {[
                        "哪些伙伴推动了金额变化？",
                        "市场规模与供应份额各自起了什么作用？",
                        "现有数据能否证明竞争力增强？",
                      ].map((q) => (
                        <button
                          key={q}
                          onClick={() => {
                            setQuestion(q);
                            if (model.configured) ask(q);
                          }}
                        >
                          {q}
                          <ArrowUpRight size={13} />
                        </button>
                      ))}
                    </div>
                    <textarea
                      placeholder="输入你的分析问题…"
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                      maxLength={1600}
                    />
                    <div className="ask-footer">
                      <small>模型解释需人工复核；数字由计算工具提供。</small>
                      <Button
                        primary
                        disabled={
                          !model.configured || aiBusy || !question.trim()
                        }
                        onClick={() => ask()}
                      >
                        {aiBusy ? (
                          <LoaderCircle className="spin" size={16} />
                        ) : (
                          <Sparkles size={16} />
                        )}
                        分析问题
                      </Button>
                    </div>
                    {aiError && <div className="alert error">{aiError}</div>}
                    {answer && (
                      <div className="answer">
                        <div className="answer-meta">
                          {answer.model} ·{" "}
                          {answer.status === "clarification"
                            ? "待澄清"
                            : answer.status === "incomplete"
                              ? "模型解释不完整，请核查漏项"
                              : answer.response_origin === "scope_rules"
                                ? "当前范围说明"
                                : "工具调用完成"}
                        </div>
                        {answer.answer && <p>{answer.answer}</p>}
                        {answer.coverage?.required > 0 && (
                          <div>
                            <p className={answer.coverage.complete ? "muted" : "alert"}>
                              模型解释覆盖{answer.coverage.model_covered}/{answer.coverage.required}项要求数值。
                              以下核查表由程序读取证据生成，不是模型补答。
                            </p>
                            <details open={!answer.coverage.complete}>
                              <summary>查看全部要求数值与模型漏项</summary>
                              <div className="table-scroll">
                                <table>
                                  <thead><tr><th>对象</th><th>窗口</th><th>指标</th><th>证据数值</th><th>模型覆盖</th></tr></thead>
                                  <tbody>{answer.coverage.rows.map((n: Obj, i: number) => (
                                    <tr key={i}>
                                      <td>{n.object}</td><td>{n.base_year}—{n.end_year}</td>
                                      <td>{(operandNames[n.field] || n.field).split(" / ")[0]}</td>
                                      <td><button className="bound-number" onClick={() => openEv(n.citation)}>{n.value == null ? "数据不足" : num(Number(n.value))} {n.unit}</button></td>
                                      <td>{n.covered_by_model ? "已引用" : "模型漏项"}</td>
                                    </tr>
                                  ))}</tbody>
                                </table>
                              </div>
                            </details>
                          </div>
                        )}
                        {(answer.presentation?.wording_warnings?.length > 0) && <p className="alert">检测到可能的百分比与百分点混用，相关原文已标记待复核。增长率看百分比，份额差值看百分点。</p>}
                        {[{label: "", indices: answer.presentation?.primary_claim_indices ?? answer.claims?.map((_: Obj, i: number) => i) ?? []},
                          {label: "展开补充分析", indices: answer.presentation?.additional_claim_indices ?? []}].map((group, g) => {
                          const contents = group.indices.map((i: number) => {
                            const c = answer.claims[i];
                            const warning = answer.presentation?.wording_warnings?.find((w: Obj) => w.section === "claims" && w.index === i);
                            return (
                          <div key={i}>
                            {warning ? <div><p className="alert">{warning.message}</p><details><summary>查看待复核原文</summary><p>{c.text}</p></details></div> : <p>{c.text}</p>}
                            {c.numbers?.map((n: Obj, j: number) => (
                              <button
                                key={j}
                                className="bound-number"
                                onClick={() => openEv(n.citation)}
                              >
                                {(operandNames[n.field] ||
                                  (n.field === "result" ? "计算结果" : n.field)).split(" / ")[0]}
                                ：
                                {n.value == null
                                  ? "数据不足"
                                  : num(Number(n.value))}{" "}
                                {n.unit}
                              </button>
                            ))}
                            {c.citations.map((id: string) => (
                              <button
                                key={id}
                                className="evidence-link"
                                onClick={() => openEv(id)}
                              >
                                {id.includes(":")
                                  ? id.split(":")[1] +
                                    " · " +
                                    answer.windows?.find(
                                      (w: Obj) =>
                                        w.analysis_id === id.split(":")[0],
                                    )?.spec.base_year
                                  : id}
                              </button>
                            ))}
                          </div>
                            );
                          });
                          return group.label ? (group.indices.length > 0 && <details key={g}><summary>{group.label}（{group.indices.length}条）</summary>{contents}</details>) : <div key={g}>{contents}</div>;
                        })}
                        {answer.limitations?.map((t: string, i: number) => (
                          answer.presentation?.wording_warnings?.some((w: Obj) => w.section === "limitations" && w.index === i)
                            ? <details key={i}><summary>边界说明含疑似单位混用，查看待复核原文</summary><p className="muted">{t}</p></details>
                            : <p className="muted" key={i}>{t}</p>
                        ))}
                        <small>{answer.validation}</small>
                        {answer.field_normalizations?.length > 0 && <p className="muted">已按证据目录规范引用字段，数值与单位以证据为准，原始输出保留在调用记录。</p>}
                        {answer.tool_calls?.length > 0 && (
                          <details className="model-call-details">
                            <summary>查看实际工具与调用记录</summary>
                            <pre>
                              {JSON.stringify(answer.tool_calls, null, 2)}
                            </pre>
                            {answer.plan_adjustments?.length > 0 && <pre>{JSON.stringify(answer.plan_adjustments, null, 2)}</pre>}
                            {answer.model_trace?.map((call: Obj, i: number) => (
                              <p key={i}>
                                请求 {i + 1} ·{" "}
                                {call.actual_model || call.requested_model} ·{" "}
                                {call.elapsed_ms}毫秒 ·{" "}
                                {call.usage?.total_tokens ?? "未报告"} tokens
                              </p>
                            ))}
                          </details>
                        )}
                      </div>
                    )}
                  </section>
                  <section className="panel">
                    <h2>当前可用的证据</h2>
                    <p className="muted">点击打开公式、输入与原始来源。</p>
                    {r.evidence
                      .filter((e: Obj) => e.status === "supported")
                      .slice(0, 12)
                      .map((e: Obj) => (
                        <button
                          className="evidence-list-item"
                          key={e.id}
                          onClick={() => openEv(e.id)}
                        >
                          <span>{e.id}</span>
                          <b>{e.label}</b>
                          <ChevronRight size={14} />
                        </button>
                      ))}
                  </section>
                </div>
              )}
              {tab === "data" && (
                <>
                  <div className="metric-grid">
                    <div className="metric-card">
                      <div className="metric-label">标准观测记录</div>
                      <strong>{catalog?.rows.toLocaleString()}</strong>
                      <small>未静默填补或删除记录</small>
                    </div>
                    <div className="metric-card">
                      <div className="metric-label">报告国</div>
                      <strong>{catalog?.reporters.length} 个</strong>
                      <small>伙伴范围另见来源表</small>
                    </div>
                    <div className="metric-card">
                      <div className="metric-label">来源文件</div>
                      <strong>{catalog?.manifest.sources.length} 份</strong>
                      <small>保留原始文件指纹</small>
                    </div>
                    <button
                      className="metric-card add-data"
                      onClick={() => setModal("import")}
                    >
                      <Plus />
                      <strong>添加数据包</strong>
                      <small>支持规范UTF-8 CSV</small>
                    </button>
                  </div>
                  <section className="panel">
                    <div className="panel-heading">
                      <div>
                        <h2>数据覆盖矩阵</h2>
                        <p>
                          以世界总额记录存在且可用作为覆盖标识，伙伴记录需另行检查。
                        </p>
                      </div>
                      <Button onClick={() => setModal("import")}>
                        <Plus size={15} />
                        导入数据
                      </Button>
                    </div>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>报告国</th>
                            <th>流向</th>
                            <th>商品</th>
                            <th>分类</th>
                            {catalog?.years.map((y: number) => (
                              <th key={y}>{y}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {catalog?.coverage.map((c: Obj, i: number) => (
                            <tr key={i}>
                              <td>{cnNames[c.reporter] || c.reporter}</td>
                              <td>{c.flow === "M" ? "进口" : "出口"}</td>
                              <td>{c.product}</td>
                              <td>{c.classification}</td>
                              {catalog.years.map((y: number) => (
                                <td key={y}>
                                  {c.years.includes(y) ? (
                                    <Check size={15} className="positive" />
                                  ) : (
                                    "—"
                                  )}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                  <section className="panel">
                    <div className="panel-heading">
                      <div>
                        <h2>来源与文件指纹</h2>
                        <p>
                          {catalog?.manifest.source || "用户导入"} ·
                          来源声明与来源真实性认证分别理解
                        </p>
                      </div>
                    </div>
                    <div className="source-list">
                      {catalog?.manifest.sources.map((s: Obj) => (
                        <div className="source-item" key={s.id}>
                          <FileText size={19} />
                          <div>
                            <a href={s.url} target="_blank" rel="noreferrer">
                              {s.id} <ExternalLink size={12} />
                            </a>
                            <small>
                              {s.rows} 条 · {s.classification || "见记录字段"} ·{" "}
                              {s.original_unit || s.unit}
                            </small>
                            <code>SHA256 {s.sha256}</code>
                          </div>
                        </div>
                      ))}
                    </div>
                    <p className="muted">数据指纹：{catalog?.sha256}</p>
                  </section>
                </>
              )}
              {tab === "methods" && (
                <section className="panel methods">
                  <span className="eyebrow">METHODOLOGY & BOUNDARIES</span>
                  <h2>让分析的每一步都能解释</h2>
                  {[
                    [
                      "国家角色",
                      "目标市场竞争使用目标国报告的进口；双边模式按报告国与流向定位；多国模式分别展示各国报告数据。出口与进口镜像数据不自动混合。",
                    ],
                    [
                      "金额与份额",
                      "金额为名义美元。增长率 = (报告期 / 基期 − 1) × 100%；份额 = 伙伴金额 / 世界总额。份额差的单位为百分点。基期或分母为零时保留无法计算。",
                    ],
                    [
                      "市场规模与份额分解",
                      "Δx = 平均份额 × 市场规模变化 + 平均市场规模 × 份额变化。两个分量精确对账。这是描述性分解，不能将份额分量命名为竞争力或政策效应。",
                    ],
                    [
                      "缺失、进入与退出",
                      "缺失不是零。只有基期明确为零、报告期为正才判进入；反向才判退出。未列示伙伴不自动判定退出。",
                    ],
                    [
                      "商品与分类",
                      "选定商品父子层级不得重叠。跨分类版本不自动衔接。预置行业分别定义为HS 0901咖啡、0902茶叶、8703乘用车；行业名称不能替代编码边界。",
                    ],
                    [
                      "覆盖与集中度",
                      "世界总额与列示伙伴合计的差异保留为残差。头部份额基于列示伙伴；无法确认完整构成时不输出整体HHI。",
                    ],
                    [
                      "AI与计算",
                      "数值、图表和计算摘要由确定性程序生成。连接模型后使用受限工具选择和带证据引用的解释；引用存在不等于语义必然正确，仍需人工复核。",
                    ],
                    [
                      "复现与验证",
                      "导出包包含数据、参数、计算代码、来源和指纹。复现保证确定性计算一致，不保证模型措辞一致。当前开发测试不能替代真实用户试用或正式保留集评测。",
                    ],
                  ].map(([title, text]) => (
                    <article key={title}>
                      <h3>{title}</h3>
                      <p>{text}</p>
                    </article>
                  ))}
                  <Button
                    primary
                    disabled={busy}
                    onClick={() => download("bundle")}
                  >
                    <Download size={16} />
                    导出当前分析复算包
                  </Button>
                </section>
              )}
              {(tab === "overview" ||
                tab === "markets" ||
                tab === "research") && (
                <section className="panel notebook-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>
                        <FileText size={17} />
                        研究笔记
                      </h2>
                      <p>
                        记录你的判断、待核查问题和证据编号。笔记随分析保存，并进入导出报告。
                      </p>
                    </div>
                    <span className="badge">使用者记录</span>
                  </div>
                  <label className="notebook-title">
                    报告标题
                    <input
                      disabled={busy}
                      value={saveTitle}
                      maxLength={160}
                      onChange={(e) =>
                        editNotebook(analysisNote, e.target.value)
                      }
                    />
                  </label>
                  <label className="notebook-label" htmlFor="research-note">
                    分析笔记
                  </label>
                  <textarea
                    id="research-note"
                    disabled={busy}
                    value={analysisNote}
                    maxLength={5000}
                    onChange={(e) => editNotebook(e.target.value)}
                    placeholder="例如：金额与份额是否同向？哪些解释还需要补充证据？可记录 E0001 等证据编号。"
                  />
                  <div className="notebook-footer">
                    <small>
                      浏览器保留当前草稿；正式保存后可从分析记录恢复。
                      {analysisNote.length} / 5000
                    </small>
                    <Button disabled={busy} onClick={() => setModal("save")}>
                      <Plus size={15} />
                      保存笔记与分析
                    </Button>
                  </div>
                  {r.saved_record && (
                    <p className="snapshot-label">
                      当前来自保存记录：{r.saved_record.title}
                      。本页编辑不会修改原记录，再次保存会创建新记录。
                    </p>
                  )}
                </section>
              )}
              <div className="boundary">
                <ShieldCheck size={17} />
                <div>
                  <strong>分析边界</strong>
                  <p>{r.warnings.join(" ")}</p>
                </div>
              </div>
              <footer className="page-footer">
                <span>贸势有据 · 数据有来源，结论有边界</span>
                <span>
                  {r.dataset_name} / {r.analysis_id.slice(0, 8)}
                </span>
              </footer>
            </>
          )}
        </div>
      </main>
      {evidence && (
        <div className="drawer-backdrop" onClick={() => setEvidence(null)}>
          <aside
            className="evidence-drawer"
            onClick={(e) => e.stopPropagation()}
          >
            <header>
              <div>
                <span className="eyebrow">TRACE THE EVIDENCE</span>
                <h2>{evidence.id} · 计算依据</h2>
              </div>
              <button
                className="icon-button"
                onClick={() => setEvidence(null)}
                aria-label="关闭证据"
              >
                <PanelRightClose />
              </button>
            </header>
            <h3>{evidence.label}</h3>
            {evidence.spec && (
              <p className="muted">
                窗口 {evidence.spec.base_year}—{evidence.spec.end_year} · 分析{" "}
                {evidence.analysis_id}
              </p>
            )}
            <div className="evidence-formula">{evidence.formula}</div>
            <div className="evidence-result">
              <small>计算结果 · {evidence.unit}</small>
              <strong>
                {evidence.result == null
                  ? "证据不足"
                  : num(Number(evidence.result))}
              </strong>
            </div>
            <h3>输入与分量</h3>
            <dl>
              {Object.entries(evidence.operands).map(([k, v]) => (
                <React.Fragment key={k}>
                  <dt>{operandNames[k] || k}</dt>
                  <dd title={v == null ? "缺失" : String(v)}>
                    {v == null
                      ? "缺失 / 无法计算"
                      : num(Number(v) * (k === "s0" || k === "s1" ? 100 : 1))}
                  </dd>
                </React.Fragment>
              ))}
            </dl>
            <h3>
              原始记录 <span className="count">{evidence.records.length}</span>
            </h3>
            <div className="raw-records">
              {evidence.records.map((row: Obj) => (
                <div key={row.record_id}>
                  <b>
                    {row.reporter} · {row.partner_name} · {row.year}
                  </b>
                  <span>
                    HS {row.product} / {row.classification} / {row.flow}
                  </span>
                  <strong>{row.value_usd || "缺失"} USD</strong>
                  <small>
                    {row.record_id} · 原表记录 {row.source_row}
                  </small>
                  {r?.sources.find((s: Obj) => s.id === row.source_id) && (
                    <a
                      target="_blank"
                      rel="noreferrer"
                      href={
                        r.sources.find((s: Obj) => s.id === row.source_id).url
                      }
                    >
                      打开来源 <ExternalLink size={11} />
                    </a>
                  )}
                </div>
              ))}
            </div>
            <p className="muted">{evidence.note}</p>
          </aside>
        </div>
      )}
      {modal && (
        <div className="modal-backdrop" onClick={() => setModal("")}>
          <section className="modal" onClick={(e) => e.stopPropagation()}>
            <header>
              <h2>
                {modal === "model"
                  ? "模型连接"
                  : modal === "import"
                    ? "导入标准数据包"
                    : modal === "saved"
                      ? "我的分析记录"
                      : "保存当前分析"}
              </h2>
              <button
                className="icon-button"
                onClick={() => setModal("")}
                aria-label="关闭对话框"
              >
                <X />
              </button>
            </header>
            {error && (
              <div className="alert error" role="alert">
                {error}
              </div>
            )}
            {modal === "model" && (
              <>
                <Button
                  onClick={() => {
                    setSettings({
                      ...settings,
                      provider: "compatible",
                      base_url: "https://api.deepseek.com",
                      model: "deepseek-flash",
                    });
                    setModelCheck(null);
                  }}
                >
                  填入 DeepSeek 接入参数
                </Button>
                <p className="muted">
                  密钥只保存在本地配置。请先保存，再检测连接；检测会实际调用模型。
                </p>
                <p className="muted">
                  当前未假设任何订阅包含API。凭据只保存在本地配置文件，不发送到浏览器读取接口或导出包。
                </p>
                <label>
                  接入方式
                  <select
                    value={settings.provider}
                    onChange={(e) =>
                      setSettings({ ...settings, provider: e.target.value })
                    }
                  >
                    <option value="none">暂不连接</option>
                    <option value="ollama">本地 Ollama</option>
                    <option value="compatible">兼容聊天接口</option>
                  </select>
                </label>
                {settings.provider !== "none" && (
                  <>
                    <label>
                      服务地址
                      <input
                        value={settings.base_url || ""}
                        onChange={(e) =>
                          setSettings({ ...settings, base_url: e.target.value })
                        }
                        placeholder={
                          settings.provider === "ollama"
                            ? "http://127.0.0.1:11434"
                            : "https://你的服务/v1"
                        }
                      />
                    </label>
                    <label>
                      模型名称
                      <input
                        value={settings.model || ""}
                        onChange={(e) =>
                          setSettings({ ...settings, model: e.target.value })
                        }
                      />
                    </label>
                    {settings.provider === "compatible" && (
                      <label>
                        API Key
                        <input
                          type="password"
                          value={settings.api_key || ""}
                          autoComplete="off"
                          placeholder={
                            model.has_key ? "已有凭据；留空保留" : "输入凭据"
                          }
                          onChange={(e) =>
                            setSettings({
                              ...settings,
                              api_key: e.target.value || undefined,
                            })
                          }
                        />
                      </label>
                    )}
                  </>
                )}
                <Button
                  primary
                  onClick={async () => {
                    try {
                      const m = await api("/model", {
                        provider: settings.provider,
                        base_url: settings.base_url,
                        model: settings.model,
                        api_key: settings.api_key ?? null,
                      });
                      setModel(m);
                      setSettings({ ...m, api_key: undefined });
                      setModelCheck(null);
                      notify("模型配置已保存，可以检测已保存连接");
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  保存连接配置
                </Button>
                <Button
                  disabled={checkingModel || !model.configured}
                  onClick={async () => {
                    setCheckingModel(true);
                    setModelCheck(null);
                    try {
                      setModelCheck(await api("/model/test", {}));
                    } catch (e) {
                      setModelCheck({
                        ok: false,
                        message: (e as Error).message,
                      });
                    } finally {
                      setCheckingModel(false);
                    }
                  }}
                >
                  {checkingModel ? "正在实际检测…" : "检测已保存连接"}
                </Button>
                {modelCheck && (
                  <div
                    className={modelCheck.ok ? "scope-box" : "alert error"}
                    role="status"
                  >
                    {modelCheck.ok
                      ? `真实连接与JSON响应通过 · ${modelCheck.actual_model || modelCheck.model} · ${modelCheck.elapsed_ms}毫秒。贸易任务效果仍需评测。`
                      : modelCheck.message}
                  </div>
                )}
              </>
            )}
            {modal === "save" && (
              <>
                <label>
                  分析名称
                  <input
                    value={saveTitle}
                    onChange={(e) => editNotebook(analysisNote, e.target.value)}
                    maxLength={160}
                  />
                </label>
                <label>
                  研究笔记
                  <textarea
                    value={analysisNote}
                    maxLength={5000}
                    onChange={(e) => editNotebook(e.target.value)}
                  />
                </label>
                <p className="muted">
                  保存计算快照、证据与笔记。每次创建独立记录，不覆盖旧记录。
                </p>
                <Button
                  primary
                  disabled={busy}
                  onClick={async () => {
                    try {
                      setBusy(true);
                      const record = await api("/saved", documentBody());
                      setResult({
                        ...r!,
                        saved_record: {
                          id: record.id,
                          title: record.title,
                          note: analysisNote,
                        },
                      });
                      setModal("");
                      notify("分析记录已保存");
                    } catch (e) {
                      setError((e as Error).message);
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  保存分析
                </Button>
              </>
            )}
            {modal === "saved" && (
              <div className="saved-list">
                {!saved.length && (
                  <div className="empty">还没有保存的分析。</div>
                )}
                {saved.map((s) => (
                  <button
                    key={s.id}
                    disabled={busy}
                    onClick={async () => {
                      try {
                        setBusy(true);
                        const rr = await api("/saved/" + s.id);
                        const c = await api("/datasets/" + rr.spec.dataset_id);
                        setCatalog(c);
                        setDraft(rr.spec);
                        setResult(rr);
                        restoreNotebook(rr);
                        setChosen(rr.partners[0]?.code || "");
                        setAnswer(null);
                        setPage(0);
                        setSearch("");
                        setEvidence(null);
                        setModal("");
                        setTab("overview");
                      } catch (e) {
                        setError((e as Error).message);
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    <FileText size={18} />
                    <div>
                      <b>{s.title}</b>
                      <small>
                        {new Date(s.created).toLocaleString("zh-CN", {
                          timeZone: "Asia/Shanghai",
                        })}
                      </small>
                    </div>
                    <ChevronRight size={16} />
                  </button>
                ))}
              </div>
            )}
            {modal === "import" && (
              <>
                <p>
                  导入UTF-8
                  CSV，金额统一为美元。系统检查重复、状态和分类字段；不会认证上传者声明的来源。
                </p>
                <a className="text-button" href="/api/import/template" download>
                  下载空白字段模板 <Download size={14} />
                </a>
                <label>
                  数据包名称
                  <input
                    value={uploadName}
                    onChange={(e) => setUploadName(e.target.value)}
                  />
                </label>
                <label>
                  来源网址
                  <input
                    value={sourceUrl}
                    onChange={(e) => setSourceUrl(e.target.value)}
                    placeholder="https://…"
                  />
                </label>
                <label>
                  CSV文件
                  <input
                    type="file"
                    accept=".csv"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                  />
                </label>
                <p className="muted">
                  流向：M / X；分类：H0—H6；世界伙伴：WLD；状态：observed /
                  explicit_zero / missing。缺失金额留空。
                </p>
                <Button
                  primary
                  disabled={!file || !uploadName || !sourceUrl || busy}
                  onClick={async () => {
                    if (!file) return;
                    setBusy(true);
                    try {
                      const fd = new FormData();
                      fd.append("file", file);
                      fd.append("name", uploadName);
                      fd.append("source_url", sourceUrl);
                      const response = await fetch("/api/import", {
                        method: "POST",
                        body: fd,
                      });
                      const data = await response.json();
                      if (!response.ok) throw Error(data.detail);
                      setDatasets(await api("/datasets"));
                      setModal("");
                      await changeDataset(data.dataset_id);
                      notify(`已导入 ${data.records} 条记录`);
                    } catch (e) {
                      setError((e as Error).message);
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  检查并导入
                </Button>
              </>
            )}
          </section>
        </div>
      )}
      {toast && (
        <div className="toast" role="status">
          <Check size={16} />
          {toast}
        </div>
      )}
    </div>
  );
}
installDisplayErrorReporting();
createRoot(document.getElementById("root")!).render(
  <DisplayBoundary>
    <App />
  </DisplayBoundary>,
);
