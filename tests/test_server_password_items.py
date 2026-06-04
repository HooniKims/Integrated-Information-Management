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
from password_manager import PasswordItemRepository


class PasswordItemsApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._original_login_id = os.environ.get("DCMS_LOGIN_ID")
        cls._original_login_password = os.environ.get("DCMS_LOGIN_PASSWORD")
        os.environ["DCMS_LOGIN_ID"] = "dcms"
        os.environ["DCMS_LOGIN_PASSWORD"] = "pw"

        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.server_module = importlib.reload(server_module)
        cls.server_module.PASSWORD_ITEM_REPOSITORY = PasswordItemRepository(
            Path(cls.temp_dir.name) / "password_items.json"
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

    def request_json(self, opener: urllib.request.OpenerDirector, path: str, *, method: str = "GET", payload: dict | None = None):
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

    def test_password_items_crud_api(self) -> None:
        opener = self.build_client()

        create_status, created = self.request_json(
            opener,
            "/api/password-items",
            method="POST",
            payload={"title": "정보실 번호키", "password": "2580"},
        )
        self.assertEqual(create_status, 201)
        self.assertEqual(created["title"], "정보실 번호키")

        list_status, listed = self.request_json(opener, "/api/password-items")
        self.assertEqual(list_status, 200)
        self.assertEqual(listed["summary"]["total"], 1)
        self.assertEqual(listed["items"][0]["password"], "2580")

        update_status, updated = self.request_json(
            opener,
            f"/api/password-items/{created['id']}",
            method="PATCH",
            payload={"title": "정보실 뒷문", "password": "1357"},
        )
        self.assertEqual(update_status, 200)
        self.assertEqual(updated["password"], "1357")

        delete_status, deleted = self.request_json(opener, f"/api/password-items/{created['id']}", method="DELETE")
        self.assertEqual(delete_status, 200)
        self.assertEqual(deleted["id"], created["id"])


if __name__ == "__main__":
    unittest.main()
