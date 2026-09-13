"""Workspace navigation, settings and report backup controls."""

from datetime import datetime, timedelta, timezone
import math
import pandas as pd
import streamlit as st
from pulse.config import DEFAULT_GEMINI_MODEL, WORKSPACE_KEYS
from pulse.data import export_reports, import_reports
from pulse.demo import demo_data
from pulse.services import live_weather, secret
from pulse.ui.ai_settings import render_ai_settings
from pulse.session import switch_workspace
from pulse.utils import now_utc


def render_sidebar():
    with st.sidebar:
        st.markdown('<div class="pulse-brand">Karachi <span>PULSE</span></div>', unsafe_allow_html=True)
        workspace = st.radio("Workspace", ["Demo", "Live"], key="workspace_choice", horizontal=True)
        switch_workspace(workspace)
        st.caption("Your submitted reports" if workspace == "Live" else "Demo reports · Simulated conditions")
        names = {"Command Center": "Overview", "Report an Issue": "Add a report", "Emerging Incidents": "Incidents",
                 "Reports": "Report records", "City Map": "City map", "Analytics": "Trends", "AI Intelligence": "How it works", "Assistant": "Assistant"}
        st.session_state.setdefault("nav_page", "Command Center")
        if "navigate_to" in st.session_state:
            st.session_state.nav_page = st.session_state.pop("navigate_to")
        def navigate(target):
            st.session_state.nav_page = target
        st.button("Add a report", key="nav_submit", type="primary", use_container_width=True,
                  icon=":material/add:", on_click=navigate, args=("Report an Issue",))
        st.markdown('<div class="pulse-overline pulse-nav-label">WORKSPACE</div>', unsafe_allow_html=True)
        icons = {"Command Center": "dashboard", "Emerging Incidents": "radar", "Reports": "list_alt",
                 "City Map": "map", "Analytics": "bar_chart"}
        for target in icons:
            with st.container(key="nav_current" if st.session_state.nav_page == target else "nav_"+icons[target]):
                st.button(names[target], key="nav_button_"+target, use_container_width=True,
                          icon=":material/"+icons[target]+":", on_click=navigate, args=(target,))
        st.button("Assistant", icon=":material/chat_bubble_outline:", on_click=navigate, args=("Assistant",), use_container_width=True)
        st.caption("AI update 2 · Gemini summaries + Assistant")
        page = st.session_state.nav_page
        st.divider()
        with st.popover("Settings", use_container_width=True):
            with st.expander("Analysis settings"):
                mode = "Live weather" if workspace == "Live" else "Demo scenario"
                st.caption("Open-Meteo forecast, refreshed every 15 minutes." if workspace == "Live" else "Scripted weather for the demo.")
                radius = st.slider("Nearby reports (km)", .5, 2.5, 1.5, .1)
                window = st.slider("Look back (hours)", 3, 48, 24, 3)
                st.caption("At least 3 distinct, related reports are needed to detect an incident.")
            with st.expander("AI connection"):
                key, model, consent = render_ai_settings()
            st.button("Refresh overview", use_container_width=True)
            if mode == "Live weather" and st.button("Refresh weather"):
                live_weather.clear()
                st.rerun()
            with st.expander("Reset session"):
                st.caption("Only this workspace is cleared. Export a report backup first if needed.")
                confirm_reset = st.checkbox("Clear this workspace's reports and history", key="confirm_reset_"+workspace)
                if st.button("Reset demo" if workspace == "Demo" else "Clear live workspace", disabled=not confirm_reset, use_container_width=True):
                    for name in WORKSPACE_KEYS:
                        st.session_state.pop(name, None)
                    st.session_state.reports = demo_data(now_utc()) if workspace == "Demo" else []
                    st.session_state.update(stage=0, offset=0, registry={}, history=[], responses={},
                                            last_fingerprint="", demo_log=[])
                    st.session_state.pop("focus_report", None)
                    st.session_state.pop("chat_"+workspace, None)
                    st.rerun()
            with st.expander("Report backup & restore"):
                st.caption("Navigation and Refresh overview keep your reports. A browser reload may start a new session. Download a backup to retain them; restore merges reports by ID.")
                st.download_button("Download report backup", export_reports(st.session_state.reports, workspace),
                                   "karachi-pulse-"+workspace.lower()+"-reports.json", "application/json")
                upload = st.file_uploader("Restore report backup", type=["json"], key="backup_upload_"+workspace)
                if st.button("Restore reports", disabled=upload is None):
                    try:
                        merged, count = import_reports(upload.getvalue(), st.session_state.reports, workspace, datetime.now(timezone.utc))
                        st.session_state.reports = merged
                        if workspace == "Demo" and merged:
                            latest = max(pd.Timestamp(r["timestamp"]) for r in merged)
                            st.session_state.offset = max(st.session_state.offset, math.ceil((latest-pd.Timestamp.now(tz="UTC")).total_seconds()/60))
                        st.session_state.restore_notice = f"Restored {count} new reports. Existing report IDs were left unchanged."
                        st.rerun()
                    except (ValueError, TypeError) as exc:
                        st.error(str(exc))
        st.button("How it works", icon=":material/help_outline:", on_click=navigate, args=("AI Intelligence",), use_container_width=True)
        st.caption("Session only · Back up reports in Settings")
    return workspace, page, names, mode, radius, window, key, model, consent
