# Streamlit Deployment Checklist

This release is Streamlit-only and uses Excel persistence.

## GitHub and Streamlit Community Cloud

- Keep `app.py` at the selected Streamlit entrypoint path.
- Commit `requirements.txt`, `src/`, `config/` and the initial Excel workbook.
- Do not commit `.env`, `.streamlit/secrets.toml`, OpenAI keys, cookie secrets or Google OAuth credentials.
- Paste all secrets into Streamlit Community Cloud Secrets.
- Set `[auth].redirect_uri` to the exact deployed URL ending in `/oauth2callback`.
- Add the same URI to the Google OAuth client's Authorized redirect URIs.
- If Google OAuth is in Testing status, add every test account under Audience > Test users.
- Keep `EXTERNAL_WRITEBACK_ENABLED=false`.
- Set `MOCK_LLM=false` and provide `OPENAI_API_KEY` for real judging.
- Run `python -m pytest` and `python scripts/validate_deployment.py` before release.

## Authentication and access

- Local execution must also use Google OIDC with `http://localhost:8501/oauth2callback`.
- Use Streamlit-native OIDC (`st.login`, `st.user`, `st.logout`).
- Google OIDC is mandatory; configure the `[auth]` section in Streamlit Secrets.
- All authenticated users have the same access; no Admin, Reviewer or Viewer lists are used.
- Google handles passwords on its hosted sign-in page. The application must never request or store Google passwords.

## Excel operational controls

- Treat the committed workbook as the initial input dataset.
- Community Cloud does not guarantee persistence of local file changes.
- Evaluation history and audit events may reset after reboot or redeployment.
- Download important result exports after demonstrations.
- Do not use `python run_all.py` on a live dataset because it resets seed data.
- Use one app instance while the workbook is writable.
- Migrate persistence before multiple users, durable history, scaling or business-critical operation.

## Release gate

Do not approve the release unless all tests pass, all configured agents load, all active input records route successfully, the intended LLM mode is selected, critical/degraded caps behave correctly, Google sign-in returns to the app successfully, and external remediation write-back remains disabled.
