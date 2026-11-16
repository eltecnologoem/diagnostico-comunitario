#!/usr/bin/env python3
"""QA de selección parcial y correo: sin SMTP real ni conexiones de red."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "bin/serverdiag.sh"
SENDER = ROOT / "tools/send-report.py"


def load_sender():
    spec = importlib.util.spec_from_file_location("serverdiag_sender", SENDER)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


class SelectiveAndMailTests(unittest.TestCase):
    def collect(self, *args, cwd=None):
        return subprocess.run(["sh", str(COLLECTOR), *args],
                              text=True, capture_output=True, timeout=30, cwd=cwd)

    def test_partial_disk_skips_other_sections(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "report.json")
            r = self.collect("--only", "disk", "--output", path)
            self.assertEqual(r.returncode, 0, r.stderr)
            obj = json.loads(Path(path).read_text())
            self.assertEqual(obj["checks"]["meminfo"], "skipped")
            self.assertEqual(obj["checks"]["process_list"], "skipped")
            self.assertEqual(obj["checks"]["tcp_listeners"], "skipped")
            self.assertIsNone(obj["metrics"]["memory"]["total_bytes"])
            self.assertIsNone(obj["metrics"]["database"]["mysql_client_available"])
            self.assertIsNone(obj["metrics"]["processes"]["sshd_process_count"])

    def test_reject_unknown_section_before_collection(self):
        with tempfile.TemporaryDirectory() as td:
            r = self.collect("--only", "secret,disk", cwd=td)
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse(list(Path(td).glob("*.json")))

    def test_mail_not_sent_without_flag_even_if_env_exists(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, ".env").write_text("SMTP_HOST=example.invalid\n")
            r = self.collect("--only", "system", cwd=td)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(len(list(Path(td).glob("*.json"))), 1)

    def test_stdout_and_email_are_mutually_exclusive(self):
        r = self.collect("--email", "--stdout")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(r.stdout.startswith("{"))

    def test_sender_env_permissions_and_no_shell_evaluation(self):
        mod = load_sender()
        env = (
            "SMTP_HOST=smtp.example.org\nSMTP_PORT=587\nSMTP_SECURITY=starttls\n"
            "SMTP_USER=a@example.org\nSMTP_PASSWORD=$(touch /tmp/never-execute-this)\n"
            "MAIL_FROM=a@example.org\nMAIL_TO=b@example.org\n"
        )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / ".env"
            p.write_text(env)
            p.chmod(0o644)
            with self.assertRaises(ValueError):
                mod.read_env(p)
            p.chmod(0o600)
            data = mod.read_env(p)
            self.assertEqual(data["SMTP_PASSWORD"], "$(touch /tmp/never-execute-this)")
            self.assertFalse(Path("/tmp/never-execute-this").exists())

    def test_sender_rejects_plaintext(self):
        mod = load_sender()
        data = dict(SMTP_HOST="smtp.example.org", SMTP_PORT="25",
                    SMTP_SECURITY="none", SMTP_USER="a@example.org",
                    SMTP_PASSWORD="pass", MAIL_FROM="a@example.org",
                    MAIL_TO="b@example.org")
        with self.assertRaises(ValueError):
            mod.validated_config(data)

    def test_message_contains_shared_json_only(self):
        mod = load_sender()
        with tempfile.TemporaryDirectory() as td:
            private = Path(td) / "private.json"
            r = self.collect("--only", "system,disk", "--output", str(private))
            self.assertEqual(r.returncode, 0, r.stderr)
            msg = mod.build_message(private, "a@example.org", "b@example.org")
            self.assertEqual(len(msg.get_payload()), 2)
            attachment = msg.get_payload()[1]
            parsed = json.loads(attachment.get_content())
            self.assertEqual(parsed["report_type"], "share")
            self.assertNotIn("hostname", attachment.get_content())
            self.assertNotIn("run_id", attachment.get_content())
            self.assertEqual(set(parsed), {"schema_version", "report_type", "collected_at",
                                           "summary", "findings", "omissions"})

    def test_starttls_sender_uses_tls_before_auth_and_send(self):
        mod = load_sender()
        class FakeSMTP:
            calls = []
            def __init__(self, **kwargs): self.calls.append("connect")
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def ehlo(self): self.calls.append("ehlo")
            def has_extn(self, ext): return ext == "starttls"
            def starttls(self, context): self.calls.append("starttls")
            def login(self, user, password): self.calls.append("login")
            def send_message(self, msg): self.calls.append("send")
        with tempfile.TemporaryDirectory() as td:
            envpath = Path(td) / ".env"
            envpath.write_text(
                "SMTP_HOST=smtp.example.org\nSMTP_PORT=587\nSMTP_SECURITY=starttls\n"
                "SMTP_USER=a@example.org\nSMTP_PASSWORD=dummy\n"
                "MAIL_FROM=a@example.org\nMAIL_TO=b@example.org\n"
            )
            envpath.chmod(0o600)
            report = Path(td) / "report.json"
            self.assertEqual(self.collect("--only", "system", "--output", str(report)).returncode, 0)
            with patch.object(mod.smtplib, "SMTP", FakeSMTP):
                mod.send(envpath, report)
            self.assertLess(FakeSMTP.calls.index("starttls"), FakeSMTP.calls.index("login"))
            self.assertLess(FakeSMTP.calls.index("login"), FakeSMTP.calls.index("send"))


if __name__ == "__main__":
    unittest.main()
