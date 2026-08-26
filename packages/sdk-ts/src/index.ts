import type { IngestionCandidateVM, IngestionProcessingStatus } from "@mipi/view-models";

export interface MipiClientOptions {
  baseUrl: string;
  fetchImpl?: typeof fetch;
}

export class MipiClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: MipiClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.fetchImpl = options.fetchImpl ?? fetch;
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

  private async get<T>(path: string): Promise<T> {
    const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error(`MIPI API error: ${response.status}`);
    return response.json() as Promise<T>;
  }
}

interface ApiEnvelope<T> {
  data: T;
  meta: { contract_version: string; count?: number; duplicate?: boolean };
  error: null;
}
