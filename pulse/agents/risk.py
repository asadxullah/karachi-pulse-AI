"""Risk Agent: deterministic risk, evidence confidence and inspection coordinates."""

from datetime import datetime, timedelta, timezone
import math
import numpy as np
from pulse.config import VULNERABILITY, WEIGHTS
from pulse.utils import haversine


def risk_level(score):
    return "Critical" if score >= 85 else "High" if score >= 70 else "Elevated" if score >= 50 else "Moderate" if score >= 30 else "Low"


def risk_agent(incident, weather, clock, radius):
    m = incident["members"]
    n = len(m)
    lat, lon = float(m.latitude.mean()), float(m.longitude.mean())
    extent = float(np.max(haversine(lat, lon, m.latitude.to_numpy(), m.longitude.to_numpy())))
    density = n/(math.pi * max(.25, extent)**2)
    recent = int((m.timestamp >= clock-timedelta(minutes=90)).sum())
    previous = int(((m.timestamp < clock-timedelta(minutes=90)) & (m.timestamp >= clock-timedelta(minutes=180))).sum())
    urgent = int(m.signal_analysis.map(lambda x: x["immediate_attention"]).sum())
    susceptibility = float(np.mean([VULNERABILITY[a] for a in m.area]))
    rain_factor = float(np.clip(max(weather["rain_mm"]/30, weather["current_mm"]/10), 0, 1))
    rain_factor *= .5 + .5*weather["probability"]/100
    # Rain is not evidence for a leaking water main; it can explain surface water instead.
    weather_factor = 0 if incident["kind"] == "leak" else rain_factor
    factors = {
        "Signal count": min(n/8, 1), "Density": min(density/12, 1),
        "Recent arrival rate": min(recent/5, 1), "Severity": float(m.severity.mean())/5,
        "Concentration": max(0, 1-extent/(2*radius)),
        "Category overlap": min(len(incident["categories"])/4, 1),
        "Weather": weather_factor, "Simulated vulnerability": susceptibility,
        "Urgency": min(urgent/2, 1),
    }
    contributions = {name: round(WEIGHTS[name]*value, 2) for name, value in factors.items()}
    score = int(np.clip(round(sum(contributions.values())), 0, 100))
    # Confidence is evidential strength, not a probability validated against outcomes.
    confidence_parts = {
        "Distinct signals": 25*min(n/8, 1),
        "Category support": 25*min(len(incident["categories"])/3, 1),
        "Spatial support": 20*max(0, 1-extent/(2*radius)),
        "Temporal support": 15*max(0, 1-(m.timestamp.max()-m.timestamp.min()).total_seconds()/(48*3600)),
        "Classification quality": 15*float(m.confidence_score.mean()),
    }
    if incident["kind"] == "leak" and rain_factor > .5:
        confidence_parts["Rain alternative explanation"] = -10
    confidence = int(np.clip(round(sum(confidence_parts.values())), 0, 95))
    # Choose a measured dense inspection point, not an invented street address.
    d = haversine(m.latitude.to_numpy()[:, None], m.longitude.to_numpy()[:, None],
                  m.latitude.to_numpy()[None, :], m.longitude.to_numpy()[None, :])
    counts = (d <= .35).sum(axis=1)
    anchor = m.iloc[int(np.argmax(counts))]
    incident.update(risk=score, level=risk_level(score), confidence=confidence,
        factors=contributions, confidence_parts=confidence_parts, latitude=lat, longitude=lon,
        extent=extent, density=density, recent=recent, previous=previous, urgency=urgent,
        area=", ".join(sorted(m.area.unique())), signals=n, reports=len(incident["related"]),
        first_signal=m.timestamp.min(), latest=incident["related"].timestamp.max(),
        trend="Increasing" if recent > previous else "Declining" if recent < previous else "Steady",
        inspection=f"Inspect near {anchor.latitude:.5f}, {anchor.longitude:.5f} ({anchor.area}) first: "
                   f"{int(counts.max())} of {n} distinct signals lie within 350 m of this point.",
        priority="P1 • Immediate verification" if score >= 85 else "P2 • Urgent review" if score >= 70 else
                 "P3 • Prioritized inspection" if score >= 50 else "P4 • Monitor / verify",
        weather=dict(weather))
    return incident
