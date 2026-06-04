from __future__ import annotations

import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DeviceInventoryFormTestCase(unittest.TestCase):
    def test_purchase_month_input_accepts_dash_year_month_format(self) -> None:
        html = (PROJECT_ROOT / "web" / "index.html").read_text(encoding="utf-8")
        match = re.search(r'id="deviceAcquiredAtInput"[^>]*pattern="([^"]+)"', html)

        self.assertIsNotNone(match)
        pattern = match.group(1)
        self.assertRegex("2026-06", re.compile(f"^(?:{pattern})$"))

    def test_app_has_single_floating_top_button(self) -> None:
        html = (PROJECT_ROOT / "web" / "index.html").read_text(encoding="utf-8")
        styles = (PROJECT_ROOT / "web" / "styles.css").read_text(encoding="utf-8")
        top_button_count = html.count('data-scroll-top-button')

        self.assertEqual(top_button_count, 1)
        self.assertIn("floating-top-button", html)
        self.assertIn("position: fixed", styles)

    def test_device_table_renders_direct_edit_action(self) -> None:
        script = (PROJECT_ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("data-device-edit", script)
        self.assertIn("showDeviceEditor(\"edit\", device", script)

    def test_device_table_has_excel_style_column_filter_menus(self) -> None:
        html = (PROJECT_ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (PROJECT_ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("data-device-filter-menu", html)
        self.assertNotIn("data-device-column-filter", html)
        self.assertNotIn("device-filter-row", html)
        self.assertIn("clearDeviceColumnFiltersButton", script)
        self.assertIn("deviceColumnFilters", script)
        self.assertIn("deviceSort", script)
        self.assertIn("renderDeviceColumnFilterMenu", script)
        self.assertIn("applyDeviceColumnFilterSelection", script)

    def test_confirm_needed_status_is_available_and_styled(self) -> None:
        script = (PROJECT_ROOT / "web" / "app.js").read_text(encoding="utf-8")
        styles = (PROJECT_ROOT / "web" / "styles.css").read_text(encoding="utf-8")

        self.assertIn('"확인 필요"', script)
        self.assertIn(".status.confirm", styles)
        self.assertIn(".status.replacement", styles)
        self.assertIn(".status.retired", styles)

    def test_device_summary_cards_filter_inventory_list(self) -> None:
        html = (PROJECT_ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (PROJECT_ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn('data-device-summary-filter="all"', html)
        self.assertIn('data-device-summary-filter="normal"', html)
        self.assertIn('data-device-summary-filter="life_cycle_due"', html)
        self.assertIn('data-device-summary-filter="repair_or_inspection_needed"', html)
        self.assertIn("deviceSummaryFilter", script)
        self.assertIn("activateDeviceSummaryFilter", script)

    def test_device_form_can_upload_internal_product_image(self) -> None:
        html = (PROJECT_ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (PROJECT_ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="deviceImageUploadInput"', html)
        self.assertIn('id="deviceImageUploadButton"', html)
        self.assertIn('accept="image/png,image/jpeg,image/webp"', html)
        self.assertIn("uploadDeviceImage", script)
        self.assertIn("/api/device-inventory/images", script)

    def test_password_manager_view_is_available(self) -> None:
        html = (PROJECT_ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (PROJECT_ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn('data-view="password-manager"', html)
        self.assertIn('data-view-panel="password-manager"', html)
        self.assertIn('id="passwordItemsTableBody"', html)
        self.assertIn('id="passwordTitleInput"', html)
        self.assertIn('id="passwordValueInput"', html)
        self.assertIn("/api/password-items", script)
        self.assertIn("loadPasswordItems", script)
        self.assertIn("savePasswordItem", script)

    def test_password_manager_displays_saved_password_values(self) -> None:
        script = (PROJECT_ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn('const displayValue = value || "-"', script)
        self.assertNotIn('const displayValue = value ? "••••" : "-"', script)

    def test_settings_navigation_is_removed(self) -> None:
        html = (PROJECT_ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (PROJECT_ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertNotIn('data-view="settings"', html)
        self.assertNotIn("<span>설정</span>", html)
        self.assertNotIn("<span class=\"nav-icon\">ST</span>", html)
        self.assertNotIn('data-view-panel="coming-soon"', html)
        self.assertNotIn("coming-soon", script)

    def test_ip_scan_inventory_fields_are_available(self) -> None:
        html = (PROJECT_ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (PROJECT_ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("사용자/담당자", html)
        self.assertIn("scanAssignedUserInput", html)
        self.assertIn("scanManualNoteInput", html)
        self.assertIn("/api/scan-inventory", script)
        self.assertIn("loadScanInventory", script)
        self.assertIn("saveScanInventoryEntry", script)
        self.assertIn("loadScanInventory({ force: true })", script)


if __name__ == "__main__":
    unittest.main()
