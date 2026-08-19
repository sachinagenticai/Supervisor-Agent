# Deploy to Streamlit Community Cloud

## Repository contents

Push this project to GitHub with `app.py` as the application entrypoint. Commit `requirements.txt`, `src/`, `config/`, `data/supervisor_control_tower.xlsx`, and `.streamlit/config.toml`. Do not commit `.env` or `.streamlit/secrets.toml`.

## Google Cloud setup

1. Create a Google OAuth client of type **Web application**.
2. If the consent screen is in Testing status, add your Google account under **Audience > Test users**.
3. Add this exact authorized redirect URI:

   `https://<your-app-name>.streamlit.app/oauth2callback`

## Streamlit Cloud Secrets

Paste the following into the app's Secrets settings and replace the placeholders:

```toml
STORAGE_BACKEND = "excel"
EXCEL_STORE_PATH = "data/supervisor_control_tower.xlsx"
EXCEL_LOCK_TIMEOUT_SECONDS = 30
ALLOW_DATA_RESET = false
AGENT_CONFIG_PATH = "config/agents.json"
RULE_CONFIG_PATH = "config/rule_packs.json"
BUSINESS_CONTEXT_PATH = "config/business_context.json"
MOCK_LLM = false
OPENAI_API_KEY = "replace-with-your-openai-key"
LLM_MODEL = "gpt-5-mini"
LLM_TIMEOUT_SECONDS = 30
LLM_MAX_RETRIES = 2
REMEDIATION_PROPOSALS_ENABLED = true
EXTERNAL_WRITEBACK_ENABLED = false
APP_ENV = "POC"
LOG_LEVEL = "INFO"

[auth]
redirect_uri = "https://<your-app-name>.streamlit.app/oauth2callback"
cookie_secret = "replace-with-a-long-random-secret"
client_id = "replace-with-google-client-id"
client_secret = "replace-with-google-client-secret"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

Generate a cookie secret locally with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Runtime behavior

Google OIDC is mandatory. Users are redirected directly to Google's hosted sign-in page. Google collects the account email and password; the Streamlit app never receives or stores the password. All authenticated users have the same access.

## Persistence warning

The Excel file is writable while an app process is running, but Streamlit Community Cloud does not guarantee persistent local storage. New evaluations and audit history can disappear after reboot or redeployment. This is a controlled POC deployment model, not durable production storage.
