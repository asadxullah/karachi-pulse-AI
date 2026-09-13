"""Response Agent: grounded hypotheses and suggested actions."""

from pulse.config import DEFAULT_GEMINI_MODEL, RULES
from pulse.models import ResponseOutput
from pulse.services import gemini_json


def response_agent(inc, key="", model=DEFAULT_GEMINI_MODEL):
    rule = RULES[inc["kind"]]
    fallback = dict(hypothesis=rule["cause"], potential_impact=rule["impact"],
        inspection=[inc["inspection"], rule["actions"][0]], immediate_response=rule["actions"][1],
        next_steps=[rule["actions"][2], "Record field findings, verify the hypothesis and reassess priority."],
        method="Deterministic response playbook")
    payload = {k: inc[k] for k in ["title", "area", "categories", "signals", "risk", "confidence", "inspection", "weather", "factors"]}
    payload["allowed_playbook"] = fallback
    diagnostics = {}
    result = gemini_json(key, model,
        "You are the Karachi PULSE Response Agent. Explain the supplied rule-based hypothesis, "
        "using only the measured facts and playbook. Do not change numeric scores, assert a confirmed cause, "
        "invent street names, or claim contact with authorities. Use cautious language and concise practical "
        "inspection advice. Distinguish simulated weather from live weather. Return plain text fields, no HTML.",
        payload, ResponseOutput, diagnostics)
    if result:
        return {**result, "method": "Gemini / AI hypothesis; human verification required"}
    if key:
        fallback["method"] += " • fallback used"
        fallback["ai_error"] = diagnostics.get("error", "No usable AI answer was returned. Retry in Settings.")
    return fallback
