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
