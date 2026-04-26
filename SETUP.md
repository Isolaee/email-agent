# Email Agent — Setup Guide

## Requirements

- Python 3.11+
- Node.js 18+
- Ollama installed and running (`ollama serve`)

## 1. Install Ollama model

```bash
ollama pull qwen2.5:14b
```

If your machine has limited RAM, use `qwen2.5:7b` instead and update `.env`.

## 2. Configure .env

```bash
cp .env.example .env
```

Edit `.env` and fill in the values for the accounts you want to use. You don't have to fill all of them.

## 3. Set up Google OAuth (Gmail + Calendar)

1. Go to https://console.cloud.google.com/
2. Create a project → **APIs & Services** → **Enable APIs**
   - Enable: **Gmail API** and **Google Calendar API**
3. **Credentials** → **Create credentials** → **OAuth 2.0 Client ID**
   - Application type: **Web application**
   - Authorized redirect URIs: `http://localhost:8000/api/auth/google/callback`
4. Download the JSON — copy `client_id` and `client_secret` to `.env`

## 4. Set up Microsoft OAuth (Outlook)

1. Go to https://portal.azure.com/ → **Azure Active Directory** → **App registrations** → **New registration**
2. Name it anything, select **Personal Microsoft accounts only**
3. Redirect URI: `http://localhost:8000/api/auth/microsoft/callback`
4. **Certificates & secrets** → **New client secret** → copy the value
5. Copy **Application (client) ID** and the secret to `.env`
6. Add your Outlook email addresses to `OUTLOOK_ACCOUNTS` in `.env`

## 5. Configure IMAP (Roundcube)

Set `IMAP_HOST`, `IMAP_PORT`, `IMAP_USERNAME`, and `IMAP_PASSWORD` in `.env`.

Your Roundcube's IMAP server is usually listed in the webmail settings or provided by your hosting provider.

## 6. Start the app

```bash
./start.sh
```

Then open http://localhost:5173 (or replace `localhost` with this machine's LAN IP to access from another computer).

## 7. Connect accounts

Go to the **Accounts** tab (🔑) in the UI and click **Connect** for each provider. You'll be redirected to Google/Microsoft to authorize access.

## Daily use

- The app syncs email automatically every 5 minutes (configurable via `SYNC_INTERVAL_SECONDS`)
- Use the **AI Assistant** (🤖) to search emails or manage your calendar with natural language
- Example prompts:
  - "Show me unread emails from today"
  - "Find emails about invoices from last week"
  - "What's on my calendar this week?"
  - "Create a meeting called 'Team sync' on Friday at 14:00 for one hour"
  - "Delete the event with ID xyz"
