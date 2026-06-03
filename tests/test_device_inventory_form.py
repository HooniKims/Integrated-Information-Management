from __future__ import annotations

import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DeviceInventoryFormTestCase(unittest.TestCase):
    def test_purchase_month_input_accepts_dash_year_month_format(self) -> None:
        html = (PROJECT_ROOT / "web" / "index.html").read_text(encoding="utf-8")
        match = re.search(r'id="deviceAcquiredAtInput"[^>]*pattern="([^"]+)"', html)

        self.assertIsNotNone(match)
        pattern = match.group(1)
        self.assertRegex("2026-06", re.compile(f"^(?:{pattern})$"))


if __name__ == "__main__":
    unittest.main()
