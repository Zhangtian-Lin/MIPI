"use client";

import type { MipiClient } from "@mipi/sdk-ts";
import type { TradeWorkbenchVM } from "@mipi/view-models";
import { useCallback, useEffect, useRef, useState } from "react";

interface TradePublicationWorkbenchProps {
  client: MipiClient;
}

export function TradePublicationWorkbench({ client }: TradePublicationWorkbenchProps) {
  const [workbench, setWorkbench] = useState<TradeWorkbenchVM | null>(null);
  const [processingActorId, setProcessingActorId] = useState("local-trade-processor-1");
  const [publisherId, setPublisherId] = useState("local-publisher-1");
  const [publishingBatch, setPublishingBatch] = useState<string | null>(null);
  const [publicationReason, setPublicationReason] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const publicationKey = useRef<string | null>(null);
  const publicationFingerprint = useRef<string | null>(null);

  const load = useCallback(async (preserveMessage = false) => {
    if (!processingActorId.trim()) return;
    if (!preserveMessage) setMessage(null);
    try {
      setWorkbench(await client.getTradeWorkbench(processingActorId.trim()));
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "贸易工作台读取失败");
    }
  }, [client, processingActorId]);

  useEffect(() => {
    void load();
  }, [load]);

  const project = async (ingestionId: string) => {
    if (
      !window.confirm(
        `确认将 ${ingestionId} 标准化为私有 L3 批次？这不会公开任何数据。`,
      )
    ) {
      return;
    }
    setBusy(`project:${ingestionId}`);
    setMessage(null);
    try {
      const batch = await client.projectTradeIndicators(
        ingestionId,
        processingActorId.trim(),
      );
      setMessage(`已生成 ${batch.batch_id}；当前仍为 ${batch.status}。`);
      await load(true);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "L3 标准化失败");
    } finally {
      setBusy(null);
    }
  };

  const publish = async (batchId: string) => {
    if (publicationReason.trim().length < 8) {
      setMessage("发布理由至少需要 8 个字符。");
      return;
    }
    const decision = {
      actorId: publisherId.trim(),
      batchId,
      reason: publicationReason.trim(),
    };
    const fingerprint = JSON.stringify(decision);
    if (publicationFingerprint.current !== fingerprint) {
      publicationFingerprint.current = fingerprint;
      publicationKey.current = crypto.randomUUID();
    }
    if (
      !window.confirm(
        `确认以 Publisher ${publisherId} 的身份发布 ${batchId}？该操作会创建公开 L4 revision 和不可覆盖的审计记录。`,
      )
    ) {
      return;
    }
    setBusy(`publish:${batchId}`);
    setMessage(null);
    try {
      const overview = await client.publishTradeIndicators(batchId, {
        actorId: publisherId.trim(),
        idempotencyKey: publicationKey.current!,
        reason: publicationReason.trim(),
      });
      publicationFingerprint.current = null;
      publicationKey.current = null;
      setPublicationReason("");
      setPublishingBatch(null);
      setMessage(
        `已发布 ${overview.publication_id} · revision ${overview.revision}。`,
      );
      await load(true);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "贸易投影发布失败");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="trade-workbench">
      <div className="trade-workbench-identities">
        <label>
          Processing Agent ID
          <input
            value={processingActorId}
            maxLength={200}
            onChange={(event) => setProcessingActorId(event.target.value)}
          />
        </label>
        <label>
          Publisher ID
          <input
            value={publisherId}
            maxLength={200}
            onChange={(event) => setPublisherId(event.target.value)}
          />
        </label>
        <p>Processing 只能写入私有 L3；只有 Publisher 可以创建公开 L4 revision。</p>
        <button type="button" disabled={!processingActorId.trim()} onClick={() => void load()}>
          刷新贸易状态
        </button>
      </div>

      {message ? <p className="form-message" role="status">{message}</p> : null}

      <div className="trade-workbench-grid">
        <div>
          <div className="subsection-heading">
            <strong>可标准化的 L2 采集</strong>
            <span>{workbench?.eligible_ingestions.length ?? 0} 条</span>
          </div>
          <div className="workbench-list">
            {workbench?.eligible_ingestions.map((item) => (
              <article key={item.ingestion_id}>
                <div>
                  <strong>{item.ingestion_id}</strong>
                  <span>{item.document_id} · {new Date(item.created_at).toLocaleString("zh-CN")}</span>
                  <a href={item.canonical_url} target="_blank" rel="noreferrer">
                    {item.canonical_url}
                  </a>
                </div>
                <button
                  type="button"
                  disabled={item.projected || busy === `project:${item.ingestion_id}`}
                  onClick={() => void project(item.ingestion_id)}
                >
                  {item.projected ? "已有 L3 批次" : "生成私有 L3"}
                </button>
              </article>
            ))}
            {workbench && workbench.eligible_ingestions.length === 0 ? (
              <p className="workbench-empty">暂无已通过 L2 的 trade_sitc_1d 采集。</p>
            ) : null}
          </div>
        </div>

        <div>
          <div className="subsection-heading">
            <strong>L3 批次与 L4 发布</strong>
            <span>{workbench?.batches.length ?? 0} 个</span>
          </div>
          <div className="workbench-list batch-list">
            {workbench?.batches.map((batch) => (
              <article key={batch.batch_id}>
                <div>
                  <div className="badges">
                    <span className="badge neutral">{batch.status}</span>
                    <span className="badge neutral">{batch.fact_level}</span>
                    <span className={`badge ${batch.publication_ready ? "ready" : "blocked"}`}>
                      {batch.publication_ready ? "可发布" : "未就绪"}
                    </span>
                  </div>
                  <strong>{batch.batch_id}</strong>
                  <span>
                    {batch.period_start} → {batch.period_end} · {batch.observation_count} 条
                  </span>
                  {batch.publication_id ? (
                    <span>{batch.publication_id} · revision {batch.revision}</span>
                  ) : null}
                  {batch.blockers.map((blocker) => (
                    <span className="blocker" key={blocker}>{blockerLabel(blocker)}</span>
                  ))}
                </div>
                {batch.publication_ready ? (
                  <button
                    type="button"
                    disabled={!publisherId.trim()}
                    onClick={() => setPublishingBatch(batch.batch_id)}
                  >
                    填写发布决定
                  </button>
                ) : null}
                {publishingBatch === batch.batch_id ? (
                  <div className="publication-decision-form">
                    <label>
                      Publisher 发布理由
                      <textarea
                        value={publicationReason}
                        maxLength={2000}
                        rows={4}
                        onChange={(event) => setPublicationReason(event.target.value)}
                      />
                    </label>
                    <p>请复核数据期、完整性、F4、修订提示和证据入口后再发布。</p>
                    <div>
                      <button type="button" onClick={() => setPublishingBatch(null)}>取消</button>
                      <button
                        className="primary-action"
                        type="button"
                        disabled={busy === `publish:${batch.batch_id}` || !publisherId.trim()}
                        onClick={() => void publish(batch.batch_id)}
                      >
                        {busy === `publish:${batch.batch_id}` ? "正在发布…" : "发布 L4 revision"}
                      </button>
                    </div>
                  </div>
                ) : null}
              </article>
            ))}
            {workbench && workbench.batches.length === 0 ? (
              <p className="workbench-empty">尚未生成贸易 L3 批次。</p>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function blockerLabel(value: string): string {
  if (value.includes("at least 12")) return "缺少至少 12 个月的总额记录";
  if (value.includes("consecutive")) return "最近 12 个月存在断档";
  if (value.includes("missing sections")) return `最新月 SITC 分区不完整：${value.split(": ")[1] ?? ""}`;
  if (value.includes("F4")) return "尚未达到 F4 权威记录验证";
  if (value.includes("already published")) return "该批次已经发布";
  return value;
}
