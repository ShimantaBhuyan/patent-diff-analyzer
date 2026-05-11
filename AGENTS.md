# AGENTS.md — Patent Diff Analyzer

## Repository type

**Hybrid design-spec + active codebase**. The repo contains authoritative planning docs (`prd.md`, `implementation-plan.md`, `high-level-agent-orchestration.md`) _and_ a runnable FastAPI + Next.js MVP. Do not treat it as a spec-only repo.

## Project

**Patent Diff Analyzer** (Stilta App) — compares two patents and produces a structured, citation-backed analysis of overlap, novelty, and infringement risk.

## Architecture

- **Directed pipeline with 7 agents**, each outputting strict JSON. Not a generic chatbot.
- Agents must not free-form leak between stages. The exact prompts in `high-level-agent-orchestration.md` encode this.
- Data contracts (`Claim`, `Component`, `RetrievalResult`) are defined there and must stay in sync with any code.
- Pipeline: Ingest → Claim Extraction → Decomposition → Retrieval Planner → Retrieval → Matching → Reasoning → Output Builder → Audit (optional).

## Authoritative sources

| File                                | What it contains                                                    |
| ----------------------------------- | ------------------------------------------------------------------- |
| `prd.md`                            | Product requirements, user flows, MVP scope, suggested stack        |
| `implementation-plan.md`            | Phased implementation plan (0–7), service boundaries, exit criteria |
| `high-level-agent-orchestration.md` | **Exact agent prompts and data contracts** — treat as authoritative |
| `design-principles.md`              | UI/UX principles, three-panel layout, evidence-first UX             |
| `assets/sample_patents/`            | Two real patent PDFs for testing/evaluation                         |
| `core/schemas.py`                   | Canonical Pydantic models — must mirror data contracts above        |

## Tech stack & entrypoints

- **Backend**: Python 3.11+, FastAPI (`api/main.py`)
- **Frontend**: Next.js 14 App Router (`web/`), TypeScript, Tailwind CSS
- **Vector DB**: PostgreSQL + pgvector (Docker, `infra/docker-compose.yml`)
- **Embeddings**: OpenAI `text-embedding-3-small`
- **LLM**: OpenAI `gpt-4o-mini`

## One-command start

```bash
./start.sh
```

This starts PostgreSQL, creates/activates a Python venv, installs backend deps, copies `.env.example` if needed, and launches the FastAPI backend (`localhost:8000`) and Next.js frontend (`localhost:3000`) in the background.

**Prerequisites**: Docker running, Python 3.11+, Node.js 18+.

## Manual start (when `start.sh` is not enough)

```bash
# Database
cd infra && docker-compose up -d

# Backend
cd api
python3 -m venv ../venv
source ../venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env  # add OPENAI_API_KEY
uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd web
npm install
npm run dev          # localhost:3000
```

## Package boundaries

- `api/` — FastAPI app, routers, and services. `api/main.py` is the entrypoint.
- `web/` — Next.js 14 frontend. `npm` commands only work inside this directory.
- `core/` — Shared Pydantic schemas, SQLAlchemy/pgvector database, config, observability. Imported by both `api/` and any workers.
- `infra/` — Docker Compose for PostgreSQL + pgvector only.
- `workers/` — Reserved for background job workers (future). Currently empty.

No root-level `package.json` or `pyproject.toml`. Backend deps are in `api/requirements.txt`.

## Key developer commands

| Task               | Command                                           |
| ------------------ | ------------------------------------------------- |
| Boot everything    | `./start.sh`                                      |
| Boot DB only       | `cd infra && docker-compose up -d`                |
| Boot backend only  | `cd api && uvicorn main:app --reload --port 8000` |
| Boot frontend only | `cd web && npm run dev`                           |
| Run backend tests  | `cd api && pytest`                                |
| Frontend lint      | `cd web && npm run lint`                          |
| API docs           | http://localhost:8000/docs                        |
| Health check       | http://localhost:8000/health                      |

## Environment

- Copy `.env.example` → `.env` and set `OPENAI_API_KEY`. All other vars have sensible defaults.
- Database URL defaults to `postgresql://postgres:postgres@localhost:5432/patent_diff`.
- The app will not start without a valid `OPENAI_API_KEY`.

## Design constraints

- **Three-panel UI**: Left = Patent A claims, Right = matched Patent B claims, Center = diff view (overlap, differences, risk, citations).
- **Evidence-first**: show citations before conclusions, make uncertainty visible.
- **Accent color**: orange/red, used sparingly (90% neutral).

## Citation rule (critical)

Every conclusion must include source document, exact quote, and chunk/section location. If evidence is weak, output must say “insufficient evidence” — never hallucinate a citation. This is enforced in the reasoning agent prompt.

## Data contracts

- `core/schemas.py` defines the canonical models (`Claim`, `Chunk`, `DiffResult`, `Citation`, `AuditFinding`, etc.).
- Any change to agent output shapes must be reflected in both `high-level-agent-orchestration.md` and `core/schemas.py`.
