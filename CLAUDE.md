# Email Agent

A self-hosted personal email and calendar assistant. It aggregates emails from Gmail, Outlook, and IMAP accounts into a local SQLite database, then exposes a chat interface where a locally-running LLM (Ollama) answers questions and manages Google Calendar events on your behalf.

## Architecture

```
frontend/   React + TypeScript + Vite + Tailwind CSS
backend/    Python FastAPI + SQLite (via SQLAlchemy async)
```

The backend serves the React build as static files in production, so only one port (8000) is needed. In development, Vite runs on :5173 and the API is on :8000.

## Tech stack

| Layer       | Technology |
|-------------|-----------|
| Frontend    | React 19, TypeScript, Vite, Tailwind CSS |
| Backend     | FastAPI, Uvicorn, SQLAlchemy 2 async, APScheduler |
| Database    | SQLite (aiosqlite) at `backend/email_agent.db` |
| AI agent    | Ollama (`qwen2.5:14b` by default) via OpenAI-compatible API |
| Email sync  | Google Gmail API, Microsoft MSAL (Outlook), aioimaplib (IMAP/Roundcube) |
| Calendar    | Google Calendar API |

## Running locally

```bash
./start.sh        # starts both backend (:8000) and frontend dev server (:5173)
```

Backend only:
```bash
cd backend && .venv/bin/uvicorn main:app --reload --port 8000
```

Frontend only:
```bash
cd frontend && npm run dev
```

## Key directories

```
backend/
  main.py               FastAPI app, lifespan, router wiring
  config.py             Settings loaded from .env
  db/
    models.py           SQLAlchemy models: Account, Email, CalendarEvent
    database.py         Engine, SessionLocal, init_db
  routers/
    emails.py           GET /api/emails/*
    calendar.py         GET/POST/DELETE /api/calendar/*
    agent.py            POST /api/agent/chat  (SSE streaming)
    auth.py             OAuth flows for Google and Microsoft
  services/
    agent.py            Ollama tool-use loop, tool implementations
    gmail_sync.py       Gmail incremental sync
    outlook_sync.py     Outlook sync via MSAL
    imap_sync.py        Generic IMAP sync
    google_calendar.py  Calendar CRUD wrappers
    scheduler.py        APScheduler — email sync every SYNC_INTERVAL_SECONDS
frontend/
  src/
    App.tsx             Top-level routing and tab layout
    api.ts              Typed fetch wrappers for all backend endpoints
```

## Environment variables (`.env`)

Copy `.env.example` and fill in the relevant sections. You don't need all providers — only configure the ones you use.

Required for AI: `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
Required per provider: Google OAuth creds, Microsoft OAuth creds, or IMAP credentials.

See `SETUP.md` for step-by-step OAuth setup instructions.

## Agent tool loop

`backend/services/agent.py` implements a simple tool-use loop: it sends the conversation to Ollama, handles any tool calls (email search, calendar read/write), then re-queries for a final answer and streams it character-by-character as SSE (`data: {"delta": "..."}`).

Available tools: `search_emails`, `get_email_body`, `list_recent_emails`, `list_calendar_events`, `create_calendar_event`, `delete_calendar_event`.


<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:ca08a54f -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->
