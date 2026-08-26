import type { FactLevel, SourceGrade } from "@mipi/shared-ts";

export interface ImportantChangeCardVM {
  eventId: string;
  title: string;
  summary: string;
  eventDate: string;
  factLevel: FactLevel;
  highestSourceGrade: SourceGrade;
  independentSourceCount: number;
  conflict: boolean;
  industries: string[];
  locations: string[];
}

export type IngestionProcessingStatus =
  | "needs_review"
  | "in_review"
  | "approved"
  | "returned"
  | "rejected"
  | "quarantined";
export type ReviewRiskLevel = "R0" | "R1" | "R2" | "R3";
export type ReviewActorRole =
  | "reviewer"
  | "senior_reviewer"
  | "publisher"
  | "security_compliance";
export type ReviewDecisionAction =
  | "approve"
  | "approve_with_limits"
  | "return_for_fix"
  | "reject"
  | "quarantine";

export interface IngestionCandidateVM {
  ingestion_id: string;
  task_id: string;
  source: {
    source_id: string;
    name: string;
    source_grade: SourceGrade;
  };
  document_id: string;
  version_number: number;
  canonical_url: string;
  content_hash: string;
  raw_object_uri: string;
  collection_relevance: "high" | "medium" | "low" | "unknown";
  verification_hint: FactLevel | null;
  publication_status: "raw_only" | "staged" | "under_review" | "rejected" | "quarantined";
  processing_status: IngestionProcessingStatus;
  review_flags: string[];
  review: {
    review_task_id: string;
    status: string;
    risk_level: ReviewRiskLevel;
    decisions: Array<{
      actor_id: string;
      actor_role: ReviewActorRole;
      action: ReviewDecisionAction;
      created_at: string;
    }>;
  };
  created_at: string;
}

export interface ReviewDecisionResultVM {
  review_task_id: string;
  ingestion_id: string;
  task_status: string;
  processing_status: IngestionProcessingStatus;
  publication_status: IngestionCandidateVM["publication_status"];
  risk_level: ReviewRiskLevel;
  decision_count: number;
  completed: boolean;
}

export type SourceLifecycleStatus =
  | "candidate"
  | "trial"
  | "active"
  | "degraded"
  | "inactive"
  | "retired";
export type RobotsStatus = "unknown" | "allowed" | "limited" | "disallowed" | "not_applicable";
export type SourceDecisionAction =
  | "approve_for_trial"
  | "activate"
  | "degrade"
  | "deactivate"
  | "retire";

export interface SourceRegistrationDraftVM {
  source_id: string;
  name: string;
  owner: string;
  base_url: string;
  source_grade: SourceGrade;
  authority_scope: string[];
  languages: string[];
}

export interface SourceVM {
  source_id: string;
  name: string;
  owner: string;
  base_url: string;
  source_grade: SourceGrade;
  authority_scope: string[];
  languages: string[];
  status: SourceLifecycleStatus;
  crawl_status: string;
  robots_status: RobotsStatus;
  terms_reviewed_at: string | null;
  identity_verified_at: string | null;
  last_reviewed_at: string | null;
  review_due_at: string | null;
  access_notes: string | null;
}

export interface TradeOverviewVM {
  publication_id: string;
  revision: number;
  published_at: string;
  dataset_id: "trade_sitc_1d";
  title: string;
  unit: "RM million";
  latest_period: string;
  provisional_periods: string[];
  latest: {
    exports_rm_million: number;
    imports_rm_million: number;
    balance_rm_million: number;
    exports_mom_percent: number | null;
    imports_mom_percent: number | null;
  };
  timeline: Array<{
    period: string;
    exports_rm_million: number;
    imports_rm_million: number;
    balance_rm_million: number;
    provisional: boolean;
  }>;
  sections: Array<{
    section: string;
    label_zh: string;
    exports_rm_million: number;
    imports_rm_million: number;
    balance_rm_million: number;
  }>;
  fact_level: "F4";
  caveats: string[];
  evidence: {
    source_id: string;
    source_name: string;
    source_grade: "S2";
    ingestion_id: string;
    document_id: string;
    document_version: number;
    canonical_url: string;
    content_hash: string;
    crawled_at: string;
    license: string | null;
    license_url: string | null;
    attribution: string | null;
  };
}

export interface TradeBatchVM {
  batch_id: string;
  ingestion_id: string;
  dataset_id: "trade_sitc_1d";
  status: "canonical_private" | "published" | "rejected";
  observation_count: number;
}

export interface TradeWorkbenchVM {
  eligible_ingestions: Array<{
    ingestion_id: string;
    document_id: string;
    canonical_url: string;
    content_hash: string;
    created_at: string;
    projected: boolean;
  }>;
  batches: Array<{
    batch_id: string;
    ingestion_id: string;
    status: TradeBatchVM["status"];
    fact_level: FactLevel;
    observation_count: number;
    period_start: string;
    period_end: string;
    publication_ready: boolean;
    blockers: string[];
    publication_id: string | null;
    revision: number | null;
    created_at: string;
  }>;
}

export interface EventPublicationVM {
  event_id: string;
  publication_id: string;
  revision: number;
  published_at: string;
  event_type: string;
  title_zh: string;
  summary_zh: string;
  event_date: string | null;
  event_date_precision: "day" | "month" | "year" | "unknown";
  fact_level: FactLevel;
  conflict: boolean;
  industries: string[];
  states: string[];
  independent_source_count: number;
  caveats: string[];
  evidence: Array<{
    claim_id: string;
    source_id: string;
    source_name: string;
    source_grade: SourceGrade;
    document_id: string;
    document_version: number;
    canonical_url: string;
    language: string | null;
    published_at: string | null;
    crawled_at: string;
    source_span: {
      start: number;
      end: number;
      quote_original: string;
      quote_zh: string;
      model_id: string;
      prompt_version: string;
    };
    independence_group: string;
  }>;
}

export interface EventWorkbenchVM {
  eligible_ingestions: Array<{
    ingestion_id: string;
    document_id: string;
    source_name: string;
    source_grade: SourceGrade;
    canonical_url: string;
    title_original: string | null;
    language: string | null;
    created_at: string;
    projected_event_count: number;
  }>;
  events: Array<{
    event_id: string;
    ingestion_id: string;
    publication_status: string;
    fact_level: FactLevel;
    title_zh: string;
    summary_zh: string;
    event_type: string;
    event_date: string | null;
    industries: string[];
    states: string[];
    conflict: boolean;
    blockers: string[];
    publication_id: string | null;
    revision: number | null;
    duplicate: boolean;
  }>;
}

export interface EventSourceTextVM {
  ingestion_id: string;
  document_id: string;
  title_original: string | null;
  language: string | null;
  text_original: string;
}
