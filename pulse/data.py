"""Report construction, validation, duplicate preparation and JSON backup exchange."""

from datetime import datetime, timedelta, timezone
import json
import pandas as pd
import re
import uuid
import base64
import binascii
from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError
from pulse.agents.correlation import duplicate_agent
from pulse.agents.signal import signal_agent
from pulse.config import AREAS, CATEGORIES, MAX_REPORTS
from pulse.models import SignalOutput


def prepare_photo(raw):
    """Decode and re-encode a bounded photo, stripping EXIF and embedded metadata."""
    if not isinstance(raw, bytes) or not raw or len(raw) > 5_000_000:
        raise ValueError("Choose a JPG, PNG or WebP photo smaller than 5 MB.")
    try:
        with Image.open(BytesIO(raw)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"} or source.width*source.height > 20_000_000:
                raise ValueError("Use a JPG, PNG or WebP photo of at most 20 megapixels.")
            source.load()
            converted = ImageOps.exif_transpose(source).convert("RGB")
            converted.thumbnail((1280, 1280))
            clean = Image.new("RGB", converted.size)
            clean.paste(converted)
            while True:
                output = BytesIO()
                clean.save(output, format="JPEG", quality=75, optimize=True)
                if output.tell() <= 350_000:
                    return {"mime": "image/jpeg", "base64": base64.b64encode(output.getvalue()).decode("ascii")}
                clean.thumbnail((max(1, int(clean.width*.8)), max(1, int(clean.height*.8))))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("This file is not a readable supported image.") from exc


def restore_photo(value):
    if value is None:
        return None
    try:
        if not isinstance(value, dict) or value.get("mime") != "image/jpeg" or len(value["base64"]) > 470_000:
            raise ValueError("Invalid photo attachment in backup.")
        raw = base64.b64decode(value["base64"], validate=True)
        # Validate the image without changing already-normalized bytes on every restore.
        with Image.open(BytesIO(raw)) as photo:
            if photo.format != "JPEG" or max(photo.size) > 1280:
                raise ValueError("Invalid photo attachment dimensions.")
            photo.verify()
        return {"mime": "image/jpeg", "base64": value["base64"]}
    except (KeyError, TypeError, binascii.Error, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Invalid photo attachment in backup.") from exc


def make_report(text, area, timestamp, category=None, severity=2, source="Synthetic demo",
                lat=None, lon=None, ai=None, scenario=False):
    ai = ai or signal_agent(text)
    return dict(report_id="R-" + uuid.uuid4().hex[:8].upper(), timestamp=timestamp,
        area=area, latitude=AREAS[area][0] if lat is None else lat,
        longitude=AREAS[area][1] if lon is None else lon, complaint_text=text,
        category=category or ai["category"], severity=int(severity), source=source, status="Open",
        ai_classification=ai["category"], confidence_score=ai["confidence"], signal_analysis=ai,
        scenario=scenario, location_basis="Area centroid (approximate)" if lat is None else "Provided / synthetic point")


def report_frame(rows):
    columns = ["report_id", "timestamp", "area", "latitude", "longitude", "complaint_text",
               "category", "severity", "source", "status", "ai_classification", "confidence_score",
               "signal_analysis", "scenario", "location_basis"]
    frame = pd.DataFrame(rows, columns=columns)
    frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)
    for c in ["latitude", "longitude", "severity", "confidence_score"]:
        frame[c] = pd.to_numeric(frame[c])
    return duplicate_agent(frame)


def export_reports(rows, workspace):
    # Only report data is exported; keys, provider prompts and widget state never are.
    return json.dumps({"format": "karachi-pulse-reports-v1", "workspace": workspace,
                       "exported_at": datetime.now(timezone.utc).isoformat(), "reports": rows},
                      ensure_ascii=False, default=str, indent=2).encode("utf-8")


def import_reports(payload, existing, workspace, clock):
    """Validate the complete backup before mutating anything; merge by report ID."""
    if len(payload) > 50_000_000:
        raise ValueError("Backup must be smaller than 50 MB, including photos.")
    try:
        data = json.loads(payload)
        if not isinstance(data, dict) or data.get("format") != "karachi-pulse-reports-v1":
            raise ValueError("Choose a report backup exported by Karachi PULSE.")
        if data.get("workspace") != workspace:
            raise ValueError("Switch to the workspace named in this backup before restoring it.")
        raw = data["reports"]
        if not isinstance(raw, list) or len(raw) > MAX_REPORTS:
            raise ValueError("This prototype supports up to 1,000 reports per workspace.")
        existing_by_id = {r["report_id"]: r for r in existing}
        checked, seen = [], set()
        for entry in raw:
            rid = entry["report_id"]
            if not isinstance(rid, str) or not re.fullmatch(r"R-[A-Z0-9]{6,32}", rid) or rid in seen:
                raise ValueError("Backup contains an invalid or repeated report ID.")
            seen.add(rid)
            if entry["area"] not in AREAS or entry["category"] not in CATEGORIES:
                raise ValueError("Backup contains an unknown area or category.")
            text_value = entry["complaint_text"]
            if not isinstance(text_value, str) or not 8 <= len(text_value.strip()) <= 2000:
                raise ValueError("Backup contains an invalid complaint description.")
            lat, lon = float(entry["latitude"]), float(entry["longitude"])
            if not (24.65 <= lat <= 25.65 and 66.5 <= lon <= 67.8):
                raise ValueError("Backup contains invalid Karachi coordinates.")
            ts = pd.Timestamp(entry["timestamp"])
            if ts.tzinfo is None or pd.isna(ts):
                raise ValueError("Backup timestamps must include a timezone.")
            ts = ts.tz_convert("UTC").to_pydatetime()
            if workspace == "Live" and ts > clock+timedelta(minutes=5):
                raise ValueError("Live backups cannot contain future reports.")
            severity = entry["severity"]
            if type(severity) is not int or not 1 <= severity <= 5:
                raise ValueError("Backup severity must be an integer from 1 to 5.")
            if entry["status"] not in ["Open", "Investigating", "Resolved"]:
                raise ValueError("Backup contains an invalid report status.")
            if not isinstance(entry["source"], str) or len(entry["source"]) > 100:
                raise ValueError("Backup contains an invalid source.")
            ai = SignalOutput.model_validate(entry["signal_analysis"]).model_dump()
            if ai["category"] not in CATEGORIES or any(c not in CATEGORIES for c in ai["related_categories"]):
                raise ValueError("Backup contains invalid classification data.")
            ai["method"] = "Restored classification (unverified backup)"
            row = make_report(text_value, entry["area"], ts, entry["category"], severity,
                              entry["source"], lat, lon, ai, workspace == "Demo" and bool(entry.get("scenario")))
            row.update(report_id=rid, status=entry["status"],
                       location_basis="Restored coordinates (unverified)")
            photo = restore_photo(entry.get("photo"))
            if photo:
                row["photo"] = photo
            if rid not in existing_by_id:
                checked.append(row)
        if len(existing)+len(checked) > MAX_REPORTS:
            raise ValueError("Restoring this backup would exceed the 1,000-report workspace limit.")
        if sum(len(r.get("photo", {}).get("base64", "")) for r in existing+checked) > 28_000_000:
            raise ValueError("This workspace supports about 20 MB of compressed photos. Export before clearing space.")
        return existing+checked, len(checked)
    except (KeyError, TypeError, OverflowError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid backup structure. Choose an original PULSE JSON backup.") from exc
