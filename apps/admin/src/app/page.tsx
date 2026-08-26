"use client";

import { MipiClient } from "@mipi/sdk-ts";
import type { IngestionCandidateVM } from "@mipi/view-models";
import { useEffect, useMemo, useState } from "react";

const statusLabels = {
  needs_review: "待审核",
  quarantined: "已隔离",
} as const;

export default function AdminHome() {
  const [records, setRecords] = useState<IngestionCandidateVM[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const client = useMemo(
    () =>
      new MipiClient({
        baseUrl: process.env.NEXT_PUBLIC_MIPI_API_URL ?? "http://localhost:8000/v1",
      }),
    [],
  );

  useEffect(() => {
    let active = true;
    client
      .listIngestionCandidates({ limit: 100 })
      .then((data) => {
        if (active) setRecords(data);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "无法读取审核队列");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [client]);

  const reviewCount = records.filter((item) => item.processing_status === "needs_review").length;
  const quarantinedCount = records.filter(
    (item) => item.processing_status === "quarantined",
  ).length;

  return (
    <main>
      <header>
        <strong>MIPI Admin</strong>
        <span>采集与证据工作台 · L2</span>
      </header>
      <section>
        <p className="eyebrow">INGESTION CONTROL</p>
        <h1>采集候选审核</h1>
        <p className="lede">原文已经留存，但这里的记录尚未获准进入公开产品。</p>

        <div className="metrics">
          <article>
            <h2>待审核</h2>
            <strong>{reviewCount}</strong>
            <p>需要核验来源、相关性与字段</p>
          </article>
          <article>
            <h2>已隔离</h2>
            <strong>{quarantinedCount}</strong>
            <p>包含高风险内容或指令模式</p>
          </article>
          <article>
            <h2>候选总量</h2>
            <strong>{records.length}</strong>
            <p>仅统计当前加载的 L2 记录</p>
          </article>
        </div>

        <div className="queue-heading">
          <div>
            <p className="eyebrow">REVIEW QUEUE</p>
            <h2>最新候选</h2>
          </div>
          <span className="refresh-state">{loading ? "正在同步…" : "已同步"}</span>
        </div>

        {error ? <div className="notice error">API 暂不可用：{error}</div> : null}
        {!loading && !error && records.length === 0 ? (
          <div className="notice">暂无候选。采集 agent 提交成功后会出现在这里。</div>
        ) : null}

        <div className="candidate-list">
          {records.map((item) => (
            <article className="candidate" key={item.ingestion_id}>
              <div className="candidate-main">
                <div className="badges">
                  <span className={`badge ${item.processing_status}`}>
                    {statusLabels[item.processing_status]}
                  </span>
                  <span className="badge neutral">{item.review.risk_level}</span>
                  <span className="badge neutral">{item.source.source_grade}</span>
                </div>
                <h3>{item.source.name}</h3>
                <a href={item.canonical_url} rel="noreferrer" target="_blank">
                  {item.canonical_url}
                </a>
                <p className="ids">
                  {item.ingestion_id} · {item.document_id} · v{item.version_number}
                </p>
              </div>
              <div className="candidate-side">
                <span>{new Date(item.created_at).toLocaleString("zh-CN")}</span>
                <strong>{item.collection_relevance}</strong>
                <p>{item.review_flags.length ? item.review_flags.join(" · ") : "无自动标记"}</p>
              </div>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
