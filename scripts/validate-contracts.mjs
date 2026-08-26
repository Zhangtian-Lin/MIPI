import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const fromRoot = (path) => resolve(repositoryRoot, path);
const schemaPath = fromRoot("packages/contracts/schemas/ingestion-envelope.schema.json");
const docsSchemaPath = fromRoot("docs/contracts/ingestion-envelope.schema.json");
const fixturePath = fromRoot("tests/contract/fixtures/ingestion-envelope.valid.json");
const openApiPath = fromRoot("packages/contracts/openapi.yaml");
const docsOpenApiPath = fromRoot("docs/contracts/openapi.yaml");
const schemaText = readFileSync(schemaPath, "utf8");
const docsSchemaText = readFileSync(docsSchemaPath, "utf8");
const schema = JSON.parse(schemaText);
const fixture = JSON.parse(readFileSync(fixturePath, "utf8"));
const openApi = readFileSync(openApiPath, "utf8");
const docsOpenApi = readFileSync(docsOpenApiPath, "utf8");

if (schemaText !== docsSchemaText) {
  throw new Error("Published and documented ingestion schemas differ");
}

const missing = schema.required.filter((field) => !(field in fixture));
if (missing.length > 0) {
  console.error(`Fixture is missing required fields: ${missing.join(", ")}`);
  process.exit(1);
}

const unknown = Object.keys(fixture).filter((field) => !(field in schema.properties));
if (schema.additionalProperties === false && unknown.length > 0) {
  console.error(`Fixture contains unknown fields: ${unknown.join(", ")}`);
  process.exit(1);
}

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
}

console.log("MIPI contract fixture OK");
