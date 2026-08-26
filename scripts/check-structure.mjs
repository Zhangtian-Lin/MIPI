import { existsSync } from "node:fs";

const requiredPaths = [
  "AGENTS.md",
  "README.md",
  "package.json",
  "pyproject.toml",
  "apps/web/package.json",
  "apps/admin/package.json",
  "apps/api/main.py",
  "apps/worker/main.py",
  "apps/scheduler/main.py",
  "backend/mipi/modules/collection/data_gov_my.py",
  "backend/mipi/bootstrap/app.py",
  "packages/contracts/openapi.yaml",
  "packages/contracts/schemas/ingestion-envelope.schema.json",
  "packages/contracts/schemas/collection-run-report.schema.json",
  "infra/database/migrations/0001_initial.sql",
  "infra/containers/compose.yaml",
  "docs/README.md",
];

const missing = requiredPaths.filter((path) => !existsSync(path));
if (missing.length > 0) {
  console.error("Missing required repository paths:");
  for (const path of missing) console.error(`- ${path}`);
  process.exit(1);
}

console.log(`MIPI structure OK (${requiredPaths.length} required paths)`);
