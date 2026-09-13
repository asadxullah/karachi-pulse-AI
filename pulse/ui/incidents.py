"""Incident queue, explainability, recommendations and review workflow."""

import base64
import pandas as pd
import plotly.express as px
import streamlit as st
from pulse.agents.response import response_agent
from pulse.config import AREAS, AUTHORITY, CATEGORIES, WEIGHTS
from pulse.ui.components import weather_panel
from pulse.utils import local_time


def incident_table(incidents):
    return pd.DataFrame([{"Incident": i["id"], "Area": i["area"], "Predicted issue": i["title"],
        "Distinct signals": i["signals"], "Citizen reports": i["reports"], "Risk": i["risk"],
        "Level": i["level"], "Confidence %": i["confidence"], "Trend": i["trend"],
        "Status": i["status"], "Priority": i["priority"], "First detected (PKT)": local_time(i["first_detected"]),
        "Latest activity (PKT)": local_time(i["latest"])} for i in incidents])


def detail_view(incidents, key, model, consent, prefix, selected=None):
    if not incidents:
        st.info("No incidents meet the current geo/time and correlation rules.")
        return
    ids = [i["id"] for i in incidents]
    widget = prefix+"_incident"
    if selected in ids:
        st.session_state[widget] = selected
    if st.session_state.get(widget) not in ids:
        st.session_state[widget] = ids[0]
    iid = st.selectbox("Incident intelligence", ids, key=widget,
                       format_func=lambda x: next(f'{i["area"]} · {i["title"]} · {i["risk"]}/100' for i in incidents if i["id"] == x))
    inc = next(i for i in incidents if i["id"] == iid)
    response = response_agent(inc)
    st.markdown(f'### {inc["title"]}')
    a, b, c = st.columns(3)
    a.metric("PULSE risk", f'{inc["risk"]}/100', f'{inc["delta"]:+d} since prior evaluation' if inc["delta"] is not None else None,
             delta_color="inverse")
    b.metric("Evidence confidence", f'{inc["confidence"]}%')
    c.metric("Distinct / total signals", f'{inc["signals"]} / {inc["reports"]}')
    st.caption(f'{inc["id"]} · {inc["level"]} · {inc["priority"]}')
    tabs = st.tabs(["Summary & actions", "Related reports", "Why this risk?", "Review status"])
    with tabs[0]:
        st.write(f'{inc["reports"]} reports across {inc["area"]} support {inc["signals"]} distinct signals involving '
                 f'{", ".join(inc["categories"])}. First signal: {local_time(inc["first_signal"])} PKT.')
        st.markdown("**Possible cause — requires inspection**")
        st.write(response["hypothesis"])
        st.markdown("**Potential impact**")
        st.write(response["potential_impact"])
        st.markdown("**Recommended inspection points**")
        # Deterministic location recommendation always remains visible.
        st.write(inc["inspection"])
        for action in dict.fromkeys(response["inspection"]):
            if action.strip() != inc["inspection"].strip():
                st.write("• " + action)
        st.markdown("**Suggested immediate response**")
        st.write(response["immediate_response"])
        st.markdown("**Next steps**")
        for action in response["next_steps"]:
            st.write("• " + action)
        st.markdown("**Suggested authority — prototype mapping**")
        for authority in sorted({AUTHORITY[c] for c in inc["categories"]}):
            st.write("• " + authority)
        st.caption("Verify jurisdiction and asset ownership. Recommendations support human decision makers; no authorities have been contacted.")
    with tabs[1]:
        columns = ["report_id", "timestamp", "area", "complaint_text", "category", "severity", "source",
                   "status", "ai_classification", "confidence_score", "duplicate_of", "latitude", "longitude", "location_basis"]
        display = inc["related"][columns].copy()
        display["timestamp"] = display.timestamp.map(local_time)
        st.dataframe(display, hide_index=True, use_container_width=True)
        st.caption("Likely duplicates remain recorded but do not add risk or confidence points. Classifier confidence is separate from incident confidence.")
        related_ids = set(inc["related"].report_id)
        photos = [r for r in st.session_state.reports if r["report_id"] in related_ids and r.get("photo")]
        if photos:
            with st.expander(f"Report photos ({len(photos)})"):
                rid = st.selectbox("Photo report", [r["report_id"] for r in photos], key=prefix+"_photo_"+iid)
                photo_report = next(r for r in photos if r["report_id"] == rid)
                st.image(base64.b64decode(photo_report["photo"]["base64"]), caption=photo_report["complaint_text"], width=360)
    with tabs[2]:
        st.markdown("**Why it was flagged**")
        st.write(f'• {inc["signals"]} distinct signals match the {inc["kind"]} relationship rule.')
        st.write(f'• Signals span about {inc["extent"]*1000:.0f} m from their center; density estimate {inc["density"]:.1f}/km².')
        st.write(f'• {inc["recent"]} arrived in the last 90 minutes, versus {inc["previous"]} in the preceding 90 minutes.')
        st.write(f'• {int((inc["members"].severity >= 4).sum())} distinct reports have severity 4–5.')
        st.write(f'• Weather contributes {inc["factors"]["Weather"]:.2f} of 100 points; vulnerability is a simulated prior.')
        st.markdown("**Why did the risk change?**")
        if inc["delta"] is None:
            st.write("First detection; no prior score exists for comparison.")
        elif inc["changes"]:
            st.write(f'Net change: {inc["delta"]:+d} points. Measured contributions since the previous changed evaluation:')
            for item in inc["changes"]:
                st.write("• " + item)
        else:
            st.write("No material score change in the latest evaluation.")
        factors = pd.DataFrame({"Factor": list(WEIGHTS), "Points": list(inc["factors"].values()), "Maximum": list(WEIGHTS.values())})
        st.plotly_chart(px.bar(factors, x="Points", y="Factor", orientation="h", range_x=[0, 20],
                              color_discrete_sequence=["#226553"]), use_container_width=True, key=prefix+"_risk_factors_"+iid)
        st.dataframe(factors, hide_index=True, use_container_width=True)
        with st.expander("Confidence components and model limitations"):
            st.json({k: round(v, 2) for k, v in inc["confidence_parts"].items()})
            st.write("Confidence is a heuristic evidence score capped at 95%, not a calibrated probability. "
                     "Synthetic susceptibility, approximate locations, keyword limitations and unverified reports affect reliability. "
                     "Greedy bounded clustering is order-dependent. Separate hypotheses can share reports and must not be summed as unique failures.")
    with tabs[3]:
        weather_panel(inc["weather"])
        status = st.selectbox("Human review status", ["Monitoring", "Acknowledged", "Inspecting", "Resolved"],
            index=["Monitoring", "Acknowledged", "Inspecting", "Resolved"].index(inc["status"]), key=prefix+"_status_"+iid)
        if st.button("Save review status", key=prefix+"_save_"+iid):
            st.session_state.registry[iid]["status"] = status
            if status == "Resolved":
                related_ids = set(inc["related"].report_id)
                for report in st.session_state.reports:
                    if report["report_id"] in related_ids:
                        report["status"] = "Resolved"
            st.rerun()
        st.caption("Resolving an incident also resolves its related reports and removes them from active risk calculations. Records remain available. A review status does not confirm the cause.")


def render_incidents(incidents, key, model, consent):
    selected = st.session_state.pop("queue_pending_incident", None)
    if selected:
        st.session_state.queue_reviewed_incident = selected
        for name, value in [("queue_area_filter", []), ("queue_category_filter", []),
                            ("queue_status_filter", []), ("queue_risk_filter", 0)]:
            st.session_state[name] = value
    with st.expander("Filter and sort incidents"):
        a, b = st.columns(2)
        areas = a.multiselect("Area", list(AREAS), key="queue_area_filter")
        cats = b.multiselect("Category", CATEGORIES, key="queue_category_filter")
        statuses = a.multiselect("Review status", ["Monitoring", "Acknowledged", "Inspecting", "Resolved"], key="queue_status_filter")
        minimum = b.slider("Minimum risk", 0, 100, 0, key="queue_risk_filter")
        order = st.selectbox("Sort by", ["Highest risk", "Latest activity", "Most signals", "Highest confidence"])
    filtered = [i for i in incidents if i["risk"] >= minimum
        and (not areas or set(areas) & set(i["members"].area))
        and (not cats or set(cats) & set(i["categories"])) and (not statuses or i["status"] in statuses)]
    field = {"Highest risk": "risk", "Latest activity": "latest", "Most signals": "signals", "Highest confidence": "confidence"}[order]
    filtered.sort(key=lambda x: x[field], reverse=True)
    if selected and selected not in [i["id"] for i in incidents]:
        st.info("This incident is no longer active. Its reports remain in Report records.")
    prefix = "selected_review" if st.session_state.get("queue_reviewed_incident") else "queue"
    detail_view(filtered, key, model, consent, prefix, selected)
    if filtered:
        with st.expander(f"Incident register · {len(filtered)} matching"):
            st.dataframe(incident_table(filtered), hide_index=True, use_container_width=True)
    archived = [{"Incident": iid, "Area": record.get("summary", {}).get("area", ""),
                 "Issue": record.get("summary", {}).get("title", ""),
                 "Review status": record["status"], "Detection": "No longer meets active detection rules"}
                for iid, record in st.session_state.registry.items() if not record.get("currently_detected")]
    if archived:
        with st.expander("Previously detected incidents"):
            st.dataframe(pd.DataFrame(archived), hide_index=True, use_container_width=True)
            st.caption("Resolved reports and expired or changed clusters remain in Report records. Reopen reports there if further review is required.")
