"""Interactive report and incident maps and map selection details."""

import hashlib
import html
import json
import math
import plotly.graph_objects as go
import streamlit as st
from pulse.config import CATEGORIES, COLORS
from pulse.ui.incidents import detail_view
from pulse.utils import local_time


def report_map_detail(frame, selection):
    if not selection or not selection.startswith("REPORT:"):
        return
    rows = frame[frame.report_id == selection.removeprefix("REPORT:")]
    if rows.empty:
        return
    row = rows.iloc[0]
    with st.container(border=True):
        st.markdown("**Selected report**")
        st.write(row.complaint_text)
        st.caption(f'{row.report_id} · {row.area} · {row.category} · Severity {row.severity}/5 · {row.status}')
        st.caption(row.location_basis)


def map_view(frame, incidents, key):
    fig = go.Figure()
    palette = ["#4d7367", "#769787", "#a98c65", "#7a8390", "#618894",
               "#457385", "#a58355", "#8a7b92", "#a76e6a", "#909b92"]
    for j, cat in enumerate(CATEGORIES):
        sub = frame[frame.category == cat]
        if sub.empty:
            continue
        # Exact shared coordinates (especially area centroids) must not hide new reports.
        sub = sub.copy()
        counts = sub.groupby(["latitude", "longitude"]).size()
        sub["point_count"] = [int(counts.loc[(r.latitude, r.longitude)]) for r in sub.itertuples()]
        sub = sub.sort_values("timestamp").drop_duplicates(["latitude", "longitude"], keep="last")
        hover = [f'{html.escape(r.report_id)} · {html.escape(r.area)}<br>{cat} · severity {r.severity}/5'
                 f'<br>{local_time(r.timestamp)} PKT<br>{html.escape(r.complaint_text[:140])}'
                 f'<br>{r.point_count} {cat} report(s) at this point · {html.escape(r.status)}'
                 f'<br>{"Likely duplicate" if r.duplicate_of else "Distinct signal"}' for r in sub.itertuples()]
        fig.add_trace(go.Scattermap(lat=sub.latitude, lon=sub.longitude, mode="markers", name=cat,
            marker=dict(size=[9+min(15, 4*math.log2(n)) for n in sub.point_count], color=palette[j % len(palette)], opacity=.8),
            text=hover, customdata=[["REPORT:"+rid] for rid in sub.report_id], hovertemplate="%{text}<extra></extra>"))
    if incidents:
        fig.add_trace(go.Scattermap(lat=[i["latitude"] for i in incidents], lon=[i["longitude"] for i in incidents],
            mode="markers", name="Emerging incidents", marker=dict(size=[20+min(i["signals"], 20)*1.5+i["risk"]/5 for i in incidents],
            color=[COLORS[i["level"]] for i in incidents], opacity=.85), customdata=[[i["id"]] for i in incidents],
            text=[f'{i["id"]}<br>{i["title"]}<br>{i["area"]}<br>Risk {i["risk"]}/100 · Confidence {i["confidence"]}%'
                  f'<br>{i["signals"]} distinct signals · {i["reports"]} reports<br>{", ".join(i["categories"])}'
                  f'<br>Latest: {local_time(i["latest"])} PKT<br>{i["inspection"]}' for i in incidents],
            hovertemplate="%{text}<extra></extra>"))
    focus_id = st.session_state.get("focus_report")
    focus = frame[frame.report_id == focus_id]
    center = dict(lat=24.87, lon=67.09)
    if not focus.empty:
        r = focus.iloc[0]
        center = dict(lat=float(r.latitude), lon=float(r.longitude))
        fig.add_trace(go.Scattermap(lat=[r.latitude], lon=[r.longitude], mode="markers", name="Selected / new report",
            marker=dict(size=15, color="#202e2b"), customdata=[["REPORT:"+r.report_id]],
            text=[html.escape(r.complaint_text[:140])], hovertemplate="%{text}<extra></extra>"))
    fig.update_layout(map=dict(style="carto-positron", center=center, zoom=12 if not focus.empty else 10),
        height=440, margin=dict(l=0, r=0, t=0, b=0), legend=dict(orientation="h", y=-.02),
        paper_bgcolor="rgba(0,0,0,0)", font_color="#52675d", clickmode="event+select")
    revision = hashlib.sha256(json.dumps([list(frame.report_id), list(frame.status),
        [(i["id"], i["risk"], i["signals"]) for i in incidents]], default=str).encode()).hexdigest()[:12]
    event = st.plotly_chart(fig, use_container_width=True, key=key+"_"+revision, on_select="rerun", selection_mode="points")
    st.caption("Small points are reports; shared points grow with report count. Incident circles grow with distinct signals and risk. Select a point for details.")
    points = event.get("selection", {}).get("points", []) if event else []
    for point in reversed(points):
        data = point.get("customdata", [])
        if data and data[0]:
            return data[0]
    return None


def render_map(frame, active, key, model, consent):
    st.subheader("City signal map")
    categories = st.multiselect("Report categories", CATEGORIES, default=CATEGORIES)
    minimum = st.slider("Minimum incident risk", 0, 100, 0)
    visible = [i for i in active if i["risk"] >= minimum and set(i["categories"]) & set(categories)]
    show_resolved = st.checkbox("Include resolved reports")
    if st.button("Show whole city"):
        st.session_state.pop("focus_report", None)
    mapped = frame[frame.category.isin(categories)]
    if not show_resolved:
        mapped = mapped[mapped.status != "Resolved"]
    picked = map_view(mapped, visible, "city_map")
    report_map_detail(frame, picked)
    detail_view(visible, key, model, consent, "map", picked)
