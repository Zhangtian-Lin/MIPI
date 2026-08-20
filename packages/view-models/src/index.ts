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

