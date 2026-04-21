# Device Inventory XLSX Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기기관리대장 XLSX 다운로드를 `대시보드 / 전체대장 / 설치장소별 탭` 구조의 보고서형 워크북으로 바꾼다.

**Architecture:** `device_inventory.py` 안에서 `export_report_workbook()`를 단순 표 시트 생성 함수에서 워크북 조립 함수로 확장한다. 집계, 시트명 정규화, 대시보드 시트 작성, 공통 표 스타일 적용을 같은 저장소 클래스 내부의 작은 헬퍼 메서드로 분리하고, 검증은 `unittest + openpyxl.load_workbook()`으로 실제 워크북 결과물을 확인한다.

**Tech Stack:** Python 3, `openpyxl`, `unittest`, 기존 `ThreadingHTTPServer` 기반 서버

---

## File Structure

- Modify: `device_inventory.py`
  - 워크북 생성 진입점 `export_report_workbook()`를 확장한다.
  - 설치장소 그룹화, 시트명 정규화, 공통 스타일, 대시보드 작성 헬퍼를 추가한다.
- Modify: `server.py`
  - API 경로는 그대로 유지한다.
  - 필요하면 파일명만 사람이 읽기 쉬운 한글로 다시 확인한다.
- Create: `tests/test_device_inventory_report.py`
  - 워크북 구조, 시트명, 집계값, 장소별 탭 생성을 검증한다.

## Task 1: 워크북 구조 테스트 먼저 고정

**Files:**
- Create: `tests/test_device_inventory_report.py`
- Modify: `device_inventory.py:236-282`

- [ ] **Step 1: 실패하는 워크북 구조 테스트 작성**

```python
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from device_inventory import DeviceInventoryRepository


def write_json(path: Path, key: str, records: list[dict]) -> None:
    path.write_text(json.dumps({key: records}, ensure_ascii=False, indent=2), encoding="utf-8")


class DeviceInventoryReportWorkbookTestCase(unittest.TestCase):
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
                    "management_no": "A-001",
                    "asset_group": "노트북",
                    "location": "컴퓨터실",
                    "device_type": "노트북",
                    "manufacturer": "삼성",
                    "model_name": "Galaxy Book",
                    "serial_no": "SN-001",
                    "cpu": "i5",
                    "ram": "16GB",
                    "introduced_date": "2020-03-01",
                    "status": "정상 사용",
                    "notes": "",
                    "user_name": "홍길동",
                    "image_url": "",
                    "created_at": "2026-04-20T00:00:00+00:00",
                    "updated_at": "2026-04-20T00:00:00+00:00",
                },
                {
                    "id": "dev-2",
                    "management_no": "A-002",
                    "asset_group": "데스크톱",
                    "location": "교무실",
                    "device_type": "데스크톱",
                    "manufacturer": "LG",
                    "model_name": "Desk Pro",
                    "serial_no": "SN-002",
                    "cpu": "i7",
                    "ram": "32GB",
                    "introduced_date": "2018-02-01",
                    "status": "점검 필요",
                    "notes": "팬 소음",
                    "user_name": "이순신",
                    "image_url": "",
                    "created_at": "2026-04-20T00:00:00+00:00",
                    "updated_at": "2026-04-20T00:00:00+00:00",
                },
                {
                    "id": "dev-3",
                    "management_no": "A-003",
                    "asset_group": "모니터",
                    "location": "",
                    "device_type": "모니터",
                    "manufacturer": "Dell",
                    "model_name": "UltraSharp",
                    "serial_no": "SN-003",
                    "cpu": "",
                    "ram": "",
                    "introduced_date": "2017-05-01",
                    "status": "정상 사용",
                    "notes": "",
                    "user_name": "",
                    "image_url": "",
                    "created_at": "2026-04-20T00:00:00+00:00",
                    "updated_at": "2026-04-20T00:00:00+00:00",
                },
            ],
        )
        write_json(self.events_path, "events", [])
        self.repository = DeviceInventoryRepository(self.inventory_path, self.events_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def load_report(self):
        payload = self.repository.export_report_workbook()
        return load_workbook(io.BytesIO(payload))

    def test_report_contains_dashboard_total_sheet_and_location_tabs(self) -> None:
        workbook = self.load_report()

        self.assertEqual(workbook.sheetnames[0], "대시보드")
        self.assertEqual(workbook.sheetnames[1], "전체대장")
        self.assertIn("컴퓨터실", workbook.sheetnames)
        self.assertIn("교무실", workbook.sheetnames)
        self.assertIn("미지정", workbook.sheetnames)

    def test_dashboard_contains_title_and_location_summary(self) -> None:
        dashboard = self.load_report()["대시보드"]

        self.assertEqual(dashboard["A1"].value, "DCMS 기기관리대장")
        self.assertEqual(dashboard["A2"].value, "설치장소별 자산 분포 요약")
        self.assertEqual(dashboard["B5"].value, 3)
        self.assertEqual(dashboard["E10"].value, "컴퓨터실")
        self.assertEqual(dashboard["F10"].value, 1)

    def test_location_sheet_contains_only_matching_rows(self) -> None:
        sheet = self.load_report()["교무실"]

        self.assertEqual(sheet["A1"].value, "교무실")
        self.assertEqual(sheet["A4"].value, "관리번호")
        self.assertEqual(sheet["A5"].value, "A-002")
        self.assertEqual(sheet.max_row, 5)
```

- [ ] **Step 2: 테스트를 실행해 현재 동작이 실패하는지 확인**

Run: `python -m unittest tests.test_device_inventory_report -v`  
Expected: `FAIL` with missing sheet names such as `대시보드` or `미지정`.

- [ ] **Step 3: 최소 변경으로 시트 순서와 장소 그룹화 헬퍼 추가**

`device_inventory.py`에 아래 헬퍼를 추가한다.

```python
    def _group_devices_by_location(self, devices: list[dict]) -> list[tuple[str, list[dict]]]:
        grouped: dict[str, list[dict]] = {}
        for device in devices:
            location = self._normalize_sheet_title(device.get("location", ""))
            grouped.setdefault(location, []).append(device)
        return sorted(grouped.items(), key=lambda item: item[0].casefold())

    def _normalize_sheet_title(self, raw_value: object, existing_titles: set[str] | None = None) -> str:
        base = self._normalize_text(raw_value) or "미지정"
        invalid_chars = set(r'[]:*?/\\')
        cleaned = "".join(char for char in base if char not in invalid_chars).strip() or "미지정"
        cleaned = cleaned[:31].rstrip() or "미지정"
        existing_titles = existing_titles or set()
        if cleaned not in existing_titles:
            return cleaned

        counter = 2
        while True:
            suffix = f" ({counter})"
            trimmed = cleaned[: 31 - len(suffix)].rstrip()
            candidate = f"{trimmed}{suffix}"
            if candidate not in existing_titles:
                return candidate
            counter += 1
```

- [ ] **Step 4: `export_report_workbook()`를 다중 시트 워크북 진입점으로 바꾸기**

`device_inventory.py`의 `export_report_workbook()`를 아래 형태로 바꾼다.

```python
    def export_report_workbook(self) -> bytes:
        workbook = Workbook()
        devices = self.list_devices()
        workbook.active.title = "대시보드"

        self._write_dashboard_sheet(workbook["대시보드"], devices)
        self._write_full_inventory_sheet(workbook.create_sheet("전체대장"), devices)

        used_titles = {"대시보드", "전체대장"}
        for location_title, location_devices in self._group_devices_by_location(devices):
            safe_title = self._normalize_sheet_title(location_title, used_titles)
            used_titles.add(safe_title)
            self._write_location_inventory_sheet(workbook.create_sheet(safe_title), safe_title, location_devices)

        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()
```

- [ ] **Step 5: 테스트를 다시 실행해 시트 구조가 통과하는지 확인**

Run: `python -m unittest tests.test_device_inventory_report -v`  
Expected: `ok` for `test_report_contains_dashboard_total_sheet_and_location_tabs`, other tests may still fail.

- [ ] **Step 6: 커밋**

```powershell
git add tests/test_device_inventory_report.py device_inventory.py
git commit -m "test: add workbook structure coverage"
```

## Task 2: 대시보드 시트 내용과 집계값 구현

**Files:**
- Modify: `device_inventory.py:236-340`
- Test: `tests/test_device_inventory_report.py`

- [ ] **Step 1: 대시보드 셀 값 검증 테스트를 보강**

`tests/test_device_inventory_report.py`에 아래 테스트를 추가한다.

```python
    def test_dashboard_lists_locations_in_descending_count_order(self) -> None:
        dashboard = self.load_report()["대시보드"]

        rows = [
            (dashboard["E10"].value, dashboard["F10"].value),
            (dashboard["E11"].value, dashboard["F11"].value),
            (dashboard["E12"].value, dashboard["F12"].value),
        ]
        self.assertEqual(rows, [("교무실", 1), ("미지정", 1), ("컴퓨터실", 1)])

    def test_dashboard_status_summary_uses_serialized_flags(self) -> None:
        dashboard = self.load_report()["대시보드"]

        self.assertEqual(dashboard["B5"].value, 3)
        self.assertEqual(dashboard["B8"].value, 2)
        self.assertEqual(dashboard["D8"].value, 1)
```

- [ ] **Step 2: 실패를 확인**

Run: `python -m unittest tests.test_device_inventory_report -v`  
Expected: `FAIL` because dashboard cells are empty or not yet written.

- [ ] **Step 3: 대시보드 집계 헬퍼 추가**

`device_inventory.py`에 아래 헬퍼를 추가한다.

```python
    def _summarize_locations(self, devices: list[dict]) -> list[tuple[str, int]]:
        counts: dict[str, int] = {}
        for device in devices:
            location = self._normalize_text(device.get("location")) or "미지정"
            counts[location] = counts.get(location, 0) + 1
        return sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold()))

    def _summarize_statuses(self, devices: list[dict]) -> dict[str, int]:
        return {
            "정상 사용": sum(1 for item in devices if item.get("status") == "정상 사용"),
            "점검 필요": sum(1 for item in devices if item.get("repair_or_inspection_needed")),
            "교체 검토": sum(1 for item in devices if item.get("life_cycle_due")),
        }
```

- [ ] **Step 4: 대시보드 시트 작성 함수 구현**

`device_inventory.py`에 아래 함수를 추가한다.

```python
    def _write_dashboard_sheet(self, sheet, devices: list[dict]) -> None:
        location_rows = self._summarize_locations(devices)
        status_summary = self._summarize_statuses(devices)

        sheet["A1"] = "DCMS 기기관리대장"
        sheet["A2"] = "설치장소별 자산 분포 요약"
        sheet["A5"] = "전체 장비 수"
        sheet["B5"] = len(devices)
        sheet["C5"] = "설치장소 수"
        sheet["D5"] = len(location_rows)
        sheet["A8"] = "정상 사용"
        sheet["B8"] = status_summary["정상 사용"]
        sheet["C8"] = "점검 필요"
        sheet["D8"] = status_summary["점검 필요"]
        sheet["E8"] = "교체 검토"
        sheet["F8"] = status_summary["교체 검토"]
        sheet["E9"] = "설치장소"
        sheet["F9"] = "수량"

        for row_index, (location, count) in enumerate(location_rows, start=10):
            sheet.cell(row=row_index, column=5, value=location)
            sheet.cell(row=row_index, column=6, value=count)
```

- [ ] **Step 5: 대시보드 차트 추가**

`device_inventory.py`에 `BarChart`, `Reference` import를 추가하고 `_write_dashboard_sheet()` 하단에 아래 코드를 넣는다.

```python
        if location_rows:
            chart = BarChart()
            chart.type = "bar"
            chart.style = 10
            chart.title = "설치장소별 장비 수"
            chart.y_axis.title = "설치장소"
            chart.x_axis.title = "수량"
            data = Reference(sheet, min_col=6, min_row=9, max_row=9 + len(location_rows))
            labels = Reference(sheet, min_col=5, min_row=10, max_row=9 + len(location_rows))
            chart.add_data(data, titles_from_data=True)
            chart.set_categories(labels)
            chart.height = 7
            chart.width = 11
            sheet.add_chart(chart, "H9")
```

- [ ] **Step 6: 테스트를 다시 실행**

Run: `python -m unittest tests.test_device_inventory_report -v`  
Expected: dashboard 관련 테스트가 모두 `ok`.

- [ ] **Step 7: 커밋**

```powershell
git add device_inventory.py tests/test_device_inventory_report.py
git commit -m "feat: add xlsx dashboard summary sheet"
```

## Task 3: 전체대장과 장소별 시트의 표 스타일 정리

**Files:**
- Modify: `device_inventory.py:236-282`
- Test: `tests/test_device_inventory_report.py`

- [ ] **Step 1: 표 스타일 검증 테스트 추가**

`tests/test_device_inventory_report.py`에 아래 테스트를 추가한다.

```python
    def test_full_inventory_sheet_has_filter_freeze_and_header_style(self) -> None:
        sheet = self.load_report()["전체대장"]

        self.assertEqual(sheet.freeze_panes, "A2")
        self.assertEqual(sheet.auto_filter.ref, f"A1:O{sheet.max_row}")
        self.assertTrue(sheet["A1"].font.bold)
        self.assertEqual(sheet["A1"].fill.fgColor.rgb[-6:], "DCE8F5")

    def test_location_sheet_has_local_heading_and_filtered_table(self) -> None:
        sheet = self.load_report()["컴퓨터실"]

        self.assertEqual(sheet["A1"].value, "컴퓨터실")
        self.assertEqual(sheet["A2"].value, "장비 수")
        self.assertEqual(sheet["B2"].value, 1)
        self.assertEqual(sheet.freeze_panes, "A5")
        self.assertEqual(sheet["A4"].value, "관리번호")
```

- [ ] **Step 2: 실패를 확인**

Run: `python -m unittest tests.test_device_inventory_report -v`  
Expected: `FAIL` because current writer does not set location-sheet headers or freeze rows consistently.

- [ ] **Step 3: 공통 표 쓰기 헬퍼 추가**

`device_inventory.py`에 아래 두 함수를 추가한다.

```python
    def _write_inventory_table(self, sheet, devices: list[dict], *, start_row: int = 1) -> None:
        headers = self.csv_headers
        for column_index, title in enumerate(headers, start=1):
            sheet.cell(row=start_row, column=column_index, value=title)

        for row_offset, device in enumerate(devices, start=1):
            row = [self._device_to_csv_row(device).get(header, "") for header in headers]
            for column_index, value in enumerate(row, start=1):
                sheet.cell(row=start_row + row_offset, column=column_index, value=value)

        self._apply_inventory_table_style(sheet, start_row=start_row, end_row=start_row + len(devices))

    def _apply_inventory_table_style(self, sheet, *, start_row: int, end_row: int) -> None:
        header_fill = PatternFill(fill_type="solid", fgColor="DCE8F5")
        zebra_fill = PatternFill(fill_type="solid", fgColor="F7FAFC")
        thin_border = Border(
            left=Side(style="thin", color="D6DEE8"),
            right=Side(style="thin", color="D6DEE8"),
            top=Side(style="thin", color="D6DEE8"),
            bottom=Side(style="thin", color="D6DEE8"),
        )

        for column_index in range(1, len(self.csv_headers) + 1):
            cell = sheet.cell(row=start_row, column=column_index)
            cell.font = Font(bold=True, color="15202B")
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border

        for row_index in range(start_row + 1, end_row + 1):
            for column_index in range(1, len(self.csv_headers) + 1):
                cell = sheet.cell(row=row_index, column=column_index)
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                cell.border = thin_border
                if (row_index - start_row) % 2 == 0:
                    cell.fill = zebra_fill

        sheet.auto_filter.ref = f"A{start_row}:{get_column_letter(len(self.csv_headers))}{end_row}"
```

- [ ] **Step 4: 전체대장과 장소별 시트 작성 함수 구현**

`device_inventory.py`에 아래 함수를 추가하고 `export_report_workbook()`에서 호출한다.

```python
    def _write_full_inventory_sheet(self, sheet, devices: list[dict]) -> None:
        self._write_inventory_table(sheet, devices, start_row=1)
        sheet.freeze_panes = "A2"
        self._apply_inventory_column_widths(sheet)

    def _write_location_inventory_sheet(self, sheet, title: str, devices: list[dict]) -> None:
        sheet["A1"] = title
        sheet["A2"] = "장비 수"
        sheet["B2"] = len(devices)
        sheet["D2"] = "생성일"
        sheet["E2"] = _today().isoformat()
        self._write_inventory_table(sheet, devices, start_row=4)
        sheet.freeze_panes = "A5"
        self._apply_inventory_column_widths(sheet)
```

- [ ] **Step 5: 열 너비 조정 함수 추가**

```python
    def _apply_inventory_column_widths(self, sheet) -> None:
        widths = {
            "A": 14,
            "B": 12,
            "C": 18,
            "D": 12,
            "E": 14,
            "F": 22,
            "G": 18,
            "H": 12,
            "I": 10,
            "J": 12,
            "K": 10,
            "L": 12,
            "M": 28,
            "N": 14,
            "O": 18,
        }
        for column_letter, width in widths.items():
            sheet.column_dimensions[column_letter].width = width
```

- [ ] **Step 6: 테스트를 다시 실행**

Run: `python -m unittest tests.test_device_inventory_report -v`  
Expected: `ok` for 전체대장/장소별 시트 스타일 검증.

- [ ] **Step 7: 커밋**

```powershell
git add device_inventory.py tests/test_device_inventory_report.py
git commit -m "feat: style xlsx inventory worksheets"
```

## Task 4: 서버 응답과 최종 검증 정리

**Files:**
- Modify: `server.py:127-132`
- Test: `tests/test_device_inventory_report.py`

- [ ] **Step 1: 서버 파일명 가독성 확인 테스트 또는 스모크 시나리오 추가**

워크북 단위 테스트는 저장소에서 처리하고, 서버 경로는 스모크로 확인한다. `server.py`의 파일명이 깨져 보인다면 아래 코드로 정리한다.

```python
        if path == "/api/device-inventory/report-xlsx":
            report_bytes = DEVICE_INVENTORY_REPOSITORY.export_report_workbook()
            self._send_file(
                report_bytes,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                file_name="기기관리대장_보고서.xlsx",
            )
            return
```

- [ ] **Step 2: 전체 테스트 실행**

Run: `python -m unittest discover -s tests -p "test_*.py"`  
Expected: all tests pass, including the new workbook test module.

- [ ] **Step 3: 파이썬 문법 검사 실행**

Run: `python -m py_compile server.py site_accounts.py device_inventory.py scanner.py`  
Expected: no output.

- [ ] **Step 4: 실제 XLSX 다운로드 스모크 테스트**

Run:

```powershell
@'
import urllib.request
response = urllib.request.urlopen("http://127.0.0.1:8765/api/device-inventory/report-xlsx", timeout=5)
print(response.status)
print(response.headers.get("Content-Disposition"))
print(response.read(4))
'@ | python -X utf8 -
```

Expected:

- `200`
- `attachment; filename*=UTF-8''...xlsx`
- first bytes start with `b'PK\x03\x04'`

- [ ] **Step 5: 커밋**

```powershell
git add server.py tests/test_device_inventory_report.py device_inventory.py
git commit -m "feat: deliver dashboard-style xlsx report"
```

## Self-Review

### Spec coverage

- `대시보드 / 전체대장 / 설치장소별 탭`: Task 1, Task 3
- `설치장소별 분포 중심`: Task 2
- `보고서형 대시보드 + 차트`: Task 2
- `전체대장 스타일 개선`: Task 3
- `설치장소별 자동 탭 생성`: Task 1, Task 3
- `시트명 정규화`: Task 1
- `검증 기준`: Task 4

### Placeholder scan

- `TODO`, `TBD`, `적절히` 같은 문구를 넣지 않았다.
- 각 단계에 실제 코드, 실제 파일 경로, 실제 명령을 넣었다.

### Type consistency

- 시트명 정규화 함수 이름은 `_normalize_sheet_title`
- 장소 집계 함수 이름은 `_summarize_locations`
- 상태 집계 함수 이름은 `_summarize_statuses`
- 전체대장/장소 시트 작성 함수 이름은 `_write_full_inventory_sheet`, `_write_location_inventory_sheet`

