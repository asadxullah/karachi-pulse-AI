"""Compact session chat with current workspace facts and explicit navigation."""
import streamlit as st
from pulse.agents.assistant import PAGES, assistant_reply, workspace_context


def render_chat(frame, incidents, weather, workspace, key, model, consent, radius, window):
    state_key = "chat_" + workspace
    history = st.session_state.setdefault(state_key, [])
    question = None
    with st.container(key="pulse_chat"):
        status, controls = st.columns([3, 1])
        status.caption(f"{workspace} workspace · " + ("AI enabled" if key and consent else "Basic help"))
        if controls.button("Clear conversation", key="chat_clear", use_container_width=True):
            st.session_state[state_key] = []
            st.rerun()
        if not history:
            st.markdown('<div class="chat-welcome"><h2>How can I help?</h2><p>Ask about an incident or find your next step.</p></div>', unsafe_allow_html=True)
            prompts = ["What needs attention?", "How do I submit a report?"]
            for col, prompt in zip(st.columns(2), prompts):
                if col.button(prompt, use_container_width=True):
                    question = prompt
        for index, entry in enumerate(history):
            with st.chat_message(entry["role"], avatar=":material/person:" if entry["role"] == "user" else ":material/hub:"):
                st.write(entry["content"])
                if entry["role"] == "assistant":
                    if entry["method"] != "Gemini":
                        st.caption("Built-in help")
                    if entry.get("error"):
                        with st.expander("Connection details"):
                            st.warning(entry["error"])
                    # Keep old replies readable; actions belong to the latest answer.
                    if index == len(history)-1:
                        pages = [p for p in entry.get("pages", []) if p in PAGES][:2]
                        for col, page in zip(st.columns(len(pages)) if pages else [], pages):
                            if col.button("Open " + page, key=f"chat_go_{workspace}_{index}_{page}"):
                                st.session_state.navigate_to = PAGES[page]
                                st.rerun()
        typed = st.chat_input("Message PULSE…", max_chars=2000)
        question = typed or question
        if question:
            context = workspace_context(frame, incidents, weather, workspace, radius, window)
            prior = [{"role": h["role"], "content": h["content"]} for h in history[-8:]]
            with st.spinner("Thinking…"):
                result = assistant_reply(question, prior, context, key if consent else "", model)
            history.extend([{"role": "user", "content": question},
                            {"role": "assistant", "content": result["answer"], "method": result["method"],
                             "error": result["error"], "pages": result["suggested_pages"]}])
            st.session_state[state_key] = history[-24:]
            st.rerun()
