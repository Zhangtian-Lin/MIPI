"use client";

import type { MipiClient } from "@mipi/sdk-ts";
import type { EventSourceTextVM, EventWorkbenchVM } from "@mipi/view-models";
import { useCallback, useEffect, useState } from "react";

export function EventPublicationWorkbench({ client }: { client: MipiClient }) {
  const [data, setData] = useState<EventWorkbenchVM | null>(null);
  const [source, setSource] = useState<EventSourceTextVM | null>(null);
  const [processor, setProcessor] = useState("local-event-processor-1");
  const [publisher, setPublisher] = useState("local-publisher-1");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    event_type: "project_update", title_zh: "", summary_zh: "", event_date: "",
    industries: "data_centres_ai", states: "johor", span_start: 0, span_end: 0,
    quote_original: "", quote_zh: "", model_id: "manual-local",
    prompt_version: "event-extraction-v1.0", conflict: false,
  });

  const load = useCallback(async (preserve = false) => {
    if (!processor.trim()) return;
    if (!preserve) setMessage(null);
    try { setData(await client.getEventWorkbench(processor.trim())); }
    catch (error: unknown) { setMessage(error instanceof Error ? error.message : "事件工作台读取失败"); }
  }, [client, processor]);
  useEffect(() => { void load(); }, [load]);

  const openSource = async (ingestionId: string) => {
    setBusy(true); setMessage(null);
    try { setSource(await client.getEventSource(ingestionId, processor.trim())); }
    catch (error: unknown) { setMessage(error instanceof Error ? error.message : "原文读取失败"); }
    finally { setBusy(false); }
  };

  const captureSelection = (element: HTMLTextAreaElement) => {
    const start = element.selectionStart;
    const end = element.selectionEnd;
    if (end > start) setForm((current) => ({ ...current, span_start: start, span_end: end,
      quote_original: element.value.slice(start, end) }));
  };

  const project = async () => {
    if (!source) return;
    if (!window.confirm("确认把当前结构化结果和精确原文片段写入私有 L3？这不会公开。")) return;
    setBusy(true); setMessage(null);
    try {
      const result = await client.projectEvent({
        ...form, ingestion_id: source.ingestion_id,
        event_date: form.event_date || null,
        event_date_precision: form.event_date ? "day" : "unknown",
        industries: split(form.industries), states: split(form.states),
        rule_version: "event-projection-v1.0",
      }, processor.trim(), crypto.randomUUID());
      setSource(null); setMessage(`已生成私有事件 ${result.event_id}，事实等级 ${result.fact_level}。`);
      await load(true);
    } catch (error: unknown) { setMessage(error instanceof Error ? error.message : "事件投影失败"); }
    finally { setBusy(false); }
  };

  const publish = async (eventId: string) => {
    const reason = window.prompt("请输入 Publisher 发布理由（至少 8 个字符）：");
    if (!reason || reason.trim().length < 8) { setMessage("发布理由至少需要 8 个字符。"); return; }
    if (!window.confirm(`确认公开发布 ${eventId}？这会创建不可覆盖的 L4 revision。`)) return;
    setBusy(true); setMessage(null);
    try {
      const result = await client.publishEvent(eventId, { actorId: publisher.trim(), reason,
        idempotencyKey: crypto.randomUUID() });
      setMessage(`已发布 ${result.publication_id} · revision ${result.revision}。`);
      await load(true);
    } catch (error: unknown) { setMessage(error instanceof Error ? error.message : "事件发布失败"); }
    finally { setBusy(false); }
  };

  return <div className="event-workbench">
    <div className="event-identities">
      <label>Processing Agent ID<input value={processor} onChange={(e) => setProcessor(e.target.value)} /></label>
      <label>Publisher ID<input value={publisher} onChange={(e) => setPublisher(e.target.value)} /></label>
      <p>原文选择形成精确 source span；新事件固定从 F1 开始，S 等级不会自动抬高 F。</p>
      <button type="button" onClick={() => void load()}>刷新事件状态</button>
    </div>
    {message ? <p className="form-message" role="status">{message}</p> : null}
    <div className="event-columns">
      <section><h3>已批准 L2 原文 <span>{data?.eligible_ingestions.length ?? 0}</span></h3>
        <div className="event-list">{data?.eligible_ingestions.map((item) => <article key={item.ingestion_id}>
          <div><strong>{item.title_original ?? item.ingestion_id}</strong><span>{item.source_name} · {item.source_grade}</span>
            <span>已投影 {item.projected_event_count} 个事件</span></div>
          <button type="button" disabled={busy} onClick={() => void openSource(item.ingestion_id)}>选择原文</button>
        </article>)}{data && !data.eligible_ingestions.length ? <p className="workbench-empty">暂无已批准 L2 原文。</p> : null}</div>
      </section>
      <section><h3>私有事件与发布 <span>{data?.events.length ?? 0}</span></h3>
        <div className="event-list">{data?.events.map((event) => <article key={event.event_id}>
          <div><div className="badges"><span className="badge neutral">{event.fact_level}</span>
            <span className={`badge ${event.blockers.length ? "blocked" : "ready"}`}>{event.blockers.length ? "未就绪" : "可发布"}</span></div>
            <strong>{event.title_zh}</strong><span>{event.event_id} · {event.event_date ?? "日期未知"}</span>
            {event.blockers.map((item) => <span className="blocker" key={item}>{item}</span>)}</div>
          {!event.blockers.length ? <button type="button" disabled={busy || !publisher.trim()}
            onClick={() => void publish(event.event_id)}>Publisher 发布</button> : null}
        </article>)}{data && !data.events.length ? <p className="workbench-empty">尚未生成私有事件。</p> : null}</div>
      </section>
    </div>
    {source ? <section className="event-extraction-form"><div><h3>从原文建立事件</h3><button type="button" onClick={() => setSource(null)}>关闭</button></div>
      <p>{source.title_original ?? source.document_id} · 请选择 textarea 中的精确原文片段。</p>
      <textarea className="source-text" readOnly value={source.text_original}
        onSelect={(e) => captureSelection(e.currentTarget)} />
      <div className="event-fields">
        <label>事件类型<select value={form.event_type} onChange={(e) => setForm({...form,event_type:e.target.value})}>
          {['investment','project_update','policy_update','company_update','tender','governance_update'].map(v=><option key={v}>{v}</option>)}</select></label>
        <label>事件日期<input type="date" value={form.event_date} onChange={(e)=>setForm({...form,event_date:e.target.value})}/></label>
        <label className="wide">中文标题<input value={form.title_zh} maxLength={160} onChange={(e)=>setForm({...form,title_zh:e.target.value})}/></label>
        <label className="wide">中文摘要<textarea rows={4} value={form.summary_zh} maxLength={800} onChange={(e)=>setForm({...form,summary_zh:e.target.value})}/></label>
        <label>产业代码（逗号）<input value={form.industries} onChange={(e)=>setForm({...form,industries:e.target.value})}/></label>
        <label>州属代码（逗号）<input value={form.states} onChange={(e)=>setForm({...form,states:e.target.value})}/></label>
        <label className="wide">原文片段<textarea readOnly rows={3} value={form.quote_original}/></label>
        <label className="wide">片段中文翻译<textarea rows={3} value={form.quote_zh} maxLength={500} onChange={(e)=>setForm({...form,quote_zh:e.target.value})}/></label>
        <label>模型 ID<input value={form.model_id} onChange={(e)=>setForm({...form,model_id:e.target.value})}/></label>
        <label>Prompt 版本<input value={form.prompt_version} onChange={(e)=>setForm({...form,prompt_version:e.target.value})}/></label>
      </div><button className="primary-action" type="button" disabled={busy || !form.quote_original}
        onClick={() => void project()}>生成私有 L3 事件</button>
    </section> : null}
  </div>;
}

function split(value: string): string[] { return value.split(",").map((item)=>item.trim()).filter(Boolean); }
