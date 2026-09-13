"""Categories, Karachi geography, correlation rules, authority suggestions and score weights."""

from zoneinfo import ZoneInfo


PKT = ZoneInfo("Asia/Karachi")

# Optional GEMINI_MODEL in Streamlit Secrets overrides this default.
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"


CATEGORIES = ["Sewage", "Drainage", "Garbage", "Roads/Potholes", "Water Supply",
              "Flooding", "Electricity", "Traffic", "Public Safety", "Other"]


AREAS = {
    "Gulshan-e-Iqbal": (24.9234, 67.0920), "Clifton": (24.8138, 67.0300),
    "DHA": (24.7940, 67.0640), "Korangi": (24.8387, 67.1209),
    "Saddar": (24.8600, 67.0300), "North Nazimabad": (24.9415, 67.0430),
    "Shah Faisal Colony": (24.8780, 67.1510), "Malir": (24.8930, 67.2160),
    "Lyari": (24.8720, 66.9950), "PECHS": (24.8700, 67.0610),
}


# Simulated susceptibility priors, not measured historical vulnerability.
VULNERABILITY = dict(zip(AREAS, [.90, .25, .30, .90, .65, .50, .70, .65, .80, .45]))


AUTHORITY = {
    "Sewage": "Water/sewerage utility — KWSC; local municipal coordination",
    "Drainage": "Municipal drainage teams — KMC / relevant TMC; verify asset ownership",
    "Garbage": "Solid-waste teams — SSWMB / relevant local service operator",
    "Roads/Potholes": "Road-owning agency — KMC / TMC / cantonment or other asset owner",
    "Water Supply": "Water utility — KWSC / relevant local operator",
    "Flooding": "Municipal drainage teams; district disaster-management coordination",
    "Electricity": "Electricity utility — K-Electric / relevant asset operator",
    "Traffic": "Karachi Traffic Police and relevant road-owning agency",
    "Public Safety": "Relevant emergency responders / district administration",
    "Other": "Relevant local municipal office for triage",
}


KEYWORDS = {
    "Sewage": ["sewage", "sewer", "gutter", "گٹر", "سیوریج", "گندا پانی"],
    "Drainage": ["drain", "naala", "nala", "naali", "nali", "نالہ", "نالی", "نکاسی"],
    "Garbage": ["garbage", "rubbish", "trash", "kachra", "کچرا", "کوڑا", "waste"],
    "Roads/Potholes": ["pothole", "road damage", "broken road", "cracked road", "gaddha", "گڑھا", "ٹوٹی سڑک"],
    "Water Supply": ["water supply", "water line", "water-line", "pipe", "pani nahi", "paani nahi", "پانی نہیں", "پائپ"],
    "Flooding": ["flood", "standing water", "waterlogged", "pani jama", "paani jama", "پانی جمع", "pani road", "پانی سڑک"],
    "Electricity": ["electric", "wire", "spark", "transformer", "bijli", "بجلی", "تار"],
    "Traffic": ["traffic", "gridlock", "congestion", "ٹریفک", "jammed"],
    "Public Safety": ["injury", "injured", "fire", "unsafe", "danger", "زخمی", "آگ", "خطرہ"],
    "Other": [],
}


INFRA = dict(zip(CATEGORIES, ["Sewer network", "Storm-water drains", "Waste collection",
    "Road surface", "Water distribution pipes", "Surface-water routes", "Electrical network",
    "Road network", "Public realm", "Unspecified infrastructure"]))


COLORS = {"Low": "#39b988", "Moderate": "#38bdf8", "Elevated": "#eab308",
          "High": "#f97316", "Critical": "#f43f5e"}


WEIGHTS = {"Signal count": 15, "Density": 8, "Recent arrival rate": 12,
           "Severity": 15, "Concentration": 8, "Category overlap": 12,
           "Weather": 18, "Simulated vulnerability": 8, "Urgency": 4}


RULES = {
    "drain": {"title": "Possible emerging drainage / flooding incident",
              "categories": {"Sewage", "Drainage", "Garbage", "Flooding"},
              "cause": "A blocked or overloaded drainage network may connect the sewage, waste and surface-water signals.",
              "impact": "Localized flooding, contaminated standing water and access disruption.",
              "actions": ["Inspect drain inlets, waste accumulation and the nearest outfall.",
                          "Ask qualified municipal crews to assess clearance and safe pumping needs.",
                          "Verify water depth and protect pedestrian access before conditions worsen."]},
    "leak": {"title": "Possible water-line leakage",
             "categories": {"Water Supply", "Roads/Potholes", "Flooding"},
             "cause": "A leaking water main may explain water-supply disruption, road damage and standing water.",
             "impact": "Water loss, weakened road foundations and possible contamination.",
             "actions": ["Inspect nearby water mains and check pressure with the utility.",
                         "Check the road for subsidence and secure damaged surfaces.",
                         "Have the utility verify the leak before isolation or excavation."]},
    "electric": {"title": "Possible electrical hazard",
                 "categories": {"Electricity", "Public Safety", "Flooding"},
                 "cause": "Electrical faults near reported public hazards may be aggravated by wet conditions.",
                 "impact": "Possible electric shock, fire or localized power interruption.",
                 "actions": ["Keep the public away from reported wires and wet electrical assets.",
                             "Request inspection by qualified utility personnel.",
                             "Only authorized crews should isolate or handle electrical equipment."]},
    "mobility": {"title": "Possible major mobility disruption",
                 "categories": {"Traffic", "Roads/Potholes", "Flooding"},
                 "cause": "Damaged or inundated road segments may be causing linked traffic disruption.",
                 "impact": "Delayed journeys, blocked access and emergency-vehicle delays.",
                 "actions": ["Inspect the affected road segment and its drainage.",
                             "Have traffic teams assess safe diversions and emergency access.",
                             "Verify road conditions before issuing public route advice."]},
}


WORKSPACE_KEYS = ["reports", "stage", "offset", "registry", "history", "responses",
                  "last_fingerprint", "demo_log", "last_submission"]


MAX_REPORTS = 1000
