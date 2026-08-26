import type {
  EventPublicationVM,
  EventSourceTextVM,
  EventWorkbenchVM,
  IngestionCandidateVM,
  IngestionProcessingStatus,
  ReviewActorRole,
  ReviewDecisionAction,
  ReviewDecisionResultVM,
  RobotsStatus,
  SourceDecisionAction,
  SourceRegistrationDraftVM,
  SourceVM,
  TradeBatchVM,
  TradeOverviewVM,
  TradeWorkbenchVM,
} from "@mipi/view-models";

export interface MipiClientOptions {
  baseUrl: string;
  fetchImpl?: typeof fetch;
}

export class MipiApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "MipiApiError";
  }
}

export class MipiClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: MipiClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.fetchImpl = options.fetchImpl ?? globalThis.fetch.bind(globalThis);
  }

  async listChanges(options: {
    industry?: string;
    state?: string;
    eventType?: string;
    limit?: number;
  } = {}): Promise<EventPublicationVM[]> {
    const query = new URLSearchParams();
    if (options.industry) query.set("industry", options.industry);
    if (options.state) query.set("state", options.state);
    if (options.eventType) query.set("event_type", options.eventType);
    if (options.limit) query.set("limit", String(options.limit));
    const suffix = query.size ? `?${query.toString()}` : "";
    const response = await this.get<ApiEnvelope<EventPublicationVM[]>>(`/changes${suffix}`);
    return response.data;
  }

  async getEvent(eventId: string): Promise<EventPublicationVM> {
    const response = await this.get<ApiEnvelope<EventPublicationVM>>(
      `/events/${encodeURIComponent(eventId)}`,
    );
    return response.data;
  }

  async getEventWorkbench(actorId: string, limit = 100): Promise<EventWorkbenchVM> {
    const response = await this.request<ApiEnvelope<EventWorkbenchVM>>(
      `/admin/events/workbench?limit=${encodeURIComponent(String(limit))}`,
      { headers: { Accept: "application/json", "X-Actor-ID": actorId,
                   "X-Actor-Role": "processing_agent" } },
    );
    return response.data;
  }

  async getEventSource(ingestionId: string, actorId: string): Promise<EventSourceTextVM> {
    const response = await this.request<ApiEnvelope<EventSourceTextVM>>(
      `/admin/events/ingestions/${encodeURIComponent(ingestionId)}/source`,
      { headers: { Accept: "application/json", "X-Actor-ID": actorId,
                   "X-Actor-Role": "processing_agent" } },
    );
    return response.data;
  }

  async projectEvent(
    payload: Record<string, unknown>, actorId: string, idempotencyKey: string,
  ): Promise<EventWorkbenchVM["events"][number]> {
    const response = await this.request<ApiEnvelope<EventWorkbenchVM["events"][number]>>(
      "/admin/events/project",
      { method: "POST", headers: { "Content-Type": "application/json", "X-Actor-ID": actorId,
          "X-Actor-Role": "processing_agent", "Idempotency-Key": idempotencyKey },
        body: JSON.stringify(payload) },
    );
    return response.data;
  }

  async publishEvent(
    eventId: string,
    decision: { actorId: string; reason: string; idempotencyKey: string },
  ): Promise<EventPublicationVM> {
    const response = await this.request<ApiEnvelope<EventPublicationVM>>(
      `/admin/events/${encodeURIComponent(eventId)}/publish`,
      { method: "POST", headers: { "Content-Type": "application/json",
          "X-Actor-ID": decision.actorId, "X-Actor-Role": "publisher",
          "Idempotency-Key": decision.idempotencyKey },
        body: JSON.stringify({ reason: decision.reason, rule_version: "event-publication-v1.0" }) },
    );
    return response.data;
  }

  async getTradeOverview(): Promise<TradeOverviewVM | null> {
    const response = await this.get<ApiEnvelope<TradeOverviewVM | null>>("/trade/overview");
    return response.data;
  }

  async projectTradeIndicators(
    ingestionId: string,
    actorId: string,
    ruleVersion = "trade-sitc-v1.0",
  ): Promise<TradeBatchVM> {
    const response = await this.request<ApiEnvelope<TradeBatchVM>>(
      "/admin/trade-indicators/project",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Actor-ID": actorId,
          "X-Actor-Role": "processing_agent",
        },
        body: JSON.stringify({ ingestion_id: ingestionId, rule_version: ruleVersion }),
      },
    );
    return response.data;
  }

  async getTradeWorkbench(actorId: string, limit = 100): Promise<TradeWorkbenchVM> {
    const response = await this.request<ApiEnvelope<TradeWorkbenchVM>>(
      `/admin/trade-indicators/workbench?limit=${encodeURIComponent(String(limit))}`,
      {
        headers: {
          Accept: "application/json",
          "X-Actor-ID": actorId,
          "X-Actor-Role": "processing_agent",
        },
      },
    );
    return response.data;
  }

  async publishTradeIndicators(
    batchId: string,
    decision: {
      actorId: string;
      idempotencyKey: string;
      reason: string;
      ruleVersion?: string;
    },
  ): Promise<TradeOverviewVM> {
    const response = await this.request<ApiEnvelope<TradeOverviewVM>>(
      `/admin/trade-indicators/${encodeURIComponent(batchId)}/publish`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Actor-ID": decision.actorId,
          "X-Actor-Role": "publisher",
          "Idempotency-Key": decision.idempotencyKey,
        },
        body: JSON.stringify({
          reason: decision.reason,
          rule_version: decision.ruleVersion ?? "trade-publication-v1.0",
        }),
      },
    );
    return response.data;
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
      throw new MipiApiError(response.status, `MIPI API error: ${response.status}${detail}`);
    }
    return response.json() as Promise<T>;
  }
}

interface ApiEnvelope<T> {
  data: T;
  meta: { contract_version: string; count?: number; duplicate?: boolean };
  error: null;
}
