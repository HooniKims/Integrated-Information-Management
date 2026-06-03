from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from device_inventory import DeviceInventoryRepository


def write_json(path: Path, key: str, records: list[dict]) -> None:
    path.write_text(json.dumps({key: records}, ensure_ascii=False, indent=2), encoding="utf-8")


class DeviceInventoryDateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.inventory_path = base / "device_inventory.json"
        self.events_path = base / "device_inventory_events.json"
        write_json(self.inventory_path, "devices", [])
        write_json(self.events_path, "events", [])
        self.repository = DeviceInventoryRepository(self.inventory_path, self.events_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_introduced_month_keeps_csv_year_month_format(self) -> None:
        device, _ = self.repository.upsert_device(
            {
                "management_no": "A-001",
                "introduced_date": "2020. 01.",
            }
        )

        self.assertEqual(device["introduced_date"], "2020. 01.")

    def test_full_date_input_is_normalized_to_year_month_format(self) -> None:
        device, _ = self.repository.upsert_device(
            {
                "management_no": "A-002",
                "introduced_date": "2020-01-15",
            }
        )

        self.assertEqual(device["introduced_date"], "2020. 01.")

    def test_usage_years_are_calculated_from_year_month(self) -> None:
        self.repository.upsert_device(
            {
                "management_no": "A-003",
                "introduced_date": "2020. 12.",
            }
        )

        with patch("device_inventory._today", return_value=date(2026, 6, 4)):
            device = self.repository.get_device("A-003")

        self.assertEqual(device["usage_years"], 5)


if __name__ == "__main__":
    unittest.main()
