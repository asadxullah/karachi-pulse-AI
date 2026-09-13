# Karachi PULSE — Gemini repair and Assistant

Extract this patch and upload its `pulse` files into the matching folders of your existing GitHub repository. Replace same-path files; add the three new modules. Keep your root `app.py`, requirements and other project files. Do not upload the ZIP itself to run the app.

Replace:
- `pulse/services.py`
- `pulse/agents/response.py`
- `pulse/ui/incidents.py`
- `pulse/ui/sidebar.py`
- `pulse/ui/app.py` (this is not the root entry point)

Add:
- `pulse/agents/assistant.py`
- `pulse/ui/ai_settings.py`
- `pulse/ui/chat.py`
- `tests/test_ai.py` (verification only; not required to launch)

## Connect Gemini

1. Keep `GEMINI_API_KEY` in Streamlit's Secrets. Never commit a key to GitHub.
2. Open Settings → AI connection in the running app.
3. Click **Load available models** and select an appropriate text model. Use the full API ID returned by Google, not a bare version such as `3.7`.
4. Enable **Allow Gemini processing…** and click **Test connection**. This sends a small structured-generation request and may consume quota.
5. A successful test shows the tested model ID. Return to Incidents and click **Explain with AI** again to replace any earlier fallback.
6. To retain the selected model across browser sessions, put its exact ID in the optional `GEMINI_MODEL` setting in Streamlit Secrets. The in-app picker is session-only.

Google documents model discovery at https://ai.google.dev/api/models . Availability and permission depend on the API/project; listing a model does not guarantee generation quota or structured-output support. Test connection checks a real structured response with your selected model.

## What changed

The previous integration swallowed all exceptions. Authentication, missing models, quota limits, invalid structured output and connectivity problems therefore looked identical. The patch adds fixed, safe diagnostic messages without showing provider error payloads or keys, normalizes the `models/` prefix, and increases the response timeout and output budget. Provider access, billing and network availability cannot be repaired by application code.

Assistant is available in the sidebar. It answers app questions using an embedded feature guide and the current workspace snapshot: report totals, category/area counts, up to 40 recent report metadata rows and 12 highest-risk active incidents. Chat history includes up to eight prior messages in each request. It does not send photos, raw report descriptions or exact GPS coordinates as context. User chat messages are sent to Google when AI processing is enabled, so avoid including personal information in messages.

Navigation buttons open existing screens. The chatbot does not submit, edit or resolve reports, inspect photos, contact authorities, or execute arbitrary commands. Those actions remain in the app's existing forms and review controls. AI answers may be mistaken; the measured incident view remains the source for decisions.

Demo and Live conversations are separate, kept in session memory only, and cleared by workspace reset or Clear conversation. Each workspace retains at most 24 messages. Built-in help remains clearly labeled if Gemini is disabled or fails. Old replies describe the snapshot at their reply time; ask again for current data.

## Simple checks after deployment

- Test connection with your actual key and selected model.
- Open a detected incident, click Explain with AI, and confirm the method says Gemini.
- Ask Assistant “What needs attention?” and compare the answer with the incident list.
- Ask “How do I submit a report?” and use Open Add a report.
- Switch Demo/Live and confirm their chats and reports remain separate.
- Disable AI processing and confirm built-in help still works.

Automated verification: `python -m unittest discover -s tests -q`. Provider calls in tests use mocks; no real API credentials are needed. Real account access and browser geolocation still need deployment checks.
