from __future__ import annotations

import ipaddress
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
from typing import Any

MAX_SCAN_HOSTS = 512
DEFAULT_WORKERS = 32
PING_TIMEOUT_MS = 650
DEFAULT_RANGE_START = "10.73.78.2"
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
        text=True,
        encoding="utf-8",
        errors="ignore",
        timeout=timeout_seconds,
        check=False,
    )
    return (completed.stdout or "") + (completed.stderr or "")


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
    if platform.system().lower() != "windows":
        return None, None

    try:
        output = run_command(["nbtstat", "-A", ip], timeout_seconds=2.5)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None, None

    for line in output.splitlines():
        match = re.search(r"^\s*([^\s]+)\s+<00>\s+UNIQUE", line, re.IGNORECASE)
        if match:
            return match.group(1).strip(), "netbios"

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


def probe_ip(ip: str, index: int) -> dict[str, Any]:
    reachable, latency_ms, ping_note = ping_ip(ip)
    hostname = None
    hostname_source = None
    mac_address = None

    if reachable:
        hostname, hostname_source = reverse_dns(ip)
        if not hostname:
            hostname, hostname_source = resolve_netbios_name(ip)
        mac_address = lookup_mac(ip)

    if reachable and hostname:
        status = "healthy"
        note = "Host responded and a name was resolved."
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
        "hostname": hostname or "",
        "hostname_source": hostname_source or "",
        "mac_address": mac_address or "",
        "status": status,
        "note": note,
        "reported_at": utc_now_iso(),
    }


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
            if result["reachable"] and not result["hostname"]:
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
    def __init__(self) -> None:
        self._jobs: dict[str, ScanJob] = {}
        self._lock = threading.Lock()

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
                    executor.submit(probe_ip, ip, index): index
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
        except Exception as exc:  # pragma: no cover - defensive path
            with job.lock:
                job.status = "failed"
                job.error = str(exc)
                job.finished_at = utc_now_iso()
