"""Streamlit orchestration: evaluate one snapshot and route to a screen."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import numpy as np
import streamlit as st
from pulse.agents.correlation import correlation_agent
from pulse.agents.risk import risk_agent
from pulse.config import AREAS, PKT
from pulse.data import report_frame
from pulse.services import live_weather, simulated_weather
from pulse.session import init_state, live_refresh, monitor
from pulse.ui.about import render_about
from pulse.ui.analytics import render_analytics
from pulse.ui.incidents import render_incidents
from pulse.ui.maps import render_map
from pulse.ui.overview import render_overview
from pulse.ui.reports import render_records, render_submission
from pulse.ui.sidebar import render_sidebar
from pulse.ui.theme import apply_theme
from pulse.utils import local_time


def main():
    st.set_page_config(page_title="Karachi PULSE", page_icon="◉", layout="wide")
    apply_theme()
    init_state()
    workspace, page, names, mode, radius, window, key, model, consent = render_sidebar()
    clock = datetime.now(timezone.utc)+timedelta(minutes=st.session_state.offset if workspace == "Demo" else 0)
    weather = simulated_weather(st.session_state.stage >= 6) if mode == "Demo scenario" else live_weather()
    frame = report_frame(st.session_state.reports)
    raw = correlation_agent(frame, clock, radius, window)
    incidents = [risk_agent(i, weather, clock, radius) for i in raw]
    fingerprint = hashlib.sha256(json.dumps({"clock": clock.replace(second=0, microsecond=0).isoformat(),
        "reports": frame[["report_id", "status", "category", "severity"]].to_dict("records"),
        "radius": radius, "window": window, "weather": weather}, sort_keys=True).encode()).hexdigest()
    incidents = monitor(incidents, clock, fingerprint)
    active = [i for i in incidents if i["status"] != "Resolved"]
    source_label = "Simulated weather" if weather["simulated"] else "Live weather · Open-Meteo"
    data_label = "Submitted reports" if workspace == "Live" else "Demo workspace"
    st.markdown(f'<div class="pulse-topline"><span>Karachi / City operations</span><span>{data_label} · {source_label} · {local_time(clock)} PKT</span></div>', unsafe_allow_html=True)
    subtitles = {
        "Command Center": "Priority incidents and recent reports.",
        "Report an Issue": "Describe the issue and attach a photo if available.",
        "Reports": "Search, review and update submitted reports.",
        "Emerging Incidents": "Review related reports and decide what should be inspected next.",
        "City Map": "Explore reports and emerging issues across Karachi.",
        "Analytics": "Follow report patterns and changes in incident risk.",
        "AI Intelligence": "How incident detection and risk scoring work.",
    }
    st.markdown(f'<div class="pulse-title"><h1>{names[page]}</h1><p>{subtitles[page]}</p></div>', unsafe_allow_html=True)
    if "restore_notice" in st.session_state:
        st.success(st.session_state.pop("restore_notice"))
    if workspace == "Live" and page == "Command Center":
        st.caption("Updates every minute while connected.")
    today = clock.astimezone(PKT).date()
    metrics = [
        ("Active Reports", int((frame.status != "Resolved").sum())), ("Emerging Incidents", len(active)),
        ("Critical Alerts", sum(i["risk"] >= 85 for i in active)), ("Areas Monitored", len(AREAS)),
        ("Average PULSE Risk", f'{np.mean([i["risk"] for i in active]):.0f}' if active else "—"),
        ("Reports Today", int((frame.timestamp.dt.tz_convert(PKT).dt.date == today).sum())),
    ]
    if page == 'Command Center':
        render_overview(frame, active, weather, workspace, mode, key, model, consent, metrics)
    elif page == 'Report an Issue':
        render_submission(frame, active, clock, key, model, consent)
    elif page == 'Reports':
        render_records(frame, active)
    elif page == 'Emerging Incidents':
        render_incidents(incidents, key, model, consent)
    elif page == 'City Map':
        render_map(frame, active, key, model, consent)
    elif page == 'Analytics':
        render_analytics(frame, active)
    else:
        render_about(active, key, model, consent)
    st.divider()
    st.caption("Findings require inspection. Reports are not sent to authorities automatically.")
    if workspace == "Live":
        live_refresh()
