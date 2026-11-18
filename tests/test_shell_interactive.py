"""UI POSIX sh: menu/progress/display; sin Python en el runtime del producto."""
from __future__ import annotations
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'diagnostico.sh'


class ConsoleOptionalTests(unittest.TestCase):
    def invoke(self, home, *args):
        env = os.environ.copy()
        env['HOME'] = str(home)
        return subprocess.run(['sh', str(SCRIPT), *args], cwd=ROOT, env=env,
                              capture_output=True, text=True, timeout=80)

    def interactive(self, home, *args, answer='2,3,6\n'):
        env = os.environ.copy()
        env['HOME'] = str(home)
        master, slave = pty.openpty()
        try:
            proc = subprocess.Popen(['sh', str(SCRIPT), *args], cwd=ROOT, env=env,
                                    stdin=slave, stdout=slave, stderr=slave)
            os.close(slave)
            slave = -1
            os.write(master, answer.encode())
            chunks = []
            deadline = time.monotonic() + 80
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], .4)
                if ready:
                    try:
                        data = os.read(master, 65536)
                    except OSError:
                        break
                    if not data:
                        break
                    chunks.append(data)
                if proc.poll() is not None:
                    break
            else:
                proc.kill()
                self.fail('Timeout menú interactivo')
            try:
                while True:
                    ready, _, _ = select.select([master], [], [], .05)
                    if not ready:
                        break
                    data = os.read(master, 65536)
                    if not data:
                        break
                    chunks.append(data)
            except OSError:
                pass
            result = proc.wait(timeout=10)
            return result, b''.join(chunks).decode('utf-8', errors='replace')
        finally:
            if slave >= 0:
                os.close(slave)
            os.close(master)

    def test_default_preserves_quiet_behavior(self):
        with tempfile.TemporaryDirectory() as home:
            r = self.invoke(home, '--only', 'disk')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn('RESUMEN LOCAL', r.stdout)
            self.assertEqual(r.stderr, '')

    def test_show_outputs_only_requested_sections(self):
        with tempfile.TemporaryDirectory() as home:
            r = self.invoke(home, '--only', 'disk', '--show')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('[Disco]', r.stdout)
            self.assertIn('Disco raíz ocupado', r.stdout)
            self.assertNotIn('[Memoria]', r.stdout)
            self.assertNotIn('[Base de datos]', r.stdout)
            run_dir = next(Path(home).rglob('basic.json')).parent
            private_host = json.loads((run_dir / 'basic.json').read_text())['source']['hostname']
            self.assertNotIn(private_host, r.stdout)
            self.assertNotIn('"source"', r.stdout)

    def test_show_extended_reports_no_raw_logs(self):
        with tempfile.TemporaryDirectory() as home:
            r = self.invoke(home, '--only', 'extended', '--show')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('[Estabilidad y eventos]', r.stdout)
            self.assertIn('[Seguridad — configuración global]', r.stdout)
            self.assertNotIn('[Disco]', r.stdout)
            self.assertNotIn('journalctl -b', r.stdout)
            self.assertTrue(next(Path(home).rglob('extended.json')).is_file())

    def test_progress_non_tty_plain_text(self):
        with tempfile.TemporaryDirectory() as home:
            r = self.invoke(home, '--only', 'disk', '--progress')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('[1/2]', r.stderr)
            self.assertIn('[2/2]', r.stderr)
            self.assertIn('OK', r.stderr)
            self.assertNotIn('\x1b', r.stderr)
            self.assertNotIn('\r', r.stderr)

    def test_menu_rejects_non_tty_before_writing(self):
        with tempfile.TemporaryDirectory() as home:
            r = self.invoke(home, '--menu')
            self.assertEqual(r.returncode, 2)
            self.assertIn('TTY', r.stderr)
            self.assertEqual(list(Path(home).rglob('*.json')), [])

    def test_menu_conflict_with_only(self):
        with tempfile.TemporaryDirectory() as home:
            r = self.invoke(home, '--menu', '--only', 'disk')
            self.assertEqual(r.returncode, 2)
            self.assertEqual(list(Path(home).rglob('*.json')), [])

    def test_menu_multiple_sections_with_progress(self):
        with tempfile.TemporaryDirectory() as home:
            rc, output = self.interactive(home, '--menu', '--show', '--progress', answer='2,3,6\n')
            self.assertEqual(rc, 0, output)
            self.assertIn('Secciones seleccionadas: memory,disk,extended', output)
            self.assertIn('[Memoria]', output)
            self.assertIn('[Disco]', output)
            self.assertIn('[Seguridad', output)
            self.assertIn('[1/3]', output)
            self.assertIn('\r', output)  # animación solo en terminal real
            root = next(Path(home).rglob('INFORME.md')).parent
            self.assertTrue((root / 'basic.json').is_file())
            self.assertTrue((root / 'extended.json').is_file())
            self.assertEqual(json.loads((root / 'basic.json').read_text())['checks']['process_list'], 'skipped')

    def test_menu_cancel_creates_no_files(self):
        with tempfile.TemporaryDirectory() as home:
            rc, output = self.interactive(home, '--menu', answer='0\n')
            self.assertEqual(rc, 0, output)
            self.assertIn('cancelada', output)
            self.assertEqual(list(Path(home).rglob('INFORME.md')), [])

    def test_menu_rejects_malicious_selection(self):
        with tempfile.TemporaryDirectory() as home:
            rc, output = self.interactive(home, '--menu', answer='2,$(touch /tmp/test)\n')
            self.assertNotEqual(rc, 0)
            self.assertIn('inválida', output)
            self.assertEqual(list(Path(home).rglob('INFORME.md')), [])

    def test_menu_all_and_duplicates(self):
        with tempfile.TemporaryDirectory() as home:
            rc, output = self.interactive(home, '--menu', answer='3,3,6\n')
            self.assertEqual(rc, 0, output)
            self.assertIn('Secciones seleccionadas: disk,extended', output)
            rc, output = self.interactive(home, '--menu', answer='7\n')
            self.assertEqual(rc, 0, output)
            self.assertIn('Secciones seleccionadas: all', output)


if __name__ == '__main__':
    unittest.main()
