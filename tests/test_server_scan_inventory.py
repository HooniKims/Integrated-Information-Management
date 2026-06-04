from __future__ import annotations

import http.cookiejar
import importlib
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import server as server_module
from scanner import ScanInventoryRepository, ScanManager


class ScanInventoryApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._original_login_id = os.environ.get("DCMS_LOGIN_ID")
        cls._original_login_password = os.environ.get("DCMS_LOGIN_PASSWORD")
        os.environ["DCMS_LOGIN_ID"] = "dcms"
        os.environ["DCMS_LOGIN_PASSWORD"] = "pw"

        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.server_module = importlib.reload(server_module)
        cls.server_module.SCAN_INVENTORY_REPOSITORY = ScanInventoryRepository(
            Path(cls.temp_dir.name) / "scan_inventory.json"
        )
        cls.server_module.SCAN_MANAGER = ScanManager(
            name_lookup=cls.server_module.SCAN_NAME_REPOSITORY.get_name,
            completion_callback=cls.server_module.SCAN_INVENTORY_REPOSITORY.merge_scan_results,
        )
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), cls.server_module.AppHandler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)
        cls.temp_dir.cleanup()

        if cls._original_login_id is None:
            os.environ.pop("DCMS_LOGIN_ID", None)
        else:
            os.environ["DCMS_LOGIN_ID"] = cls._original_login_id

        if cls._original_login_password is None:
            os.environ.pop("DCMS_LOGIN_PASSWORD", None)
        else:
            os.environ["DCMS_LOGIN_PASSWORD"] = cls._original_login_password

    def build_client(self) -> urllib.request.OpenerDirector:
        cookie_jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
        self.request_json(opener, "/api/login", method="POST", payload={"username": "dcms", "password": "pw"})
        return opener

    def request_json(
        self,
        opener: urllib.request.OpenerDirector,
        path: str,
        *,
        method: str = "GET",
        payload: dict | None = None,
    ):
        body = None
        headers: dict[str, str] = {}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with opener.open(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_scan_inventory_list_api_returns_items_and_summary(self) -> None:
        opener = self.build_client()
        self.server_module.SCAN_INVENTORY_REPOSITORY.merge_scan_results(
            [
                {
                    "ip": "10.73.78.51",
                    "reachable": True,
                    "hostname": "DESKTOP-ABC",
                    "hostname_source": "netbios",
                    "mac_address": "00-11-22-33-44-55",
                    "status": "healthy",
                    "note": "ok",
                    "reported_at": "2026-06-04T01:00:00+00:00",
                }
            ]
        )

        status, payload = self.request_json(opener, "/api/scan-inventory")

        self.assertEqual(status, 200)
        self.assertEqual(payload["summary"]["total"], 1)
        self.assertEqual(payload["items"][0]["ip"], "10.73.78.51")

    def test_scan_inventory_patch_updates_manual_fields(self) -> None:
        opener = self.build_client()

        status, updated = self.request_json(
            opener,
            "/api/scan-inventory/10.73.78.52",
            method="PATCH",
            payload={
                "assigned_user": "Science Lab",
                "custom_name": "Teacher PC",
                "manual_note": "fixed ip",
            },
        )

        self.assertEqual(status, 200)
        self.assertEqual(updated["assigned_user"], "Science Lab")
        self.assertEqual(updated["custom_name"], "Teacher PC")
        self.assertEqual(updated["manual_note"], "fixed ip")

    def test_scan_inventory_patch_rejects_invalid_ip(self) -> None:
        opener = self.build_client()

        status, payload = self.request_json(
            opener,
            "/api/scan-inventory/not-an-ip",
            method="PATCH",
            payload={"assigned_user": "Science Lab"},
        )

        self.assertEqual(status, 400)
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
