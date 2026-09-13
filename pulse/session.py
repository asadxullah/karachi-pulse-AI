"""Workspace lifecycle, monitoring history, simulation and live refresh."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import streamlit as st
import time
import uuid
from pulse.config import AREAS, WORKSPACE_KEYS
from pulse.data import make_report
from pulse.demo import SCENARIO, STAGES, demo_data
from pulse.utils import local_time, now_utc


def init_state():
    if "reports" not in st.session_state:
        st.session_state.reports = demo_data(now_utc())
        st.session_state.stage = 0
        st.session_state.offset = 0
        st.session_state.registry = {}
        st.session_state.history = []
        st.session_state.responses = {}
        st.session_state.last_fingerprint = ""
        st.session_state.demo_log = []
    if "workspace_bank" not in st.session_state:
        st.session_state.workspace_bank = {}
        st.session_state.active_workspace = "Demo"


def switch_workspace(target):
    """Keep user reports, simulation time and review history in separate sessions."""
    old = st.session_state.active_workspace
    if old == target:
        return
    st.session_state.workspace_bank[old] = {
        k: deepcopy(st.session_state[k]) for k in WORKSPACE_KEYS if k in st.session_state}
    fresh = dict(reports=demo_data(now_utc()) if target == "Demo" else [], stage=0, offset=0,
                 registry={}, history=[], responses={}, last_fingerprint="", demo_log=[])
    saved = st.session_state.workspace_bank.get(target, fresh)
    for k in WORKSPACE_KEYS:
        st.session_state.pop(k, None)
    st.session_state.update(deepcopy(saved))
    st.session_state.active_workspace = target
    # Remove cross-workspace selections before their widgets are instantiated.
    for k in list(st.session_state):
        if k.startswith(("records_", "command_", "map_", "queue_", "intel_")):
            del st.session_state[k]


@st.fragment(run_every=60)
def live_refresh():
    """Reevaluate time windows while a live tab is connected; no background worker."""
    current = time.monotonic()
    previous = st.session_state.get("live_tick", current)
    st.session_state.setdefault("live_tick", current)
    if st.session_state.active_workspace == "Live" and current-previous >= 55:
        st.session_state.live_tick = current
        st.rerun(scope="app")


def simulate():
    step = st.session_state.stage
    if step >= len(STAGES):
        return
    if step < len(SCENARIO):
        st.session_state.offset += 20
    clock = now_utc() + timedelta(minutes=st.session_state.offset)
    if step < len(SCENARIO):
        cat, text, severity, da, db = SCENARIO[step]
        a, b = AREAS["Gulshan-e-Iqbal"]
        st.session_state.reports.append(make_report(text, "Gulshan-e-Iqbal", clock,
            cat, severity, lat=a+da, lon=b+db, scenario=True))
    st.session_state.stage += 1
    st.session_state.demo_log.append({"time": local_time(clock), "event": STAGES[step]})


def monitor(incidents, clock, fingerprint):
    """Session registry preserves IDs/status by same-rule signal overlap."""
    registry = st.session_state.registry
    for record in registry.values():
        record["currently_detected"] = False
    used = set()
    changed = fingerprint != st.session_state.last_fingerprint
    for inc in incidents:
        ids = set(inc["members"].report_id)
        candidates = [(len(ids & set(v["ids"])), k) for k, v in registry.items()
                      if v["kind"] == inc["kind"] and k not in used]
        best = max(candidates, default=(0, ""))
        iid = best[1] if best[0] else "PULSE-"+uuid.uuid4().hex[:6].upper()
        if iid not in registry:
            registry[iid] = dict(kind=inc["kind"], ids=list(ids), first=clock, status="Monitoring", last=None, changes=[])
        record = registry[iid]
        if record["status"] == "Resolved":
            record["status"] = "Monitoring"
        record["currently_detected"] = True
        record["summary"] = dict(area=inc["area"], title=inc["title"], risk=inc["risk"],
                                 signals=inc["signals"], latest=inc["latest"])
        if changed:
            old = record["last"]
            changes = []
            if old:
                for factor, value in inc["factors"].items():
                    delta = round(value-old["factors"][factor], 2)
                    if abs(delta) >= .1:
                        changes.append(f"{factor}: {delta:+.2f} risk points")
            record["changes"] = changes
            record["delta"] = inc["risk"]-old["risk"] if old else None
            record["last"] = {"risk": inc["risk"], "factors": inc["factors"]}
            record["ids"] = sorted(ids | set(record["ids"]))
            st.session_state.history.append(dict(time=clock, incident=iid, area=inc["area"],
                risk=inc["risk"], signals=inc["signals"], stage=st.session_state.stage))
        used.add(iid)
        inc.update(id=iid, first_detected=record["first"], status=record["status"],
                   delta=record.get("delta"), changes=record["changes"])
    st.session_state.last_fingerprint = fingerprint
    st.session_state.history = st.session_state.history[-2000:]
    return sorted(incidents, key=lambda x: x["risk"], reverse=True)
