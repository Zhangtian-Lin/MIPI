import type {
  IngestionCandidateVM,
  IngestionProcessingStatus,
  ReviewActorRole,
  ReviewDecisionAction,
  ReviewDecisionResultVM,
  RobotsStatus,
  SourceDecisionAction,
  SourceRegistrationDraftVM,
  SourceVM,
} from "@mipi/view-models";

export interface MipiClientOptions {
  baseUrl: string;
  fetchImpl?: typeof fetch;
}

export class MipiClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: MipiClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.fetchImpl = options.fetchImpl ?? globalThis.fetch.bind(globalThis);
  }

  async listChanges(): Promise<unknown> {
    return this.get("/changes");
  }

  async listIngestionCandidates(options: {
    limit?: number;
    status?: IngestionProcessingStatus;
  } = {}): Promise<IngestionCandidateVM[]> {
    const query = new URLSearchParams();
    if (options.limit !== undefined) query.set("limit", String(options.limit));
    if (options.status !== undefined) query.set("status", options.status);
    const suffix = query.size === 0 ? "" : `?${query.toString()}`;
    const response = await this.get<ApiEnvelope<IngestionCandidateVM[]>>(
      `/admin/ingestion-records${suffix}`,
    );
    return response.data;
  }

  async decideReviewTask(
    reviewTaskId: string,
    decision: {
      actorId: string;
      actorRole: ReviewActorRole;
      action: ReviewDecisionAction;
      reason: string;
      limitations?: string[];
      ruleVersion?: string;
    },
  ): Promise<ReviewDecisionResultVM> {
    const response = await this.request<ApiEnvelope<ReviewDecisionResultVM>>(
      `/admin/review-tasks/${encodeURIComponent(reviewTaskId)}/decisions`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Actor-ID": decision.actorId,
          "X-Actor-Role": decision.actorRole,
        },
        body: JSON.stringify({
          action: decision.action,
          reason: decision.reason,
          limitations: decision.limitations ?? [],
          rule_version: decision.ruleVersion ?? "review-v1.0",
        }),
      },
    );
    return response.data;
  }

  async listSources(limit = 100): Promise<SourceVM[]> {
    const response = await this.get<ApiEnvelope<SourceVM[]>>(
      `/admin/sources?limit=${encodeURIComponent(String(limit))}`,
    );
    return response.data;
  }

  async registerSource(
    registration: SourceRegistrationDraftVM,
    actorId: string,
  ): Promise<SourceVM> {
    const response = await this.request<ApiEnvelope<SourceVM>>("/admin/sources", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Actor-ID": actorId,
        "X-Actor-Role": "source_admin",
      },
      body: JSON.stringify(registration),
    });
    return response.data;
  }

  async decideSource(
    sourceId: string,
    decision: {
      actorId: string;
      idempotencyKey: string;
      action: SourceDecisionAction;
      reason: string;
      robotsStatus?: RobotsStatus;
      identityVerified?: boolean;
      termsReviewed?: boolean;
      authorityScopeReviewed?: boolean;
      evidenceUrls?: string[];
      accessNotes?: string;
      ruleVersion?: string;
    },
  ): Promise<{ decision_id: string; source: SourceVM }> {
    const response = await this.request<
      ApiEnvelope<{ decision_id: string; source: SourceVM }>
    >(`/admin/sources/${encodeURIComponent(sourceId)}/decisions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Actor-ID": decision.actorId,
        "X-Actor-Role": "source_admin",
        "Idempotency-Key": decision.idempotencyKey,
      },
      body: JSON.stringify({
        action: decision.action,
        reason: decision.reason,
        rule_version: decision.ruleVersion ?? "source-review-v1.0",
        identity_verified: decision.identityVerified ?? false,
        terms_reviewed: decision.termsReviewed ?? false,
        authority_scope_reviewed: decision.authorityScopeReviewed ?? false,
        robots_status: decision.robotsStatus,
        evidence_urls: decision.evidenceUrls ?? [],
        access_notes: decision.accessNotes,
      }),
    });
    return response.data;
  }

  private async get<T>(path: string): Promise<T> {
    return this.request(path, { headers: { Accept: "application/json" } });
  }

  private async request<T>(path: string, init: RequestInit): Promise<T> {
    const response = await this.fetchImpl(`${this.baseUrl}${path}`, init);
    if (!response.ok) {
      let detail = "";
      try {
        const body = (await response.json()) as {
          error?: { code?: string; message?: string };
        };
        if (body.error?.code || body.error?.message) {
          detail = ` · ${body.error.code ?? "API_ERROR"}: ${body.error.message ?? "请求失败"}`;
        }
      } catch {
        // The status remains useful when an upstream proxy returns a non-JSON error page.
      }
      throw new Error(`MIPI API error: ${response.status}${detail}`);
    }
    return response.json() as Promise<T>;
  }
}

interface ApiEnvelope<T> {
  data: T;
  meta: { contract_version: string; count?: number; duplicate?: boolean };
  error: null;
}
