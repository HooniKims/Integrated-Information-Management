from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SiteAccountRepository:
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
            key=lambda item: (item.get("site_name", "").casefold(), item.get("username", "").casefold()),
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
