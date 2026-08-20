import type { ReactNode } from "react";
import type { FactLevel } from "@mipi/shared-ts";

export function StatusBadge({ level, children }: { level: FactLevel; children: ReactNode }) {
  return <span className="status-badge" data-fact-level={level}>{children}</span>;
}

