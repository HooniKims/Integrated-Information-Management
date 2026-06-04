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

    def test_dash_year_month_input_is_normalized_to_csv_year_month_format(self) -> None:
        device, _ = self.repository.upsert_device(
            {
                "management_no": "A-002-1",
                "introduced_date": "2026-06",
            }
        )

        self.assertEqual(device["introduced_date"], "2026. 06.")

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

    def test_notebook_life_cycle_due_uses_six_year_threshold(self) -> None:
        self.repository.upsert_device(
            {
                "management_no": "A-004",
                "device_type": "노트북",
                "introduced_date": "2020. 07.",
            }
        )
        self.repository.upsert_device(
            {
                "management_no": "A-005",
                "device_type": "노트북",
                "introduced_date": "2020. 06.",
            }
        )

        with patch("device_inventory._today", return_value=date(2026, 6, 4)):
            five_year_notebook = self.repository.get_device("A-004")
            six_year_notebook = self.repository.get_device("A-005")

        self.assertEqual(five_year_notebook["usage_years"], 5)
        self.assertFalse(five_year_notebook["life_cycle_due"])
        self.assertEqual(six_year_notebook["usage_years"], 6)
        self.assertTrue(six_year_notebook["life_cycle_due"])

    def test_electronic_whiteboard_life_cycle_due_uses_seven_year_threshold(self) -> None:
        self.repository.upsert_device(
            {
                "management_no": "A-006",
                "device_type": "전자칠판",
                "introduced_date": "2019. 07.",
            }
        )
        self.repository.upsert_device(
            {
                "management_no": "A-007",
                "device_type": "전자칠판",
                "introduced_date": "2019. 06.",
            }
        )

        with patch("device_inventory._today", return_value=date(2026, 6, 4)):
            six_year_whiteboard = self.repository.get_device("A-006")
            seven_year_whiteboard = self.repository.get_device("A-007")

        self.assertEqual(six_year_whiteboard["usage_years"], 6)
        self.assertFalse(six_year_whiteboard["life_cycle_due"])
        self.assertEqual(seven_year_whiteboard["usage_years"], 7)
        self.assertTrue(seven_year_whiteboard["life_cycle_due"])

    def test_tablet_and_desktop_life_cycle_due_use_five_year_threshold(self) -> None:
        self.repository.upsert_device(
            {
                "management_no": "A-008",
                "device_type": "태블릿",
                "introduced_date": "2021. 06.",
            }
        )
        self.repository.upsert_device(
            {
                "management_no": "A-009",
                "device_type": "데스크톱",
                "introduced_date": "2021. 06.",
            }
        )

        with patch("device_inventory._today", return_value=date(2026, 6, 4)):
            tablet = self.repository.get_device("A-008")
            desktop = self.repository.get_device("A-009")

        self.assertEqual(tablet["usage_years"], 5)
        self.assertTrue(tablet["life_cycle_due"])
        self.assertEqual(desktop["usage_years"], 5)
        self.assertTrue(desktop["life_cycle_due"])

    def test_confirm_needed_status_counts_as_inspection_needed(self) -> None:
        device, _ = self.repository.upsert_device(
            {
                "management_no": "A-010",
                "status": "확인 필요",
            }
        )

        summary = self.repository.summarize_devices()

        self.assertTrue(device["repair_or_inspection_needed"])
        self.assertEqual(summary["repair_or_inspection_needed"], 1)


if __name__ == "__main__":
    unittest.main()
