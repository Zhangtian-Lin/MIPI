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

export type IngestionProcessingStatus = "needs_review" | "quarantined";
export type ReviewRiskLevel = "R0" | "R1" | "R2" | "R3";

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
  publication_status: "raw_only" | "staged" | "under_review" | "quarantined";
  processing_status: IngestionProcessingStatus;
  review_flags: string[];
  review: {
    review_task_id: string;
    status: string;
    risk_level: ReviewRiskLevel;
  };
  created_at: string;
}
