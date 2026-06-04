from __future__ import annotations

import base64
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from device_inventory import DeviceInventoryRepository
from server import store_device_image_upload


TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def write_json(path: Path, key: str, records: list[dict]) -> None:
    path.write_text(json.dumps({key: records}, ensure_ascii=False, indent=2), encoding="utf-8")


class DeviceInventoryImageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)
        self.image_dir = base / "device_images"
        self.image_dir.mkdir()
        self.inventory_path = base / "device_inventory.json"
        self.events_path = base / "device_inventory_events.json"
        write_json(
            self.inventory_path,
            "devices",
            [
                {
                    "id": "dev-1",
                    "management_no": "IMG-001",
                    "asset_group": "노트북",
                    "location": "정보실",
                    "device_type": "노트북",
                    "manufacturer": "Samsung",
                    "model_name": "Galaxy Book",
                    "serial_no": "SN-IMG",
                    "cpu": "i5",
                    "ram": "16GB",
                    "introduced_date": "2024-03-01",
                    "status": "정상 사용",
                    "notes": "",
                    "user_name": "",
                    "image_url": "/device-images/notebook.png",
                    "created_at": "2026-06-04T00:00:00+00:00",
                    "updated_at": "2026-06-04T00:00:00+00:00",
                }
            ],
        )
        write_json(self.events_path, "events", [])
        (self.image_dir / "notebook.png").write_bytes(TINY_PNG)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_uploaded_device_image_is_saved_as_internal_url(self) -> None:
        result = store_device_image_upload(
            self.image_dir,
            file_name="Notebook.PNG",
            content_type="image/png",
            data=TINY_PNG,
        )

        self.assertRegex(result["url"], r"^/device-images/[a-f0-9]{16}\.png$")
        self.assertTrue((self.image_dir / Path(result["url"]).name).is_file())
        self.assertEqual((self.image_dir / Path(result["url"]).name).read_bytes(), TINY_PNG)

    def test_report_embeds_internal_device_images(self) -> None:
        repository = DeviceInventoryRepository(self.inventory_path, self.events_path, image_dir=self.image_dir)

        report_bytes = repository.export_report_workbook()

        with zipfile.ZipFile(io.BytesIO(report_bytes)) as workbook_zip:
            media_files = [name for name in workbook_zip.namelist() if name.startswith("xl/media/")]
            self.assertTrue(media_files)
            self.assertTrue(any(name.endswith(".png") for name in media_files))


if __name__ == "__main__":
    unittest.main()
