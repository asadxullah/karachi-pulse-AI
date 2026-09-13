"""Operational overview: priorities beside their geographic context."""
import html
import pandas as pd
import streamlit as st
from pulse.session import simulate
from pulse.ui.maps import map_view, report_map_detail
from pulse.ui.reports import report_register


def render_overview(frame, active, weather, workspace, mode, key, model, consent, metrics):
    for col, (label, value) in zip(st.columns(4), metrics[:4]):
        col.metric(label, value)
    source = "Simulated weather" if weather["simulated"] else "Open-Meteo forecast"
    st.markdown(f'<div class="pulse-context"><span><b>Weather outlook</b> · {weather["temperature"]:.0f}°C · '
                f'{weather["probability"]:.0f}% rain chance · {weather["rain_mm"]:.1f} mm / 12h</span>'
                f'<span>{source}</span></div>', unsafe_allow_html=True)
    queue, geography = st.columns([5, 7], gap="large")
    with queue:
        st.subheader("Needs attention")
        st.caption("Ranked by PULSE risk · findings require review")
        if not active:
            st.info("No emerging incidents. New reports will appear on the map as they arrive.")
        for rank, inc in enumerate(active[:3], 1):
            short = {"drain": "Drainage & flooding", "leak": "Possible water-line leak", "electric": "Electrical hazard", "mobility": "Road disruption"}[inc["kind"]]
            with st.container(border=True):
                st.markdown(f'<div class="pulse-priority"><div><span class="pulse-overline">PRIORITY {rank:02d}</span>'
                            f'<h3>{html.escape(inc["area"])}</h3><p>{short}</p></div>'
                            f'<div class="pulse-score"><strong>{inc["risk"]}</strong><span>/100</span>'
                            f'<span class="pulse-badge pulse-{inc["level"].lower()}">{inc["level"]}</span></div></div>'
                            f'<div class="pulse-evidence"><span>{inc["signals"]} distinct signals</span>'
                            f'<span>{inc["confidence"]}% confidence</span></div>', unsafe_allow_html=True)
                if st.button("Review incident →", key="review_"+inc["id"], use_container_width=True):
                    st.session_state.queue_pending_incident = inc["id"]
                    st.session_state.navigate_to = "Emerging Incidents"
                    st.rerun()
        if len(active) > 3 and st.button(f"View all {len(active)} incidents", use_container_width=True):
            st.session_state.navigate_to = "Emerging Incidents"
            st.rerun()
    with geography:
        st.subheader("City situation")
        st.caption("Report locations and emerging incident clusters")
        picked = map_view(frame[frame.status != "Resolved"], active, "command_map", compact=True)
        report_map_detail(frame, picked)
        if picked and not picked.startswith("REPORT:"):
            if st.button("Open selected incident", type="primary"):
                st.session_state.queue_pending_incident = picked
                st.session_state.navigate_to = "Emerging Incidents"
                st.rerun()
        if st.button("Explore city map", use_container_width=True):
            st.session_state.navigate_to = "City Map"
            st.rerun()
    st.divider()
    report_register(frame, active, "overview_records", compact=True)
    if st.button("Open report records"):
        st.session_state.navigate_to = "Reports"
        st.rerun()
    if workspace != "Demo":
        return
    with st.expander("Demo controls" if workspace == "Live" else "Try the six-step demo", expanded=False):
        st.write("Add nearby reports in Gulshan-e-Iqbal, then introduce heavy rain. Watch the incident and its risk develop.")
        st.progress(st.session_state.stage/6, text=f"Stage {st.session_state.stage}/6")
        if st.button("Simulate Incoming City Signals", type="primary", disabled=st.session_state.stage >= 6 or mode != "Demo scenario"):
            simulate()
            st.rerun()
        if mode != "Demo scenario":
            st.caption("Select Demo scenario weather to run the scripted showcase.")
        if st.session_state.demo_log:
            st.dataframe(pd.DataFrame(st.session_state.demo_log), hide_index=True, use_container_width=True)
        showcase = [i for i in active if i["members"].scenario.any()]
        if showcase:
            i = showcase[0]
            st.warning(f'Incident detected in {i["area"]} · {i["level"]} risk · {i["risk"]}/100 · {i["confidence"]}% confidence')
            st.write(i["title"])
            st.write(i["inspection"])
        elif st.session_state.stage:
            st.success("Signals recorded. No qualifying showcase cluster yet under the current thresholds.")
