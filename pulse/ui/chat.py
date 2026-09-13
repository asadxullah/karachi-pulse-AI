"""Session-only chat with current workspace facts and explicit navigation."""
import streamlit as st
from pulse.agents.assistant import PAGES, assistant_reply, workspace_context


def render_chat(frame, incidents, weather, workspace, key, model, consent, radius, window):
    state_key = "chat_" + workspace
    history = st.session_state.setdefault(state_key, [])
    st.caption("Gemini enabled · Current workspace context" if key and consent else "Built-in help · Enable Gemini in Settings for AI answers")
    st.caption("Answers use workspace totals, recent report metadata and priority incidents. Photos and report descriptions are not analyzed here.")
    if st.button("Clear conversation"):
        st.session_state[state_key] = []
        st.rerun()
    if not history:
        st.info("Try: What needs attention? · How do I submit a report? · Why is Gemini failing?")
    for index, entry in enumerate(history):
        with st.chat_message(entry["role"]):
            st.write(entry["content"])
            if entry["role"] == "assistant":
                st.caption(entry["method"] + " · Snapshot at reply time")
                if entry.get("error"):
                    st.warning(entry["error"])
                for page in entry.get("pages", []):
                    if st.button("Open " + page, key=f"chat_go_{workspace}_{index}_{page}"):
                        st.session_state.navigate_to = PAGES[page]
                        st.rerun()
    question = st.chat_input("Ask PULSE", max_chars=2000)
    if question:
        context = workspace_context(frame, incidents, weather, workspace, radius, window)
        prior = [{"role": h["role"], "content": h["content"]} for h in history[-8:]]
        with st.spinner("Preparing an answer…"):
            result = assistant_reply(question, prior, context, key if consent else "", model)
        history.extend([{"role": "user", "content": question},
                        {"role": "assistant", "content": result["answer"], "method": result["method"],
                         "error": result["error"], "pages": result["suggested_pages"]}])
        st.session_state[state_key] = history[-24:]
        st.rerun()
