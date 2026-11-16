"""Auditoría read-only y hardening: pruebas sintéticas, ningún sysctl real cambia."""
from __future__ import annotations
import copy
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
COLLECTOR=ROOT/'bin/audit-extended.sh'
ANALYZER=ROOT/'tools/analyze-extended.py'
HARDENING=ROOT/'tools/hardening.py'


def load(path, name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

ext=load(ANALYZER,'extended_analysis')
hard=load(HARDENING,'hardening_controls')
cli=load(ROOT/'diagnostico.py','community_diagnostic_cli_v03')


def example():
    return json.loads(subprocess.check_output(['sh',str(COLLECTOR),'--stdout'],timeout=30))


class ExtendedAuditTests(unittest.TestCase):
    def test_extended_posix_syntax(self):
        self.assertEqual(subprocess.run(['sh','-n',str(COLLECTOR)],capture_output=True).returncode,0)

    def test_json_closed_contract_readonly_and_private(self):
        obj=example()
        self.assertEqual(obj['schema_version'],'extended-1.0')
        self.assertEqual(obj['report_type'],'private_extended')
        self.assertIsInstance(ext.analyze(obj)['findings'],list)
        raw=json.dumps(obj)
        self.assertNotIn('hostname',obj.keys())
        self.assertNotIn('source',obj.keys())
        self.assertFalse(obj['privacy']['hostnames'])
        self.assertNotIn('password=',raw)
        self.assertNotIn('SSH_PRIVATE_KEY',raw)
        self.assertFalse(obj['privacy']['raw_logs'])
        self.assertFalse(obj['privacy']['addresses'])
        self.assertEqual(obj['incident_sample']['max_entries'],300)

    def test_report_no_overwrite_and_mode(self):
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td)/'report.json'
            r=subprocess.run(['sh',str(COLLECTOR),'--output',str(dest)],capture_output=True,timeout=30)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(stat.S_IMODE(dest.stat().st_mode),0o600)
            self.assertNotEqual(subprocess.run(['sh',str(COLLECTOR),'--output',str(dest)],capture_output=True,timeout=30).returncode,0)

    def test_unknown_not_equivalent_to_safe(self):
        obj=example()
        for section in ext.SCHEMA:
            for key in ext.SCHEMA[section]:
                if key not in ('max_entries','window_hours'):
                    obj[section][key]=None
        obj['checks']={k:'unavailable' for k in ext.CHECKS}
        analyzed=ext.analyze(obj)
        self.assertEqual(analyzed['findings'],[])
        self.assertEqual(set(analyzed['unknown_checks']),ext.CHECKS)

    def test_synthetic_findings_and_no_auto_remediation(self):
        obj=example()
        obj['storage']['root_inode_used_percent']=96
        obj['storage']['root_read_only']=True
        obj['security']['sshd_global_root_login']='yes'
        obj['security']['sshd_global_empty_passwords']='yes'
        obj['security']['kernel_dmesg_restrict']=0
        obj['incident_sample']['oom_mentions']=2
        obj['incident_sample']['io_error_mentions']=1
        out=ext.analyze(obj)
        codes={x['code'] for x in out['findings']}
        self.assertTrue({'DC-STOR-101','DC-STOR-102','DC-SSH-101','DC-INC-101','DC-INC-102','DC-HARD-105'} <= codes)
        html=ext.render_html(obj,out)
        self.assertNotIn('<script',html)
        self.assertIn("default-src 'none'",html)
        self.assertIn('Ninguna acción fue ejecutada',html)

    def test_injected_fields_or_sensitive_data_rejected(self):
        base=example()
        for injected in ({'host':'server.real.invalid'},{'credentials':'bad'}):
            obj=copy.deepcopy(base);obj.update(injected)
            with self.assertRaises(ValueError):ext.validate(obj)
        obj=copy.deepcopy(base);obj['security']['password']='secret'
        with self.assertRaises(ValueError):ext.validate(obj)
        obj=copy.deepcopy(base);obj['checks']['sshd']='compliant'
        with self.assertRaises(ValueError):ext.validate(obj)

    def test_cli_extended_local_private_artifacts(self):
        if not sys.platform.startswith('linux'):self.skipTest('Linux-only local')
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)/'state'
            with mock.patch.object(cli,'state_dir',return_value=home):
                with mock.patch.object(cli.webbrowser,'open') as open_view:
                    rc=cli.main(['auditar','--local','--no-abrir'])
            self.assertEqual(rc,0)
            self.assertFalse(open_view.called)
            paths=list((home/'reports').glob('auditoria-*.json'))
            self.assertEqual(len(paths),1)
            self.assertTrue(paths[0].with_suffix('.html').exists())
            self.assertEqual(stat.S_IMODE(paths[0].stat().st_mode),0o600)

    def test_ssh_command_uses_only_stdin_and_fails_closed(self):
        p={'host':'192.0.2.10','port':22,'user':'diagnostic','auth':'agent','key_path':None}
        sample=example()
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(cli,'ssh_argv',return_value=['ssh','safe-target','initial']) as ssh_args:
                def mock_run(argv,**kwargs):
                    self.assertEqual(argv[-1],'sh -s -- --stdout')
                    self.assertIn(b'"private_extended"',kwargs['input'])
                    kwargs['stdout'].write(json.dumps(sample).encode())
                    return type('Response',(),{'returncode':0})()
                with mock.patch.object(cli.subprocess,'run',side_effect=mock_run):
                    # example() uses subprocess.check_output, not subprocess.run.
                    path=cli.collect_extended(Path(td)/'state',p)
            self.assertTrue(path.is_file())
            self.assertTrue(ssh_args.called)


class HardeningTests(unittest.TestCase):
    def test_plan_and_controls_are_safe_by_default(self):
        self.assertEqual(set(hard.CONTROLS),{'fs.protected_hardlinks','fs.protected_symlinks','kernel.dmesg_restrict','kernel.kptr_restrict'})
        with self.assertRaises(hard.HardeningError):hard.parse_controls('net.ipv4.ip_forward')
        with self.assertRaises(hard.HardeningError):hard.parse_controls('kernel.kptr_restrict,kernel.kptr_restrict')
        r=subprocess.run([sys.executable,str(HARDENING),'--plan'],capture_output=True,text=True,timeout=5)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('NO SE HA MODIFICADO NADA',r.stdout)

    def test_apply_without_interactive_console_refused(self):
        r=subprocess.run([sys.executable,str(HARDENING),'--apply','fs.protected_hardlinks'],input='',capture_output=True,text=True,timeout=5)
        self.assertNotEqual(r.returncode,0)

    def test_mocked_apply_rollback_and_checkpoints(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)/'rootstate'; folder.mkdir()
            file=Path(td)/'sysctl-managed.conf'
            values={'fs.protected_hardlinks':'0','fs.protected_symlinks':'0'}
            def set_fake(k,v):values[k]=v
            with mock.patch.object(hard,'STATE_DIR',folder),mock.patch.object(hard,'MANAGED',file),\
                 mock.patch.object(hard,'secure_state',return_value=folder),\
                 mock.patch.object(hard,'require_operator'),\
                 mock.patch.object(hard,'current',side_effect=lambda k:values[k]),\
                 mock.patch.object(hard,'set_runtime',side_effect=set_fake):
                hard.apply(['fs.protected_hardlinks'])
                self.assertEqual(values['fs.protected_hardlinks'],'1')
                pending=list(folder.glob('pending-*.json'))
                self.assertEqual(len(pending),1)
                self.assertIn('fs.protected_hardlinks = 1',file.read_text())
                snapshot_id=pending[0].stem.split('-',1)[1]
                hard.rollback(snapshot_id)
                self.assertFalse(file.exists())
                self.assertEqual(values['fs.protected_hardlinks'],'0')
                self.assertEqual(len(list(folder.glob('pending-*.json'))),0)
                self.assertEqual(len(list(folder.glob('completed-*.json'))),1)

    def test_rollback_refuses_external_runtime_changes(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)/'rootstate';folder.mkdir()
            managed=Path(td)/'managed.conf'
            values={'fs.protected_hardlinks':'0'}
            with mock.patch.object(hard,'STATE_DIR',folder),\
                 mock.patch.object(hard,'MANAGED',managed),\
                 mock.patch.object(hard,'secure_state',return_value=folder),\
                 mock.patch.object(hard,'require_operator'),\
                 mock.patch.object(hard,'current',side_effect=lambda k:values[k]),\
                 mock.patch.object(hard,'set_runtime',side_effect=lambda k,v:values.__setitem__(k,v)):
                hard.apply(['fs.protected_hardlinks'])
                pending=list(folder.glob('pending-*.json'))
                self.assertEqual(len(pending),1)
                op=pending[0].stem.split('-',1)[1]
                # Simulate an authorized administrator changing the runtime.
                values['fs.protected_hardlinks']='2'
                with self.assertRaises(hard.HardeningError):
                    hard.rollback(op)
                self.assertTrue(managed.exists())
                self.assertTrue(pending[0].exists())
                self.assertEqual(values['fs.protected_hardlinks'],'2')
                values['fs.protected_hardlinks']='1'
                hard.rollback(op)
                self.assertFalse(managed.exists())

    def test_existing_foreign_sysctl_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/'managed.conf';file.write_text('kernel.dmesg_restrict=0\n')
            with mock.patch.object(hard,'MANAGED',file):
                with self.assertRaises(hard.HardeningError):hard.read_managed_config()
            self.assertEqual(file.read_text(),'kernel.dmesg_restrict=0\n')

if __name__=='__main__':unittest.main()
