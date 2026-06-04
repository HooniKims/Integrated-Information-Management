import unittest
import tempfile
import subprocess
import time
from pathlib import Path
from unittest.mock import patch

import scanner


class CommandEncodingTests(unittest.TestCase):
    def test_run_command_decodes_korean_windows_command_output(self) -> None:
        raw_output = "교무실PC\n".encode("cp949")

        def fake_run(command, **kwargs):
            if kwargs.get("text"):
                decoded = raw_output.decode(kwargs.get("encoding") or "utf-8", kwargs.get("errors") or "strict")
                return subprocess.CompletedProcess(command, 0, stdout=decoded, stderr="")
            return subprocess.CompletedProcess(command, 0, stdout=raw_output, stderr=b"")

        with patch("scanner.subprocess.run", side_effect=fake_run):
            output = scanner.run_command(["nbtstat", "-A", "10.73.78.51"], timeout_seconds=2.5)

        self.assertIn("교무실PC", output)


class NetbiosResolutionTests(unittest.TestCase):
    def test_linux_nbtscan_primary_resolves_host_name(self) -> None:
        output = """10.73.78.52     DESKTOP-ABC123  <server>  WORKGROUP  00:11:22:33:44:55
"""

        with (
            patch("scanner.platform.system", return_value="Linux"),
            patch("scanner.run_command", return_value=output) as run_command,
        ):
            hostname, source = scanner.resolve_netbios_name("10.73.78.52")

        self.assertEqual(hostname, "DESKTOP-ABC123")
        self.assertEqual(source, "nbtscan")
        run_command.assert_called_once_with(["nbtscan", "-q", "10.73.78.52"], timeout_seconds=2.5)

    def test_linux_nmblookup_fallback_resolves_host_name(self) -> None:
        nbtscan_output = """10.73.78.51     <unknown>  <server>  WORKGROUP  00:11:22:33:44:55
"""
        nmblookup_output = """Looking up status of 10.73.78.51
        FX-1C7D2230FF3C <00> -         B <ACTIVE> <PERMANENT>
        WORKGROUP       <00> - <GROUP> B <ACTIVE> <PERMANENT>

        MAC Address = 1C-7D-22-30-FF-3C
"""

        with (
            patch("scanner.platform.system", return_value="Linux"),
            patch("scanner.run_command", side_effect=[nbtscan_output, nmblookup_output]) as run_command,
        ):
            hostname, source = scanner.resolve_netbios_name("10.73.78.51")

        self.assertEqual(hostname, "FX-1C7D2230FF3C")
        self.assertEqual(source, "netbios")
        self.assertEqual(run_command.call_args_list[0].args[0], ["nbtscan", "-q", "10.73.78.51"])
        self.assertEqual(run_command.call_args_list[1].args[0], ["nmblookup", "-A", "10.73.78.51"])


class IpConflictDetectionTests(unittest.TestCase):
    def test_linux_arping_detects_multiple_mac_addresses_for_same_ip(self) -> None:
        output = """ARPING 10.73.78.51
Unicast reply from 10.73.78.51 [1C:7D:22:30:FF:3C]  1.001ms
Unicast reply from 10.73.78.51 [AA:BB:CC:DD:EE:FF]  1.112ms
Sent 3 probes (1 broadcast(s))
Received 2 response(s)
"""

        with (
            patch("scanner.platform.system", return_value="Linux"),
            patch("scanner.run_command", return_value=output) as run_command,
        ):
            has_conflict, mac_addresses = scanner.detect_ip_conflict("10.73.78.51")

        self.assertTrue(has_conflict)
        self.assertEqual(mac_addresses, ["1c-7d-22-30-ff-3c", "aa-bb-cc-dd-ee-ff"])
        run_command.assert_called_once_with(["arping", "-c", "3", "-w", "2", "10.73.78.51"], timeout_seconds=3.0)

    def test_linux_arping_single_mac_address_is_not_conflict(self) -> None:
        output = """ARPING 10.73.78.51
Unicast reply from 10.73.78.51 [1C:7D:22:30:FF:3C]  1.001ms
Unicast reply from 10.73.78.51 [1C:7D:22:30:FF:3C]  1.102ms
Received 2 response(s)
"""

        with (
            patch("scanner.platform.system", return_value="Linux"),
            patch("scanner.run_command", return_value=output),
        ):
            has_conflict, mac_addresses = scanner.detect_ip_conflict("10.73.78.51")

        self.assertFalse(has_conflict)
        self.assertEqual(mac_addresses, ["1c-7d-22-30-ff-3c"])


class ScanNameRepositoryTests(unittest.TestCase):
    def test_custom_name_is_saved_and_loaded_by_ip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "scan_device_names.json"
            repository = scanner.ScanNameRepository(path)

            saved = repository.set_name("10.73.78.51", "교무실 복합기")
            reloaded = scanner.ScanNameRepository(path)
            loaded_name = reloaded.get_name("10.73.78.51")

        self.assertEqual(saved["ip"], "10.73.78.51")
        self.assertEqual(saved["name"], "교무실 복합기")
        self.assertEqual(loaded_name, "교무실 복합기")

    def test_probe_ip_includes_custom_name_and_conflict_note(self) -> None:
        with (
            patch("scanner.ping_ip", return_value=(True, 2, "Ping success")),
            patch("scanner.reverse_dns", return_value=(None, None)),
            patch("scanner.resolve_netbios_name", return_value=("FX-1C7D2230FF3C", "netbios")),
            patch("scanner.lookup_mac", return_value=None),
            patch("scanner.detect_ip_conflict", return_value=(True, ["1c-7d-22-30-ff-3c", "aa-bb-cc-dd-ee-ff"])),
        ):
            result = scanner.probe_ip("10.73.78.51", 0, custom_name="교무실 복합기")

        self.assertEqual(result["custom_name"], "교무실 복합기")
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["mac_address"], "1c-7d-22-30-ff-3c")
        self.assertEqual(result["conflict_mac_addresses"], ["1c-7d-22-30-ff-3c", "aa-bb-cc-dd-ee-ff"])
        self.assertIn("IP 충돌 의심", result["note"])

    def test_probe_ip_uses_custom_name_as_resolved_name_signal(self) -> None:
        with (
            patch("scanner.ping_ip", return_value=(True, 2, "Ping success")),
            patch("scanner.reverse_dns", return_value=(None, None)),
            patch("scanner.resolve_netbios_name", return_value=(None, None)),
            patch("scanner.lookup_mac", return_value=None),
            patch("scanner.detect_ip_conflict", return_value=(False, [])),
        ):
            result = scanner.probe_ip("10.73.78.51", 0, custom_name="교무실 복합기")

        self.assertEqual(result["status"], "healthy")
        self.assertIn("saved name", result["note"])

    def test_summary_does_not_count_saved_name_as_unresolved(self) -> None:
        job = scanner.ScanJob(id="job", start_ip="10.73.78.51", end_ip="10.73.78.51", targets=["10.73.78.51"])
        job.completed = 1
        job.results[0] = {
            "reachable": True,
            "hostname": "",
            "custom_name": "교무실 복합기",
            "mac_address": "",
        }

        self.assertEqual(job.summary()["unresolved"], 0)


class ScanInventoryRepositoryTests(unittest.TestCase):
    def test_merge_scan_results_creates_inventory_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = scanner.ScanInventoryRepository(Path(temp_dir) / "scan_inventory.json")

            result = repository.merge_scan_results(
                [
                    {
                        "ip": "10.73.78.51",
                        "reachable": True,
                        "latency_ms": 3,
                        "custom_name": "Lab PC",
                        "hostname": "DESKTOP-ABC",
                        "hostname_source": "netbios",
                        "mac_address": "00-11-22-33-44-55",
                        "status": "healthy",
                        "note": "Host responded",
                        "reported_at": "2026-06-04T01:00:00+00:00",
                    }
                ]
            )
            items = repository.list_entries()

        self.assertEqual(result["merged"], 1)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["ip"], "10.73.78.51")
        self.assertEqual(items[0]["custom_name"], "Lab PC")
        self.assertEqual(items[0]["assigned_user"], "")
        self.assertEqual(items[0]["last_seen_at"], "2026-06-04T01:00:00+00:00")

    def test_merge_scan_results_preserves_manual_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = scanner.ScanInventoryRepository(Path(temp_dir) / "scan_inventory.json")
            repository.merge_scan_results(
                [
                    {
                        "ip": "10.73.78.51",
                        "reachable": True,
                        "custom_name": "Lab PC",
                        "hostname": "OLD",
                        "hostname_source": "netbios",
                        "mac_address": "00-11-22-33-44-55",
                        "status": "healthy",
                        "note": "old note",
                        "reported_at": "2026-06-04T01:00:00+00:00",
                    }
                ]
            )
            repository.update_manual_fields(
                "10.73.78.51",
                {
                    "assigned_user": "Science Lab",
                    "custom_name": "Teacher PC",
                    "manual_note": "fixed ip",
                },
            )

            repository.merge_scan_results(
                [
                    {
                        "ip": "10.73.78.51",
                        "reachable": False,
                        "custom_name": "",
                        "hostname": "",
                        "hostname_source": "",
                        "mac_address": "",
                        "status": "offline",
                        "note": "No ping response",
                        "reported_at": "2026-06-04T02:00:00+00:00",
                    }
                ]
            )
            item = repository.list_entries()[0]

        self.assertEqual(item["assigned_user"], "Science Lab")
        self.assertEqual(item["custom_name"], "Teacher PC")
        self.assertEqual(item["manual_note"], "fixed ip")
        self.assertEqual(item["status"], "offline")
        self.assertEqual(item["last_seen_at"], "2026-06-04T01:00:00+00:00")

    def test_malformed_inventory_file_recovers_to_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "scan_inventory.json"
            path.write_text("{not json", encoding="utf-8")
            repository = scanner.ScanInventoryRepository(path)

            items = repository.list_entries()

        self.assertEqual(items, [])

    def test_scan_inventory_summary_counts_saved_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = scanner.ScanInventoryRepository(Path(temp_dir) / "scan_inventory.json")
            repository.merge_scan_results(
                [
                    {
                        "ip": "10.73.78.51",
                        "reachable": True,
                        "hostname": "",
                        "custom_name": "",
                        "mac_address": "",
                        "status": "warning",
                        "note": "name missing",
                        "reported_at": "2026-06-04T01:00:00+00:00",
                    },
                    {
                        "ip": "10.73.78.52",
                        "reachable": True,
                        "hostname": "DESKTOP-ABC",
                        "custom_name": "",
                        "mac_address": "00-11-22-33-44-55",
                        "status": "healthy",
                        "note": "ok",
                        "reported_at": "2026-06-04T01:00:00+00:00",
                    },
                ]
            )

            summary = repository.summarize_entries()

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["alive"], 2)
        self.assertEqual(summary["unresolved"], 1)
        self.assertEqual(summary["has_mac"], 1)

    def test_merge_scan_results_persists_conflict_details_and_updates_latest_scan_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = scanner.ScanInventoryRepository(Path(temp_dir) / "scan_inventory.json")
            repository.merge_scan_results(
                [
                    {
                        "ip": "10.73.78.53",
                        "reachable": True,
                        "hostname": "OLD-HOST",
                        "hostname_source": "netbios",
                        "mac_address": "00-11-22-33-44-55",
                        "conflict_detected": False,
                        "conflict_mac_addresses": [],
                        "status": "healthy",
                        "note": "old",
                        "reported_at": "2026-06-04T01:00:00+00:00",
                    }
                ]
            )
            repository.merge_scan_results(
                [
                    {
                        "ip": "10.73.78.53",
                        "reachable": True,
                        "hostname": "NEW-HOST",
                        "hostname_source": "nbtscan",
                        "mac_address": "aa-bb-cc-dd-ee-ff",
                        "conflict_detected": True,
                        "conflict_mac_addresses": ["aa-bb-cc-dd-ee-ff", "11-22-33-44-55-66"],
                        "status": "conflict",
                        "note": "conflict",
                        "reported_at": "2026-06-04T02:00:00+00:00",
                    }
                ]
            )
            item = repository.list_entries()[0]

        self.assertEqual(item["hostname"], "NEW-HOST")
        self.assertEqual(item["hostname_source"], "nbtscan")
        self.assertEqual(item["mac_address"], "aa-bb-cc-dd-ee-ff")
        self.assertTrue(item["conflict_detected"])
        self.assertEqual(item["conflict_mac_addresses"], ["aa-bb-cc-dd-ee-ff", "11-22-33-44-55-66"])
        self.assertEqual(item["status"], "conflict")
        self.assertEqual(item["last_seen_at"], "2026-06-04T02:00:00+00:00")


class ScanManagerCompletionTests(unittest.TestCase):
    def test_scan_manager_calls_completion_callback_with_results(self) -> None:
        captured_results = []

        def fake_probe(ip: str, index: int, custom_name: str = "") -> dict:
            return {
                "index": index,
                "ip": ip,
                "reachable": True,
                "latency_ms": 1,
                "custom_name": custom_name,
                "hostname": "DESKTOP-ABC",
                "hostname_source": "netbios",
                "mac_address": "00-11-22-33-44-55",
                "conflict_detected": False,
                "conflict_mac_addresses": [],
                "status": "healthy",
                "note": "ok",
                "reported_at": "2026-06-04T01:00:00+00:00",
            }

        with patch("scanner.probe_ip", side_effect=fake_probe):
            manager = scanner.ScanManager(
                name_lookup=lambda ip: "Lab PC",
                completion_callback=lambda results: captured_results.extend(results),
            )
            job = manager.create_job("10.73.78.51", "10.73.78.51")

            for _ in range(100):
                snapshot = job.snapshot()
                if snapshot["status"] == "completed":
                    break
                time.sleep(0.01)

        self.assertEqual(len(captured_results), 1)
        self.assertEqual(captured_results[0]["ip"], "10.73.78.51")
        self.assertEqual(captured_results[0]["custom_name"], "Lab PC")


if __name__ == "__main__":
    unittest.main()
