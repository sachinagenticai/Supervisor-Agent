# Mandatory Google Sign-In Setup

Google authentication is mandatory in both local development and Streamlit
Community Cloud. The application has no demo login, local-user fallback,
email allow-list, Admin/Reviewer/Viewer role, or authentication bypass flag.
All successfully authenticated Google users receive the same application access.

The application uses Streamlit's native OIDC functions: `st.login()`, `st.user`
and `st.logout()`. Google collects the user's email and password on Google's
hosted sign-in page. The application never receives or stores the password.

## 1. Configure the Google OAuth client

Create a Google OAuth 2.0 client of type **Web application**. Add both redirect
URIs to the same client when you need local and cloud access:

```text
http://localhost:8501/oauth2callback
https://YOUR-APP-NAME.streamlit.app/oauth2callback
```

The values must match exactly, including scheme, hostname, port and
`/oauth2callback` path. While the Google application is in Testing mode, add
each allowed Google account under **Test users**.

## 2. Local authentication

Create `.streamlit/secrets.toml` in the project root:

```toml
# Application settings stay above [auth]
STORAGE_BACKEND = "excel"
EXCEL_STORE_PATH = "data/supervisor_control_tower.xlsx"
MOCK_LLM = false
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"
LLM_MODEL = "gpt-5-mini"
APP_ENV = "POC"

[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "REPLACE_WITH_A_LONG_RANDOM_SECRET"
client_id = "YOUR_GOOGLE_CLIENT_ID"
client_secret = "YOUR_GOOGLE_CLIENT_SECRET"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

Generate the cookie secret:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Run from the project root:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

Opening `http://localhost:8501` starts the Google sign-in flow immediately.
There is no local bypass or demo button.

## 3. Streamlit Community Cloud authentication

Paste the same application settings into the app's **Secrets** page, but change:

```toml
[auth]
redirect_uri = "https://YOUR-APP-NAME.streamlit.app/oauth2callback"
cookie_secret = "REPLACE_WITH_A_LONG_RANDOM_SECRET"
client_id = "YOUR_GOOGLE_CLIENT_ID"
client_secret = "YOUR_GOOGLE_CLIENT_SECRET"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

Do not commit `.streamlit/secrets.toml`. The repository includes only
`.streamlit/secrets.toml.example`.

## 4. Common errors

- **redirect_uri_mismatch**: Add the exact callback URL to the Google OAuth client.
- **Access blocked / app not verified**: Add the account as a test user or publish
  the Google OAuth application according to your organization's policy.
- **Missing [auth] configuration**: Ensure the file is located at
  `.streamlit/secrets.toml` in the directory from which `streamlit run` is called.
- **Login loop**: Confirm the browser URL and configured `redirect_uri` use the
  same hostname (`localhost` versus `127.0.0.1`) and port.
