# Salegate QA Assistant

A small [Google ADK](https://google.github.io/adk-docs/) agent that answers questions about
[Salegate](https://github.com/ShreyasUpadhyaya/salegate)-scored sales calls. Ask it why a lead
is held, what a specific check's evidence says, or how an agent's first pass yield looks this
month, and it calls the real Salegate API and answers with the actual check id, status,
timestamp and reason — never a guess.

This agent is **read-only** against Salegate, with one exception: it can trigger a scoring run
(`score_lead`) if you ask it to. It never submits a sale and never writes an override; both are
treated as human decisions the agent surfaces, not ones it makes.

## Prerequisites

- Python 3.12, [uv](https://docs.astral.sh/uv/getting-started/installation/)
- A [Gemini API key](https://aistudio.google.com/apikey) (free tier works)
- A running [Salegate](https://github.com/ShreyasUpadhyaya/salegate) API. Clone that repo as a
  sibling directory and follow its own README to get `uv run uvicorn app.main:app --port 8000`
  running with some scored leads (seeded or real).

## Setup

```bash
git clone https://github.com/ShreyasUpadhyaya/salegate-agent.git
cd salegate-agent
cp .env.example .env
```

Open `.env` and set `GEMINI_API_KEY`. Leave `SALEGATE_API_BASE` as `http://127.0.0.1:8000` if
Salegate's API is running locally on its default port.

## Run it

With Salegate's API already running in its own terminal (it defaults to port 8000):

```bash
uv run adk web --port 8080
```

`adk web` also defaults to port 8000, so pass `--port` with something else or it will fail to
bind with `[winerror 10048] only one usage of each socket address`. This opens ADK's local dev
UI in a browser at `http://127.0.0.1:8080`. Pick `salegate_agent` from the agent list and start
asking questions. `SALEGATE_API_BASE` in `.env` still points the agent's tools at Salegate's own
port 8000, unaffected by which port the dev UI itself runs on.

Or from the terminal directly:

```bash
uv run adk run salegate_agent
```

## Try it

Assumes `L-DEMO-1` (or any lead id you've scored) exists in your Salegate instance:

- "Why is L-DEMO-1 held?"
- "What does the ongoing price check say for L-DEMO-1, with evidence?"
- "Has L-DEMO-2 been scored? If not, score it."
- "What's the first pass yield across all agents right now?"
- "Can you submit L-DEMO-1?" — it will explain that it can't, and that submitting happens in
  Salegate directly.

## Tools

| Tool | Salegate endpoint | What it's for |
|---|---|---|
| `get_score(lead_id)` | `GET /api/leads/{id}/score` | Full check results with evidence, for explaining a verdict |
| `get_gate(lead_id)` | `GET /api/leads/{id}/gate` | Just the decision and which critical checks drove it |
| `get_transcript(lead_id)` | `GET /api/leads/{id}/transcript` | The call transcript, for quoting exactly what was said |
| `score_lead(lead_id)` | `POST /api/leads/{id}/score` | Triggers a (re)score — only on explicit request |
| `list_overrides(check_result_id)` | `GET /api/check-results/{id}/overrides` | Audit history for one check result |
| `get_agent_rollup()` | `GET /api/dashboards/agents` | Per-agent first pass yield and critical fail rate |

`submit_lead` and `create_override` are deliberately not exposed. See `salegate_agent/agent.py`
for the full instruction text that governs this.

## Tests

```bash
uv run pytest -q
```

The suite starts a real Salegate API as a subprocess (against a fresh temp SQLite database) and
drives the tools over real HTTP, so it confirms the tools parse genuine API responses correctly,
including the 404/409 error paths. It's skipped automatically if the `salegate` repo isn't
present as a sibling directory (`../salegate`).

`uv run ruff check . --fix` runs the linter.

## Why a separate repo

This agent depends on `google-adk`, which the Salegate project's own conventions ask not to add
without discussion. Keeping it as its own repo, talking to Salegate purely over HTTP, means it
never touches Salegate's database or Python package directly — it works against any Salegate
instance reachable at a URL, local or deployed.
