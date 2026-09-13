"""Signal Agent: multilingual complaint classification."""

from pulse.config import CATEGORIES, DEFAULT_GEMINI_MODEL, INFRA, KEYWORDS
from pulse.models import SignalOutput
from pulse.services import gemini_json
from pulse.utils import normalize


def signal_agent(text, key="", model=DEFAULT_GEMINI_MODEL):
    cleaned = normalize(text)
    hits = {c: [w for w in words if w in cleaned] for c, words in KEYWORDS.items()}
    category = max(CATEGORIES, key=lambda c: len(hits[c]))
    if not hits[category]:
        category = "Other"
    urgent = any(w in cleaned for w in ["live wire", "electrocut", "spark", "injured", "fire", "کرنٹ", "آگ", "زخمی"])
    severity = 5 if urgent else 3 if any(w in cleaned for w in ["overflow", "blocked", "block", "flood", "بند"]) else 2
    fallback = dict(category=category, estimated_severity=severity,
        keywords=[w for words in hits.values() for w in words], infrastructure=INFRA[category],
        immediate_attention=urgent, related_categories=[c for c in CATEGORIES if hits[c] and c != category],
        confidence=.78 if hits[category] else .30, method="Rules / multilingual keywords")
    result = gemini_json(key, model,
        "You are the Signal Agent for Karachi. Classify English, Urdu and Roman Urdu complaints. "
        f"Choose category and related_categories only from {CATEGORIES}. Severity 1 minor to 5 urgent. "
        "Extract infrastructure and keywords. Confidence reflects uncertainty; do not infer unseen facts.",
        {"complaint": text}, SignalOutput)
    if result and result["category"] in CATEGORIES and all(c in CATEGORIES for c in result["related_categories"]):
        result["method"] = "Gemini / structured output"
        return result
    fallback["method"] += " (Gemini unavailable)" if key else ""
    return fallback
