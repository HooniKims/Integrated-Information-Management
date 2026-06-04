from __future__ import annotations

import ipaddress
import json
import locale
import platform
import re
import socket
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_SCAN_HOSTS = 512
DEFAULT_WORKERS = 32
PING_TIMEOUT_MS = 650
DEFAULT_RANGE_START = "10.73.78.1"
DEFAULT_RANGE_END = "10.73.78.254"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_ip_range(start_ip: str, end_ip: str) -> tuple[list[str], str, str]:
    start = ipaddress.IPv4Address(start_ip.strip())
    end = ipaddress.IPv4Address(end_ip.strip())

    if start > end:
        start, end = end, start

    total = int(end) - int(start) + 1
    if total < 1:
        raise ValueError("Empty IP range.")
    if total > MAX_SCAN_HOSTS:
        raise ValueError(f"Range too large. Maximum {MAX_SCAN_HOSTS} IPs per scan.")

    targets = [str(ipaddress.IPv4Address(value)) for value in range(int(start), int(end) + 1)]
    return targets, str(start), str(end)


def get_local_host_info() -> dict[str, Any]:
    hostname = socket.gethostname()
    ips: list[str] = []

    try:
        host_entries = socket.gethostbyname_ex(hostname)
        ips.extend(host_entries[2])
    except OSError:
        pass

    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique_ips: list[str] = []
    for ip in ips:
        if ip not in seen:
            seen.add(ip)
            unique_ips.append(ip)

    return {
        "hostname": hostname,
        "ips": unique_ips,
        "platform": platform.platform(),
        "suggested_urls": [f"http://{ip}:8765" for ip in unique_ips if "." in ip],
        "default_range": {
            "start_ip": DEFAULT_RANGE_START,
            "end_ip": DEFAULT_RANGE_END,
        },
    }


def run_command(command: list[str], timeout_seconds: float) -> str:
    completed = subprocess.run(
        command,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    return decode_command_output(completed.stdout) + decode_command_output(completed.stderr)


def decode_command_output(output: bytes | str | None) -> str:
    if not output:
        return ""
    if isinstance(output, str):
        return output

    encodings = ["utf-8", locale.getpreferredencoding(False), "cp949", "mbcs"]
    seen: set[str] = set()
    for encoding in encodings:
        normalized = encoding.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        try:
            return output.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue

    return output.decode("utf-8", errors="replace")


def normalize_mac_address(value: str) -> str:
    return value.strip().lower().replace(":", "-")


def ping_ip(ip: str) -> tuple[bool, int | None, str]:
    system = platform.system().lower()
    if system == "windows":
        command = ["ping", "-n", "1", "-w", str(PING_TIMEOUT_MS), ip]
    else:
        command = ["ping", "-c", "1", "-W", str(max(1, PING_TIMEOUT_MS // 1000)), ip]

    started = time.perf_counter()
    try:
        output = run_command(command, timeout_seconds=3.0)
    except subprocess.TimeoutExpired:
        return False, None, "Ping timeout"

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    reachable = "ttl=" in output.lower()

    latency_match = re.search(r"time[=<]?\s*(\d+)\s*ms", output, re.IGNORECASE)
    latency_ms = int(latency_match.group(1)) if latency_match else (elapsed_ms if reachable else None)

    note = "Ping success" if reachable else "No ping response"
    return reachable, latency_ms, note


def reverse_dns(ip: str) -> tuple[str | None, str | None]:
    try:
        hostname = socket.gethostbyaddr(ip)[0]
        return hostname, "reverse-dns"
    except OSError:
        return None, None


def resolve_netbios_name(ip: str) -> tuple[str | None, str | None]:
    system = platform.system().lower()
    if system == "windows":
        return resolve_nbtstat_name(ip)

    hostname, source = resolve_nbtscan_name(ip)
    if hostname:
        return hostname, source

    return resolve_nmblookup_name(ip)


def resolve_nbtstat_name(ip: str) -> tuple[str | None, str | None]:
    try:
        output = run_command(["nbtstat", "-A", ip], timeout_seconds=2.5)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None, None

    return parse_netbios_status_name(output)


def resolve_nmblookup_name(ip: str) -> tuple[str | None, str | None]:
    try:
        output = run_command(["nmblookup", "-A", ip], timeout_seconds=2.5)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None, None

    return parse_netbios_status_name(output)


def parse_netbios_status_name(output: str) -> tuple[str | None, str | None]:
    for line in output.splitlines():
        match = re.search(r"^\s*([^\s]+)\s+<00>", line, re.IGNORECASE)
        if match and "<GROUP>" not in line.upper():
            return match.group(1).strip(), "netbios"

    return None, None


def resolve_nbtscan_name(ip: str) -> tuple[str | None, str | None]:
    try:
        output = run_command(["nbtscan", "-q", ip], timeout_seconds=2.5)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None, None

    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == ip:
            hostname = parts[1].strip()
            if hostname and hostname != "<unknown>":
                return hostname, "nbtscan"

    return None, None


def lookup_mac(ip: str) -> str | None:
    if platform.system().lower() != "windows":
        return None

    try:
        output = run_command(["arp", "-a", ip], timeout_seconds=2.0)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    match = re.search(rf"{re.escape(ip)}\s+([0-9a-fA-F:-]{{17}})", output)
    if match:
        return match.group(1).lower().replace(":", "-")
    return None


def detect_ip_conflict(ip: str) -> tuple[bool, list[str]]:
    if platform.system().lower() == "windows":
        return False, []

    try:
        output = run_command(["arping", "-c", "3", "-w", "2", ip], timeout_seconds=3.0)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, []

    seen: set[str] = set()
    mac_addresses: list[str] = []
    for match in re.finditer(r"\[([0-9a-fA-F:-]{17})\]", output):
        mac_address = normalize_mac_address(match.group(1))
        if mac_address not in seen:
            seen.add(mac_address)
            mac_addresses.append(mac_address)

    return len(mac_addresses) > 1, mac_addresses


def probe_ip(ip: str, index: int, custom_name: str = "") -> dict[str, Any]:
    reachable, latency_ms, ping_note = ping_ip(ip)
    hostname = None
    hostname_source = None
    mac_address = None
    conflict_detected = False
    conflict_mac_addresses: list[str] = []

    if reachable:
        hostname, hostname_source = reverse_dns(ip)
        if not hostname:
            hostname, hostname_source = resolve_netbios_name(ip)
        mac_address = lookup_mac(ip)
        conflict_detected, conflict_mac_addresses = detect_ip_conflict(ip)
        if not mac_address and conflict_mac_addresses:
            mac_address = conflict_mac_addresses[0]

    if conflict_detected:
        status = "conflict"
        note = f"IP 충돌 의심: 같은 IP에서 여러 MAC 응답 ({', '.join(conflict_mac_addresses)})"
    elif reachable and hostname:
        status = "healthy"
        note = "Host responded and a name was resolved."
    elif reachable and custom_name:
        status = "healthy"
        note = "Host responded and a saved name is available."
    elif reachable:
        status = "warning"
        note = "Host responded but name resolution was not available."
    else:
        status = "offline"
        note = ping_note

    return {
        "index": index,
        "ip": ip,
        "reachable": reachable,
        "latency_ms": latency_ms,
        "custom_name": custom_name,
        "hostname": hostname or "",
        "hostname_source": hostname_source or "",
        "mac_address": mac_address or "",
        "conflict_detected": conflict_detected,
        "conflict_mac_addresses": conflict_mac_addresses,
        "status": status,
        "note": note,
        "reported_at": utc_now_iso(),
    }


class ScanNameRepository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._ensure_file()

    def get_name(self, ip: str) -> str:
        normalized_ip = self._normalize_ip(ip)
        with self._lock:
            payload = self._read_payload()
        return str(payload.get("names", {}).get(normalized_ip, "") or "")

    def set_name(self, ip: str, name: str) -> dict[str, str]:
        normalized_ip = self._normalize_ip(ip)
        normalized_name = str(name or "").strip()
        with self._lock:
            payload = self._read_payload()
            names = dict(payload.get("names", {}))
            if normalized_name:
                names[normalized_ip] = normalized_name
            else:
                names.pop(normalized_ip, None)
            self._write_payload({"names": names})
        return {"ip": normalized_ip, "name": normalized_name}

    def _ensure_file(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_payload({"names": {}})

    def _read_payload(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"names": {}}
        if not isinstance(data, dict) or not isinstance(data.get("names"), dict):
            return {"names": {}}
        return data

    def _write_payload(self, payload: dict[str, Any]) -> None:
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _normalize_ip(ip: str) -> str:
        try:
            return str(ipaddress.IPv4Address(str(ip).strip()))
        except ipaddress.AddressValueError as exc:
            raise ValueError("Invalid IP address.") from exc


class ScanInventoryRepository:
    MANUAL_FIELDS = {"assigned_user", "custom_name", "manual_note"}
    SCAN_FIELDS = {
        "hostname",
        "hostname_source",
        "mac_address",
        "reachable",
        "latency_ms",
        "status",
        "note",
        "reported_at",
        "conflict_detected",
        "conflict_mac_addresses",
    }

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._ensure_file()

    def list_entries(self) -> list[dict[str, Any]]:
        with self._lock:
            payload = self._read_payload()
        items = [self._normalize_entry(item) for item in payload.get("items", {}).values()]
        items.sort(key=lambda item: ipaddress.IPv4Address(item["ip"]))
        return items

    def summarize_entries(self) -> dict[str, int]:
        items = self.list_entries()
        alive = sum(1 for item in items if item.get("reachable"))
        unresolved = sum(
            1
            for item in items
            if item.get("reachable") and not item.get("hostname") and not item.get("custom_name")
        )
        has_mac = sum(1 for item in items if item.get("mac_address"))
        missing_user = sum(1 for item in items if not item.get("assigned_user"))
        return {
            "total": len(items),
            "completed": len(items),
            "alive": alive,
            "unresolved": unresolved,
            "has_mac": has_mac,
            "missing_user": missing_user,
        }

    def merge_scan_results(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        merged = 0
        with self._lock:
            payload = self._read_payload()
            items = dict(payload.get("items", {}))
            for result in results:
                ip = self._normalize_ip(str(result.get("ip", "") or ""))
                previous = self._normalize_entry(items.get(ip, {"ip": ip}))
                now = utc_now_iso()
                reported_at = str(result.get("reported_at") or now)

                next_item = {
                    **previous,
                    "ip": ip,
                    "hostname": str(result.get("hostname", "") or ""),
                    "hostname_source": str(result.get("hostname_source", "") or ""),
                    "mac_address": str(result.get("mac_address", "") or ""),
                    "reachable": bool(result.get("reachable")),
                    "latency_ms": result.get("latency_ms"),
                    "status": str(result.get("status", "") or ("healthy" if result.get("reachable") else "offline")),
                    "note": str(result.get("note", "") or ""),
                    "reported_at": reported_at,
                    "conflict_detected": bool(result.get("conflict_detected", False)),
                    "conflict_mac_addresses": [
                        str(value)
                        for value in result.get("conflict_mac_addresses", [])
                        if str(value or "").strip()
                    ],
                    "updated_at": now,
                }
                if not next_item.get("first_seen_at"):
                    next_item["first_seen_at"] = reported_at
                if result.get("reachable"):
                    next_item["last_seen_at"] = reported_at
                if not previous.get("custom_name") and result.get("custom_name"):
                    next_item["custom_name"] = str(result.get("custom_name", "") or "")

                items[ip] = self._normalize_entry(next_item)
                merged += 1

            self._write_payload({"items": items})
        return {"merged": merged, "summary": self.summarize_entries()}

    def update_manual_fields(self, ip: str, payload: dict[str, Any]) -> dict[str, Any]:
        normalized_ip = self._normalize_ip(ip)
        with self._lock:
            data = self._read_payload()
            items = dict(data.get("items", {}))
            item = self._normalize_entry(items.get(normalized_ip, {"ip": normalized_ip}))
            now = utc_now_iso()

            for field_name in self.MANUAL_FIELDS:
                if field_name in payload:
                    item[field_name] = str(payload.get(field_name, "") or "").strip()
            if not item.get("first_seen_at"):
                item["first_seen_at"] = now
            item["updated_at"] = now
            items[normalized_ip] = self._normalize_entry(item)
            self._write_payload({"items": items})
        return items[normalized_ip]

    def _ensure_file(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_payload({"items": {}})

    def _read_payload(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"items": {}}
        if not isinstance(data, dict) or not isinstance(data.get("items"), dict):
            return {"items": {}}
        return data

    def _write_payload(self, payload: dict[str, Any]) -> None:
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _normalize_entry(self, item: dict[str, Any]) -> dict[str, Any]:
        ip = self._normalize_ip(str(item.get("ip", "") or ""))
        return {
            "ip": ip,
            "assigned_user": str(item.get("assigned_user", "") or ""),
            "custom_name": str(item.get("custom_name", "") or ""),
            "hostname": str(item.get("hostname", "") or ""),
            "hostname_source": str(item.get("hostname_source", "") or ""),
            "mac_address": str(item.get("mac_address", "") or ""),
            "reachable": bool(item.get("reachable", False)),
            "latency_ms": item.get("latency_ms"),
            "status": str(item.get("status", "") or "offline"),
            "note": str(item.get("note", "") or ""),
            "conflict_detected": bool(item.get("conflict_detected", False)),
            "conflict_mac_addresses": [
                str(value)
                for value in item.get("conflict_mac_addresses", [])
                if str(value or "").strip()
            ],
            "manual_note": str(item.get("manual_note", "") or ""),
            "reported_at": str(item.get("reported_at", "") or ""),
            "last_seen_at": str(item.get("last_seen_at", "") or ""),
            "first_seen_at": str(item.get("first_seen_at", "") or ""),
            "updated_at": str(item.get("updated_at", "") or ""),
        }

    @staticmethod
    def _normalize_ip(ip: str) -> str:
        try:
            return str(ipaddress.IPv4Address(str(ip).strip()))
        except ipaddress.AddressValueError as exc:
            raise ValueError("Invalid IP address.") from exc


@dataclass
class ScanJob:
    id: str
    start_ip: str
    end_ip: str
    targets: list[str]
    status: str = "queued"
    created_at: str = field(default_factory=utc_now_iso)
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    completed: int = 0
    results: dict[int, dict[str, Any]] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)
    cancel_requested: bool = False

    @property
    def total(self) -> int:
        return len(self.targets)

    def summary(self) -> dict[str, int]:
        alive = 0
        unresolved = 0
        has_mac = 0
        for result in self.results.values():
            if result["reachable"]:
                alive += 1
            if result["reachable"] and not result.get("hostname") and not result.get("custom_name"):
                unresolved += 1
            if result["mac_address"]:
                has_mac += 1
        return {
            "total": self.total,
            "completed": self.completed,
            "alive": alive,
            "unresolved": unresolved,
            "has_mac": has_mac,
        }

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            ordered_results = [self.results[key] for key in sorted(self.results.keys())]
            progress = round((self.completed / self.total) * 100, 1) if self.total else 0.0
            return {
                "job_id": self.id,
                "status": self.status,
                "created_at": self.created_at,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "start_ip": self.start_ip,
                "end_ip": self.end_ip,
                "progress_percent": progress,
                "summary": self.summary(),
                "results": ordered_results,
                "error": self.error,
                "cancel_requested": self.cancel_requested,
            }


class ScanManager:
    def __init__(self, name_lookup=None, completion_callback=None) -> None:
        self._jobs: dict[str, ScanJob] = {}
        self._lock = threading.Lock()
        self._name_lookup = name_lookup or (lambda _ip: "")
        self._completion_callback = completion_callback

    def create_job(self, start_ip: str, end_ip: str) -> ScanJob:
        targets, normalized_start, normalized_end = normalize_ip_range(start_ip, end_ip)
        job = ScanJob(
            id=uuid.uuid4().hex,
            start_ip=normalized_start,
            end_ip=normalized_end,
            targets=targets,
        )
        with self._lock:
            self._jobs[job.id] = job

        worker = threading.Thread(target=self._run_scan, args=(job,), daemon=True)
        worker.start()
        return job

    def get_job(self, job_id: str) -> ScanJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        job = self.get_job(job_id)
        if not job:
            return False
        with job.lock:
            job.cancel_requested = True
            if job.status in {"queued", "running"}:
                job.status = "cancelling"
        return True

    def _run_scan(self, job: ScanJob) -> None:
        with job.lock:
            job.status = "running"
            job.started_at = utc_now_iso()

        max_workers = min(DEFAULT_WORKERS, max(1, len(job.targets)))

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {
                    executor.submit(probe_ip, ip, index, self._name_lookup(ip)): index
                    for index, ip in enumerate(job.targets)
                }

                for future in as_completed(future_map):
                    result = future.result()
                    with job.lock:
                        job.results[result["index"]] = result
                        job.completed += 1

                        if job.cancel_requested and job.status == "cancelling":
                            # Keep collecting already-started tasks, but expose the cancellation intent.
                            pass

            with job.lock:
                job.status = "cancelled" if job.cancel_requested else "completed"
                job.finished_at = utc_now_iso()
                ordered_results = [job.results[key] for key in sorted(job.results.keys())]
            if self._completion_callback:
                self._completion_callback(ordered_results)
        except Exception as exc:  # pragma: no cover - defensive path
            with job.lock:
                job.status = "failed"
                job.error = str(exc)
                job.finished_at = utc_now_iso()
