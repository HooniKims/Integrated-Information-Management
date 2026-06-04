from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from device_inventory import DeviceInventoryRepository


def write_json(path: Path, key: str, records: list[dict]) -> None:
    path.write_text(json.dumps({key: records}, ensure_ascii=False, indent=2), encoding="utf-8")


class DeviceInventoryImportTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.inventory_path = base / "device_inventory.json"
        self.events_path = base / "device_inventory_events.json"
        write_json(
            self.inventory_path,
            "devices",
            [
                {
                    "id": "dev-1",
                    "management_no": "LAB-NB-001",
                    "asset_group": "정보교과실PC",
                    "location": "정보실",
                    "device_type": "노트북",
                    "manufacturer": "LG",
                    "model_name": "Gram",
                    "serial_no": "SN-001",
                    "cpu": "i5",
                    "ram": "",
                    "introduced_date": "2022. 03.",
                    "status": "정상 사용",
                    "notes": "",
                    "user_name": "",
                    "image_url": "",
                    "created_at": "2026-06-01T00:00:00+00:00",
                    "updated_at": "2026-06-01T00:00:00+00:00",
                }
            ],
        )
        write_json(self.events_path, "events", [])
        self.repository = DeviceInventoryRepository(self.inventory_path, self.events_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_import_csv_updates_existing_device_by_management_no(self) -> None:
        result = self.repository.import_csv("management_no,ram\nLAB-NB-001,16GB\n")

        device = self.repository.get_device("LAB-NB-001")

        self.assertEqual(result["created"], 0)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["upserted"], 1)
        self.assertEqual(device["ram"], "16GB")
        self.assertEqual(device["location"], "정보실")


if __name__ == "__main__":
    unittest.main()
