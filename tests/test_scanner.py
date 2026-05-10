import unittest
import tempfile
import subprocess
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


if __name__ == "__main__":
    unittest.main()
