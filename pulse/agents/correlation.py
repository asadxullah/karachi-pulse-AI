"""Correlation Agent: duplicate detection and bounded spatial/time relationships."""

from datetime import datetime, timedelta, timezone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import pandas as pd
from pulse.config import RULES
from pulse.utils import haversine, normalize


def duplicate_agent(frame):
    """Conservative same-category similarity; every group has a fixed representative.

    No chaining. Repeated reports never raise severity, counts or rate of the
    representative. Without verified reporter identities we do not award a
    confidence bonus for alleged independent citizens.
    """
    frame = frame.sort_values(["timestamp", "report_id"]).reset_index(drop=True).copy()
    frame["duplicate_of"] = ""
    if len(frame) < 2:
        return frame
    texts = frame.complaint_text.map(normalize)
    try:
        vectors = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)).fit_transform(texts)
        similarity = cosine_similarity(vectors)
    except ValueError:
        similarity = np.equal.outer(texts.to_numpy(), texts.to_numpy()).astype(float)
    roots = []
    for i, row in frame.iterrows():
        match = None
        for j in roots:
            other = frame.iloc[j]
            if (row.category == other.category and similarity[i, j] >= .82
                and (row.status == "Resolved") == (other.status == "Resolved")
                and abs((row.timestamp-other.timestamp).total_seconds()) <= 6*3600
                and haversine(row.latitude, row.longitude, other.latitude, other.longitude) <= .15):
                match = other.report_id
                break
        if match:
            frame.at[i, "duplicate_of"] = match
        else:
            roots.append(i)
    return frame


def rule_matches(kind, cats):
    if kind == "drain":
        return len(cats) >= 2 and bool(cats & {"Sewage", "Drainage"})
    if kind == "electric":
        return "Electricity" in cats and bool(cats & {"Public Safety", "Flooding"})
    return RULES[kind]["categories"].issubset(cats)


def correlation_agent(frame, clock, radius, window):
    """Greedy complete-link grouping: EVERY pair is within radius and window.

    Unlike district counts or single-link DBSCAN, this prevents long spatial or
    temporal chains. A report may support different explicit hypotheses.
    """
    unique = frame[(frame.duplicate_of == "") & (frame.status != "Resolved")
                   & (frame.timestamp >= clock-timedelta(hours=window)) & (frame.timestamp <= clock)]
    detected = []
    for kind, rule in RULES.items():
        relevant = unique[unique.category.isin(rule["categories"])].sort_values(["timestamp", "report_id"])
        groups = []
        for _, row in relevant.iterrows():
            for group in groups:
                if all(abs((row.timestamp-r.timestamp).total_seconds()) <= window*3600
                       and haversine(row.latitude, row.longitude, r.latitude, r.longitude) <= radius for r in group):
                    group.append(row)
                    break
            else:
                groups.append([row])
        for group in groups:
            members = pd.DataFrame(group)
            cats = set(members.category)
            if len(group) >= 3 and rule_matches(kind, cats):
                ids = set(members.report_id)
                related = frame[(frame.report_id.isin(ids) | frame.duplicate_of.isin(ids))
                                & (frame.status != "Resolved") & (frame.timestamp <= clock)]
                detected.append(dict(kind=kind, members=members, related=related,
                                     categories=sorted(cats), title=rule["title"]))
    return detected
