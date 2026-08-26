# Malaysia Industry & Policy Intelligence

MIPI is a Chinese-language intelligence platform for tracking Malaysian industries, policies, investments, projects, companies, states, and governance context.

## Repository status

This repository contains governed local vertical slices for source registration, L0-L2
ingestion and review, official trade indicators, and event/evidence publication. Raw text,
immutable versions, exact evidence spans and published revisions are stored with audit trails.
It is not production-ready and does not yet run autonomous collection.

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
- Docker Desktop with the WSL 2 backend on Windows

The JavaScript and Python dependencies are already locked. Create the local environment file and start the infrastructure:

```powershell
Copy-Item .env.example .env
pnpm infra:up
pnpm check:env
```

The bootstrap command starts PostgreSQL 18 with pgvector, Redis, and MinIO, creates the
`mipi-local` object-storage bucket, and applies every pending SQL migration. On a new Windows
setup, restart Windows after enabling WSL before running Docker Desktop.

Run the API and admin console in separate terminals:

```powershell
.\.venv\Scripts\python.exe -m uvicorn mipi.bootstrap.app:create_app --factory --reload
pnpm dev:admin
```

Local API docs are at `http://localhost:8000/docs`; the review console is at
`http://localhost:3001`. A source administrator can register a candidate in the console, or
through `POST /v1/admin/sources`, then submit evidence through `POST /v1/ingestion/records`
using contract version 1.1. Registration does not approve trial collection. The candidate card
provides a structured human-only trial approval form for identity, terms, authority scope,
robots status, evidence links, and an audited reason. Local human
review decisions use `POST /v1/admin/review-tasks/{reviewTaskId}/decisions`; production review
writes remain disabled until a real identity provider is configured. Source lifecycle decisions
use `POST /v1/admin/sources/{sourceId}/decisions`; regular scheduled collection is allowed only
after a source has moved through `candidate → trial → active`.

The first source-specific connector targets the official `data.gov.my` Open Data API. It is
source-gated and dry-run by default; see
`docs/agents/data.gov.my首个采集连接器运行规范.md`. No collection is attempted until
`SRC-MY-DATAGOV` has entered `trial` or `active` through the source-governance workflow.

The first public vertical slice is the governed `trade_sitc_1d` overview. An approved L2
ingestion can be normalized into a private L3 trade batch; only a human Publisher can create
the versioned L4 projection returned by `GET /v1/trade/overview`. See
`docs/product/贸易指标首条数据闭环.md`.

The event workbench can turn an approved L2 document into a private F1 Event + Claim + exact
source span. Only a human Publisher can create the L4 revision returned by `GET /v1/changes`;
see `docs/product/事件与证据首条闭环.md`.

Public search uses `GET /v1/search` and only reads current L4 event projections. It explains
whether a result matched the Chinese title, Chinese summary, original evidence, or source name;
see `docs/product/公开搜索首条闭环.md`.

## Documentation

Start with [docs/README.md](docs/README.md). All production-affecting documents are currently drafts and require review before autonomous collection or public release.

## Local checks

```text
pnpm check:structure
pnpm check:contracts
pnpm check:env
pnpm typecheck
pnpm build
python -m compileall backend apps/api apps/worker apps/scheduler
python -m pytest
```

With local infrastructure running, include the real PostgreSQL/MinIO flow:

```powershell
$env:MIPI_RUN_INTEGRATION="1"
.\.venv\Scripts\python.exe -m pytest tests/integration/test_local_ingestion_flow.py
```
