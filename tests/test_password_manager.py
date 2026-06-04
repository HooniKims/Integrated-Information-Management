from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from password_manager import PasswordItemRepository


class PasswordItemRepositoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "password_items.json"
        self.repository = PasswordItemRepository(self.path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_create_list_update_and_delete_password_item(self) -> None:
        created = self.repository.create_item({"title": "과학실 번호키", "password": "1234"})

        self.assertEqual(created["title"], "과학실 번호키")
        self.assertEqual(created["password"], "1234")
        self.assertEqual(self.repository.summarize_items()["total"], 1)
        self.assertEqual(self.repository.list_items()[0]["id"], created["id"])

        updated = self.repository.update_item(created["id"], {"title": "과학실 앞문", "password": "5678"})
        self.assertEqual(updated["title"], "과학실 앞문")
        self.assertEqual(updated["password"], "5678")

        deleted = self.repository.delete_item(created["id"])
        self.assertEqual(deleted["id"], created["id"])
        self.assertEqual(self.repository.list_items(), [])

    def test_title_is_required(self) -> None:
        with self.assertRaises(ValueError):
            self.repository.create_item({"title": "", "password": "1234"})

    def test_existing_file_structure_is_preserved(self) -> None:
        self.path.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "id": "item-1",
                            "title": "방송실",
                            "password": "0000",
                            "created_at": "2026-06-04T00:00:00+00:00",
                            "updated_at": "2026-06-04T00:00:00+00:00",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        self.assertEqual(self.repository.list_items()[0]["title"], "방송실")


if __name__ == "__main__":
    unittest.main()
