import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const fromRoot = (path) => resolve(repositoryRoot, path);
const schemaPath = fromRoot("packages/contracts/schemas/ingestion-envelope.schema.json");
const docsSchemaPath = fromRoot("docs/contracts/ingestion-envelope.schema.json");
const fixturePath = fromRoot("tests/contract/fixtures/ingestion-envelope.valid.json");
const runReportSchemaPath = fromRoot(
  "packages/contracts/schemas/collection-run-report.schema.json",
);
const docsRunReportSchemaPath = fromRoot(
  "docs/contracts/collection-run-report.schema.json",
);
const runReportFixturePath = fromRoot(
  "tests/contract/fixtures/collection-run-report.valid.json",
);
const openApiPath = fromRoot("packages/contracts/openapi.yaml");
const docsOpenApiPath = fromRoot("docs/contracts/openapi.yaml");
const tradeSchemaPath = fromRoot("packages/contracts/schemas/trade-overview.schema.json");
const docsTradeSchemaPath = fromRoot("docs/contracts/trade-overview.schema.json");
const tradeFixturePath = fromRoot("tests/contract/fixtures/trade-overview.valid.json");
const schemaText = readFileSync(schemaPath, "utf8");
const docsSchemaText = readFileSync(docsSchemaPath, "utf8");
const schema = JSON.parse(schemaText);
const fixture = JSON.parse(readFileSync(fixturePath, "utf8"));
const runReportSchemaText = readFileSync(runReportSchemaPath, "utf8");
const docsRunReportSchemaText = readFileSync(docsRunReportSchemaPath, "utf8");
const runReportSchema = JSON.parse(runReportSchemaText);
const runReportFixture = JSON.parse(readFileSync(runReportFixturePath, "utf8"));
const openApi = readFileSync(openApiPath, "utf8");
const docsOpenApi = readFileSync(docsOpenApiPath, "utf8");
const tradeSchemaText = readFileSync(tradeSchemaPath, "utf8");
const docsTradeSchemaText = readFileSync(docsTradeSchemaPath, "utf8");
const tradeSchema = JSON.parse(tradeSchemaText);
const tradeFixture = JSON.parse(readFileSync(tradeFixturePath, "utf8"));

if (schemaText !== docsSchemaText) {
  throw new Error("Published and documented ingestion schemas differ");
}
if (runReportSchemaText !== docsRunReportSchemaText) {
  throw new Error("Published and documented collection run report schemas differ");
}
if (tradeSchemaText !== docsTradeSchemaText) {
  throw new Error("Published and documented trade overview schemas differ");
}

validateRequiredAndUnknown(schema, fixture, "ingestion fixture");
validateRequiredAndUnknown(runReportSchema, runReportFixture, "collection run report fixture");
validateRequiredAndUnknown(tradeSchema, tradeFixture, "trade overview fixture");

if (!schema.properties.contract_version.enum.includes(fixture.contract_version)) {
  throw new Error("Unsupported contract_version");
}
if (!/^SRC-[A-Za-z0-9][A-Za-z0-9._-]*$/.test(fixture.source_id)) {
  throw new Error("Invalid source_id");
}
if (!/^sha256:[0-9a-fA-F]{64}$/.test(fixture.content_hash)) {
  throw new Error("Invalid content_hash");
}
if (!(fixture.raw_object_uri || typeof fixture.raw_content === "string")) {
  throw new Error("Fixture requires raw_object_uri or raw_content");
}
if (
  runReportFixture.contract_version !== "1.0" ||
  runReportFixture.status !== "succeeded" ||
  runReportFixture.success_count !== 1
) {
  throw new Error("Collection run report fixture must describe one successful dry run");
}
if (
  tradeFixture.dataset_id !== "trade_sitc_1d" ||
  tradeFixture.fact_level !== "F4" ||
  tradeFixture.timeline.length !== 12 ||
  tradeFixture.sections.length !== 10
) {
  throw new Error("Trade overview fixture does not satisfy the V1 publication shape");
}

for (const content of [openApi, docsOpenApi]) {
  if (!content.includes("operationId: submitIngestionRecord")) {
    throw new Error("OpenAPI is missing the ingestion operation");
  }
  if (!content.includes("operationId: decideReviewTask")) {
    throw new Error("OpenAPI is missing the review decision operation");
  }
  if (!content.includes("operationId: decideSourceLifecycle")) {
    throw new Error("OpenAPI is missing the source lifecycle operation");
  }
  if (!content.includes("operationId: getTradeOverview")) {
    throw new Error("OpenAPI is missing the public trade overview operation");
  }
}

console.log("MIPI contract fixture OK");

function validateRequiredAndUnknown(schemaValue, fixtureValue, label) {
  const missing = schemaValue.required.filter((field) => !(field in fixtureValue));
  if (missing.length > 0) {
    throw new Error(`${label} is missing required fields: ${missing.join(", ")}`);
  }
  const unknown = Object.keys(fixtureValue).filter(
    (field) => !(field in schemaValue.properties),
  );
  if (schemaValue.additionalProperties === false && unknown.length > 0) {
    throw new Error(`${label} contains unknown fields: ${unknown.join(", ")}`);
  }
}
