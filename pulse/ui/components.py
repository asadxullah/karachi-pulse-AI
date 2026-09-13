"""Small shared UI components."""

import streamlit as st
from pulse.utils import local_time


def weather_panel(weather):
    with st.container(border=True):
        st.caption("NEXT 12 HOURS")
        st.markdown(f'## {weather["temperature"]:.0f}°C')
        st.write(f'Rain probability: **{weather["probability"]:.0f}%**')
        st.write(f'Expected rainfall: **{weather["rain_mm"]:.1f} mm**')
        st.caption(f'{weather["source"]} · Current precipitation: {weather["current_mm"]:.1f} mm · '
                   f'Fetched {local_time(weather["fetched"])} PKT. City-wide context, not street-level measurement.')
        if weather["simulated"]:
            st.caption("Scenario assumptions only; this is not a real Karachi weather alert.")
        else:
            st.caption(f'Forecast: {local_time(weather["forecast_start"])}–{local_time(weather["forecast_end"])} PKT. Source: https://open-meteo.com/')
