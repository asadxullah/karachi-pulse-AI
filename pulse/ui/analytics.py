"""Compact charts with honest scales, including sparse live data."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pulse.config import COLORS, PKT
from pulse.ui.incidents import incident_table


def show_chart(fig):
    fig.update_layout(height=260, margin=dict(l=12, r=24, t=12, b=32),
                      paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
                      font=dict(size=12, color="#475650"),
                      legend=dict(title=None, orientation="h", y=1.18, x=0))
    st.plotly_chart(fig, use_container_width=True, theme=None,
                    config={"displayModeBar": False, "responsive": True})


def bars(labels, values, unit="Distinct signals", colors=None, risk=False):
    labels, values = list(labels), list(values)
    fig = go.Figure(go.Bar(x=values, y=list(range(len(labels))), orientation="h",
                          width=.32, marker_color=colors or "#226553",
                          text=values, textposition="outside", cliponaxis=False,
                          customdata=labels, hovertemplate="%{customdata}: %{x}<extra></extra>"))
    fig.update_yaxes(tickvals=list(range(len(labels))), ticktext=labels,
                     range=[max(4, len(labels))-.5, -.5], showgrid=False, title=None)
    fig.update_xaxes(range=[0, 100 if risk else max(2, max(values, default=0)*1.2)],
                     title=unit, dtick=20 if risk else max(1, int(max(values, default=0)/4)),
                     gridcolor="#edf0ee", zeroline=False)
    return fig


def time_axis(fig, times, count=True):
    start, end = times.min(), times.max()
    padding = max(pd.Timedelta(minutes=30), (end-start)*.05)
    fig.update_xaxes(range=[start-padding, end+padding], tickformat="%H:%M<br>%d %b",
                     title="Karachi time (PKT)", nticks=5, showgrid=False)
    fig.update_yaxes(rangemode="tozero", gridcolor="#edf0ee", title=None)
    if count:
        fig.update_yaxes(tickformat="d", tickmode="linear", dtick=max(1, int(max((max(t.y) for t in fig.data if len(t.y)), default=1)/5)))
    return fig


def analytics(frame, incidents):
    if frame.empty:
        st.info("Charts will appear after the first report is recorded.")
        return
    unique = frame[frame.duplicate_of == ""]
    reports, issues = st.tabs(["Report trends", "Incident analysis"])
    with reports:
        a, b = st.columns(2, gap="large")
        with a, st.container(border=True):
            st.subheader("Reports by category")
            counts = unique.category.value_counts()
            show_chart(bars(counts.index, counts.values))
        with b, st.container(border=True):
            st.subheader("Report arrivals")
            hourly = frame.assign(hour=frame.timestamp.dt.tz_convert(PKT).dt.floor("h")).groupby("hour").size().reset_index(name="Reports")
            fig = px.line(hourly, x="hour", y="Reports", markers=True)
            show_chart(time_axis(fig, hourly.hour))
            st.caption("Hourly report counts, including duplicates.")
        with st.expander("Reports by area"):
            counts = unique.area.value_counts()
            show_chart(bars(counts.index, counts.values))
        st.caption(f"{len(frame)} reports · {len(unique)} distinct signals · {len(frame)-len(unique)} likely duplicates")
    with issues:
        if not incidents:
            st.info("No active emerging incidents. Individual reports remain visible in Report records.")
            return
        data = incident_table(incidents).sort_values("Risk", ascending=False)
        a, b = st.columns(2, gap="large")
        with a, st.container(border=True):
            st.subheader("Incident risk")
            show_chart(bars(data.Area, data.Risk, "PULSE risk / 100", data.Level.map(COLORS).tolist(), True))
        with b, st.container(border=True):
            st.subheader("Risk distribution")
            counts = data.Level.value_counts().reindex(list(COLORS), fill_value=0)
            show_chart(bars(counts.index, counts.values, "Incidents", list(COLORS.values())))
        with st.expander("Risk and signal history"):
            history = pd.DataFrame(st.session_state.history)
            if history.empty:
                st.caption("History appears after an incident evaluation changes.")
            else:
                history["time"] = pd.to_datetime(history.time, utc=True).dt.tz_convert(PKT)
                for col, measure, title in zip(st.columns(2), ["risk", "signals"], ["Risk over time", "Supporting signals"]):
                    with col:
                        st.subheader(title)
                        fig = px.line(history.sort_values("time"), x="time", y=measure, color="incident", markers=True)
                        time_axis(fig, history.time, count=measure == "signals")
                        if measure == "risk":
                            fig.update_yaxes(range=[0, 100])
                        show_chart(fig)
                st.caption("Session observations only; not historical municipal data.")


def render_analytics(frame, active):
    analytics(frame, active)
