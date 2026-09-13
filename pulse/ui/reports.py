"""Report submission, searchable records, editing and export UI."""

import streamlit as st
import base64
import uuid
from pulse.agents.signal import signal_agent
from pulse.config import AREAS, CATEGORIES, MAX_REPORTS
from pulse.data import make_report, prepare_photo
from pulse.ui.location import capture_location, checked_location
from pulse.utils import local_time, haversine


def report_register(frame, incidents, prefix, compact=False):
    """Every report is visible here, including isolated and duplicate observations."""
    st.subheader("Recent reports" if compact else "Report records")
    if frame.empty:
        st.info("No reports yet. Use Add a report to record your first observation.")
        return
    view = frame.sort_values("timestamp", ascending=False).copy()
    if not compact:
        a, b, c = st.columns(3)
        query = a.text_input("Search reports", key=prefix+"_search")
        area = b.multiselect("Report area", list(AREAS), key=prefix+"_area")
        statuses = c.multiselect("Report status", ["Open", "Investigating", "Resolved"], key=prefix+"_filter_status")
        if query:
            view = view[view.complaint_text.str.contains(query, case=False, regex=False)
                        | view.report_id.str.contains(query, case=False, regex=False)]
        if area:
            view = view[view.area.isin(area)]
        if statuses:
            view = view[view.status.isin(statuses)]
    incident_ids = {}
    for inc in incidents:
        for rid in inc["related"].report_id:
            incident_ids.setdefault(rid, []).append(inc["id"])
    view["Incident"] = view.report_id.map(lambda rid: ", ".join(incident_ids.get(rid, [])) or "No active incident")
    view["Received (PKT)"] = view.timestamp.map(local_time)
    view["Signal"] = view.duplicate_of.map(lambda rid: "Duplicate of "+rid if rid else "Distinct report")
    display = view[["report_id", "Received (PKT)", "area", "complaint_text", "category", "severity", "status", "Signal", "Incident"]].rename(
        columns={"report_id": "Report ID", "area": "Area", "complaint_text": "Description", "category": "Category", "severity": "Severity", "status": "Status"})
    if compact:
        display = display[["Report ID", "Area", "Description", "Category", "Status"]].head(5)
    st.dataframe(display, hide_index=True, use_container_width=True)
    st.caption(f'{len(frame)} reports · {int((frame.duplicate_of == "").sum())} distinct signals')
    if compact or view.empty:
        return
    st.download_button("Export filtered records (CSV)", display.to_csv(index=False).encode("utf-8-sig"),
                       "karachi-pulse-records.csv", "text/csv", key=prefix+"_csv")
    ids = list(view.report_id)
    selected_key = prefix+"_report"
    if st.session_state.get(selected_key) not in ids:
        st.session_state[selected_key] = ids[0]
    rid = st.selectbox("Inspect a report", ids, key=selected_key)
    row = view[view.report_id == rid].iloc[0]
    st.write(row.complaint_text)
    saved_report = next((r for r in st.session_state.reports if r["report_id"] == rid), {})
    if saved_report.get("photo"):
        st.image(base64.b64decode(saved_report["photo"]["base64"]), caption="Attached report photo", width=360)
    st.caption(f'{row.area} · {row.latitude:.5f}, {row.longitude:.5f} · {row.location_basis} · {row.source}')
    if st.button("Locate on city map", key=prefix+"_locate"):
        st.session_state.focus_report = rid
        st.session_state.navigate_to = "City Map"
        st.rerun()
    with st.expander("Update report"):
        with st.form(prefix+"_edit_"+rid):
            status = st.selectbox("Status", ["Open", "Investigating", "Resolved"],
                index=["Open", "Investigating", "Resolved"].index(row.status))
            category = st.selectbox("Correct category", CATEGORIES, index=CATEGORIES.index(row.category))
            severity = st.slider("Severity", 1, 5, int(row.severity))
            if st.form_submit_button("Save report changes"):
                for saved in st.session_state.reports:
                    if saved["report_id"] == rid:
                        saved.update(status=status, category=category, severity=severity)
                st.rerun()


def render_submission(frame, active, clock, key, model, consent):
    workspace = st.session_state.get("active_workspace", "Demo")
    token_key = "report_draft_"+workspace
    st.session_state.setdefault(token_key, uuid.uuid4().hex)
    token = st.session_state[token_key]
    st.caption("Allow location access if you are at the incident. Otherwise, select the approximate-area option below.")
    location = capture_location(key="capture_"+workspace+token, default=None)
    with st.form("report_form", clear_on_submit=False):
        description = st.text_area("What did you observe?", max_chars=2000,
            placeholder="Gali mein gutter overflow ho raha hai…", key="description_"+token,
            help="English, Urdu and Roman Urdu are supported.")
        a, b, c = st.columns(3)
        area = a.selectbox("Area", list(AREAS), help="Used only for the approximate-area fallback. Browser locations use the nearest listed area as a label.")
        category = b.selectbox("Category", ["Auto classify"]+CATEGORIES)
        severity = c.slider("Reported severity: 1 minor → 5 urgent", 1, 5, 2)
        approximate = st.checkbox("Use the selected area's approximate center instead of my current location", key="approximate_"+token,
                                  help="For remote reports or unavailable location access. The map will show the area's center, not an exact incident location.")
        source = st.selectbox("Source", ["Citizen web report", "Community volunteer", "Field observation", "Social media observation"])
        upload = st.file_uploader("Add a photo (optional)", type=["jpg", "jpeg", "png", "webp"], key="photo_"+token,
                                  help="Maximum 5 MB and 20 megapixels. Photos are compressed, saved with the report and included in JSON backups. Not sent to Gemini.")
        submitted = st.form_submit_button("Analyze & add signal", type="primary")
    if submitted:
        try:
            if len(st.session_state.reports) >= MAX_REPORTS:
                raise ValueError("This workspace has reached the 1,000-report prototype limit. Export your records before clearing it.")
            if len(description.strip()) < 8 or not any(c.isalnum() for c in description):
                raise ValueError("Please enter at least eight characters describing the issue.")
            lat = lon = None
            accuracy = None
            if not approximate:
                lat, lon, accuracy = checked_location(location)
                area = min(AREAS, key=lambda name: haversine(lat, lon, AREAS[name][0], AREAS[name][1]))
            photo = prepare_photo(upload.getvalue()) if upload else None
            if photo and len(photo["base64"])+sum(len(r.get("photo", {}).get("base64", "")) for r in st.session_state.reports) > 28_000_000:
                raise ValueError("Photo storage for this session is full. Download a backup before clearing reports.")
            with st.spinner("Signal Agent is analyzing the report…"):
                ai = signal_agent(description.strip(), key if consent else "", model)
            row = make_report(description.strip(), area, clock,
                None if category == "Auto classify" else category, severity, source, lat, lon, ai)
            if accuracy is not None:
                row["location_basis"] = f"Browser location (estimated accuracy {accuracy:.0f} m; nearest-area label)"
                row["location_accuracy_m"] = accuracy
            if photo:
                row["photo"] = photo
            st.session_state.reports.append(row)
            st.session_state.focus_report = row["report_id"]
            st.session_state.last_submission = {"id": row["report_id"], "classification": ai,
                "category": row["category"], "reported_severity": severity}
            st.session_state[token_key] = uuid.uuid4().hex
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    if "last_submission" in st.session_state:
        last = st.session_state.last_submission
        st.success(f'Signal {last["id"]} recorded · {last["category"]}')
        saved = next((r for r in st.session_state.reports if r["report_id"] == last["id"]), {})
        if saved.get("photo"):
            st.image(base64.b64decode(saved["photo"]["base64"]), caption="Photo saved with this report", width=360)
        st.write(f'Category: {last["category"]} · Reported severity: {last["reported_severity"]}/5')
        with st.expander("Classification details"):
            st.json(last)
        matching = frame[frame.report_id == last["id"]]
        if not matching.empty and matching.iloc[0].duplicate_of:
            st.warning(f'Likely duplicate of {matching.iloc[0].duplicate_of}. Recorded as corroboration; not an additional risk signal.')
        if last["classification"]["immediate_attention"]:
            st.warning("Potential immediate hazard: keep a safe distance and seek appropriate local emergency assistance. This app does not dispatch responders.")
        a, b = st.columns(2)
        if a.button("View report records"):
            st.session_state.navigate_to = "Reports"
            st.rerun()
        if b.button("Show new report on map"):
            st.session_state.navigate_to = "City Map"
            st.rerun()
    report_register(frame, active, "submission_records", compact=True)


def render_records(frame, active):
    report_register(frame, active, "records")
