"""Browser location component and strict coordinate validation."""
import math
import time
from pathlib import Path
import streamlit.components.v1 as components

capture_location = components.declare_component(
    "pulse_location", path=str(Path(__file__).with_name("location_component")))


def checked_location(value):
    if not isinstance(value, dict) or value.get("status") != "ok":
        raise ValueError("Allow location access and retry, or explicitly select the approximate-area fallback.")
    try:
        lat, lon, accuracy, timestamp = (float(value[k]) for k in ("latitude", "longitude", "accuracy", "timestamp"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Location could not be validated. Please retry.") from exc
    if not all(math.isfinite(x) for x in (lat, lon, accuracy, timestamp)):
        raise ValueError("Invalid location. Please retry.")
    if not -60 <= time.time()-timestamp/1000 <= 600:
        raise ValueError("Location has expired. Please retry location capture.")
    if not (24.65 <= lat <= 25.65 and 66.5 <= lon <= 67.8):
        raise ValueError("Your current location is outside Karachi. Use the approximate-area option only to report an issue in Karachi.")
    if not 0 <= accuracy <= 1000:
        raise ValueError("Location accuracy is too low. Retry near a window or use the approximate-area option.")
    return lat, lon, accuracy
