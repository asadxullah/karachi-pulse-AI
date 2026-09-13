"""Synthetic Karachi reports and the staged demonstration scenario."""

from datetime import datetime, timedelta, timezone
import numpy as np
import uuid
from pulse.config import AREAS
from pulse.data import make_report


def demo_data(clock):
    rng = np.random.default_rng(42)
    rows = []
    templates = ["A streetlight is not working on this residential lane.",
                 "A pothole needs repair near the bus stop.", "Low water supply since morning.",
                 "Garbage collection missed this side street.", "Traffic congestion near the market."]
    cats = ["Electricity", "Roads/Potholes", "Water Supply", "Garbage", "Traffic"]
    for i in range(36):
        area = list(AREAS)[i % len(AREAS)]
        # Keep background signals outside the showcase locality's detection window.
        age = int(rng.integers(26, 70))
        lat, lon = AREAS[area]
        rows.append(make_report(templates[i % 5] + f" Reference lane {i+1}.", area,
            clock-timedelta(hours=age), cats[i % 5], int(rng.integers(1, 4)),
            lat=lat+float(rng.uniform(-.018, .018)), lon=lon+float(rng.uniform(-.018, .018))))
    high = [
        ("Sewage", "Sewer overflow at the factory lane junction.", 4),
        ("Drainage", "Storm drain blocked beside the bus depot.", 4),
        ("Garbage", "Waste bags cover the western culvert mouth.", 4),
        ("Flooding", "Standing water is spreading across the school entrance.", 4),
        ("Sewage", "Dirty sewage is backing up through the clinic manhole.", 5),
        ("Drainage", "Eastern outlet cannot discharge; debris is visible.", 4),
        ("Garbage", "Uncollected rubbish is spilling into the channel by the workshops.", 3),
        ("Flooding", "Flood water is entering ground-floor shop thresholds.", 5),
        ("Drainage", "Northern inlet grate is sealed by silt and plastic.", 4),
    ]
    for i, (cat, text, sev) in enumerate(high):
        a, b = AREAS["Korangi"]
        rows.append(make_report(text, "Korangi", clock-timedelta(minutes=10+i*8), cat, sev,
            lat=a+float(rng.uniform(-.003, .003)), lon=b+float(rng.uniform(-.003, .003))))
    # Exact repeated report proves corroboration does not multiply risk signals.
    duplicate = dict(rows[-1])
    duplicate.update(report_id="R-"+uuid.uuid4().hex[:8].upper(), timestamp=clock-timedelta(minutes=3))
    rows.append(duplicate)
    for i, (cat, text) in enumerate([
        ("Water Supply", "Water-line pressure has dropped near the Clifton service road."),
        ("Roads/Potholes", "Cracked road surface beside the Clifton supply main."),
        ("Flooding", "Standing water persists on the adjacent verge without rainfall."),
    ]):
        a, b = AREAS["Clifton"]
        rows.append(make_report(text, "Clifton", clock-timedelta(hours=5, minutes=20*i), cat, 2,
                               lat=a+.004*i, lon=b+.003*i))
    return rows


SCENARIO = [
    ("Sewage", "Gali mein gutter overflow ho raha hai, Block 7 ki side lane mein.", 2, 0, 0),
    ("Drainage", "Drain block hai aur pani road pe jama ho raha hai near the market inlet.", 2, .002, .001),
    ("Garbage", "Garbage has not been collected for three days beside the culvert.", 2, -.002, .002),
    ("Drainage", "Debris is obstructing the eastern storm drain outlet; water cannot pass.", 3, .001, -.003),
    ("Drainage", "The school-side drain inlet is backing up into the service lane.", 3, -.001, -.002),
]


STAGES = ["One sewage signal", "A nearby blocked drain", "Waste overlaps: incident emerges",
          "Another obstructed outlet", "A fifth supporting signal", "Severe rain forecast: risk escalates"]
