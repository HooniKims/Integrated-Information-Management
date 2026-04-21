from __future__ import annotations

import json
import mimetypes
import os
import secrets
import threading
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from scanner import ScanManager, get_local_host_info
from device_inventory import DeviceInventoryRepository
from site_accounts import SiteAccountRepository

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DATA_DIR = ROOT / "data"


def load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    loaded: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized = value.strip().strip('"').strip("'")
        loaded[key.strip()] = normalized
    return loaded


APP_ENV = load_env_file(ROOT / ".env")


def get_setting(name: str, default: str = "") -> str:
    return os.environ.get(name, APP_ENV.get(name, default))


HOST = get_setting("APP_HOST", "0.0.0.0")
PORT = int(get_setting("APP_PORT", "8765"))
APP_AUTH_CONFIG = {
    "login_id": get_setting("DCMS_LOGIN_ID"),
    "login_password": get_setting("DCMS_LOGIN_PASSWORD"),
}
SESSION_COOKIE_NAME = "dcms_session"
PUBLIC_API_PATHS = {"/api/health", "/api/login", "/api/logout", "/api/session"}
SESSIONS: dict[str, dict[str, str]] = {}
SESSION_LOCK = threading.Lock()

SCAN_MANAGER = ScanManager()
SITE_ACCOUNT_REPOSITORY = SiteAccountRepository(DATA_DIR / "site_accounts.json", DATA_DIR / "site_account_audit.json")
DEVICE_INVENTORY_REPOSITORY = DeviceInventoryRepository(
    DATA_DIR / "device_inventory.json",
    DATA_DIR / "device_inventory_events.json",
)


class AppHandler(BaseHTTPRequestHandler):
    server_version = "IpScanWebApp/0.2"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if self._requires_auth(path) and not self._ensure_authenticated():
            return

        if path == "/api/health":
            self._send_json({"ok": True})
            return

        if path == "/api/session":
            session = self._get_authenticated_session()
            payload: dict[str, object] = {"authenticated": bool(session)}
            if session:
                payload["username"] = session["username"]
            self._send_json(payload)
            return

        if path == "/api/self":
            self._send_json(get_local_host_info())
            return

        if path == "/api/site-accounts":
            self._send_json(
                {
                    "items": SITE_ACCOUNT_REPOSITORY.list_accounts(),
                    "summary": SITE_ACCOUNT_REPOSITORY.summarize_accounts(),
                }
            )
            return

        if path == "/api/device-inventory":
            filters = {
                "q": query.get("q", [""])[0],
                "management_no": query.get("management_no", [""])[0],
                "asset_group": query.get("asset_group", [""])[0],
                "device_type": query.get("device_type", [""])[0],
                "status": query.get("status", [""])[0],
                "life_cycle_due": query.get("life_cycle_due", [""])[0],
                "repair_or_inspection_needed": query.get("repair_or_inspection_needed", [""])[0],
            }
            self._send_json(
                {
                    "items": DEVICE_INVENTORY_REPOSITORY.list_devices(filters),
                    "summary": DEVICE_INVENTORY_REPOSITORY.summarize_devices(filters),
                }
            )
            return

        if path == "/api/device-inventory/export-csv":
            self._send_json(
                {
                    "filename": "device_inventory.csv",
                    "csv_text": DEVICE_INVENTORY_REPOSITORY.export_csv(),
                }
            )
            return

        if path == "/api/device-inventory/report-xlsx":
            report_bytes = DEVICE_INVENTORY_REPOSITORY.export_report_workbook()
            self._send_file(
                report_bytes,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                file_name="기기관리대장_보고서.xlsx",
            )
            return

        if path == "/api/device-inventory/events":
            limit_value = query.get("limit", ["20"])[0]
            event_type = query.get("event_type", [""])[0].strip() or None
            try:
                limit = int(limit_value)
            except ValueError:
                limit = 20
            self._send_json({"items": DEVICE_INVENTORY_REPOSITORY.list_events(limit=limit, event_type=event_type)})
            return

        if path.startswith("/api/device-inventory/") and path.count("/") == 3:
            device_id = path.rsplit("/", 1)[-1]
            try:
                device = DEVICE_INVENTORY_REPOSITORY.get_device(device_id)
            except KeyError:
                self._send_json({"error": "장비를 찾지 못했습니다."}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json(device)
            return

        if path.startswith("/api/scan/"):
            job_id = path.rsplit("/", 1)[-1]
            job = SCAN_MANAGER.get_job(job_id)
            if not job:
                self._send_json({"error": "Scan job not found."}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json(job.snapshot())
            return

        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if self._requires_auth(path) and not self._ensure_authenticated():
            return

        if path == "/api/login":
            payload = self._read_json_body()
            if payload is None:
                self._send_json({"error": "로그인 요청 형식이 올바르지 않습니다."}, status=HTTPStatus.BAD_REQUEST)
                return

            configured_id = str(APP_AUTH_CONFIG.get("login_id", "") or "")
            configured_password = str(APP_AUTH_CONFIG.get("login_password", "") or "")
            if not configured_id or not configured_password:
                self._send_json({"error": "로그인 환경설정이 없습니다."}, status=HTTPStatus.SERVICE_UNAVAILABLE)
                return

            submitted_id = str(payload.get("username", payload.get("id", "")) or "").strip()
            submitted_password = str(payload.get("password", "") or "")

            if not (
                secrets.compare_digest(submitted_id, configured_id)
                and secrets.compare_digest(submitted_password, configured_password)
            ):
                self._send_json({"error": "아이디 또는 비밀번호가 올바르지 않습니다."}, status=HTTPStatus.UNAUTHORIZED)
                return

            token = self._create_session(submitted_id)
            self._send_json(
                {"authenticated": True, "username": submitted_id},
                extra_headers={"Set-Cookie": self._build_session_cookie(token)},
            )
            return

        if path == "/api/logout":
            self._delete_session()
            self._send_json(
                {"authenticated": False},
                extra_headers={"Set-Cookie": self._build_session_cookie("", max_age=0)},
            )
            return

        if path == "/api/site-accounts":
            payload = self._read_json_body()
            if payload is None:
                self._send_json({"error": "Invalid JSON body."}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                created = SITE_ACCOUNT_REPOSITORY.create_account(payload)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(created, status=HTTPStatus.CREATED)
            return

        if path == "/api/device-inventory":
            payload = self._read_json_body()
            if payload is None:
                self._send_json({"error": "Invalid JSON body."}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                device, created = DEVICE_INVENTORY_REPOSITORY.upsert_device(payload, event_type="create")
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(device, status=HTTPStatus.CREATED if created else HTTPStatus.OK)
            return

        if path == "/api/device-inventory/import-csv":
            payload = self._read_json_body()
            if payload is None:
                self._send_json({"error": "Invalid JSON body."}, status=HTTPStatus.BAD_REQUEST)
                return
            csv_text = str(payload.get("csv_text", "") or "")
            try:
                result = DEVICE_INVENTORY_REPOSITORY.import_csv(csv_text)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(result)
            return

        if path == "/api/scan":
            payload = self._read_json_body()
            if payload is None:
                self._send_json({"error": "Invalid JSON body."}, status=HTTPStatus.BAD_REQUEST)
                return

            start_ip = str(payload.get("start_ip", "")).strip()
            end_ip = str(payload.get("end_ip", "")).strip()
            if not start_ip or not end_ip:
                self._send_json({"error": "Both start_ip and end_ip are required."}, status=HTTPStatus.BAD_REQUEST)
                return

            try:
                job = SCAN_MANAGER.create_job(start_ip, end_ip)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return

            self._send_json(job.snapshot(), status=HTTPStatus.CREATED)
            return

        if path.startswith("/api/scan/") and path.endswith("/cancel"):
            job_id = path.split("/")[-2]
            if not SCAN_MANAGER.cancel_job(job_id):
                self._send_json({"error": "Scan job not found."}, status=HTTPStatus.NOT_FOUND)
                return
            job = SCAN_MANAGER.get_job(job_id)
            self._send_json(job.snapshot())
            return

        self._send_json({"error": "Unsupported route."}, status=HTTPStatus.NOT_FOUND)

    def do_PATCH(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if self._requires_auth(path) and not self._ensure_authenticated():
            return

        if path.startswith("/api/device-inventory/") and path.count("/") == 3:
            payload = self._read_json_body()
            if payload is None:
                self._send_json({"error": "Invalid JSON body."}, status=HTTPStatus.BAD_REQUEST)
                return
            device_id = path.rsplit("/", 1)[-1]
            try:
                updated = DEVICE_INVENTORY_REPOSITORY.update_device(device_id, payload)
            except KeyError:
                self._send_json({"error": "장비를 찾지 못했습니다."}, status=HTTPStatus.NOT_FOUND)
                return
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(updated)
            return

        if path.startswith("/api/site-accounts/") and path.count("/") == 3:
            payload = self._read_json_body()
            if payload is None:
                self._send_json({"error": "Invalid JSON body."}, status=HTTPStatus.BAD_REQUEST)
                return
            account_id = path.rsplit("/", 1)[-1]
            try:
                updated = SITE_ACCOUNT_REPOSITORY.update_account(account_id, payload)
            except KeyError:
                self._send_json({"error": "Site account not found."}, status=HTTPStatus.NOT_FOUND)
                return
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(updated)
            return

        self._send_json({"error": "Unsupported route."}, status=HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if self._requires_auth(path) and not self._ensure_authenticated():
            return

        if path.startswith("/api/device-inventory/") and path.count("/") == 3:
            device_id = path.rsplit("/", 1)[-1]
            try:
                deleted = DEVICE_INVENTORY_REPOSITORY.delete_device(device_id)
            except KeyError:
                self._send_json({"error": "장비를 찾지 못했습니다."}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json(deleted)
            return

        if path.startswith("/api/site-accounts/") and path.count("/") == 3:
            account_id = path.rsplit("/", 1)[-1]
            try:
                deleted = SITE_ACCOUNT_REPOSITORY.delete_account(account_id)
            except KeyError:
                self._send_json({"error": "Site account not found."}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json(deleted)
            return

        self._send_json({"error": "Unsupported route."}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _serve_static(self, path: str) -> None:
        if path in {"/", ""}:
            target = (WEB_DIR / "index.html").resolve()
        else:
            relative = path.lstrip("/")
            target = (WEB_DIR / relative).resolve()

        try:
            target.relative_to(WEB_DIR.resolve())
        except ValueError:
            self._send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)
            return

        if not target.exists() or not target.is_file():
            self._send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)
            return

        content_type, _ = mimetypes.guess_type(str(target))
        if content_type in {"text/html", "text/css", "application/javascript", "text/javascript", "application/x-javascript", "image/svg+xml"}:
            content_type = f"{content_type}; charset=utf-8"
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self, allow_empty: bool = False) -> dict | None:
        content_length = self.headers.get("Content-Length")
        if not content_length:
            return {} if allow_empty else None
        try:
            length = int(content_length)
        except ValueError:
            return None
        if length == 0:
            return {} if allow_empty else None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return None

    def _client_ip(self) -> str:
        forwarded_for = self.headers.get("X-Forwarded-For", "")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return self.client_address[0]

    def _requires_auth(self, path: str) -> bool:
        return path.startswith("/api/") and path not in PUBLIC_API_PATHS

    def _cookie_value(self, name: str) -> str | None:
        header = self.headers.get("Cookie", "")
        if not header:
            return None

        cookie = SimpleCookie()
        try:
            cookie.load(header)
        except Exception:
            return None

        morsel = cookie.get(name)
        if morsel is None:
            return None
        return morsel.value

    def _build_session_cookie(self, token: str, *, max_age: int | None = None) -> str:
        cookie = SimpleCookie()
        cookie[SESSION_COOKIE_NAME] = token
        morsel = cookie[SESSION_COOKIE_NAME]
        morsel["path"] = "/"
        morsel["httponly"] = True
        morsel["samesite"] = "Lax"
        if max_age is not None:
            morsel["max-age"] = str(max_age)
            if max_age == 0:
                morsel["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        return morsel.OutputString()

    def _create_session(self, username: str) -> str:
        token = secrets.token_urlsafe(32)
        with SESSION_LOCK:
            SESSIONS[token] = {
                "username": username,
                "ip": self._client_ip(),
            }
        return token

    def _get_authenticated_session(self) -> dict[str, str] | None:
        token = self._cookie_value(SESSION_COOKIE_NAME)
        if not token:
            return None
        with SESSION_LOCK:
            session = SESSIONS.get(token)
            return dict(session) if session else None

    def _delete_session(self) -> None:
        token = self._cookie_value(SESSION_COOKIE_NAME)
        if not token:
            return
        with SESSION_LOCK:
            SESSIONS.pop(token, None)

    def _ensure_authenticated(self) -> bool:
        if self._get_authenticated_session():
            return True
        self._send_json({"error": "로그인이 필요합니다."}, status=HTTPStatus.UNAUTHORIZED)
        return False

    def _send_json(
        self,
        payload: object,
        status: HTTPStatus = HTTPStatus.OK,
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, data: bytes, *, content_type: str, file_name: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded_name = file_name.encode("utf-8")
        quoted_name = "".join(chr(byte) if 32 <= byte < 127 and chr(byte) not in {'"', '\\'} else f"%{byte:02X}" for byte in encoded_name)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quoted_name}")
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    WEB_DIR.mkdir(exist_ok=True)
    httpd = ThreadingHTTPServer((HOST, PORT), AppHandler)
    host_info = get_local_host_info()
    print(f"Serving on http://{HOST}:{PORT}")
    for url in host_info.get("suggested_urls", []):
        print(f"LAN URL: {url}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
