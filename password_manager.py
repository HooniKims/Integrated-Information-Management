from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PasswordItemRepository:
    def __init__(self, items_path: Path) -> None:
        self.items_path = items_path
        self._lock = threading.Lock()
        self._ensure_file()

    def list_items(self) -> list[dict]:
        with self._lock:
            items = self._read_records()
        sorted_items = sorted(
            items,
            key=lambda item: (
                item.get("updated_at", ""),
                item.get("created_at", ""),
                item.get("title", "").casefold(),
            ),
            reverse=True,
        )
        return [self._serialize_item(item) for item in sorted_items]

    def create_item(self, payload: dict) -> dict:
        item = self._build_item_record(payload)
        with self._lock:
            items = self._read_records()
            items.append(item)
            self._write_records(items)
        return self._serialize_item(item)

    def update_item(self, item_id: str, payload: dict) -> dict:
        with self._lock:
            items = self._read_records()
            for index, existing in enumerate(items):
                if existing["id"] != item_id:
                    continue

                updated = dict(existing)
                if "title" in payload:
                    updated["title"] = self._normalize_text(payload.get("title"))
                if "password" in payload:
                    updated["password"] = self._normalize_text(payload.get("password"))
                if not updated["title"]:
                    raise ValueError("제목은 필수입니다.")

                updated["updated_at"] = utc_now_iso()
                items[index] = updated
                self._write_records(items)
                return self._serialize_item(updated)

        raise KeyError(item_id)

    def delete_item(self, item_id: str) -> dict:
        with self._lock:
            items = self._read_records()
            for index, existing in enumerate(items):
                if existing["id"] != item_id:
                    continue
                deleted = items.pop(index)
                self._write_records(items)
                return self._serialize_item(deleted)
        raise KeyError(item_id)

    def summarize_items(self) -> dict:
        items = self.list_items()
        return {
            "total": len(items),
            "missing_password": sum(1 for item in items if not item.get("password")),
        }

    def _build_item_record(self, payload: dict) -> dict:
        title = self._normalize_text(payload.get("title"))
        if not title:
            raise ValueError("제목은 필수입니다.")

        now = utc_now_iso()
        return {
            "id": uuid.uuid4().hex,
            "title": title,
            "password": self._normalize_text(payload.get("password")),
            "created_at": now,
            "updated_at": now,
        }

    def _serialize_item(self, item: dict) -> dict:
        return {
            "id": item["id"],
            "title": item.get("title", ""),
            "password": item.get("password", ""),
            "created_at": item.get("created_at", ""),
            "updated_at": item.get("updated_at", ""),
        }

    def _ensure_file(self) -> None:
        self.items_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.items_path.exists():
            self._write_records([])

    def _read_records(self) -> list[dict]:
        payload = json.loads(self.items_path.read_text(encoding="utf-8"))
        records = payload.get("items", [])
        if not isinstance(records, list):
            raise ValueError(f"{self.items_path.name} 파일 구조가 올바르지 않습니다.")
        return records

    def _write_records(self, records: list[dict]) -> None:
        self.items_path.write_text(json.dumps({"items": records}, ensure_ascii=False, indent=2), encoding="utf-8")

    def _normalize_text(self, value: object) -> str:
        return str(value or "").strip()
