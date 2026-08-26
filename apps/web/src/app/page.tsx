import { MipiClient } from "@mipi/sdk-ts";
import { StatusBadge } from "@mipi/ui-web";
import type { EventPublicationVM, TradeOverviewVM } from "@mipi/view-models";

const industries = ["数据中心与 AI 基础设施", "半导体", "先进制造与新能源"];

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const tradeResult = await loadTradeOverview();
  const changesResult = await loadChanges();
  const trade = tradeResult.overview;
  return (
    <main>
      <header className="site-header">
        <a className="brand" href="/">MIPI</a>
        <nav aria-label="主导航">
          <a href="#changes">重要变化</a>
          <a href="#industries">产业</a>
          <a href="#states">州属</a>
          <a href="#methodology">方法论</a>
        </nav>
      </header>

      <section className="hero">
        <StatusBadge level={trade ? "F4" : "F0"}>
          {trade ? "首条官方数据" : "数据闭环准备中"}
        </StatusBadge>
        <h1>马来西亚产业与政策情报</h1>
        <p>把分散的政策、投资、项目与企业信息，整理成可查询、可追踪、可验证的结构化知识。</p>
        <label className="search-shell">
          <span className="sr-only">搜索</span>
          <input disabled placeholder="搜索企业、项目、政策或提问……" />
          <button disabled>搜索</button>
        </label>
        <p className="notice">
          {trade
            ? `贸易数据已通过人工发布，投影版本 v${trade.revision}。`
            : "当前没有经过人工发布的数据；候选、试采和 L3 私有数据不会出现在这里。"}
        </p>
      </section>

      <TradeOverview overview={trade} unavailable={tradeResult.unavailable} />

      <section id="changes" className="section">
        <div className="section-heading">
          <div><span className="eyebrow">TODAY</span><h2>今日重要变化</h2></div>
          <span className="muted">最多 10 条 · 只读取已发布 L4</span>
        </div>
        {changesResult.changes.length ? (
          <div className="change-list">
            {changesResult.changes.map((event) => <ChangeCard event={event} key={event.event_id} />)}
          </div>
        ) : (
          <div className={`empty-state${changesResult.unavailable ? " error-state" : ""}`}>
            {changesResult.unavailable
              ? "重要变化 API 暂时不可用；页面不会用私有候选代替正式事件。"
              : "尚未收录可公开事件。真实数据必须经过来源、证据和 Publisher 发布流程。"}
          </div>
        )}
      </section>

      <section id="industries" className="section">
        <div className="section-heading"><div><span className="eyebrow">SECTORS</span><h2>重点产业</h2></div></div>
        <div className="card-grid">
          {industries.map((industry) => <article className="card" key={industry}><h3>{industry}</h3><p>产业页面模块已预留，等待 View Model 和 API。</p></article>)}
        </div>
      </section>

      <section id="states" className="section split">
        <article><span className="eyebrow">STATES</span><h2>重点州属</h2><p>Johor · Penang · Selangor · Kuala Lumpur</p></article>
        <article id="methodology"><span className="eyebrow">TRUST</span><h2>证据优先</h2><p>S1–S6 描述来源，F0–F4 描述事实验证。关键字段必须能回到原文证据。</p></article>
      </section>
    </main>
  );
}

function ChangeCard({ event }: { event: EventPublicationVM }) {
  const evidence = event.evidence[0]!;
  return (
    <article className="change-card">
      <div className="change-meta">
        <StatusBadge level={event.fact_level}>{event.fact_level}</StatusBadge>
        <span>{event.event_date ?? "日期待确认"}</span>
        <span>{event.event_type}</span>
        {event.conflict ? <span className="conflict-label">存在冲突</span> : null}
      </div>
      <h3>{event.title_zh}</h3>
      <p>{event.summary_zh}</p>
      <div className="change-scopes">
        {[...event.industries, ...event.states].map((item) => <span key={item}>{item}</span>)}
      </div>
      <details className="evidence-drawer">
        <summary>查看原文证据与来源</summary>
        <blockquote>{evidence.source_span.quote_zh}</blockquote>
        <p lang={evidence.language ?? undefined}>{evidence.source_span.quote_original}</p>
        <div>
          <span>{evidence.source_name} · {evidence.source_grade}</span>
          <span>文档 v{evidence.document_version} · {event.independent_source_count} 个独立信源</span>
          <a href={evidence.canonical_url} target="_blank" rel="noreferrer">打开原始来源 ↗</a>
        </div>
        {event.caveats.map((item) => <small key={item}>{item}</small>)}
      </details>
    </article>
  );
}

function TradeOverview({
  overview,
  unavailable,
}: {
  overview: TradeOverviewVM | null;
  unavailable: boolean;
}) {
  if (!overview) {
    return (
      <section id="trade" className="section trade-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">OFFICIAL INDICATORS</span>
            <h2>贸易与产业指标</h2>
          </div>
          <span className="muted">只读取已发布 L4 投影</span>
        </div>
        <div className={`empty-state${unavailable ? " error-state" : ""}`}>
          {unavailable
            ? "贸易指标 API 暂时不可用。页面不会使用缓存外的候选数据替代正式投影。"
            : "页面契约已经就绪。完成来源试采、L2 审核、L3 标准化和 Publisher 批准后，官方月度贸易数据会自动出现在这里。"}
        </div>
      </section>
    );
  }
  const maximum = Math.max(...overview.sections.map((item) => item.exports_rm_million), 1);
  return (
    <section id="trade" className="section trade-section">
      <div className="section-heading">
        <div>
          <span className="eyebrow">OFFICIAL INDICATORS</span>
          <h2>贸易与产业指标</h2>
        </div>
        <span className="muted">
          数据期 {formatMonth(overview.latest_period)} · 最近两个月可能修订
        </span>
      </div>
      <div className="trade-metrics">
        <Metric
          label="出口"
          value={overview.latest.exports_rm_million}
          change={overview.latest.exports_mom_percent}
        />
        <Metric
          label="进口"
          value={overview.latest.imports_rm_million}
          change={overview.latest.imports_mom_percent}
        />
        <Metric label="贸易差额" value={overview.latest.balance_rm_million} change={null} />
      </div>
      <div className="trade-layout">
        <article className="trade-panel">
          <span className="eyebrow">SITC SECTIONS</span>
          <h3>最新月份出口构成</h3>
          <div className="section-bars">
            {[...overview.sections]
              .sort((left, right) => right.exports_rm_million - left.exports_rm_million)
              .map((item) => (
                <div className="section-row" key={item.section}>
                  <div>
                    <strong>{item.section}</strong>
                    <span>{item.label_zh}</span>
                  </div>
                  <div className="bar-track" aria-hidden="true">
                    <span
                      style={{ width: `${item.exports_rm_million / maximum * 100}%` }}
                    />
                  </div>
                  <span>{formatMoney(item.exports_rm_million)}</span>
                </div>
              ))}
          </div>
        </article>
        <article className="trade-panel timeline-panel">
          <span className="eyebrow">12 MONTHS</span>
          <h3>月度总额</h3>
          <div className="timeline-table" role="table" aria-label="最近十二个月贸易总额">
            {overview.timeline.map((item) => (
              <div className="timeline-row" role="row" key={item.period}>
                <span role="cell">
                  {formatMonth(item.period)}{item.provisional ? "*" : ""}
                </span>
                <span role="cell">出口 {formatMoney(item.exports_rm_million)}</span>
                <span role="cell">进口 {formatMoney(item.imports_rm_million)}</span>
              </div>
            ))}
          </div>
        </article>
      </div>
      <aside className="evidence-strip">
        <div>
          <StatusBadge level={overview.fact_level}>
            {overview.fact_level} 权威记录
          </StatusBadge>
          <strong>{overview.evidence.source_name}</strong>
        </div>
        <p>{overview.caveats.join(" ")}单位为百万林吉特（RM million）。</p>
        <a href={overview.evidence.canonical_url} target="_blank" rel="noreferrer">查看 data.gov.my 原始数据 ↗</a>
      </aside>
    </section>
  );
}

function Metric({
  label,
  value,
  change,
}: {
  label: string;
  value: number;
  change: number | null;
}) {
  return (
    <article>
      <span>{label}</span>
      <strong>{formatMoney(value)}</strong>
      <p>
        {change === null
          ? "以出口减进口计算"
          : `较上月 ${change >= 0 ? "+" : ""}${change.toFixed(2)}%`}
      </p>
    </article>
  );
}

async function loadTradeOverview(): Promise<{
  overview: TradeOverviewVM | null;
  unavailable: boolean;
}> {
  const client = new MipiClient({
    baseUrl:
      process.env.MIPI_PUBLIC_API_URL ??
      process.env.NEXT_PUBLIC_MIPI_API_URL ??
      "http://localhost:8000/v1",
  });
  try {
    return { overview: await client.getTradeOverview(), unavailable: false };
  } catch {
    return { overview: null, unavailable: true };
  }
}

async function loadChanges(): Promise<{ changes: EventPublicationVM[]; unavailable: boolean }> {
  const client = new MipiClient({
    baseUrl: process.env.MIPI_PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_MIPI_API_URL
      ?? "http://localhost:8000/v1",
  });
  try {
    return { changes: await client.listChanges(), unavailable: false };
  } catch {
    return { changes: [], unavailable: true };
  }
}

function formatMoney(value: number): string {
  return `RM ${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 1 }).format(value)}m`;
}

function formatMonth(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}
