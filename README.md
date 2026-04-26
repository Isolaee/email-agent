# Email Agent

A self-hosted personal email and calendar assistant. It pulls your Gmail, Outlook, and IMAP accounts into a local database and gives you a single chat interface where a locally-running AI answers questions, organizes your inbox, and manages your calendar — without any of your data leaving your machine.

## Why this exists

Most email clients are passive: they show you messages and wait for you to act. Most AI email tools require sending your inbox to a third-party cloud. Email Agent does neither. It runs entirely on your hardware, uses a local LLM (via Ollama), and stores everything in a local SQLite database.

### Own your data

Nothing touches an external AI service. Your emails, calendar events, and conversation history stay on your machine. You control the model, the database, and the network.

### One inbox for everything

Gmail, Outlook, and IMAP accounts sync into a single unified view. Switch between accounts or search across all of them at once. Labels from Gmail and flags from IMAP servers are preserved and kept in sync.

### Ask instead of click

The built-in AI assistant understands your inbox. Instead of building complex filters, just ask:

- *"What did Sarah send me about the contract last week?"*
- *"Label everything from noreply@github.com as GitHub."*
- *"Reply to the invoice email and say we'll process it by Friday."*
- *"What's on my calendar this week? Block Thursday afternoon for focused work."*

The agent can search emails, read threads, apply labels, send replies, compose new emails, and create or delete calendar events — all from a single chat panel.

### Organize without manual work

Label filtering and sorting are built into the email list. The AI can bulk-label emails based on sender, subject, or content. Labels sync back to Gmail (via the API) and to IMAP servers (via STORE flags), so changes are reflected in your regular email client too.

### Send and reply from anywhere

A compose modal and inline reply composer let you send emails from any of your connected accounts without opening a separate app. The AI can also draft and send replies on your behalf when you ask it to.

### Always up to date

Email syncs automatically in the background every 5 minutes (configurable). Gmail uses incremental history sync; Outlook uses delta queries. New messages appear in real time via server-sent events.

---

## Quick start

See [SETUP.md](SETUP.md) for full instructions. The short version:

```bash
cp .env.example .env      # fill in your credentials
./start.sh                # starts backend (:8000) and frontend (:5173)
```

Then open `http://localhost:5173`, go to the **Accounts** tab, and connect your email providers.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy 2 async, APScheduler |
| Database | SQLite (local, no server required) |
| AI | Ollama — runs `qwen2.5:14b` locally by default |
| Email | Gmail API, Microsoft Graph (Outlook), aioimaplib + aiosmtplib |
| Calendar | Google Calendar API |

## Requirements

- Python 3.11+, Node.js 18+
- [Ollama](https://ollama.com) running locally (`ollama pull qwen2.5:14b`)
- OAuth credentials for the providers you want to connect (see SETUP.md)
