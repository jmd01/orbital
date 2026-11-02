# Orbital — Product Engineering Take-Home

A document Q&A tool for commercial real estate lawyers, extended with a **structured, verifiable risk review**.

- **[PART1.md](PART1.md)**: Part 1, my most significant technical achievement
- **[DECISIONS.md](DECISIONS.md)**: what I built, why, what I rejected and what I'd do next
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**: how it works, end to end
- **[Loom walkthrough](https://www.loom.com/share/6b0bb2ad320c4fa68fc2845a2a3e2877)**
- **[Haiku 4.5 vs 5.5 comparison](https://claude.ai/artifact/MZnq3agMMBHrVEUGR295ZC)**

## The feature

Upload a document, then ask for a risk review ("Run a risk review of this document"). Instead of a wall of prose you get:

- a placeholder while the model works, then an interactive **risk table** in the chat: worst first, filterable by severity, each risk with a short reason and the exact clause it rests on;
- **click a clause** to open its page in the document reader with the passage highlighted;
- reviews are **saved**: they survive a refresh, and the latest review of each document is listed under **Risk reviews** in the sidebar, where it opens full-page next to the document.

The model passes risks to a `present_risks` tool instead of writing them out. The backend saves them, works out each page from the quote (never from the model), and streams the saved table to the browser. The app runs on Claude Haiku 5.5, chosen with the eval harness in `evals/`.

**Assumptions:** single user, no authentication (out of scope for this exercise), text-based PDFs (scanned PDFs need OCR).

## Tests and evals

```
just check            # ruff, pyright, biome, tsc
just test-frontend    # Vitest + React Testing Library (risk table)
uv run pytest         # backend tests, from the repo root (uv sync --group dev first)
uv run python evals/risk_eval.py 5 [--model anthropic:claude-haiku-4-5]
```

The eval runs the real agent over `sample-docs/` (5 runs per document by default, about 6¢ in total on Haiku 5.5) and reports whether each quote is found in the PDF, risks per review, time, and tokens. Results are saved in `evals/results/`.

---

*The original setup instructions follow.*

## Setup

### Prerequisites
- Docker and Docker Compose
- just (command runner) — install via `brew install just` or `cargo install just`

That's it. Everything else runs inside containers.

### Getting Started

1. Clone this repository

2. Run the setup command:
```
just setup
```
   This copies `.env.example` to `.env` and builds the Docker images.

3. Add your Anthropic API key to `.env`:
```
ANTHROPIC_API_KEY=your_key_here
```
   We've provided an API key in the task email. You can also use your own.

4. Start everything:
```
just dev
```
   This starts PostgreSQL, the FastAPI backend (port 8000), and the React frontend (port 5173).
   Database migrations run automatically when the backend starts — no separate step needed.

5. Open http://localhost:5173 in your browser.

Your local `backend/src/` and `frontend/src/` directories are mounted into the containers —
edit files normally on your machine and changes hot-reload automatically.

### Sample Documents

We've included sample legal documents in `sample-docs/` for testing.

### Project Structure

- `frontend/` — React frontend (Vite + Tailwind + shadcn/Radix UI)
- `backend/` — FastAPI backend (Python 3.12 + SQLAlchemy + PydanticAI)
- `alembic/` — Database migrations
- `sample-docs/` — Sample PDF documents for testing
- `evals/` — Risk-review eval harness and saved results
- `docs/` — Architecture notes

### Useful Commands

- `just dev` — Start full stack (Postgres + backend + frontend)
- `just stop` — Stop all services
- `just reset` — Stop everything and clear database
- `just check` — Run all linters and type checks
- `just test-frontend` — Run the frontend tests
- `just fmt` — Format all code
- `just db-init` — Run database migrations
- `just db-shell` — Open a psql shell
- `just shell-backend` — Shell into backend container
- `just logs-backend` — Tail backend logs
