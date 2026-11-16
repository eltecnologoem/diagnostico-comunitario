#!/usr/bin/env python3
"""Tests offline: no internet, no SSH, no producción."""
import json
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "bin/serverdiag.sh"
EXPORTER = ROOT / "tools/export-share.py"
PROBE = ROOT / "bin/probe-connectivity.sh"
REMOTE = ROOT / "bin/remote-collect.sh"


class CollectorTests(unittest.TestCase):
    def test_syntax_posix_sh(self):
        for path in (COLLECTOR, PROBE, REMOTE):
            with self.subTest(path=path.name):
                self.assertEqual(subprocess.run(["sh", "-n", str(path)], capture_output=True).returncode, 0)

    def test_local_and_private(self):
        with tempfile.TemporaryDirectory() as td:
            original = pathlib.Path(td, "private.json")
            r = subprocess.run(["sh", str(COLLECTOR), "--output", str(original)],
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(stat.S_IMODE(original.stat().st_mode), 0o600)
            obj = json.loads(original.read_text())
            self.assertEqual(obj["schema_version"], "1.0")
            self.assertEqual(obj["report_type"], "private")
            self.assertIn("hostname", obj["source"])
            self.assertIn("embedded_mysql_present", obj["metrics"]["database"])
            again = subprocess.run(["sh", str(COLLECTOR), "--output", str(original)],
                                   capture_output=True, timeout=30)
            self.assertNotEqual(again.returncode, 0)

    def test_stdout_is_json_only(self):
        r = subprocess.run(["sh", str(COLLECTOR), "--stdout"],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["report_type"], "private")

    def test_share_allowlist(self):
        with tempfile.TemporaryDirectory() as td:
            private = pathlib.Path(td, "private.json")
            subprocess.run(["sh", str(COLLECTOR), "--output", str(private)],
                           check=True, capture_output=True, timeout=30)
            r = subprocess.run([sys.executable, str(EXPORTER), str(private)],
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            share = next(pathlib.Path(td).glob("diagnostico-compartible-*.json"))
            obj = json.loads(share.read_text())
            self.assertEqual(obj["report_type"], "share")
            self.assertEqual(set(obj), {"schema_version", "report_type", "collected_at",
                                        "summary", "findings", "omissions"})
            self.assertNotIn("source", share.read_text())
            self.assertNotIn("run_id", share.read_text())
            self.assertEqual(stat.S_IMODE(share.stat().st_mode), 0o600)

    def test_reject_sensitive(self):
        with tempfile.TemporaryDirectory() as td:
            private = pathlib.Path(td, "private.json")
            subprocess.run(["sh", str(COLLECTOR), "--output", str(private)],
                           check=True, capture_output=True, timeout=30)
            obj = json.loads(private.read_text())
            obj["privacy"]["sensitive_sharing_enabled"] = True
            private.write_text(json.dumps(obj))
            result = subprocess.run([sys.executable, str(EXPORTER), str(private)],
                                    capture_output=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)

    def test_reject_extra_fields(self):
        with tempfile.TemporaryDirectory() as td:
            private = pathlib.Path(td, "private.json")
            subprocess.run(["sh", str(COLLECTOR), "--output", str(private)],
                           check=True, capture_output=True, timeout=30)
            obj = json.loads(private.read_text())
            obj["metrics"]["database"]["internal_ip"] = "10.10.10.1"
            private.write_text(json.dumps(obj))
            result = subprocess.run([sys.executable, str(EXPORTER), str(private)],
                                    capture_output=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)

    def test_no_overwrite_share(self):
        with tempfile.TemporaryDirectory() as td:
            private = pathlib.Path(td, "private.json")
            share = pathlib.Path(td, "share.json")
            share.write_text("original")
            subprocess.run(["sh", str(COLLECTOR), "--output", str(private)],
                           check=True, capture_output=True, timeout=30)
            result = subprocess.run([sys.executable, str(EXPORTER), str(private), "--output", str(share)],
                                    capture_output=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(share.read_text(), "original")

    def test_optional_scripts_require_arguments(self):
        for path in (PROBE, REMOTE):
            self.assertNotEqual(
                subprocess.run(["sh", str(path)], capture_output=True, timeout=5).returncode, 0
            )


if __name__ == "__main__":
    unittest.main()
