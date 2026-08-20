import { readFileSync } from "node:fs";

const schemaPath = "packages/contracts/schemas/ingestion-envelope.schema.json";
const fixturePath = "tests/contract/fixtures/ingestion-envelope.valid.json";
const schema = JSON.parse(readFileSync(schemaPath, "utf8"));
const fixture = JSON.parse(readFileSync(fixturePath, "utf8"));

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

if (!fixture.source_id.startsWith("SRC-")) throw new Error("Invalid source_id");
if (!fixture.content_hash.startsWith("sha256:")) throw new Error("Invalid content_hash");

console.log("MIPI contract fixture OK");

