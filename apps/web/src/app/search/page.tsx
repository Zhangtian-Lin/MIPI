import { MipiApiError, MipiClient } from "@mipi/sdk-ts";
import { StatusBadge } from "@mipi/ui-web";
import type { Metadata } from "next";

export const dynamic = "force-dynamic";

interface PageProps { searchParams: Promise<Record<string, string | string[] | undefined>> }

export async function generateMetadata({ searchParams }: PageProps): Promise<Metadata> {
  const query = one((await searchParams).q)?.trim();
  const title = query ? `搜索“${query}” — MIPI` : "搜索 — MIPI";
  return { title, description: "搜索 MIPI 已经人工发布的马来西亚产业与政策情报。",
    robots: { index: false, follow: true }, openGraph: { title, images: [] },
    twitter: { card: "summary", title, images: [] } };
}

export default async function SearchPage({ searchParams }: PageProps) {
  const query = one((await searchParams).q)?.trim() ?? "";
  const result = query.length >= 2 ? await search(query) : { status: "idle" as const };
  return <main><header className="site-header"><a className="brand" href="/">MIPI</a>
    <nav aria-label="搜索导航"><a href="/">首页</a><a href="/#changes">重要变化</a></nav></header>
    <section className="search-page"><span className="eyebrow">PUBLISHED INTELLIGENCE</span><h1>搜索已发布情报</h1>
      <form className="search-shell" action="/search" method="get"><label className="sr-only" htmlFor="search-query">搜索词</label>
        <input id="search-query" name="q" required minLength={2} maxLength={100} defaultValue={query}
          placeholder="中文标题、摘要、英语或马来语原文……" autoFocus/><button type="submit">搜索</button></form>
      <p className="search-boundary">只检索当前公开 L4 revision，不包含候选、审核中、隔离或私有数据。</p>
      {result.status === "idle" ? <div className="empty-state">请输入至少两个字符开始搜索。</div> : null}
      {result.status === "unavailable" ? <div className="empty-state error-state">搜索服务暂时不可用；不会返回未经发布的数据作为替代。</div> : null}
      {result.status === "ok" ? <section className="search-results"><div className="section-heading"><div><span className="eyebrow">EVENTS</span>
        <h2>事件</h2></div><span className="muted">{result.data.groups.events.length} 条结果</span></div>
        {result.data.groups.events.length ? <div className="search-result-list">{result.data.groups.events.map((hit) => <article key={hit.event.event_id}>
          <div className="change-meta"><StatusBadge level={hit.event.fact_level}>{hit.event.fact_level}</StatusBadge>
            <span>{hit.event.event_date ?? "日期待确认"}</span><span>{reasonLabel(hit.match_reason)}</span></div>
          <h3><a href={`/events/${encodeURIComponent(hit.event.event_id)}`}>{hit.event.title_zh}</a></h3>
          <p>{hit.event.summary_zh}</p><blockquote>{hit.match_excerpt}</blockquote>
          <a className="event-detail-link" href={`/events/${encodeURIComponent(hit.event.event_id)}`}>查看证据与详情 →</a>
        </article>)}</div> : <div className="empty-state">没有匹配的已发布事件。企业、项目、政策和州属分组将在相应 L4 数据上线后启用。</div>}
      </section> : null}
    </section></main>;
}

type SearchState = { status: "ok"; data: Awaited<ReturnType<MipiClient["search"]>> } | { status: "unavailable" };

async function search(query: string): Promise<SearchState> {
  const client = new MipiClient({ baseUrl: process.env.MIPI_PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_MIPI_API_URL ?? "http://localhost:8000/v1" });
  try { return { status: "ok", data: await client.search(query) }; }
  catch (error: unknown) {
    if (error instanceof MipiApiError) return { status: "unavailable" };
    return { status: "unavailable" };
  }
}

function one(value: string | string[] | undefined): string | undefined { return Array.isArray(value) ? value[0] : value; }

function reasonLabel(value: string): string {
  return ({ title_zh: "命中中文标题", summary_zh: "命中中文摘要", evidence_original: "命中原文证据", source_name: "命中来源名称" } as Record<string,string>)[value] ?? "匹配";
}
