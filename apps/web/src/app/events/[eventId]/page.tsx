import { MipiApiError, MipiClient } from "@mipi/sdk-ts";
import { StatusBadge } from "@mipi/ui-web";
import type { EventPublicationVM } from "@mipi/view-models";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { eventId } = await params;
  const result = await loadEvent(eventId);
  if (result.status !== "ok") return { title: result.status === "not_found" ? "事件未找到 — MIPI" : "事件暂不可用 — MIPI" };
  const event = result.event;
  return {
    title: `${event.title_zh} — MIPI`,
    description: event.summary_zh,
    openGraph: { title: event.title_zh, description: event.summary_zh, images: [] },
    twitter: { card: "summary", title: event.title_zh, description: event.summary_zh, images: [] },
  };
}

interface PageProps { params: Promise<{ eventId: string }> }

export default async function EventPage({ params }: PageProps) {
  const { eventId } = await params;
  const result = await loadEvent(eventId);
  if (result.status === "not_found") notFound();
  if (result.status === "unavailable") return <main><header className="site-header"><a className="brand" href="/">MIPI</a></header><section className="event-detail"><span className="eyebrow">TEMPORARILY UNAVAILABLE</span><h1>事件详情暂时不可用</h1><div className="empty-state error-state">公开事件 API 暂时无法访问。页面不会以候选或私有数据替代已发布 revision。</div><a className="event-detail-link" href="/#changes">← 返回重要变化</a></section></main>;
  const event = result.event;
  return <main>
    <header className="site-header"><a className="brand" href="/">MIPI</a><nav aria-label="事件导航"><a href="/#changes">返回重要变化</a><a href="#evidence">证据</a></nav></header>
    <article className="event-detail">
      <div className="change-meta"><StatusBadge level={event.fact_level}>{event.fact_level}</StatusBadge>
        <span>{event.event_date ?? "日期待确认"}</span><span>{eventTypeLabel(event.event_type)}</span>
        {event.conflict ? <span className="conflict-label">存在冲突</span> : null}</div>
      <h1>{event.title_zh}</h1><p className="event-lead">{event.summary_zh}</p>
      <div className="change-scopes">{[...event.industries, ...event.states].map((item) => <span key={item}>{item}</span>)}</div>
      <dl className="event-facts">
        <div><dt>事实等级</dt><dd>{event.fact_level}</dd></div>
        <div><dt>独立信源</dt><dd>{event.independent_source_count}</dd></div>
        <div><dt>公开版本</dt><dd>revision {event.revision}</dd></div>
        <div><dt>发布时间</dt><dd>{formatDateTime(event.published_at)}</dd></div>
      </dl>
      <section id="evidence" className="event-evidence-section"><span className="eyebrow">EVIDENCE</span><h2>原文证据</h2>
        {event.evidence.map((evidence) => <article className="evidence-record" key={`${evidence.claim_id}-${evidence.document_id}`}>
          <blockquote>{evidence.source_span.quote_zh}</blockquote>
          <p lang={evidence.language ?? undefined}>{evidence.source_span.quote_original}</p>
          <dl><div><dt>来源</dt><dd>{evidence.source_name} · {evidence.source_grade}</dd></div>
            <div><dt>文档版本</dt><dd>{evidence.document_id} · v{evidence.document_version}</dd></div>
            <div><dt>原文位置</dt><dd>{evidence.source_span.start}–{evidence.source_span.end}</dd></div>
            <div><dt>抓取时间</dt><dd>{formatDateTime(evidence.crawled_at)}</dd></div>
            <div><dt>模型与提示词</dt><dd>{evidence.source_span.model_id} · {evidence.source_span.prompt_version}</dd></div></dl>
          <a href={evidence.canonical_url} target="_blank" rel="noreferrer">打开原始来源 ↗</a>
        </article>)}
        {event.caveats.map((item) => <p className="event-caveat" key={item}>{item}</p>)}
      </section>
    </article>
  </main>;
}

type EventLoadResult = { status: "ok"; event: EventPublicationVM } | { status: "not_found" } | { status: "unavailable" };

async function loadEvent(eventId: string): Promise<EventLoadResult> {
  const client = new MipiClient({ baseUrl: process.env.MIPI_PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_MIPI_API_URL ?? "http://localhost:8000/v1" });
  try { return { status: "ok", event: await client.getEvent(eventId) }; }
  catch (error: unknown) {
    return error instanceof MipiApiError && error.status === 404
      ? { status: "not_found" }
      : { status: "unavailable" };
  }
}

function eventTypeLabel(value: string): string {
  return ({ investment: "投资", project_update: "项目", policy_update: "政策", company_update: "企业", tender: "招标", governance_update: "治理" } as Record<string,string>)[value] ?? value;
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Shanghai" }).format(new Date(value));
}
