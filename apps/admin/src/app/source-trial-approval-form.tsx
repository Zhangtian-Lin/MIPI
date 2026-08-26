"use client";

import type { MipiClient } from "@mipi/sdk-ts";
import type { RobotsStatus, SourceVM } from "@mipi/view-models";
import { useRef, useState } from "react";

interface SourceTrialApprovalFormProps {
  actorId: string;
  client: MipiClient;
  source: SourceVM;
  onApproved: (source: SourceVM) => Promise<void>;
}

export function SourceTrialApprovalForm({
  actorId,
  client,
  source,
  onApproved,
}: SourceTrialApprovalFormProps) {
  const [expanded, setExpanded] = useState(false);
  const [identityVerified, setIdentityVerified] = useState(false);
  const [termsReviewed, setTermsReviewed] = useState(false);
  const [authorityScopeReviewed, setAuthorityScopeReviewed] = useState(false);
  const [robotsStatus, setRobotsStatus] = useState<RobotsStatus>("unknown");
  const [accessNotes, setAccessNotes] = useState("");
  const [evidenceUrls, setEvidenceUrls] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const idempotencyKey = useRef<string | null>(null);
  const requestFingerprint = useRef<string | null>(null);

  const submit = async () => {
    if (!identityVerified || !termsReviewed || !authorityScopeReviewed) {
      setMessage("必须分别确认来源身份、访问条款和权威范围已由人工完成核验。");
      return;
    }
    if (!["allowed", "limited", "not_applicable"].includes(robotsStatus)) {
      setMessage("robots 结论必须是 allowed、limited 或 not_applicable。");
      return;
    }
    if (robotsStatus === "limited" && !accessNotes.trim()) {
      setMessage("limited 状态必须说明允许路径、频率和其他限制。");
      return;
    }
    if (reason.trim().length < 8) {
      setMessage("审批理由至少需要 8 个字符。");
      return;
    }
    const urls = splitUrls(evidenceUrls);
    if (urls.length > 20) {
      setMessage("单次决定最多记录 20 个证据链接。");
      return;
    }
    if (urls.some((url) => !isHttpUrl(url))) {
      setMessage("证据链接必须是有效的 HTTP 或 HTTPS URL；多项请换行填写。");
      return;
    }
    if (
      !window.confirm(
        `确认以 ${actorId} 的身份批准 ${source.source_id} 进入小流量试采？该决定会写入不可覆盖的审计记录。`,
      )
    ) {
      return;
    }

    const decision = {
      actorId: actorId.trim(),
      action: "approve_for_trial" as const,
      reason: reason.trim(),
      robotsStatus,
      accessNotes: robotsStatus === "limited" ? accessNotes.trim() : undefined,
      evidenceUrls: urls,
      identityVerified,
      termsReviewed,
      authorityScopeReviewed,
    };
    const nextFingerprint = JSON.stringify(decision);
    if (requestFingerprint.current !== nextFingerprint) {
      idempotencyKey.current = crypto.randomUUID();
      requestFingerprint.current = nextFingerprint;
    }
    setSubmitting(true);
    setMessage(null);
    try {
      const result = await client.decideSource(source.source_id, {
        ...decision,
        idempotencyKey: idempotencyKey.current!,
      });
      idempotencyKey.current = null;
      requestFingerprint.current = null;
      setMessage(`决定 ${result.decision_id} 已保存；来源现为 trial，仅允许小流量试采。`);
      await onApproved(result.source);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "试运行审批提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  if (!expanded) {
    return (
      <button type="button" disabled={!actorId.trim()} onClick={() => setExpanded(true)}>
        审核试运行
      </button>
    );
  }

  return (
    <div className="trial-approval-form">
      <div className="trial-approval-heading">
        <strong>试运行审批</strong>
        <button type="button" disabled={submitting} onClick={() => setExpanded(false)}>
          收起
        </button>
      </div>
      <p>以下确认必须由来源管理员根据实际证据逐项完成，Agent 不得代填。</p>
      <div className="approval-checklist">
        <label>
          <input
            type="checkbox"
            checked={identityVerified}
            onChange={(event) => setIdentityVerified(event.target.checked)}
          />
          来源主体身份已核验
        </label>
        <label>
          <input
            type="checkbox"
            checked={termsReviewed}
            onChange={(event) => setTermsReviewed(event.target.checked)}
          />
          访问与使用条款已检查
        </label>
        <label>
          <input
            type="checkbox"
            checked={authorityScopeReviewed}
            onChange={(event) => setAuthorityScopeReviewed(event.target.checked)}
          />
          权威范围和语言已审核
        </label>
      </div>
      <label>
        robots 结论
        <select
          value={robotsStatus}
          onChange={(event) => setRobotsStatus(event.target.value as RobotsStatus)}
        >
          <option value="unknown">unknown — 尚未核验</option>
          <option value="allowed">allowed — 允许</option>
          <option value="limited">limited — 有条件允许</option>
          <option value="not_applicable">not_applicable — 不适用</option>
          <option value="disallowed">disallowed — 禁止</option>
        </select>
      </label>
      {robotsStatus === "limited" ? (
        <label>
          访问限制
          <textarea
            value={accessNotes}
            onChange={(event) => setAccessNotes(event.target.value)}
            placeholder="允许路径、每分钟频率、禁止范围等"
            maxLength={2000}
            rows={3}
          />
        </label>
      ) : null}
      <label>
        核验依据链接（推荐填写，每行一个）
        <textarea
          value={evidenceUrls}
          onChange={(event) => setEvidenceUrls(event.target.value)}
          placeholder="https://example.gov.my/terms"
          rows={3}
        />
      </label>
      <label>
        审批理由
        <textarea
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="说明为什么允许进入小流量试采（至少 8 个字符）"
          maxLength={2000}
          rows={3}
        />
      </label>
      <div className="trial-approval-footer">
        <span>批准后仍不会正式激活来源。</span>
        <button
          className="primary-action"
          type="button"
          disabled={submitting || !actorId.trim()}
          onClick={() => void submit()}
        >
          {submitting ? "正在保存…" : "批准小流量试采"}
        </button>
      </div>
      {message ? <p className="form-message" role="status">{message}</p> : null}
    </div>
  );
}

function splitUrls(value: string): string[] {
  return [...new Set(value.split(/[\n,，]/).map((item) => item.trim()).filter(Boolean))];
}

function isHttpUrl(value: string): boolean {
  try {
    return ["http:", "https:"].includes(new URL(value).protocol);
  } catch {
    return false;
  }
}
