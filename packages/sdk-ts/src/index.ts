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
    const response = await this.fetchImpl(`${this.baseUrl}/changes`, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error(`MIPI API error: ${response.status}`);
    return response.json();
  }
}

