"""Shared text, time and geographic calculations; no UI or session state."""

from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import re
from pulse.config import PKT


def now_utc():
    return datetime.now(timezone.utc).replace(second=0, microsecond=0)


def local_time(value):
    return pd.Timestamp(value).tz_convert(PKT).strftime("%d %b %H:%M")


def haversine(lat1, lon1, lat2, lon2):
    """Broadcast-compatible great-circle distance in kilometers."""
    a, b, c, d = map(np.radians, [lat1, lon1, lat2, lon2])
    x = np.sin((c-a)/2)**2 + np.cos(a)*np.cos(c)*np.sin((d-b)/2)**2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(x, 0, 1)))


def normalize(text):
    return re.sub(r"[^\w\s]", " ", text.casefold(), flags=re.UNICODE).strip()
