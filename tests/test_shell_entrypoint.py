"""CLI shell sin Python/jq en tiempo de ejecución; el runner de QA sí usa Python."""
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'diagnostico.sh'


class ShellDiagnosticTests(unittest.TestCase):
    def run_shell(self, home, *flags, env_extra=None):
        env = os.environ.copy()
        env['HOME'] = str(home)
        if env_extra:
            env.update(env_extra)
        return subprocess.run(['sh', str(CLI), *flags], cwd=ROOT, env=env,
                              capture_output=True, text=True, timeout=75)

    def test_posix_sh_syntax(self):
        for name in ('diagnostico.sh', 'bin/serverdiag.sh', 'bin/audit-extended.sh'):
            with self.subTest(name=name):
                res = subprocess.run(['sh','-n',str(ROOT/name)],capture_output=True)
                self.assertEqual(res.returncode,0,res.stderr.decode(errors='replace'))

    def test_help_does_not_run_diagnostic(self):
        with tempfile.TemporaryDirectory() as td:
            res = self.run_shell(td,'--help')
            self.assertEqual(res.returncode,0,res.stderr)
            self.assertIn('Sin --only',res.stdout)
            self.assertEqual(list(Path(td).rglob('*.json')),[])

    def test_default_creates_private_basic_extended_and_markdown(self):
        with tempfile.TemporaryDirectory() as td:
            res=self.run_shell(td)
            self.assertEqual(res.returncode,0,res.stderr)
            files=list(Path(td).rglob('INFORME.md'))
            self.assertEqual(len(files),1)
            run_dir=files[0].parent
            self.assertEqual(stat.S_IMODE(run_dir.stat().st_mode),0o700)
            for name in ('basic.json','extended.json','INFORME.md'):
                p=run_dir/name
                self.assertTrue(p.is_file(),name)
                self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o600)
            basic=json.loads((run_dir/'basic.json').read_text())
            extended=json.loads((run_dir/'extended.json').read_text())
            self.assertEqual(basic['schema_version'],'1.0')
            self.assertEqual(extended['schema_version'],'extended-1.0')
            self.assertIn('## Señales para investigar',files[0].read_text())
            self.assertNotIn(basic['source']['hostname'],files[0].read_text())

    def test_only_disk_memory_does_not_collect_others(self):
        with tempfile.TemporaryDirectory() as td:
            res=self.run_shell(td,'--only','disk,memory')
            self.assertEqual(res.returncode,0,res.stderr)
            run_dir=next(Path(td).rglob('INFORME.md')).parent
            basic=json.loads((run_dir/'basic.json').read_text())
            self.assertFalse((run_dir/'extended.json').exists())
            self.assertEqual(basic['checks']['process_list'],'skipped')
            self.assertEqual(basic['checks']['tcp_listeners'],'skipped')
            self.assertIsNone(basic['metrics']['system']['cpu_cores'])
            self.assertIn(basic['checks']['disk_root'],('collected','unavailable'))

    def test_only_extended(self):
        with tempfile.TemporaryDirectory() as td:
            res=self.run_shell(td,'--only','extended')
            self.assertEqual(res.returncode,0,res.stderr)
            run_dir=next(Path(td).rglob('INFORME.md')).parent
            self.assertFalse((run_dir/'basic.json').exists())
            self.assertTrue((run_dir/'extended.json').exists())
            self.assertIn('sin datos', (run_dir/'INFORME.md').read_text())

    def test_bad_sections_and_no_email(self):
        with tempfile.TemporaryDirectory() as td:
            for flags in (('--only','invalid'),('--only','disk,invalid'),('--only',''),('--email',),('--output-dir','relative/path')):
                with self.subTest(flags=flags):
                    self.assertNotEqual(self.run_shell(td,*flags).returncode,0)
            self.assertEqual(list(Path(td).rglob('*.json')),[])

    def test_custom_output_dir_does_not_chmod_parent(self):
        with tempfile.TemporaryDirectory() as td:
            output=Path(td)/'my-existing-output'
            output.mkdir(mode=0o755)
            output.chmod(0o755)
            res=self.run_shell(td,'--only','extended','--output-dir',str(output))
            self.assertEqual(res.returncode,0,res.stderr)
            self.assertEqual(stat.S_IMODE(output.stat().st_mode),0o755)
            report_dir=next(output.glob('diagnostico-*'))
            self.assertEqual(stat.S_IMODE(report_dir.stat().st_mode),0o700)

    def test_no_python_jq_mail_or_remote_binary_invoked(self):
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)/'home';home.mkdir()
            fake_bin=Path(td)/'fake-bin';fake_bin.mkdir()
            marker=Path(td)/'forbidden-invocations'
            for name in ('python','python3','jq','ssh','curl','wget','ping','nc','pip','pip3','sendmail'):
                stub=fake_bin/name
                stub.write_text('#!/bin/sh\nprintf "%s\\n" "$0" >> "$SHELL_DIAG_SENTINEL"\nexit 97\n')
                stub.chmod(0o700)
            env={'PATH':str(fake_bin)+os.pathsep+os.environ.get('PATH','/usr/bin:/bin'),
                 'SHELL_DIAG_SENTINEL':str(marker)}
            res=self.run_shell(home,'--only','disk',env_extra=env)
            self.assertEqual(res.returncode,0,res.stderr)
            self.assertFalse(marker.exists(),marker.read_text() if marker.exists() else '')


if __name__=='__main__':unittest.main()
