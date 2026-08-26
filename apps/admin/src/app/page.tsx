"use client";

import { MipiClient } from "@mipi/sdk-ts";
import type {
  IngestionCandidateVM,
  RobotsStatus,
  ReviewActorRole,
  ReviewDecisionAction,
  SourceDecisionAction,
  SourceVM,
} from "@mipi/view-models";
import { useCallback, useEffect, useMemo, useState } from "react";
import { SourceRegistrationForm } from "./source-registration-form";
import { SourceTrialApprovalForm } from "./source-trial-approval-form";

const statusLabels = {
  needs_review: "待审核",
  in_review: "审核中",
  approved: "已接收入库",
  returned: "已退回",
  rejected: "已拒绝",
  quarantined: "已隔离",
} as const;

const roleLabels: Record<ReviewActorRole, string> = {
  reviewer: "Reviewer",
  senior_reviewer: "Senior Reviewer",
  publisher: "Publisher",
  security_compliance: "Security / Compliance",
};

const sourceStatusLabels: Record<SourceVM["status"], string> = {
  candidate: "候选",
  trial: "试运行",
  active: "已激活",
  degraded: "已降级",
  inactive: "已停用",
  retired: "已退役",
};

export default function AdminHome() {
  const [records, setRecords] = useState<IngestionCandidateVM[]>([]);
  const [sources, setSources] = useState<SourceVM[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [actorId, setActorId] = useState("local-reviewer-1");
  const [actorRole, setActorRole] = useState<ReviewActorRole>("reviewer");
  const [sourceActorId, setSourceActorId] = useState("local-source-admin-1");
  const client = useMemo(
    () =>
      new MipiClient({
        baseUrl: process.env.NEXT_PUBLIC_MIPI_API_URL ?? "http://localhost:8000/v1",
      }),
    [],
  );

  const loadRecords = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [candidateData, sourceData] = await Promise.all([
        client.listIngestionCandidates({ limit: 100 }),
        client.listSources(100),
      ]);
      setRecords(candidateData);
      setSources(sourceData);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "无法读取审核队列");
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    void loadRecords();
  }, [loadRecords]);

  const decide = async (item: IngestionCandidateVM, action: ReviewDecisionAction) => {
    if (
      ["reject", "quarantine"].includes(action) &&
      !window.confirm("这项决定会终止当前审核任务，但不会删除原文和审计记录。继续吗？")
    ) {
      return;
    }
    const reason = window.prompt("请输入审核理由（至少 8 个字符）：");
    if (!reason) return;
    if (reason.trim().length < 8) {
      setError("审核理由至少需要 8 个字符。");
      return;
    }
    let limitations: string[] = [];
    if (action === "approve_with_limits") {
      const value = window.prompt("请输入限制条件；多项请用分号分隔：");
      limitations = value?.split(/[;；]/).map((part) => part.trim()).filter(Boolean) ?? [];
      if (limitations.length === 0) {
        setError("限制通过必须填写至少一项限制条件。");
        return;
      }
    }
    setBusy(item.review.review_task_id);
    setError(null);
    try {
      await client.decideReviewTask(item.review.review_task_id, {
        actorId,
        actorRole,
        action,
        reason,
        limitations,
      });
      await loadRecords();
    } catch (reasonValue: unknown) {
      setError(reasonValue instanceof Error ? reasonValue.message : "审核决定提交失败");
    } finally {
      setBusy(null);
    }
  };

  const decideSource = async (source: SourceVM, action: SourceDecisionAction) => {
    if (
      ["degrade", "deactivate", "retire"].includes(action) &&
      !window.confirm("该操作会限制或停止自动采集，但不会删除来源和历史。继续吗？")
    ) {
      return;
    }
    let robotsStatus: RobotsStatus | undefined;
    let accessNotes: string | undefined;
    let evidenceUrls: string[] = [];
    if (action === "activate") {
      const evidenceInput = window.prompt("请输入试采证据 URL；多项使用逗号分隔：");
      evidenceUrls = evidenceInput?.split(/[,，]/).map((item) => item.trim()).filter(Boolean) ?? [];
      if (evidenceUrls.length === 0) {
        setError("正式激活必须提供至少一个试采证据 URL。");
        return;
      }
      robotsStatus = source.robots_status;
    }
    const reason = window.prompt("请输入来源治理理由（至少 8 个字符）：");
    if (!reason) return;
    if (reason.trim().length < 8) {
      setError("来源治理理由至少需要 8 个字符。");
      return;
    }
    const busyKey = `source:${source.source_id}`;
    setBusy(busyKey);
    setError(null);
    try {
      await client.decideSource(source.source_id, {
        actorId: sourceActorId,
        idempotencyKey: crypto.randomUUID(),
        action,
        reason,
        robotsStatus,
        accessNotes,
        evidenceUrls,
      });
      await loadRecords();
    } catch (reasonValue: unknown) {
      setError(reasonValue instanceof Error ? reasonValue.message : "来源决定提交失败");
    } finally {
      setBusy(null);
    }
  };

  const reviewCount = records.filter((item) =>
    ["needs_review", "in_review"].includes(item.processing_status),
  ).length;
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
          <button className="refresh" disabled={loading} onClick={() => void loadRecords()}>
            {loading ? "正在同步…" : "刷新队列"}
          </button>
        </div>

        <div className="reviewer-bar">
          <label>
            审核人 ID
            <input value={actorId} onChange={(event) => setActorId(event.target.value)} />
          </label>
          <label>
            本地测试角色
            <select
              value={actorRole}
              onChange={(event) => setActorRole(event.target.value as ReviewActorRole)}
            >
              {Object.entries(roleLabels).map(([role, label]) => (
                <option key={role} value={role}>{label}</option>
              ))}
            </select>
          </label>
          <p>生产环境在接入身份系统前禁用审核写入；这里的角色选择仅供本地验证。</p>
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
                {["queued", "in_review"].includes(item.review.status) ? (
                  <div className="actions">
                    <button disabled={busy === item.review.review_task_id} onClick={() => void decide(item, "approve")}>通过</button>
                    <button disabled={busy === item.review.review_task_id} onClick={() => void decide(item, "approve_with_limits")}>限制通过</button>
                    <button disabled={busy === item.review.review_task_id} onClick={() => void decide(item, "return_for_fix")}>退回</button>
                    <button className="danger" disabled={busy === item.review.review_task_id} onClick={() => void decide(item, "reject")}>拒绝</button>
                    <button className="danger" disabled={busy === item.review.review_task_id} onClick={() => void decide(item, "quarantine")}>隔离</button>
                  </div>
                ) : null}
              </div>
              <div className="candidate-side">
                <span>{new Date(item.created_at).toLocaleString("zh-CN")}</span>
                <strong>{item.collection_relevance}</strong>
                <p>{item.review_flags.length ? item.review_flags.join(" · ") : "无自动标记"}</p>
                {item.review.decisions.length ? (
                  <div className="decision-history">
                    <strong>已有决定</strong>
                    {item.review.decisions.map((decision) => (
                      <span key={`${decision.actor_id}-${decision.created_at}`}>
                        {roleLabels[decision.actor_role]} · {decision.action} · {decision.actor_id}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            </article>
          ))}
        </div>

        <div className="queue-heading source-heading">
          <div>
            <p className="eyebrow">SOURCE GOVERNANCE</p>
            <h2>来源注册表</h2>
          </div>
          <span className="refresh-state">{sources.length} 个来源</span>
        </div>
        <div className="reviewer-bar source-admin-bar">
          <label>
            来源管理员 ID
            <input
              value={sourceActorId}
              maxLength={200}
              onChange={(event) => setSourceActorId(event.target.value)}
            />
          </label>
          <p>候选来源先进入小流量试采；正式激活必须补充试采证据。</p>
        </div>
        <SourceRegistrationForm
          actorId={sourceActorId}
          client={client}
          existingSourceIds={new Set(sources.map((source) => source.source_id))}
          onRegistered={async () => loadRecords()}
        />
        <div className="source-list">
          {sources.map((source) => {
            const busyKey = `source:${source.source_id}`;
            return (
              <article className="source-card" key={source.source_id}>
                <div>
                  <div className="badges">
                    <span className={`badge source-${source.status}`}>
                      {sourceStatusLabels[source.status]}
                    </span>
                    <span className="badge neutral">{source.source_grade}</span>
                    <span className="badge neutral">robots: {source.robots_status}</span>
                  </div>
                  <h3>{source.name}</h3>
                  <a href={source.base_url} rel="noreferrer" target="_blank">{source.base_url}</a>
                  <p>{source.owner} · {source.languages.join(" / ") || "语言未登记"}</p>
                  <p className="ids">{source.source_id} · {source.crawl_status}</p>
                </div>
                <div className="source-actions">
                  {source.status === "candidate" ? (
                    <>
                      <SourceTrialApprovalForm
                        actorId={sourceActorId}
                        client={client}
                        source={source}
                        onApproved={async () => loadRecords()}
                      />
                      <button className="danger" disabled={busy === busyKey} onClick={() => void decideSource(source, "retire")}>不采用</button>
                    </>
                  ) : null}
                  {["trial", "degraded", "inactive"].includes(source.status) ? (
                    <button disabled={busy === busyKey} onClick={() => void decideSource(source, "activate")}>激活</button>
                  ) : null}
                  {source.status === "active" ? (
                    <button disabled={busy === busyKey} onClick={() => void decideSource(source, "degrade")}>降级</button>
                  ) : null}
                  {["trial", "active", "degraded"].includes(source.status) ? (
                    <button className="danger" disabled={busy === busyKey} onClick={() => void decideSource(source, "deactivate")}>停用</button>
                  ) : null}
                  {source.status === "inactive" ? (
                    <button className="danger" disabled={busy === busyKey} onClick={() => void decideSource(source, "retire")}>退役</button>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </main>
  );
}
