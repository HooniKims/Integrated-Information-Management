from __future__ import annotations

import csv
import io
import json
import threading
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


EXPECTED_LIFE_CYCLE_YEARS = 5


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> date:
    return date.today()


class DeviceInventoryRepository:
    csv_headers = [
        "관리번호",
        "분류",
        "설치장소",
        "형태",
        "제조회사",
        "모델명",
        "시리얼넘버",
        "CPU",
        "RAM",
        "구입시기",
        "사용연수",
        "상태",
        "비고",
        "사용자명",
        "제품이미지",
    ]

    _editable_fields = [
        "management_no",
        "asset_group",
        "location",
        "device_type",
        "manufacturer",
        "model_name",
        "serial_no",
        "cpu",
        "ram",
        "introduced_date",
        "status",
        "notes",
        "user_name",
        "image_url",
    ]

    _field_aliases = {
        "관리번호": "management_no",
        "management_no": "management_no",
        "분류": "asset_group",
        "asset_group": "asset_group",
        "카테고리": "asset_group",
        "설치장소": "location",
        "location": "location",
        "형태": "device_type",
        "device_type": "device_type",
        "제조회사": "manufacturer",
        "manufacturer": "manufacturer",
        "모델명": "model_name",
        "model_name": "model_name",
        "시리얼넘버": "serial_no",
        "시리얼번호": "serial_no",
        "serial_no": "serial_no",
        "CPU": "cpu",
        "cpu": "cpu",
        "RAM": "ram",
        "ram": "ram",
        "구입시기": "introduced_date",
        "도입일자": "introduced_date",
        "introduced_date": "introduced_date",
        "상태": "status",
        "status": "status",
        "비고": "notes",
        "notes": "notes",
        "사용자명": "user_name",
        "사용자": "user_name",
        "user_name": "user_name",
        "제품이미지": "image_url",
        "이미지 URL": "image_url",
        "image_url": "image_url",
        "사용연수": "usage_years",
    }

    def __init__(self, inventory_path: Path, events_path: Path) -> None:
        self.inventory_path = inventory_path
        self.events_path = events_path
        self._lock = threading.Lock()
        self._ensure_files()

    def list_devices(self, filters: dict | None = None) -> list[dict]:
        filters = filters or {}
        with self._lock:
            devices = self._read_records(self.inventory_path, key="devices")

        serialized = [self._serialize_device(item) for item in self._sorted_devices(devices)]
        return [item for item in serialized if self._matches_filters(item, filters)]

    def get_device(self, identifier: str) -> dict:
        with self._lock:
            devices = self._read_records(self.inventory_path, key="devices")
        record = self._find_device(devices, identifier)
        if record is None:
            raise KeyError(identifier)
        return self._serialize_device(record)

    def upsert_device(self, payload: dict, event_type: str = "create") -> tuple[dict, bool]:
        normalized = self._build_device_record(payload)
        with self._lock:
            devices = self._read_records(self.inventory_path, key="devices")
            existing_index = self._find_device_index(devices, normalized["management_no"])
            now = utc_now_iso()

            if existing_index is None:
                devices.append(normalized)
                self._write_records(self.inventory_path, key="devices", records=devices)
                self._append_event(
                    device_id=normalized["id"],
                    management_no=normalized["management_no"],
                    event_type=event_type,
                    event_summary=f'{normalized["management_no"]} 등록',
                )
                return self._serialize_device(normalized), True

            existing = devices[existing_index]
            updated = self._merge_device_record(existing, normalized, keep_identity=True)
            updated["created_at"] = existing.get("created_at", now)
            updated["updated_at"] = now
            devices[existing_index] = updated
            self._write_records(self.inventory_path, key="devices", records=devices)
            self._append_event(
                device_id=updated["id"],
                management_no=updated["management_no"],
                event_type="import" if event_type == "import" else "update",
                event_summary=f'{updated["management_no"]} 갱신',
            )
            return self._serialize_device(updated), False

    def update_device(self, identifier: str, payload: dict) -> dict:
        with self._lock:
            devices = self._read_records(self.inventory_path, key="devices")
            index = self._find_device_index(devices, identifier)
            if index is None:
                raise KeyError(identifier)

            existing = devices[index]
            updated = self._merge_device_record(existing, payload, keep_identity=False)
            updated["id"] = existing["id"]
            updated["created_at"] = existing.get("created_at", utc_now_iso())
            updated["updated_at"] = utc_now_iso()
            devices[index] = updated
            self._write_records(self.inventory_path, key="devices", records=devices)
            self._append_event(
                device_id=updated["id"],
                management_no=updated["management_no"],
                event_type="update",
                event_summary=f'{updated["management_no"]} 수정',
            )
            return self._serialize_device(updated)

    def delete_device(self, identifier: str) -> dict:
        with self._lock:
            devices = self._read_records(self.inventory_path, key="devices")
            index = self._find_device_index(devices, identifier)
            if index is None:
                raise KeyError(identifier)

            deleted = devices.pop(index)
            self._write_records(self.inventory_path, key="devices", records=devices)
            self._append_event(
                device_id=deleted["id"],
                management_no=deleted["management_no"],
                event_type="delete",
                event_summary=f'{deleted["management_no"]} 삭제',
            )
            return self._serialize_device(deleted)

    def import_csv(self, csv_text: str) -> dict:
        text = self._normalize_text(csv_text).lstrip("\ufeff")
        if not text:
            raise ValueError("CSV 내용이 비어 있습니다.")

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("CSV 헤더를 읽을 수 없습니다.")

        created_count = 0
        updated_count = 0
        processed_items: list[dict] = []

        for row in reader:
            if not row:
                continue
            payload = self._payload_from_csv_row(row)
            if not any(payload.values()):
                continue
            device, created = self.upsert_device(payload, event_type="import")
            processed_items.append(device)
            if created:
                created_count += 1
            else:
                updated_count += 1

        return {
            "row_count": len(processed_items),
            "created": created_count,
            "updated": updated_count,
            "upserted": len(processed_items),
            "items": processed_items,
        }

    def export_csv(self) -> str:
        devices = self.list_devices()
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=self.csv_headers)
        writer.writeheader()
        for device in devices:
            writer.writerow(self._device_to_csv_row(device))
        return "\ufeff" + buffer.getvalue()

    def export_report_workbook(self) -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "기기관리대장"

        headers = self.csv_headers
        sheet.append(headers)

        header_fill = PatternFill(fill_type="solid", fgColor="DCE8F5")
        thin_border = Border(
            left=Side(style="thin", color="D6DEE8"),
            right=Side(style="thin", color="D6DEE8"),
            top=Side(style="thin", color="D6DEE8"),
            bottom=Side(style="thin", color="D6DEE8"),
        )

        for column_index, title in enumerate(headers, start=1):
            cell = sheet.cell(row=1, column=column_index)
            cell.font = Font(bold=True, color="15202B")
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border
            sheet.column_dimensions[get_column_letter(column_index)].width = max(14, len(str(title)) + 4)

        for device in self.list_devices():
            row = [self._device_to_csv_row(device).get(header, "") for header in headers]
            sheet.append(row)

        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                cell.border = thin_border

        sheet.auto_filter.ref = f"A1:{get_column_letter(sheet.max_column)}{sheet.max_row}"
        sheet.freeze_panes = "A2"

        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    def list_events(self, limit: int = 50, event_type: str | None = None) -> list[dict]:
        safe_limit = max(1, min(limit, 100))
        with self._lock:
            events = self._read_records(self.events_path, key="events")

        if event_type:
            events = [item for item in events if item.get("event_type") == event_type]
        return events[:safe_limit]

    def summarize_devices(self, filters: dict | None = None) -> dict:
        devices = self.list_devices(filters)
        return {
            "total": len(devices),
            "normal_use": sum(1 for item in devices if item.get("status") == "정상 사용"),
            "life_cycle_due": sum(1 for item in devices if item.get("life_cycle_due")),
            "repair_or_inspection_needed": sum(1 for item in devices if item.get("repair_or_inspection_needed")),
        }

    def _build_device_record(self, payload: dict) -> dict:
        management_no = self._normalize_text(payload.get("management_no"))
        if not management_no:
            raise ValueError("관리번호는 필수입니다.")

        now = utc_now_iso()
        return {
            "id": uuid.uuid4().hex,
            "management_no": management_no,
            "asset_group": self._normalize_text(payload.get("asset_group")),
            "location": self._normalize_text(payload.get("location")),
            "device_type": self._normalize_text(payload.get("device_type")),
            "manufacturer": self._normalize_text(payload.get("manufacturer")),
            "model_name": self._normalize_text(payload.get("model_name")),
            "serial_no": self._normalize_text(payload.get("serial_no")),
            "cpu": self._normalize_text(payload.get("cpu")),
            "ram": self._normalize_text(payload.get("ram")),
            "introduced_date": self._normalize_date(payload.get("introduced_date")),
            "status": self._normalize_text(payload.get("status")) or "정상 사용",
            "notes": self._normalize_text(payload.get("notes")),
            "user_name": self._normalize_text(payload.get("user_name")),
            "image_url": self._normalize_text(payload.get("image_url")),
            "created_at": now,
            "updated_at": now,
        }

    def _merge_device_record(self, existing: dict, payload: dict, *, keep_identity: bool) -> dict:
        merged = dict(existing)
        source = payload if keep_identity else payload

        for field in self._editable_fields:
            if field not in source:
                continue
            value = source.get(field)
            if field == "introduced_date":
                merged[field] = self._normalize_date(value)
            else:
                merged[field] = self._normalize_text(value)

        if "management_no" in source:
            management_no = self._normalize_text(source.get("management_no"))
            if not management_no:
                raise ValueError("관리번호는 필수입니다.")
            merged["management_no"] = management_no

        if "status" in source and not merged.get("status"):
            merged["status"] = "정상 사용"

        return merged

    def _serialize_device(self, device: dict) -> dict:
        introduced_date = device.get("introduced_date", "")
        usage_years = self._calculate_usage_years(introduced_date)
        status = device.get("status", "")
        return {
            "id": device["id"],
            "management_no": device.get("management_no", ""),
            "asset_group": device.get("asset_group", ""),
            "location": device.get("location", ""),
            "device_type": device.get("device_type", ""),
            "manufacturer": device.get("manufacturer", ""),
            "model_name": device.get("model_name", ""),
            "serial_no": device.get("serial_no", ""),
            "cpu": device.get("cpu", ""),
            "ram": device.get("ram", ""),
            "introduced_date": introduced_date,
            "status": status,
            "notes": device.get("notes", ""),
            "user_name": device.get("user_name", ""),
            "image_url": device.get("image_url", ""),
            "created_at": device.get("created_at", ""),
            "updated_at": device.get("updated_at", ""),
            "usage_years": usage_years,
            "life_cycle_due": usage_years is not None and usage_years >= EXPECTED_LIFE_CYCLE_YEARS,
            "repair_or_inspection_needed": status in {"수리중", "점검 필요", "점검중"},
        }

    def _device_to_csv_row(self, device: dict) -> dict:
        return {
            "관리번호": device.get("management_no", ""),
            "분류": device.get("asset_group", ""),
            "설치장소": device.get("location", ""),
            "형태": device.get("device_type", ""),
            "제조회사": device.get("manufacturer", ""),
            "모델명": device.get("model_name", ""),
            "시리얼넘버": device.get("serial_no", ""),
            "CPU": device.get("cpu", ""),
            "RAM": device.get("ram", ""),
            "구입시기": device.get("introduced_date", ""),
            "사용연수": self._serialize_device(device).get("usage_years", ""),
            "상태": device.get("status", ""),
            "비고": device.get("notes", ""),
            "사용자명": device.get("user_name", ""),
            "제품이미지": device.get("image_url", ""),
        }

    def _payload_from_csv_row(self, row: dict) -> dict:
        payload: dict[str, str] = {}
        for raw_key, raw_value in row.items():
            if raw_key is None:
                continue
            key = self._field_aliases.get(self._normalize_text(raw_key))
            if not key or key == "usage_years":
                continue
            payload[key] = self._normalize_text(raw_value)
        return payload

    def _append_event(self, device_id: str, management_no: str, event_type: str, event_summary: str) -> None:
        events = self._read_records(self.events_path, key="events")
        event = {
            "event_id": uuid.uuid4().hex,
            "device_id": device_id,
            "management_no": management_no,
            "event_type": event_type,
            "event_summary": event_summary,
            "event_at": utc_now_iso(),
        }
        events.insert(0, event)
        self._write_records(self.events_path, key="events", records=events)

    def _matches_filters(self, device: dict, filters: dict) -> bool:
        query = self._normalize_text(filters.get("q") or filters.get("query"))
        if query:
            haystack = " ".join(
                [
                    device.get("management_no", ""),
                    device.get("asset_group", ""),
                    device.get("location", ""),
                    device.get("device_type", ""),
                    device.get("manufacturer", ""),
                    device.get("model_name", ""),
                    device.get("serial_no", ""),
                    device.get("cpu", ""),
                    device.get("ram", ""),
                    device.get("status", ""),
                    device.get("notes", ""),
                    device.get("user_name", ""),
                ]
            ).casefold()
            if query.casefold() not in haystack:
                return False

        for key, field in [
            ("management_no", "management_no"),
            ("asset_group", "asset_group"),
            ("device_type", "device_type"),
            ("status", "status"),
        ]:
            filter_value = self._normalize_text(filters.get(key))
            if filter_value and device.get(field) != filter_value:
                return False

        if "life_cycle_due" in filters:
            expected = self._as_bool(filters.get("life_cycle_due"))
            if expected is not None and device.get("life_cycle_due") is not expected:
                return False

        if "repair_or_inspection_needed" in filters:
            expected = self._as_bool(filters.get("repair_or_inspection_needed"))
            if expected is not None and device.get("repair_or_inspection_needed") is not expected:
                return False

        return True

    def _find_device(self, devices: list[dict], identifier: str) -> dict | None:
        index = self._find_device_index(devices, identifier)
        if index is None:
            return None
        return devices[index]

    def _find_device_index(self, devices: list[dict], identifier: str) -> int | None:
        search_value = self._normalize_text(identifier)
        for index, device in enumerate(devices):
            if device.get("id") == search_value or device.get("management_no") == search_value:
                return index
        return None

    def _sorted_devices(self, devices: list[dict]) -> list[dict]:
        return sorted(
            devices,
            key=lambda item: (
                item.get("management_no", "").casefold(),
                item.get("asset_group", "").casefold(),
                item.get("created_at", ""),
            ),
        )

    def _calculate_usage_years(self, introduced_date: str) -> int | None:
        if not introduced_date:
            return None
        try:
            start = date.fromisoformat(introduced_date)
        except ValueError:
            return None

        current = _today()
        years = current.year - start.year
        if (current.month, current.day) < (start.month, start.day):
            years -= 1
        return max(years, 0)

    def _normalize_date(self, value: object) -> str:
        raw = self._normalize_text(value)
        if not raw:
            return ""

        raw = raw.split("T", 1)[0].strip()
        for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
            try:
                return datetime.strptime(raw, pattern).date().isoformat()
            except ValueError:
                continue
        try:
            return date.fromisoformat(raw).isoformat()
        except ValueError as exc:
            raise ValueError(f"날짜 형식이 올바르지 않습니다: {raw}") from exc

    def _normalize_text(self, value: object) -> str:
        return str(value or "").strip()

    def _as_bool(self, value: object) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        text = self._normalize_text(value).casefold()
        if not text:
            return None
        if text in {"1", "true", "yes", "y", "on", "예", "참"}:
            return True
        if text in {"0", "false", "no", "n", "off", "아니오", "거짓"}:
            return False
        return None

    def _ensure_files(self) -> None:
        self.inventory_path.parent.mkdir(parents=True, exist_ok=True)
        self.events_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.inventory_path.exists():
            self._write_records(self.inventory_path, key="devices", records=[])
        if not self.events_path.exists():
            self._write_records(self.events_path, key="events", records=[])

    def _read_records(self, path: Path, key: str) -> list[dict]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get(key, [])
        if not isinstance(records, list):
            raise ValueError(f"{path.name} 파일 구조가 올바르지 않습니다.")
        return records

    def _write_records(self, path: Path, key: str, records: list[dict]) -> None:
        payload = {key: records}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
