"""QA: no real SSH, servers, credentials, network or user data."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('community_diagnostic_cli',ROOT/'diagnostico.py')
cli=importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def fake_report():
    return {
        'schema_version':'1.0','report_type':'private',
        'collected_at':'2026-11-16T12:00:00Z',
        'source':{'hostname':'very-secret-server.invalid'},
        'metrics':{
            'system':{'cpu_cores':4,'load_1m':0.5,'uptime_seconds':9000},
            'memory':{'total_bytes':100,'available_bytes':20,'swap_total_bytes':0,'swap_free_bytes':0},
            'disk_root':{'used_percent':30},
            'database':{'mysql_process_count':0,'tcp_3306_listening':None},
            'processes':{'sshd_process_count':1}},
        'checks':{'disk_root':'collected','meminfo':'collected','tcp_listeners':'unavailable'},
        'privacy':{},'findings':[]
    }


class DiagnosticAppTests(unittest.TestCase):
    def test_knowledge_20_guides_marked(self):
        catalog=cli.load_catalog()
        self.assertEqual(len(catalog),20)
        self.assertEqual(sum(1 for x in catalog.values() if x['automatic']),10)
        for x in catalog.values():
            self.assertIn(x['severity'],('info','warning','critical','manual'))
            self.assertTrue(x['checks'])
            self.assertTrue(x['warnings'])

    def test_unknown_not_interpreted_as_down(self):
        obj=fake_report();obj['metrics']['disk_root']['used_percent']=None
        obj['metrics']['memory']['available_bytes']=None
        obj['metrics']['processes']['sshd_process_count']=None
        out=cli.analyze(obj)
        self.assertEqual(out['findings'],[])
        self.assertIn('Sin alertas',out['message'])
        self.assertEqual(out['unavailable_checks'],['tcp_listeners'])

    def test_disk_critical_and_memory_warning(self):
        obj=fake_report();obj['metrics']['disk_root']['used_percent']=96
        obj['metrics']['memory']['available_bytes']=10
        out=cli.analyze(obj)
        self.assertEqual({e['code'] for e in out['findings']},{'DC-DISK-002','DC-MEM-001'})

    def test_html_escapes_untrusted_strings_and_has_no_js(self):
        obj=fake_report();obj['source']['hostname']='<script>alert(1)</script>'
        page=cli.render_html(obj,cli.analyze(obj),cli.load_catalog())
        self.assertNotIn('<script>alert',page)
        self.assertIn('&lt;script&gt;',page)
        self.assertIn("default-src 'none'",page)
        self.assertNotIn('https://',page)

    def test_strict_profile_validation(self):
        base={'host':'192.0.2.10','port':2222,'user':'diagnostic','auth':'agent','key_path':None}
        self.assertEqual(cli.validate_profile(base)['port'],2222)
        for key,invalid in (('host','-oProxyCommand=touch'),('user','root;id'),('port',0),('auth','unsafe')):
            with self.subTest(key=key):
                value=dict(base,**{key:invalid})
                with self.assertRaises(cli.DiagnosticError): cli.validate_profile(value)
        with tempfile.TemporaryDirectory() as td:
            key=Path(td)/'key'; key.write_text('NOT AN ACTUAL PRIVATE KEY')
            val=dict(base,auth='key',key_path=str(key))
            self.assertEqual(cli.validate_profile(val)['auth'],'key')

    def test_ssh_arguments_avoid_shell_and_host_key_weakening(self):
        p={'host':'192.0.2.10','port':2222,'user':'diagnostic','auth':'agent','key_path':None}
        with mock.patch.object(cli.shutil,'which',return_value='/usr/bin/ssh'):
            args=cli.ssh_argv(p,'disk,memory')
        joined=' '.join(args)
        self.assertIn('StrictHostKeyChecking=yes',joined)
        self.assertIn('BatchMode=yes',joined)
        self.assertIn('ProxyCommand=none',joined)
        self.assertIn('-F none',joined)
        self.assertIn('sh -s -- --stdout --only disk,memory',joined)
        self.assertNotIn('accept-new',joined)
        self.assertNotIn('StrictHostKeyChecking=no',joined)

    def test_profiles_stored_private_with_no_secret(self):
        p={'host':'192.0.2.10','port':2222,'user':'diagnostic','auth':'agent','key_path':None}
        with tempfile.TemporaryDirectory() as td:
            home=Path(td)/'state'
            cli.save_profiles(home,{'lab':p})
            text=(home/'profiles.json').read_text()
            self.assertNotIn('password',text)
            self.assertEqual(cli.read_profiles(home),{'lab':p})
            if os.name!='nt':
                self.assertEqual(stat.S_IMODE((home/'profiles.json').stat().st_mode),0o600)
                self.assertEqual(stat.S_IMODE(home.stat().st_mode),0o700)

    def test_local_run_generates_private_html_json(self):
        if os.name=='nt':self.skipTest('Linux/mac local collector only')
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(cli,'state_dir',return_value=Path(td)/'home'):
                with mock.patch.object(cli.webbrowser,'open') as opened:
                    rc=cli.main(['ejecutar','--local','--only','disk','--no-abrir'])
            self.assertEqual(rc,0)
            self.assertFalse(opened.called)
            reports=list((Path(td)/'home'/'reports').glob('diagnostico-*.json'))
            self.assertEqual(len(reports),1)
            data=json.loads(reports[0].read_text())
            self.assertEqual(data['checks']['meminfo'],'skipped')
            self.assertEqual(reports[0].with_suffix('.html').is_file(),True)
            if os.name!='nt':
                self.assertEqual(stat.S_IMODE(reports[0].stat().st_mode),0o600)

    def test_sections_validation(self):
        self.assertEqual(cli.validate_sections('disk,memory,disk'),'disk,memory')
        for value in ('','disk,unknown','disk;curl','disk,,memory'):
            with self.subTest(value=value):
                with self.assertRaises(cli.DiagnosticError):cli.validate_sections(value)

    def test_remote_never_called_in_local_run(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(cli,'state_dir',return_value=Path(td)/'home'):
                with mock.patch.object(cli,'collect',side_effect=cli.DiagnosticError('locked')) as collect:
                    self.assertEqual(cli.main(['ejecutar','--perfil','missing','--only','disk','--no-abrir']),1)
                    self.assertFalse(collect.called)


if __name__=='__main__':unittest.main()
