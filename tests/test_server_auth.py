from __future__ import annotations

import http.cookiejar
import importlib
import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import server as server_module


class AuthServerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._original_login_id = os.environ.get("DCMS_LOGIN_ID")
        cls._original_login_password = os.environ.get("DCMS_LOGIN_PASSWORD")
        os.environ["DCMS_LOGIN_ID"] = "dcms"
        os.environ["DCMS_LOGIN_PASSWORD"] = "dcms04935!"

        cls.server_module = importlib.reload(server_module)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), cls.server_module.AppHandler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)

        if cls._original_login_id is None:
            os.environ.pop("DCMS_LOGIN_ID", None)
        else:
            os.environ["DCMS_LOGIN_ID"] = cls._original_login_id

        if cls._original_login_password is None:
            os.environ.pop("DCMS_LOGIN_PASSWORD", None)
        else:
            os.environ["DCMS_LOGIN_PASSWORD"] = cls._original_login_password

    def build_client(self) -> tuple[urllib.request.OpenerDirector, http.cookiejar.CookieJar]:
        cookie_jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
        return opener, cookie_jar

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
                return response.status, response.headers, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, exc.headers, json.loads(exc.read().decode("utf-8"))

    def test_protected_api_requires_login(self) -> None:
        opener, _ = self.build_client()

        status, _, payload = self.request_json(opener, "/api/self")

        self.assertEqual(status, 401)
        self.assertEqual(payload["error"], "로그인이 필요합니다.")

    def test_login_rejects_wrong_credentials(self) -> None:
        opener, _ = self.build_client()

        status, _, payload = self.request_json(
            opener,
            "/api/login",
            method="POST",
            payload={"username": "dcms", "password": "wrong-password"},
        )

        self.assertEqual(status, 401)
        self.assertEqual(payload["error"], "아이디 또는 비밀번호가 올바르지 않습니다.")

    def test_login_creates_session_and_allows_protected_api(self) -> None:
        opener, _ = self.build_client()

        status, headers, payload = self.request_json(
            opener,
            "/api/login",
            method="POST",
            payload={"username": "dcms", "password": "dcms04935!"},
        )

        self.assertEqual(status, 200)
        self.assertTrue(payload["authenticated"])
        self.assertEqual(payload["username"], "dcms")
        self.assertIn("dcms_session=", headers.get("Set-Cookie", ""))

        session_status, _, session_payload = self.request_json(opener, "/api/session")
        self.assertEqual(session_status, 200)
        self.assertTrue(session_payload["authenticated"])
        self.assertEqual(session_payload["username"], "dcms")

        protected_status, _, protected_payload = self.request_json(opener, "/api/self")
        self.assertEqual(protected_status, 200)
        self.assertIn("hostname", protected_payload)

    def test_logout_clears_session(self) -> None:
        opener, _ = self.build_client()

        login_status, _, _ = self.request_json(
            opener,
            "/api/login",
            method="POST",
            payload={"username": "dcms", "password": "dcms04935!"},
        )
        self.assertEqual(login_status, 200)

        logout_status, headers, payload = self.request_json(opener, "/api/logout", method="POST", payload={})
        self.assertEqual(logout_status, 200)
        self.assertEqual(payload["authenticated"], False)
        self.assertIn("Max-Age=0", headers.get("Set-Cookie", ""))

        protected_status, _, protected_payload = self.request_json(opener, "/api/self")
        self.assertEqual(protected_status, 401)
        self.assertEqual(protected_payload["error"], "로그인이 필요합니다.")


if __name__ == "__main__":
    unittest.main()
