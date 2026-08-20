# Malaysia Industry & Policy Intelligence

MIPI is a Chinese-language intelligence platform for tracking Malaysian industries, policies, investments, projects, companies, states, and governance context.

## Repository status

This repository is an initialized V0 engineering scaffold. It is not production-ready and does not yet perform autonomous collection or public publishing.

## Architecture

```text
Web / Admin / future Miniapp
             ↓
         FastAPI API
             ↓
 Modular domain application
       ├── PostgreSQL + pgvector
       ├── S3-compatible object storage
       └── Redis / task queue
```

## Applications

- `apps/web`: public Web application
- `apps/admin`: review and operations console
- `apps/api`: HTTP API entry point
- `apps/worker`: asynchronous processing entry point
- `apps/scheduler`: scheduled task entry point

## Shared packages

- `packages/contracts`: machine-readable API and ingestion contracts
- `packages/sdk-ts`: TypeScript API client
- `packages/shared-ts`: platform-neutral formatting and status helpers
- `packages/view-models`: client-facing data models
- `packages/design-tokens`: cross-platform design semantics
- `packages/ui-web`: Web-only UI components

## Quick start prerequisites

- Node.js 24+
- pnpm 10+
- Python 3.12+
- Docker-compatible container runtime

Copy `.env.example` to `.env`, then install dependencies and start local infrastructure. Dependency installation has intentionally not been run during repository initialization.

## Documentation

Start with [docs/README.md](docs/README.md). All production-affecting documents are currently drafts and require review before autonomous collection or public release.

## Local checks

```text
pnpm check:structure
python -m compileall backend apps/api apps/worker apps/scheduler
```

