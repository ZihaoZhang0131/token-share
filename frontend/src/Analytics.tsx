import { useEffect, useId, useState } from "react";
import { api, formatNumber } from "./api";
import { Button, Empty, InlineError } from "./components";
import { exactTokens, formatTokens } from "./formatTokens";
import type { AnalyticsData, AnalyticsDay, AnalyticsPeriod, AnalyticsRank } from "./types";

const periods: { id: AnalyticsPeriod; label: string }[] = [
  { id: "month", label: "本月" },
  { id: "7d", label: "近 7 天" },
  { id: "30d", label: "近 30 天" }
];

function periodLabel(period: AnalyticsPeriod) {
  return periods.find((item) => item.id === period)?.label ?? "本月";
}

function latency(value: number | null) {
  return value === null ? "—" : `${(value / 1000).toLocaleString("zh-CN", { maximumFractionDigits: 2 })} 秒`;
}

export default function Analytics({ admin = false, refreshVersion = 0 }: { admin?: boolean; refreshVersion?: number }) {
  const [period, setPeriod] = useState<AnalyticsPeriod>("month");
  const [snapshot, setSnapshot] = useState<{ data: AnalyticsData; admin: boolean } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  const [retry, setRetry] = useState(0);
  const data = snapshot?.admin === admin ? snapshot.data : null;

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setBusy(true);
    setError("");
    api<AnalyticsData>(`/api/${admin ? "admin" : "me"}/analytics?period=${period}`, { signal: controller.signal })
      .then((value) => { if (active) setSnapshot({ data: value, admin }); })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : "统计加载失败");
      })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; controller.abort(); };
  }, [admin, period, retry, refreshVersion]);

  return <div className="analytics-stack" aria-busy={busy}>
    <div className="analytics-toolbar">
      <div><h2>{admin ? "站点用量手账" : "用量手账"}</h2><p>北京时间 · 已入账请求</p></div>
      <div className="period-switch" role="group" aria-label="统计时间范围">
        {periods.map((item) => <button key={item.id} type="button" aria-pressed={period === item.id} onClick={() => setPeriod(item.id)}>{item.label}</button>)}
      </div>
    </div>
    {error && <div className="analytics-error"><InlineError message={`${error}${data ? `。下方仍显示上次成功加载的${periodLabel(data.period)}数据。` : "。请重试。"}`} /><Button variant="secondary" onClick={() => setRetry((value) => value + 1)}>重新加载</Button></div>}
    <p className="analytics-status" role="status" aria-live="polite">{busy ? `正在加载${periodLabel(period)}统计…` : data ? `${periodLabel(data.period)} · ${data.daily[0]?.date ?? ""} 至 ${data.daily.at(-1)?.date ?? ""}` : "统计暂不可用"}</p>
    {!data && !error && <div className="skeleton-grid" aria-hidden="true"><div /><div /><div /></div>}
    {data && <>
      <section className="stats-grid analytics-summary" aria-label="期间统计">
        <article className="stat-card"><span>Token 消耗</span><strong title={exactTokens(data.summary.total_tokens)}>{formatTokens(data.summary.total_tokens)}</strong><small>{periodLabel(data.period)}累计</small></article>
        <article className="stat-card"><span>调用次数</span><strong>{formatNumber(data.summary.requests)}</strong><small>{formatNumber(data.summary.successes)} 成功 / {formatNumber(data.summary.failures)} 失败</small></article>
        <article className="stat-card"><span>请求成功率</span><strong>{data.summary.success_rate === null ? "—" : `${data.summary.success_rate.toFixed(1)}%`}</strong></article>
        <article className="stat-card"><span title="包含流式完整响应时间">平均请求耗时</span><strong>{latency(data.summary.avg_latency_ms)}</strong></article>
      </section>
      <div className={admin ? "analytics-grid analytics-trends" : "analytics-trends"}>
      <section className="panel analytics-chart">
        <div className="panel-head"><div><h2>每日 Token 用量</h2></div></div>
        <div className="chart-totals"><span>输入 <strong title={exactTokens(data.summary.input_tokens)}>{formatTokens(data.summary.input_tokens)}</strong></span><span>输出 <strong title={exactTokens(data.summary.output_tokens)}>{formatTokens(data.summary.output_tokens)}</strong></span></div>
        {data.summary.total_tokens ? <DailyChart key={`token-${data.period}`} days={data.daily} kind="tokens" compact={admin} /> : <Empty>暂无 Token 消耗</Empty>}
      </section>
      {admin && <section className="panel analytics-chart"><div className="panel-head"><div><h2>调用情况</h2></div></div><div className="chart-totals"><span>成功 <strong>{formatNumber(data.summary.successes)} 次</strong></span><span>失败 <strong>{formatNumber(data.summary.failures)} 次</strong></span></div>{data.summary.requests ? <DailyChart key={`request-${data.period}`} days={data.daily} kind="requests" compact /> : <Empty>暂无调用</Empty>}</section>}
      </div>
      <div className={`analytics-grid ${admin ? "analytics-grid-two" : "analytics-grid-one"}`}>
        <Ranking title={admin ? "模型消耗排行" : "模型消耗占比"} rows={data.models} total={data.summary.total_tokens} />
        {admin && <Ranking title="用户消耗排行" rows={data.users ?? []} total={data.summary.total_tokens} />}
      </div>
    </>}
  </div>;
}

function DailyChart({ days, kind, compact = false }: { days: AnalyticsDay[]; kind: "tokens" | "requests"; compact?: boolean }) {
  const [selected, setSelected] = useState<AnalyticsDay | null>(null);
  const tooltipId = useId();
  const width = compact ? 520 : 760, height = 240, left = 66, right = 14, top = 20, bottom = 38;
  const chartWidth = width - left - right;
  const chartHeight = height - top - bottom;
  const values = (day: AnalyticsDay): [number, number] => kind === "tokens" ? [day.input_tokens, day.output_tokens] : [day.successes, day.failures];
  const rawMax = Math.max(1, ...days.map((day) => values(day).reduce((a, b) => a + b, 0)));
  // Request ticks must stay on exact whole counts, including a single-call day.
  const maxValue = kind === "requests" && rawMax > 1 ? Math.ceil(rawMax / 2) * 2 : rawMax;
  const tickRatios = kind === "requests" && maxValue === 1 ? [0, 1] : [0, 0.5, 1];
  const step = chartWidth / Math.max(1, days.length);
  const barWidth = Math.min(28, step * 0.64);
  const firstLabel = kind === "tokens" ? "输入" : "成功";
  const secondLabel = kind === "tokens" ? "输出" : "失败";
  const firstClass = kind === "tokens" ? "chart-input" : "chart-success";
  const secondClass = kind === "tokens" ? "chart-output" : "chart-failure";
  const description = (day: AnalyticsDay) => {
    const [a, b] = values(day);
    const format = kind === "tokens" ? exactTokens : (value: number) => `${formatNumber(value)} 次`;
    return `${day.date} · ${firstLabel} ${format(a)} · ${secondLabel} ${format(b)}`;
  };
  const axis = (value: number) => kind === "tokens" ? formatTokens(value) : formatNumber(Math.round(value));

  return <div className="chart-frame">
    <div className="chart-legend"><span><i className={firstClass} />{firstLabel}</span><span><i className={secondClass} />{secondLabel}</span></div>
    <svg className="chart-svg" viewBox={`0 0 ${width} ${height}`} role="group" aria-label={kind === "tokens" ? "每日输入与输出 Token 柱状图" : "每日成功与失败请求柱状图"}>
      {tickRatios.map((ratio) => <g key={ratio}><line className="chart-gridline" x1={left} x2={width - right} y1={top + chartHeight * (1 - ratio)} y2={top + chartHeight * (1 - ratio)} /><text className="chart-axis-label" x={left - 10} y={top + chartHeight * (1 - ratio) + 4} textAnchor="end">{axis(maxValue * ratio)}</text></g>)}
      {days.map((day, index) => {
        const [a, b] = values(day);
        const x = left + step * index + (step - barWidth) / 2;
        const h1 = chartHeight * a / maxValue;
        const h2 = chartHeight * b / maxValue;
        const showLabel = index === 0 || index === days.length - 1 || (index % Math.max(1, Math.ceil(days.length / 6)) === 0 && index < days.length - 2);
        return <g key={day.date} tabIndex={0} role="img" aria-label={description(day)} aria-describedby={tooltipId} onMouseEnter={() => setSelected(day)} onMouseLeave={() => setSelected(null)} onFocus={() => setSelected(day)} onBlur={() => setSelected(null)} className={`chart-day ${selected?.date === day.date ? "is-selected" : ""}`}>
          <title>{description(day)}</title>
          <rect className="chart-hit-area" fill="transparent" x={left + step * index} y={top} width={step} height={chartHeight} />
          <rect className={firstClass} x={x} y={top + chartHeight - h1} width={barWidth} height={h1} />
          <rect className={secondClass} x={x} y={top + chartHeight - h1 - h2} width={barWidth} height={h2} />
          {showLabel && <text className="chart-axis-label" x={x + barWidth / 2} y={height - 12} textAnchor="middle">{day.date.slice(5)}</text>}
        </g>;
      })}
    </svg>
    <div className="chart-tooltip" id={tooltipId} aria-live="polite">{selected ? description(selected) : ""}</div>
  </div>;
}

function Ranking({ title, rows, total }: { title: string; rows: AnalyticsRank[]; total: number }) {
  return <section className="panel analytics-chart">
    <div className="panel-head"><div><h2>{title}</h2></div></div>
    {!rows.length || !total ? <Empty>暂无消耗数据</Empty> : <div className="ranking-list">{rows.map((row, index) => {
      const percent = total > 0 ? row.total_tokens / total * 100 : 0;
      const label = `${row.label}：${exactTokens(row.total_tokens)}，占比 ${percent.toFixed(1)}%，${formatNumber(row.requests)} 次请求`;
      return <div key={`${row.id}:${row.label}`} className="ranking-row" tabIndex={0} aria-label={label} title={label}>
        <div className="ranking-label"><span className="ranking-number">{row.id === "other" && row.label === "其他" ? "·" : String(index + 1).padStart(2, "0")}</span><strong title={row.label}>{row.label}</strong><span className="ranking-value">{formatTokens(row.total_tokens)}</span></div>
        <svg className="ranking-track" viewBox="0 0 400 10" preserveAspectRatio="none" role="img" aria-label={`${row.label}占 ${percent.toFixed(1)}%`}><rect className="ranking-track-bg" width="400" height="10" /><rect className={index % 2 ? "chart-output" : "chart-input"} width={Math.min(400, Math.max(0, percent * 4))} height="10" /></svg>
        <div className="ranking-meta"><span>{formatNumber(row.requests)} 次调用</span><span>{percent.toFixed(1)}%</span></div>
      </div>;
    })}</div>}
  </section>;
}
