from __future__ import annotations

import json
import mimetypes
import os
import secrets
import hashlib
import threading
from email.message import Message
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from scanner import ScanInventoryRepository, ScanManager, ScanNameRepository, get_local_host_info
from device_inventory import DeviceInventoryRepository
from password_manager import PasswordItemRepository
from site_accounts import SiteAccountRepository

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DATA_DIR = ROOT / "data"
DEVICE_IMAGE_DIR = DATA_DIR / "device_images"
MAX_DEVICE_IMAGE_BYTES = 5 * 1024 * 1024
DEVICE_IMAGE_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


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

SCAN_NAME_REPOSITORY = ScanNameRepository(DATA_DIR / "scan_device_names.json")
SCAN_INVENTORY_REPOSITORY = ScanInventoryRepository(DATA_DIR / "scan_inventory.json")
SCAN_MANAGER = ScanManager(
    name_lookup=SCAN_NAME_REPOSITORY.get_name,
    completion_callback=SCAN_INVENTORY_REPOSITORY.merge_scan_results,
)
SITE_ACCOUNT_REPOSITORY = SiteAccountRepository(DATA_DIR / "site_accounts.json", DATA_DIR / "site_account_audit.json")
PASSWORD_ITEM_REPOSITORY = PasswordItemRepository(DATA_DIR / "password_items.json")
DEVICE_INVENTORY_REPOSITORY = DeviceInventoryRepository(
    DATA_DIR / "device_inventory.json",
    DATA_DIR / "device_inventory_events.json",
    image_dir=DEVICE_IMAGE_DIR,
)


def store_device_image_upload(image_dir: Path, *, file_name: str, content_type: str, data: bytes) -> dict[str, object]:
    if not data:
        raise ValueError("이미지 파일이 비어 있습니다.")
    if len(data) > MAX_DEVICE_IMAGE_BYTES:
        raise ValueError("이미지 파일은 5MB 이하만 업로드할 수 있습니다.")

    normalized_content_type = content_type.split(";", 1)[0].strip().lower()
    suffix = DEVICE_IMAGE_CONTENT_TYPES.get(normalized_content_type)
    if suffix is None:
        original_suffix = Path(file_name).suffix.lower()
        suffix = original_suffix if original_suffix in {".jpg", ".jpeg", ".png", ".webp"} else ""
        if suffix == ".jpeg":
            suffix = ".jpg"
    if suffix not in {".jpg", ".png", ".webp"}:
        raise ValueError("JPG, PNG, WEBP 이미지만 업로드할 수 있습니다.")

    digest = hashlib.sha256(data).hexdigest()[:16]
    stored_name = f"{digest}{suffix}"
    image_dir.mkdir(parents=True, exist_ok=True)
    target = image_dir / stored_name
    if not target.exists():
        target.write_bytes(data)

    return {
        "file_name": stored_name,
        "url": f"/device-images/{stored_name}",
        "size": len(data),
        "content_type": normalized_content_type or mimetypes.guess_type(stored_name)[0] or "application/octet-stream",
    }


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

        if path.startswith("/device-images/"):
            if not self._ensure_authenticated():
                return
            self._serve_device_image(path)
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

        if path == "/api/scan-inventory":
            self._send_json(
                {
                    "items": SCAN_INVENTORY_REPOSITORY.list_entries(),
                    "summary": SCAN_INVENTORY_REPOSITORY.summarize_entries(),
                }
            )
            return

        if path == "/api/site-accounts":
            self._send_json(
                {
                    "items": SITE_ACCOUNT_REPOSITORY.list_accounts(),
                    "summary": SITE_ACCOUNT_REPOSITORY.summarize_accounts(),
                }
            )
            return

        if path == "/api/site-accounts/template-csv":
            self._send_json(
                {
                    "filename": "site_accounts_template.csv",
                    "csv_text": SITE_ACCOUNT_REPOSITORY.export_csv(include_items=False),
                }
            )
            return

        if path == "/api/site-accounts/export-csv":
            self._send_json(
                {
                    "filename": "site_accounts.csv",
                    "csv_text": SITE_ACCOUNT_REPOSITORY.export_csv(),
                }
            )
            return

        if path == "/api/password-items":
            self._send_json(
                {
                    "items": PASSWORD_ITEM_REPOSITORY.list_items(),
                    "summary": PASSWORD_ITEM_REPOSITORY.summarize_items(),
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

        if path == "/api/device-inventory/template-csv":
            self._send_json(
                {
                    "filename": "device_inventory_template.csv",
                    "csv_text": DEVICE_INVENTORY_REPOSITORY.export_csv_template(),
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

        if path == "/api/scan-device-names/template-csv":
            self._send_json(
                {
                    "filename": "scan_device_names_template.csv",
                    "csv_text": "IP,저장 장치명\n10.73.78.1,\n",
                }
            )
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

        if path.startswith("/api/password-items/") and path.count("/") == 3:
            self._send_json({"error": "Unsupported route."}, status=HTTPStatus.NOT_FOUND)
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

        if path == "/api/site-accounts/import-csv":
            payload = self._read_json_body()
            if payload is None:
                self._send_json({"error": "Invalid JSON body."}, status=HTTPStatus.BAD_REQUEST)
                return
            csv_text = str(payload.get("csv_text", "") or "")
            try:
                result = SITE_ACCOUNT_REPOSITORY.import_csv(csv_text)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(result)
            return

        if path == "/api/password-items":
            payload = self._read_json_body()
            if payload is None:
                self._send_json({"error": "Invalid JSON body."}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                created = PASSWORD_ITEM_REPOSITORY.create_item(payload)
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

        if path == "/api/device-inventory/images":
            try:
                upload = self._read_multipart_file("image")
                result = store_device_image_upload(
                    DEVICE_IMAGE_DIR,
                    file_name=upload["file_name"],
                    content_type=upload["content_type"],
                    data=upload["data"],
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(result, status=HTTPStatus.CREATED)
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

        if path == "/api/scan-device-names":
            payload = self._read_json_body()
            if payload is None:
                self._send_json({"error": "Invalid JSON body."}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                updated = SCAN_NAME_REPOSITORY.set_name(
                    str(payload.get("ip", "") or ""),
                    str(payload.get("name", "") or ""),
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(updated)
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

        if path.startswith("/api/scan-inventory/") and path.count("/") == 3:
            ip = unquote(path.rsplit("/", 1)[-1])
            payload = self._read_json_body()
            if payload is None:
                self._send_json({"error": "Invalid JSON body."}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                updated = SCAN_INVENTORY_REPOSITORY.update_manual_fields(ip, payload)
                if "custom_name" in payload:
                    SCAN_NAME_REPOSITORY.set_name(ip, str(payload.get("custom_name", "") or ""))
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(updated)
            return

        if path.startswith("/api/password-items/") and path.count("/") == 3:
            payload = self._read_json_body()
            if payload is None:
                self._send_json({"error": "Invalid JSON body."}, status=HTTPStatus.BAD_REQUEST)
                return
            item_id = path.rsplit("/", 1)[-1]
            try:
                updated = PASSWORD_ITEM_REPOSITORY.update_item(item_id, payload)
            except KeyError:
                self._send_json({"error": "비밀번호 항목을 찾을 수 없습니다."}, status=HTTPStatus.NOT_FOUND)
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

        if path.startswith("/api/password-items/") and path.count("/") == 3:
            item_id = path.rsplit("/", 1)[-1]
            try:
                deleted = PASSWORD_ITEM_REPOSITORY.delete_item(item_id)
            except KeyError:
                self._send_json({"error": "비밀번호 항목을 찾을 수 없습니다."}, status=HTTPStatus.NOT_FOUND)
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
        if target.suffix.lower() == ".ttf":
            content_type = "font/ttf"
        if content_type in {"text/html", "text/css", "application/javascript", "text/javascript", "application/x-javascript", "image/svg+xml"}:
            content_type = f"{content_type}; charset=utf-8"
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_device_image(self, path: str) -> None:
        file_name = Path(unquote(path.rsplit("/", 1)[-1])).name
        target = (DEVICE_IMAGE_DIR / file_name).resolve()
        try:
            target.relative_to(DEVICE_IMAGE_DIR.resolve())
        except ValueError:
            self._send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)
            return

        if not target.exists() or not target.is_file():
            self._send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)
            return

        content_type, _ = mimetypes.guess_type(str(target))
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "private, max-age=86400")
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

    def _read_multipart_file(self, field_name: str) -> dict[str, object]:
        content_type = self.headers.get("Content-Type", "")
        message = Message()
        message["content-type"] = content_type
        if message.get_content_type() != "multipart/form-data":
            raise ValueError("이미지 업로드 요청 형식이 올바르지 않습니다.")

        boundary = message.get_param("boundary", header="content-type")
        if not boundary:
            raise ValueError("이미지 업로드 경계값이 없습니다.")

        content_length = self.headers.get("Content-Length")
        if not content_length:
            raise ValueError("이미지 파일이 없습니다.")
        try:
            length = int(content_length)
        except ValueError as exc:
            raise ValueError("이미지 업로드 크기를 확인할 수 없습니다.") from exc
        if length <= 0 or length > MAX_DEVICE_IMAGE_BYTES + 1024 * 256:
            raise ValueError("이미지 파일은 5MB 이하만 업로드할 수 있습니다.")

        raw = self.rfile.read(length)
        boundary_bytes = f"--{boundary}".encode("utf-8")
        for raw_part in raw.split(boundary_bytes):
            part = raw_part.strip(b"\r\n")
            if not part or part == b"--":
                continue
            if part.endswith(b"--"):
                part = part[:-2].rstrip(b"\r\n")
            header_blob, separator, body = part.partition(b"\r\n\r\n")
            if not separator:
                continue

            part_headers = self._parse_multipart_headers(header_blob)
            disposition = part_headers.get("content-disposition", "")
            disposition_message = Message()
            disposition_message["content-disposition"] = disposition
            name = disposition_message.get_param("name", header="content-disposition")
            file_name = disposition_message.get_param("filename", header="content-disposition")
            if name != field_name or not file_name:
                continue

            return {
                "file_name": Path(str(file_name)).name,
                "content_type": part_headers.get("content-type", ""),
                "data": body.rstrip(b"\r\n"),
            }

        raise ValueError("업로드할 이미지 파일을 찾을 수 없습니다.")

    def _parse_multipart_headers(self, header_blob: bytes) -> dict[str, str]:
        headers: dict[str, str] = {}
        for raw_line in header_blob.decode("iso-8859-1").split("\r\n"):
            if ":" not in raw_line:
                continue
            key, value = raw_line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
        return headers

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
