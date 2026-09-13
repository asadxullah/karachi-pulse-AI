"""Location validation and photo storage regression checks."""
import base64
import time
import unittest
from io import BytesIO
from datetime import datetime, timezone
from PIL import Image
from pulse.data import prepare_photo, restore_photo, make_report, export_reports, import_reports
from pulse.ui.location import checked_location


class ReportAttachments(unittest.TestCase):
    def test_location_validation(self):
        point = dict(status="ok", latitude=24.9234, longitude=67.092, accuracy=12, timestamp=time.time()*1000)
        self.assertEqual(checked_location(point), (24.9234, 67.092, 12))
        for invalid in [None, {"status": "error"}, dict(point, latitude=31.5),
                        dict(point, accuracy=5000), dict(point, latitude=float("nan")),
                        dict(point, timestamp=0)]:
            with self.assertRaises(ValueError):
                checked_location(invalid)

    def test_photo_roundtrip_and_backup(self):
        output = BytesIO()
        Image.new("RGB", (1800, 900), "green").save(output, format="PNG")
        photo = prepare_photo(output.getvalue())
        self.assertEqual(restore_photo(photo), photo)
        with Image.open(BytesIO(base64.b64decode(photo["base64"]))) as image:
            self.assertLessEqual(max(image.size), 1280)
            self.assertEqual(len(image.getexif()), 0)
        clock = datetime.now(timezone.utc)
        report = make_report("Blocked drain near the market", "Gulshan-e-Iqbal", clock)
        report["photo"] = photo
        restored, count = import_reports(export_reports([report], "Live"), [], "Live", clock)
        self.assertEqual(count, 1)
        self.assertEqual(restored[0]["photo"], photo)

    def test_invalid_photos_rejected(self):
        for raw in [b"not an image", b"", b"x"*5_000_001]:
            with self.assertRaises(ValueError):
                prepare_photo(raw)
        with self.assertRaises(ValueError):
            restore_photo({"mime": "image/jpeg", "base64": "invalid"})
