"""Explicit provider diagnostics and model discovery without storing credentials."""
import hashlib
import streamlit as st
from pulse.config import DEFAULT_GEMINI_MODEL
from pulse.services import available_models, normalize_model, secret, test_connection


def render_ai_settings():
    key = secret("GEMINI_API_KEY") or st.text_input(
        "Gemini API key (session only)", type="password", key="temporary_api_key")
    # Invalidate diagnostics and model options whenever credentials change.
    scope = hashlib.sha256(key.encode()).hexdigest() if key else "none"
    if st.session_state.get("ai_key_scope") != scope:
        for field in ("ai_models", "ai_connection_result", "ai_discovery_error", "ai_available_choice"):
            st.session_state.pop(field, None)
        st.session_state.ai_key_scope = scope
    st.session_state.setdefault("ai_model", secret("GEMINI_MODEL", DEFAULT_GEMINI_MODEL))
    model = st.text_input("Gemini model", key="ai_model", help="Use the full API model ID or select a model below.")
    st.session_state.setdefault("ai_consent", True)
    consent = st.checkbox("Allow Gemini processing of submitted text and incident summaries", key="ai_consent")
    st.caption("Assistant messages and workspace summaries also go to Google when AI is enabled. Photos and exact GPS coordinates are excluded from Assistant requests.")
    if st.button("Load available models", disabled=not key):
        with st.spinner("Checking available models…"):
            models, error = available_models(key)
        st.session_state.ai_models = models
        st.session_state.ai_discovery_error = error
    if st.session_state.get("ai_discovery_error"):
        st.warning(st.session_state.ai_discovery_error)
    options = st.session_state.get("ai_models", [])
    if options:
        def choose_model():
            st.session_state.ai_model = st.session_state.ai_available_choice
            st.session_state.pop("ai_connection_result", None)
        st.selectbox("Available generation models", options, index=None,
                     placeholder="Choose a model", key="ai_available_choice", on_change=choose_model)
        st.caption("Model listing confirms availability. Test connection also checks structured generation; some listed models serve other purposes.")
    if st.button("Test connection", disabled=not (key and consent)):
        with st.spinner("Testing a short structured response…"):
            ok, error = test_connection(key, model)
        st.session_state.ai_connection_result = (normalize_model(model), ok, error)
    result = st.session_state.get("ai_connection_result")
    if result and result[0] == normalize_model(model):
        if result[1]:
            st.success("Gemini connected · " + result[0])
        else:
            st.error(result[2])
    if not consent:
        st.caption("Enable AI processing to test generation, explain incidents or chat with Gemini.")
    return key, model, consent
