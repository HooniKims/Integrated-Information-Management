from __future__ import annotations

import csv
import io
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SiteAccountRepository:
    csv_headers = [
        "사이트",
        "설명",
        "URL",
        "ID",
        "PW",
        "비고",
    ]

    _field_aliases = {
        "사이트": "site_name",
        "site_name": "site_name",
        "사이트명": "site_name",
        "설명": "description",
        "description": "description",
        "URL": "url",
        "url": "url",
        "주소": "url",
        "ID": "username",
        "id": "username",
        "username": "username",
        "계정": "username",
        "PW": "password",
        "password": "password",
        "비밀번호": "password",
        "비고": "note",
        "note": "note",
        "메모": "note",
    }

    def __init__(self, accounts_path: Path, audit_log_path: Path) -> None:
        self.accounts_path = accounts_path
        self.audit_log_path = audit_log_path
        self._lock = threading.Lock()
        self._ensure_files()

    def list_accounts(self) -> list[dict]:
        with self._lock:
            accounts = self._read_records(self.accounts_path, key="accounts")
        sorted_accounts = sorted(
            accounts,
            key=lambda item: (
                item.get("updated_at", ""),
                item.get("created_at", ""),
                item.get("site_name", "").casefold(),
            ),
            reverse=True,
        )
        return [self._serialize_account(item) for item in sorted_accounts]

    def create_account(self, payload: dict) -> dict:
        account = self._build_account_record(payload)
        with self._lock:
            accounts = self._read_records(self.accounts_path, key="accounts")
            accounts.append(account)
            self._write_records(self.accounts_path, key="accounts", records=accounts)
        return self._serialize_account(account)

    def update_account(self, account_id: str, payload: dict) -> dict:
        with self._lock:
            accounts = self._read_records(self.accounts_path, key="accounts")
            for index, existing in enumerate(accounts):
                if existing["id"] != account_id:
                    continue

                updated = dict(existing)
                for field in ("site_name", "description", "url", "username", "note"):
                    if field in payload:
                        updated[field] = self._normalize_text(payload.get(field))

                if "url" in payload:
                    updated["url"] = self._normalize_url(payload.get("url"))

                if "password" in payload:
                    updated["password"] = self._normalize_text(payload.get("password"))

                if not updated["site_name"]:
                    raise ValueError("사이트 이름은 비워둘 수 없습니다.")

                updated["updated_at"] = utc_now_iso()
                accounts[index] = updated
                self._write_records(self.accounts_path, key="accounts", records=accounts)
                return self._serialize_account(updated)

        raise KeyError(account_id)

    def delete_account(self, account_id: str) -> dict:
        with self._lock:
            accounts = self._read_records(self.accounts_path, key="accounts")
            for index, existing in enumerate(accounts):
                if existing["id"] != account_id:
                    continue
                deleted = accounts.pop(index)
                self._write_records(self.accounts_path, key="accounts", records=accounts)
                return self._serialize_account(deleted)
        raise KeyError(account_id)

    def import_csv(self, csv_text: str) -> dict:
        text = self._normalize_text(csv_text).lstrip("\ufeff")
        if not text:
            raise ValueError("CSV 내용이 비어 있습니다.")

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("CSV 헤더를 읽을 수 없습니다.")

        created_count = 0
        skipped_count = 0
        processed_items: list[dict] = []
        skipped_items: list[dict] = []

        for row in reader:
            if not row:
                continue
            payload = self._payload_from_csv_row(row)
            if not any(payload.values()):
                continue
            account, created = self.create_account_if_new(payload)
            if created:
                processed_items.append(account)
                created_count += 1
            else:
                skipped_items.append(account)
                skipped_count += 1

        return {
            "row_count": len(processed_items),
            "created": created_count,
            "updated": 0,
            "skipped": skipped_count,
            "upserted": created_count,
            "items": processed_items,
            "skipped_items": skipped_items,
        }

    def create_account_if_new(self, payload: dict) -> tuple[dict, bool]:
        account = self._build_account_record(payload)
        with self._lock:
            accounts = self._read_records(self.accounts_path, key="accounts")
            existing_index = self._find_account_index(accounts, account["site_name"], account["username"])
            if existing_index is None:
                accounts.append(account)
                self._write_records(self.accounts_path, key="accounts", records=accounts)
                return self._serialize_account(account), True

            return self._serialize_account(accounts[existing_index]), False

    def export_csv(self, *, include_items: bool = True) -> str:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=self.csv_headers)
        writer.writeheader()
        if include_items:
            for account in self.list_accounts():
                writer.writerow(self._account_to_csv_row(account))
        return "\ufeff" + buffer.getvalue()

    def summarize_accounts(self) -> dict:
        accounts = self.list_accounts()
        return {
            "total": len(accounts),
            "with_url": sum(1 for item in accounts if item.get("url")),
            "with_note": sum(1 for item in accounts if item.get("note")),
            "missing_description": sum(1 for item in accounts if not item.get("description")),
            "missing_password": sum(1 for item in accounts if not item.get("password")),
        }

    def _build_account_record(self, payload: dict) -> dict:
        site_name = self._normalize_text(payload.get("site_name"))
        if not site_name:
            raise ValueError("사이트 이름은 필수입니다.")

        now = utc_now_iso()
        return {
            "id": uuid.uuid4().hex,
            "site_name": site_name,
            "description": self._normalize_text(payload.get("description")),
            "url": self._normalize_url(payload.get("url")),
            "username": self._normalize_text(payload.get("username")),
            "password": self._normalize_text(payload.get("password")),
            "note": self._normalize_text(payload.get("note")),
            "created_at": now,
            "updated_at": now,
        }

    def _serialize_account(self, account: dict) -> dict:
        return {
            "id": account["id"],
            "site_name": account.get("site_name", ""),
            "description": account.get("description", ""),
            "url": account.get("url", ""),
            "username": account.get("username", ""),
            "password": account.get("password", ""),
            "note": account.get("note", ""),
            "created_at": account.get("created_at", ""),
            "updated_at": account.get("updated_at", ""),
        }

    def _account_to_csv_row(self, account: dict) -> dict:
        return {
            "사이트": account.get("site_name", ""),
            "설명": account.get("description", ""),
            "URL": account.get("url", ""),
            "ID": account.get("username", ""),
            "PW": account.get("password", ""),
            "비고": account.get("note", ""),
        }

    def _payload_from_csv_row(self, row: dict) -> dict:
        payload = {
            "site_name": "",
            "description": "",
            "url": "",
            "username": "",
            "password": "",
            "note": "",
        }
        for raw_key, raw_value in row.items():
            key = self._normalize_text(raw_key)
            if not key:
                continue
            field = self._field_aliases.get(key)
            if field and field in payload:
                payload[field] = self._normalize_text(raw_value)
        return payload

    def _find_account_index(self, accounts: list[dict], site_name: str, username: str) -> int | None:
        target_site_name = site_name.casefold()
        target_username = username.casefold()
        for index, account in enumerate(accounts):
            if (
                self._normalize_text(account.get("site_name")).casefold() == target_site_name
                and self._normalize_text(account.get("username")).casefold() == target_username
            ):
                return index
        return None

    def _normalize_text(self, value: object) -> str:
        return str(value or "").strip()

    def _normalize_url(self, value: object) -> str:
        raw = self._normalize_text(value)
        if not raw:
            return ""

        parsed = urlparse(raw)
        if not parsed.scheme:
            raw = f"https://{raw}"
            parsed = urlparse(raw)

        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("URL은 http 또는 https 주소여야 합니다.")
        return raw

    def _ensure_files(self) -> None:
        self.accounts_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.accounts_path.exists():
            self._write_records(self.accounts_path, key="accounts", records=[])

    def _read_records(self, path: Path, key: str) -> list[dict]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get(key, [])
        if not isinstance(records, list):
            raise ValueError(f"{path.name} 파일 구조가 올바르지 않습니다.")
        return records

    def _write_records(self, path: Path, key: str, records: list[dict]) -> None:
        payload = {key: records}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
