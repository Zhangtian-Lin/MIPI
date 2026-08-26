"use client";

import type { MipiClient } from "@mipi/sdk-ts";
import type { SourceRegistrationDraftVM, SourceVM } from "@mipi/view-models";
import { useState } from "react";

const dataGovMyPreset: SourceRegistrationDraftVM = {
  source_id: "SRC-MY-DATAGOV",
  name: "Malaysia Official Open Data Portal",
  owner: "Jabatan Digital Negara / Ministry of Digital",
  base_url: "https://data.gov.my/",
  source_grade: "S2",
  authority_scope: ["official_open_data", "statistics", "dataset_catalogue"],
  languages: ["en", "ms"],
};

interface SourceRegistrationFormProps {
  actorId: string;
  client: MipiClient;
  existingSourceIds: Set<string>;
  onRegistered: (source: SourceVM) => Promise<void>;
}

export function SourceRegistrationForm({
  actorId,
  client,
  existingSourceIds,
  onRegistered,
}: SourceRegistrationFormProps) {
  const [draft, setDraft] = useState<SourceRegistrationDraftVM>(dataGovMyPreset);
  const [authorityScope, setAuthorityScope] = useState(
    dataGovMyPreset.authority_scope.join(", "),
  );
  const [languages, setLanguages] = useState(dataGovMyPreset.languages.join(", "));
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const alreadyRegistered = existingSourceIds.has(draft.source_id);

  const loadDataGovPreset = () => {
    setDraft(dataGovMyPreset);
    setAuthorityScope(dataGovMyPreset.authority_scope.join(", "));
    setLanguages(dataGovMyPreset.languages.join(", "));
    setMessage(null);
  };

  const submit = async () => {
    const scopes = splitList(authorityScope);
    const languageList = splitList(languages);
    if (!/^SRC-[A-Za-z0-9][A-Za-z0-9._-]*$/.test(draft.source_id)) {
      setMessage("来源 ID 必须以 SRC- 开头，且只能包含字母、数字、点、下划线和连字符。");
      return;
    }
    if (!draft.name.trim() || !draft.owner.trim() || scopes.length === 0 || languageList.length === 0) {
      setMessage("名称、所有者、权威范围和语言均不能为空。");
      return;
    }
    try {
      const parsedUrl = new URL(draft.base_url);
      if (!["http:", "https:"].includes(parsedUrl.protocol)) throw new Error("invalid protocol");
    } catch {
      setMessage("请输入有效的 HTTP 或 HTTPS 来源入口。");
      return;
    }
    if (
      !window.confirm(
        "此操作只登记候选来源，不会批准联网采集或改变 S 等级。确认登记吗？",
      )
    ) {
      return;
    }
    setSubmitting(true);
    setMessage(null);
    try {
      const source = await client.registerSource(
        {
          ...draft,
          name: draft.name.trim(),
          owner: draft.owner.trim(),
          base_url: draft.base_url.trim(),
          authority_scope: scopes,
          languages: languageList,
        },
        actorId,
      );
      setMessage(`已登记 ${source.source_id}；当前仍为 candidate，尚未允许采集。`);
      await onRegistered(source);
    } catch (reason: unknown) {
      setMessage(reason instanceof Error ? reason.message : "来源登记失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="source-registration">
      <div className="source-registration-heading">
        <div>
          <strong>登记候选来源</strong>
          <p id="source-registration-note">
            登记与批准分离。这里不会启用采集，也不会把 S2 自动提升为更高事实等级。
          </p>
        </div>
        <button type="button" onClick={loadDataGovPreset}>载入 data.gov.my 候选</button>
      </div>
      <div className="source-form-grid" aria-describedby="source-registration-note">
        <label>
          来源 ID
          <input
            value={draft.source_id}
            onChange={(event) => setDraft({ ...draft, source_id: event.target.value })}
          />
        </label>
        <label>
          建议来源等级
          <select
            value={draft.source_grade}
            onChange={(event) =>
              setDraft({
                ...draft,
                source_grade: event.target.value as SourceRegistrationDraftVM["source_grade"],
              })
            }
          >
            {(["S1", "S2", "S3", "S4", "S5", "S6"] as const).map((grade) => (
              <option key={grade} value={grade}>{grade}</option>
            ))}
          </select>
        </label>
        <label>
          名称
          <input
            value={draft.name}
            onChange={(event) => setDraft({ ...draft, name: event.target.value })}
          />
        </label>
        <label>
          所有者
          <input
            value={draft.owner}
            onChange={(event) => setDraft({ ...draft, owner: event.target.value })}
          />
        </label>
        <label className="wide-field">
          来源入口
          <input
            type="url"
            value={draft.base_url}
            onChange={(event) => setDraft({ ...draft, base_url: event.target.value })}
          />
        </label>
        <label>
          权威范围（逗号分隔）
          <input value={authorityScope} onChange={(event) => setAuthorityScope(event.target.value)} />
        </label>
        <label>
          语言（逗号分隔）
          <input value={languages} onChange={(event) => setLanguages(event.target.value)} />
        </label>
      </div>
      <div className="source-registration-footer">
        <p>
          data.gov.my：官方 Open API；Data Catalogue 标注 CC BY 4.0；限速 4 次/分钟。
        </p>
        <button
          className="primary-action"
          type="button"
          disabled={submitting || alreadyRegistered || !actorId.trim()}
          onClick={() => void submit()}
        >
          {alreadyRegistered ? "该来源已登记" : submitting ? "正在登记…" : "登记为候选"}
        </button>
      </div>
      {message ? <p className="form-message" role="status">{message}</p> : null}
    </div>
  );
}

function splitList(value: string): string[] {
  return [...new Set(value.split(/[,，]/).map((item) => item.trim()).filter(Boolean))];
}
