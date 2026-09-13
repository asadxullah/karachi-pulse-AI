"""Overview metrics, recent reports, map and demonstration controls."""

import html
import pandas as pd
import streamlit as st
from pulse.session import simulate
from pulse.ui.components import weather_panel
from pulse.ui.incidents import detail_view
from pulse.ui.maps import map_view, report_map_detail
from pulse.ui.reports import report_register


def render_overview(frame, active, weather, workspace, mode, key, model, consent, metrics):
    for col, (label, value) in zip(st.columns(4), metrics[:4]):
        col.metric(label, value)
    st.caption(f'Average risk: {metrics[4][1]}/100 · Reports today: {metrics[5][1]}')
    st.write("")
    st.subheader("Needs attention")
    reviewed = None
    for col, inc in zip(st.columns(3), active[:3]):
        with col:
            short = {"drain": "Drainage & flooding", "leak": "Possible water-line leak", "electric": "Electrical hazard", "mobility": "Road disruption"}[inc["kind"]]
            st.markdown(f'<div class="pulse-card"><span class="pulse-badge pulse-{inc["level"].lower()}">{inc["level"]} risk · {inc["risk"]}/100</span>'
                        f'<h3>{html.escape(inc["area"])}</h3><p>{short}</p>'
                        f'<div class="pulse-card-foot"><span>{inc["signals"]} distinct signals</span><span>{inc["confidence"]}% confidence</span></div></div>', unsafe_allow_html=True)
            if st.button("Review incident →", key="review_"+inc["id"], use_container_width=True):
                st.session_state.command_incident = inc["id"]
                reviewed = inc["id"]
    if not active:
        st.info("No emerging incidents under the current settings.")
    st.write("")
    report_register(frame, active, "overview_records", compact=True)
    picked = None
    with st.expander("City snapshot & weather"):
        picked = map_view(frame[frame.status != "Resolved"], active, "command_map")
        report_map_detail(frame, picked)
        weather_panel(weather)
    if workspace == "Live":
        if reviewed or (picked and not picked.startswith("REPORT:")):
            with st.expander("Selected incident", expanded=True):
                detail_view(active, key, model, consent, "command", reviewed or picked)
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
    with st.expander("Incident details", expanded=bool(reviewed or picked)):
        detail_view(active, key, model, consent, "command", reviewed or picked)
