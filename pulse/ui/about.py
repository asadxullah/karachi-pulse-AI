"""Explain the agents, scoring rules and prototype limitations."""

import pandas as pd
import streamlit as st
from pulse.config import AUTHORITY, VULNERABILITY, WEIGHTS
from pulse.ui.incidents import detail_view


def render_about(active, key, model, consent):
    st.subheader("From report to recommended action")
    st.dataframe(pd.DataFrame([
        ["Signal Agent", "Multilingual classification, severity estimate, infrastructure and urgency", "Rules + optional Gemini"],
        ["Correlation Agent", "Duplicate screening, bounded geo/time clusters and cross-category rules", "Python + TF-IDF + haversine"],
        ["Risk Agent", "Weighted risk, evidence confidence and measured score changes", "Python analytics only"],
        ["Response Agent", "Hypotheses, impact and recommended inspection actions", "Playbooks + optional Gemini"],
        ["Monitoring", "Reevaluate on interaction; preserve IDs, workflow and score history", "Streamlit session state"],
    ], columns=["Agent", "Responsibility", "Implementation"]), hide_index=True, use_container_width=True)
    st.markdown("**Deterministic relationships**")
    st.write("• Sewage / drainage plus at least one other drainage-family category → blocked drainage hypothesis; rain amplifies risk.")
    st.write("• Water supply + road damage + standing water → possible water-line leak; rain reduces confidence in this explanation.")
    st.write("• Electricity + public safety or flooding → possible electrical hazard; rain amplifies risk.")
    st.write("• Traffic + road damage + flooding → possible mobility disruption.")
    with st.expander("How risk is calculated", expanded=False):
        st.write("Risk is the rounded sum of factor × weight, clipped to 0–100. Each factor is capped at 1.")
        st.code("Count = n/8\nDensity = [n / (π × max(0.25 km, center-radius)²)] / 12\n"
                "Arrival rate = distinct reports in last 90 minutes / 5\nSeverity = mean submitted severity / 5\n"
                "Concentration = 1 − center-radius / (2 × configured distance)\nCategory overlap = category count / 4\n"
                "Weather = min(1, max(next-12h rain / 30mm, current rain / 10mm)) × (0.5 + 0.5 × rain probability)\n"
                "Weather = 0 for leak hypothesis\nVulnerability = mean simulated area susceptibility\nUrgency = urgent distinct signals / 2", language="text")
        st.json(WEIGHTS)
        st.write("Low 0–29 · Moderate 30–49 · Elevated 50–69 · High 70–84 · Critical 85–100")
    with st.expander("Authority mapping and simulated area priors"):
        st.dataframe(pd.DataFrame(AUTHORITY.items(), columns=["Category", "Suggested authority type"]), hide_index=True)
        st.dataframe(pd.DataFrame(VULNERABILITY.items(), columns=["Area", "Simulated susceptibility"]), hide_index=True)
        st.caption("Illustrative routing, not a legal or administrative determination. No measured historical vulnerability data is claimed.")
    st.caption("Live monitoring reevaluates approximately every minute while the tab is connected. State is per-session; use report backups before reloading or restarting. "
               "The prototype uses pairwise operations appropriate for small demo datasets, not city-scale production ingestion.")
    detail_view(active, key, model, consent, "intel")
