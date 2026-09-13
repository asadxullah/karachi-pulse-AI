"""Load local styling and configure the shared Plotly chart theme."""

from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def apply_theme():
    css = Path(__file__).with_name("styles.css").read_text(encoding="utf-8")
    st.markdown("<style>" + css + "</style>", unsafe_allow_html=True)
    import plotly.io as pio
    pio.templates["pulse"] = go.layout.Template(layout=dict(
        height=280, bargap=.65,
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        font=dict(family="Arial, sans-serif", color="#344b43", size=12),
        colorway=["#226553", "#8bada1", "#b59362", "#6d8197", "#9a7474"],
        xaxis=dict(gridcolor="#e4e9e3", zeroline=False),
        yaxis=dict(gridcolor="#e4e9e3", zeroline=False),
        margin=dict(l=15, r=15, t=55, b=25), title=dict(font=dict(size=16)),
    ))
    pio.templates.default = "plotly_white+pulse"
    px.defaults.template = "plotly_white+pulse"
