#!/usr/bin/env python3
"""Diagnostico Comunitario: asistente local y analizador determinista.

Python 3.9+ stdlib. No model calls, telemetry, HTTP, SMTP or cloud requests.
Remote mode makes an explicit outbound SSH connection to an approved target.
No guarantees of secrecy from an AI process sharing the same OS account.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import webbrowser

ROOT = Path(__file__).resolve().parent
COLLECTOR = ROOT / 'bin' / 'serverdiag.sh'
CATALOG = ROOT / 'knowledge' / 'catalog.json'
SECTIONS = ('system', 'memory', 'disk', 'database', 'processes')
MAX_JSON_BYTES = 2 * 1024 * 1024


class DiagnosticError(Exception):
    pass


def state_dir() -> Path:
    """Private state outside the source checkout. No env override by design."""
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA') or (Path.home() / 'AppData' / 'Local'))
        return base / 'DiagnosticoComunitario'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'DiagnosticoComunitario'
    return Path.home() / '.local' / 'state' / 'diagnostico-comunitario'


def safe_dir(path: Path) -> Path:
    """Create storage 0700 on POSIX. Refuse symlinked final dir."""
    if path.is_symlink():
        raise DiagnosticError('El directorio de trabajo no puede ser un enlace simbólico')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise DiagnosticError('Directorio de trabajo inválido')
    if os.name != 'nt':
        os.chmod(path, 0o700)
    return path


def private_write(path: Path, content: bytes):
    """Exclusive create, never overwrite, no symlink following."""
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, 'wb') as handle:
            fd = -1
            handle.write(content)
            handle.flush()
    finally:
        if fd >= 0:
            os.close(fd)


def validate_host(host):
    import ipaddress
    host = host.strip()
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?', host):
        raise DiagnosticError('El host debe ser un nombre DNS o una IP sin opciones ni espacios')
    return host


def validate_profile(profile):
    if not isinstance(profile, dict) or set(profile) != {'host','port','user','auth','key_path'}:
        raise DiagnosticError('Perfil de conexión inválido')
    host = validate_host(profile['host'])
    port = profile['port']
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise DiagnosticError('Puerto SSH inválido')
    user = profile['user']
    if not isinstance(user, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]{0,63}', user):
        raise DiagnosticError('Usuario SSH inválido')
    if profile['auth'] not in ('agent', 'key', 'password'):
        raise DiagnosticError('Método SSH no permitido')
    key_path = profile['key_path']
    if profile['auth'] == 'key':
        if not isinstance(key_path, str) or not key_path:
            raise DiagnosticError('Indica una ruta local de llave privada')
        p = Path(key_path).expanduser()
        if not p.is_absolute() or not p.is_file():
            raise DiagnosticError('No se encontró la llave privada local')
    elif key_path is not None:
        raise DiagnosticError('key_path debe ser null fuera del modo key')
    return {**profile, 'host':host}


def read_profiles(home: Path):
    path = home / 'profiles.json'
    if not path.exists():
        return {}
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 128 * 1024:
        raise DiagnosticError('Archivo de perfiles inválido')
    if os.name != 'nt' and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise DiagnosticError('Perfiles con permisos inseguros; usar chmod 600')
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, UnicodeError) as exc:
        raise DiagnosticError('No se pueden leer los perfiles') from exc
    if not isinstance(value, dict) or len(value) > 100:
        raise DiagnosticError('Estructura de perfiles inválida')
    for alias, profile in value.items():
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,39}', alias):
            raise DiagnosticError('Alias de perfil inválido')
        validate_profile(profile)
    return value


def save_profiles(home: Path, profiles):
    safe_dir(home)
    # Atomic replacement; temporary file is private. Same-UID agents remain a risk.
    tmp = home / ('.profiles-' + secrets.token_hex(8))
    private_write(tmp, (json.dumps(profiles, ensure_ascii=True, indent=2) + '\n').encode('utf-8'))
    try:
        os.replace(tmp, home / 'profiles.json')
    finally:
        if tmp.exists():
            tmp.unlink()


def prompt(label, default=None):
    postfix = (' [' + str(default) + ']') if default is not None else ''
    value = input(label + postfix + ': ').strip()
    if not value and default is not None:
        return str(default)
    if not value:
        raise DiagnosticError('Este dato es obligatorio')
    return value


def setup(home: Path):
    print('\nDiagnóstico Comunitario — configuración guiada')
    print('La configuración se guarda fuera del repositorio; no almacena contraseñas.')
    kind = prompt('Tipo de diagnóstico: local / ssh', 'ssh').lower()
    if kind == 'local':
        print('Listo. Ejecútalo con: python diagnostico.py ejecutar --local')
        return
    if kind != 'ssh':
        raise DiagnosticError('Selecciona local o ssh')
    alias = prompt('Alias corto para identificar esta conexión', 'servidor-01').lower()
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,39}', alias):
        raise DiagnosticError('Alias inválido; usa letras, números y guiones')
    host = validate_host(prompt('IP o nombre DNS'))
    port = int(prompt('Puerto SSH', 22))
    user = prompt('Usuario SSH (preferiblemente no root)', 'diagnostic')
    auth = prompt('Autenticación: agent / key / password', 'agent').lower()
    key_path = prompt('Ruta COMPLETA de la llave privada') if auth == 'key' else None
    profile = validate_profile(dict(host=host, port=port, user=user, auth=auth, key_path=key_path))
    profiles = read_profiles(home)
    if alias in profiles and prompt('¿Reemplazar este perfil? escribe SI') != 'SI':
        print('Configuración no modificada.')
        return
    profiles[alias] = profile
    save_profiles(home, profiles)
    print('\nPerfil guardado. La contraseña no se ha solicitado ni almacenado.')
    print('Antes del primer diagnóstico, verifica la huella SSH del equipo mediante')
    print('una fuente independiente y acepta la clave en una sesión SSH manual.')
    print('No usaremos StrictHostKeyChecking=no ni accept-new automáticamente.')
    print('Después ejecuta: python diagnostico.py ejecutar --perfil ' + alias)


def validate_sections(value):
    parts = value.split(',')
    if not parts or any(x not in SECTIONS for x in parts):
        raise DiagnosticError('Secciones permitidas: ' + ','.join(SECTIONS))
    return ','.join(dict.fromkeys(parts))


def ssh_argv(profile, only):
    profile = validate_profile(profile)
    ssh = shutil.which('ssh')
    if not ssh:
        raise DiagnosticError('No se encontró OpenSSH. Instálalo mediante las herramientas oficiales del sistema')
    # No shell=True, no custom user ssh config (ProxyCommand/LocalCommand).
    args = [ssh, '-F', 'none', '-T', '-p', str(profile['port']),
            '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=15',
            '-o', 'ConnectionAttempts=1', '-o', 'ClearAllForwardings=yes',
            '-o', 'ForwardAgent=no', '-o', 'PermitLocalCommand=no',
            '-o', 'LogLevel=ERROR', '-o', 'ProxyCommand=none',
            '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=2']
    if profile['auth'] == 'key':
        args += ['-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-i', str(Path(profile['key_path']).expanduser())]
    elif profile['auth'] == 'agent':
        args += ['-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=no']
    else:
        # Interactive password prompt belongs to local SSH console, never Python/agent.
        args += ['-o', 'BatchMode=no', '-o', 'NumberOfPasswordPrompts=1',
                 '-o', 'PubkeyAuthentication=no', '-o', 'PreferredAuthentications=password,keyboard-interactive']
    args += ['--', profile['user'] + '@' + profile['host'],
             'sh -s -- --stdout --only ' + only]
    return args


def narrow_ssh_env():
    names = ('PATH','HOME','USER','LOGNAME','LANG','LC_ALL','LC_CTYPE',
             'SYSTEMROOT','WINDIR','USERPROFILE','APPDATA','LOCALAPPDATA',
             'TEMP','TMP','SSH_AUTH_SOCK','SSH_AGENT_PID')
    return {k:os.environ[k] for k in names if k in os.environ}


def collect(home: Path, only: str, profile: dict | None):
    safe_dir(home)
    reports = safe_dir(home / 'reports')
    if not COLLECTOR.is_file():
        raise DiagnosticError('No se encontró el colector Bash del proyecto')
    if profile is None:
        if os.name == 'nt':
            raise DiagnosticError('Diagnóstico local requiere Linux; en Windows utiliza SSH')
        if not shutil.which('sh'):
            raise DiagnosticError('Este equipo no dispone de sh')
        argv = ['sh', str(COLLECTOR), '--stdout', '--only', only]
    else:
        argv = ssh_argv(profile, only)
    # stdout/stderr go to private temporary files; never to Codex terminal.
    fd, tempname = tempfile.mkstemp(prefix='.capture-', dir=reports)
    os.chmod(tempname, 0o600) if os.name != 'nt' else None
    try:
        with os.fdopen(fd, 'wb') as captured, tempfile.TemporaryFile() as errors:
            kwargs = dict(stdout=captured, stderr=errors, timeout=75, check=False, env=narrow_ssh_env())
            if profile is not None:
                kwargs['input'] = COLLECTOR.read_bytes()
            run = subprocess.run(argv, **kwargs)
            if run.returncode:
                raise DiagnosticError('La recolección no pudo completarse. Verifica el acceso SSH, la llave y la huella en una terminal privada')
        tmp = Path(tempname)
        if tmp.stat().st_size > MAX_JSON_BYTES:
            raise DiagnosticError('La captura excede el tamaño máximo permitido')
        raw = tmp.read_bytes()
        obj = read_diagnostic(raw)
        name = 'diagnostico-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(5)
        path = reports / (name + '.json')
        private_write(path, raw)
        return path, obj
    except subprocess.TimeoutExpired as exc:
        raise DiagnosticError('Tiempo de espera agotado, no se generó informe') from exc
    finally:
        Path(tempname).unlink(missing_ok=True)


def reject_duplicates(pairs):
    out = {}
    for k,v in pairs:
        if k in out:
            raise ValueError('Campo duplicado')
        out[k] = v
    return out


def read_diagnostic(raw):
    if len(raw) > MAX_JSON_BYTES:
        raise DiagnosticError('Informe demasiado grande')
    try:
        obj = json.loads(raw, object_pairs_hook=reject_duplicates,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Número no finito')))
    except (ValueError, UnicodeError) as exc:
        raise DiagnosticError('Salida no corresponde a un JSON válido') from exc
    if not isinstance(obj, dict) or obj.get('schema_version') != '1.0' or obj.get('report_type') != 'private':
        raise DiagnosticError('Contrato JSON privado incompatible')
    if any(not isinstance(obj.get(k), dict) for k in ('source','metrics','checks','privacy')):
        raise DiagnosticError('Contrato JSON incompleto')
    if not isinstance(obj.get('findings'), list):
        raise DiagnosticError('Hallazgos inválidos')
    return obj


def load_catalog():
    entries = json.loads(CATALOG.read_text(encoding='utf-8'))
    if not isinstance(entries, list) or len(entries) < 15 or len(entries) > 40:
        raise DiagnosticError('Catálogo de diagnóstico inválido')
    return {entry['code']:entry for entry in entries}


def metric(obj, group, key):
    section = obj['metrics'].get(group)
    if not isinstance(section, dict):
        return None
    v = section.get(key)
    return v if isinstance(v,(int,float)) and not isinstance(v,bool) else None


def analyze(obj):
    """Facts only: finite numeric thresholds, no claims of causality or server outage."""
    findings = []
    def emit(code, evidence):
        findings.append(dict(code=code,evidence=evidence))
    disk = metric(obj,'disk_root','used_percent')
    if disk is not None:
        if disk >= 95: emit('DC-DISK-002', f'Disco raíz al {disk}% (>=95%)')
        elif disk >= 85: emit('DC-DISK-001', f'Disco raíz al {disk}% (>=85%)')
    mem = metric(obj,'memory','total_bytes')
    avail = metric(obj,'memory','available_bytes')
    if mem is not None and mem > 0 and avail is not None and 0 <= avail <= mem:
        ratio = avail/mem
        if ratio <= 0.05: emit('DC-MEM-002', f'MemAvailable ~{ratio*100:.1f}% del total')
        elif ratio <= 0.15: emit('DC-MEM-001', f'MemAvailable ~{ratio*100:.1f}% del total')
    st = metric(obj,'memory','swap_total_bytes')
    sf = metric(obj,'memory','swap_free_bytes')
    if st is not None and st>0 and sf is not None and 0 <= sf <= st and (st-sf)/st>=0.8:
        emit('DC-MEM-003', f'Swap utilizada ~{(st-sf)/st*100:.1f}% (no confirma presión actual)')
    cores = metric(obj,'system','cpu_cores')
    load = metric(obj,'system','load_1m')
    if cores is not None and cores>0 and load is not None and load>2*cores:
        emit('DC-SYS-001',f'Load 1 min={load:.2f} para {cores} CPU lógicas')
    uptime = metric(obj,'system','uptime_seconds')
    if uptime is not None and uptime < 1800:
        emit('DC-SYS-002',f'Uptime={uptime:.0f}s, reinicio reciente o arranque nuevo')
    # Presence/absence is not enough to assert that an optional service has failed.
    db = obj['metrics'].get('database') or {}
    if isinstance(db, dict):
        count = db.get('mysql_process_count')
        listen = db.get('tcp_3306_listening')
        if isinstance(count,int) and not isinstance(count,bool):
            if count>0 and listen is False:
                emit('DC-DB-001','Proceso MySQL/MariaDB observado; puerto TCP 3306 no escuchando (puede usar socket Unix u otro puerto)')
            if count==0 and listen is True:
                emit('DC-DB-002','Puerto TCP 3306 escuchando sin proceso MySQL/MariaDB reconocido; revisar propietario localmente')
    ssh = metric(obj,'processes','sshd_process_count')
    if ssh == 0:
        emit('DC-SSH-001','No se identificó proceso sshd en el instante de la captura; no prueba que SSH esté inaccesible')
    unavailable=[k for k,v in obj['checks'].items() if v == 'unavailable']
    return {'findings':findings,'unavailable_checks':unavailable,
            'observed_at':obj.get('collected_at','unknown'),
            'message':'Sin alertas automáticas para las métricas disponibles' if not findings else 'Se identificaron condiciones que requieren revisión'}


def render_html(obj, analysis, catalog):
    def h(value): return html.escape(str(value), quote=True)
    source = obj['source']
    rows=[]
    for category,metrics in obj['metrics'].items():
        if isinstance(metrics,dict):
            for key,value in metrics.items():
                rows.append(f'<tr><td>{h(category)}.{h(key)}</td><td>{h("sin datos" if value is None else value)}</td></tr>')
    cards=[]
    for f in analysis['findings']:
        guide=catalog.get(f['code'],{})
        steps=''.join('<li>'+h(x)+'</li>' for x in guide.get('checks',[]))
        cautions=''.join('<li>'+h(x)+'</li>' for x in guide.get('warnings',[]))
        cards.append(f'<article><h3>{h(f["code"])} · {h(guide.get("title","Revisar"))}</h3>'
                     f'<p><strong>Evidencia:</strong> {h(f["evidence"])}</p>'
                     f'<p>Estos datos no confirman por sí solos una causa.</p><h4>Verificaciones sugeridas</h4>'
                     f'<ol>{steps}</ol><h4>Precauciones</h4><ul>{cautions}</ul></article>')
    return ("<!doctype html><html lang='es'><head><meta charset='utf-8'>"
            "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
            "<title>Diagnóstico Comunitario · Informe privado</title>"
            "<style>body{font:16px system-ui;margin:3em auto;max-width:880px;padding:0 1em;color:#162236}"
            "article{border:1px solid #cad0d8;border-radius:12px;padding:1em;margin:1em 0}"
            "td,th{border-bottom:1px solid #ddd;padding:.45em;text-align:left}table{border-collapse:collapse;width:100%}"
            "small{color:#586579} .notice{background:#eef3f7;padding:1em;border-radius:9px}</style></head><body>"
            "<h1>Diagnóstico Comunitario</h1><p class='notice'>Informe PRIVADO generado localmente; "
            "no compartir esta página. Sin contenido remoto, scripts ni analítica externa.</p>"
            f"<p><strong>Equipo:</strong> {h(source.get('hostname','no identificado'))} · "
            f"<strong>UTC:</strong> {h(obj.get('collected_at','?'))}</p>"
            f"<p>{h(analysis['message'])}. Las comprobaciones disponibles no prueban la salud global.</p>"
            "<h2>Hallazgos observados</h2>" + (''.join(cards) if cards else '<p>No se detectaron alertas en los umbrales configurados.</p>')
            + '<h2>Métricas locales</h2><table><thead><tr><th>Indicador</th><th>Valor</th></tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table><h2>Comprobaciones sin datos</h2><p>'
            + h(', '.join(analysis['unavailable_checks']) or 'Ninguna marcada')
            + '</p><small>Hechos observados ≠ hipótesis ≠ causas confirmadas. El proyecto no ejecuta reparaciones.</small></body></html>')


def run_diagnostic(home:Path, profile_alias, only, local, open_view):
    only=validate_sections(only)
    profile=None
    if not local:
        if not profile_alias:
            raise DiagnosticError('Usa --perfil ALIAS o --local; para nuevos usuarios: python diagnostico.py configurar')
        profiles=read_profiles(home)
        if profile_alias not in profiles:
            raise DiagnosticError('Perfil no encontrado. Ejecuta configurar.')
        profile=profiles[profile_alias]
    path,obj=collect(home,only,profile)
    result=analyze(obj)
    page=path.with_suffix('.html')
    private_write(page,render_html(obj,result,load_catalog()).encode('utf-8'))
    print('Diagnóstico completado. Reporte guardado en un directorio privado del usuario.')
    print('Abre el informe local desde la terminal de confianza (no desde el contexto de Codex).')
    if open_view:
        webbrowser.open(page.as_uri())
    return 0


def list_guides(code=None):
    catalog=load_catalog()
    if code:
        guide=catalog.get(code)
        if not guide:
            raise DiagnosticError('Guía inexistente')
        print(guide['code']+' - '+guide['title'])
        print('Alcance: '+('detección automática' if guide['automatic'] else 'guía manual, no detectada automáticamente'))
        print('Comprobaciones recomendadas:')
        for x in guide['checks']:
            print(' - '+x)
        return
    print('Guías comunitarias (los códigos no representan diagnósticos de tu equipo):')
    for item in catalog.values():
        print(f" {item['code']}: {item['title']} ({'automática' if item['automatic'] else 'manual'})")


def compare(home, left, right):
    # Explicit user-only command: never called by Codex strict skill.
    reports=safe_dir(home/'reports').resolve()
    def read(path):
        p=Path(path).expanduser().resolve()
        if p.parent != reports or not p.is_file():
            raise DiagnosticError('Solo se comparan JSON del directorio privado de reportes')
        return read_diagnostic(p.read_bytes())
    a,b=read(left),read(right)
    print('Comparación local; los resultados siguientes contienen datos reales y no deben pegarse en Codex.')
    for group in ('system','memory','disk_root','database','processes'):
        ga=a['metrics'].get(group) or {}; gb=b['metrics'].get(group) or {}
        for key in set(ga)|set(gb):
            va,vb=ga.get(key),gb.get(key)
            if va != vb:
                print(f'{group}.{key}: {va} -> {vb}')


def main(argv=None):
    ap=argparse.ArgumentParser(prog='diagnostico.py', description='Diagnóstico Linux local/SSH, sin IA ni transferencias externas')
    sub=ap.add_subparsers(dest='command')
    sub.add_parser('configurar',help='Asistente para configurar un servidor SSH')
    p=sub.add_parser('ejecutar',help='Recopila, analiza localmente y genera HTML privado')
    p.add_argument('--perfil', help='Alias de servidor preconfigurado')
    p.add_argument('--local', action='store_true',help='Ejecuta diagnóstico en este Linux')
    p.add_argument('--only',default=','.join(SECTIONS),help='system,memory,disk,database,processes')
    p.add_argument('--no-abrir',action='store_true',help='No abrir visor privado al terminar')
    p=sub.add_parser('guias', help='Consulta documentación pública sin datos de servidores')
    p.add_argument('--codigo',help='Código de guía (p.ej. DC-DISK-001)')
    p=sub.add_parser('comparar',help='Compara dos JSON privados en terminal local de confianza')
    p.add_argument('anterior');p.add_argument('nuevo')
    p=sub.add_parser('estado',help='Estado genérico, sin diagnóstico ni datos de servidores')
    args=ap.parse_args(argv)
    try:
        home=state_dir()
        if args.command is None:
            # Beginner: one command enters setup. Keep it local and interactive.
            setup(home)
        elif args.command=='configurar':
            setup(home)
        elif args.command=='ejecutar':
            if args.local and args.perfil:
                raise DiagnosticError('--local y --perfil son excluyentes')
            return run_diagnostic(home,args.perfil,args.only,args.local,not args.no_abrir)
        elif args.command=='guias':
            list_guides(args.codigo)
        elif args.command=='comparar':
            compare(home,args.anterior,args.nuevo)
        else:
            print('Diagnóstico Comunitario: herramienta disponible. No hay datos de servidores en esta respuesta.')
    except (DiagnosticError,ValueError,OSError) as exc:
        # For CLI used by humans only; never send stderr verbatim to Codex tools.
        print('Error: '+str(exc),file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':
    sys.exit(main())
