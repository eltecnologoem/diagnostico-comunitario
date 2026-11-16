#!/usr/bin/env python3
"""Hardening Linux altamente restringido, con confirmación manual y rollback.

NO es el recolector: este programa PUEDE modificar sysctl si root ejecuta --apply
localmente desde una terminal. Nunca se debe invocar desde Codex ni SSH remoto.
No cambia sshd, UFW/nftables, apt, ni reinicia servicios.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import uuid

CONTROLS = {
    'fs.protected_hardlinks': ('1', 'Previene ciertos ataques mediante hardlinks; comprobar workloads de enlaces.'),
    'fs.protected_symlinks': ('1', 'Reduce ataques con symlinks en directorios sticky; revisar apps legacy.'),
    'kernel.dmesg_restrict': ('1', 'Restringe dmesg a usuarios privilegiados; afecta troubleshooting sin root.'),
    'kernel.kptr_restrict': ('2', 'Oculta punteros kernel; puede limitar depuración, eBPF y diagnósticos.'),
}
MANAGED = Path('/etc/sysctl.d/99-diagnostico-comunitario.conf')
STATE_DIR = Path('/var/lib/diagnostico-comunitario/hardening')
MARKER = '# managed-by: Diagnostico Comunitario - cambios autorizados por operador\n'
ACK_APPLY = 'APLICAR HARDENING LOCAL'
ACK_ROLLBACK = 'REVERTIR HARDENING LOCAL'


class HardeningError(Exception):
    pass


def os_compatible():
    try:
        lines=Path('/etc/os-release').read_text(encoding='utf-8').splitlines()
    except OSError:
        return False
    values={}
    for line in lines:
        if '=' in line:
            k,v=line.split('=',1); values[k]=v.strip('"\'')
    return values.get('ID') in ('debian','ubuntu')


def sysctl_file(control):
    if control not in CONTROLS: raise HardeningError('Control no aprobado')
    return Path('/proc/sys')/control.replace('.','/')


def current(control):
    p=sysctl_file(control)
    try:
        v=p.read_text(encoding='ascii').strip()
    except OSError as exc:
        raise HardeningError('Control no disponible en este kernel') from exc
    if not re.fullmatch(r'\d{1,3}',v): raise HardeningError('Valor kernel no esperado')
    return v


def parse_controls(value):
    parts=value.split(',')
    if not parts or any(x not in CONTROLS for x in parts) or len(parts)!=len(set(parts)):
        raise HardeningError('Control no permitido o repetido; use --list')
    return parts


def read_managed_config():
    if MANAGED.is_symlink(): raise HardeningError('El archivo gestionado no debe ser symlink')
    if not MANAGED.exists(): return None, {}
    if not MANAGED.is_file() or MANAGED.stat().st_size>8192:
        raise HardeningError('Archivo de configuración no esperado')
    raw=MANAGED.read_bytes()
    text=raw.decode('utf-8')
    if not text.startswith(MARKER):
        raise HardeningError('Existe un sysctl ajeno con mismo nombre: no sobrescribir')
    kv={}
    for line in text.splitlines()[1:]:
        if not line.strip(): continue
        if '=' not in line: raise HardeningError('Archivo de sysctl con formato desconocido')
        k,v=(x.strip() for x in line.split('=',1))
        if k not in CONTROLS or v!=CONTROLS[k][0] or k in kv:
            raise HardeningError('Archivo gestionado modificado; intervención manual')
        kv[k]=v
    return raw,kv


def secure_state():
    for d in (STATE_DIR.parent, STATE_DIR):
        if d.is_symlink(): raise HardeningError('Directorio de respaldo no confiable')
        d.mkdir(mode=0o700,parents=True,exist_ok=True)
        st=d.stat()
        if st.st_uid != 0 or not stat.S_ISDIR(st.st_mode) or (st.st_mode & 0o077):
            raise HardeningError('Respaldo debe ser directorio root 0700')
    return STATE_DIR


def atomic_write(path,raw,mode=0o600):
    if path.is_symlink(): raise HardeningError('No escribir en enlace simbólico')
    tmp=path.with_name('.'+path.name+'-'+uuid.uuid4().hex)
    fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,'O_NOFOLLOW',0),mode)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if tmp.exists(): tmp.unlink()


def sysctl_binary():
    for p in ('/usr/sbin/sysctl','/sbin/sysctl','/usr/bin/sysctl','/bin/sysctl'):
        if os.path.isfile(p) and os.access(p,os.X_OK):
            return p
    raise HardeningError('sysctl no disponible')


def set_runtime(control,value):
    result=subprocess.run([sysctl_binary(),'-w',f'{control}={value}'],capture_output=True,timeout=10,check=False)
    if result.returncode != 0 or current(control) != value:
        raise HardeningError('No se pudo verificar el cambio de kernel')


def require_operator(action):
    if not sys.platform.startswith('linux') or not os_compatible():
        raise HardeningError('Aplicación limitada a Debian/Ubuntu Linux')
    if os.geteuid()!=0:
        raise HardeningError('Aplicación requiere root y consola de recuperación')
    if any(os.environ.get(k) for k in ('SSH_CONNECTION','SSH_CLIENT','SSH_TTY')):
        raise HardeningError('Aplicación por SSH deshabilitada; usa acceso de consola verificado')
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise HardeningError('Aplicación requiere confirmación interactiva desde terminal')
    print('ADVERTENCIA: esto modifica configuración del sistema. Exija copia de seguridad y acceso de consola.')
    expected=ACK_APPLY if action=='apply' else ACK_ROLLBACK
    if input('Escribe exactamente '+expected+': ').strip()!=expected:
        raise HardeningError('No se autorizó la operación')


def plan():
    print('HARDENING: PLAN LOCAL, NO SE HA MODIFICADO NADA')
    print('No incluye cambios automáticos a SSH, firewall, AppArmor o APT.')
    for k,(target,impact) in CONTROLS.items():
        try: now=current(k)
        except HardeningError: now='no disponible'
        print(f'- {k}: actual={now}, propuesto={target}. Impacto: {impact}')
    print('Ejemplo (solo desde terminal local autorizada):')
    print('sudo python3 tools/hardening.py --apply fs.protected_hardlinks,fs.protected_symlinks')


def apply(controls):
    require_operator('apply')
    import fcntl  # Linux-only; avoids import failure for Windows users inspecting --plan
    folder=secure_state()
    # Keep exactly one outstanding state to avoid ambiguous rollback ordering.
    with (folder/'lock').open('a+b') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        if list(folder.glob('pending-*.json')):
            raise HardeningError('Existe una operación anterior pendiente de rollback; no apilar cambios')
        original,oldkv=read_managed_config()
        previous={k:current(k) for k in controls}
        desired=dict(oldkv)
        for k in controls: desired[k]=CONTROLS[k][0]
        new_bytes=(MARKER+''.join(f'{k} = {desired[k]}\n' for k in sorted(desired))).encode()
        operation_id=uuid.uuid4().hex
        state={
            'version':1,'operation_id':operation_id,
            'timestamp_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'controls':controls,'previous_runtime':previous,
            'original_config_b64':base64.b64encode(original).decode() if original is not None else None,
            'new_config_sha256':hashlib.sha256(new_bytes).hexdigest(),
        }
        snapshot=folder/('pending-'+operation_id+'.json')
        atomic_write(snapshot,json.dumps(state,sort_keys=True).encode(),mode=0o600)
        try:
            atomic_write(MANAGED,new_bytes)
            for k in controls: set_runtime(k,CONTROLS[k][0])
        except Exception:
            # Snapshot remains for manual recovery even if automatic compensation fails.
            try:
                if original is None: MANAGED.unlink(missing_ok=True)
                else: atomic_write(MANAGED,original)
                for k,v in previous.items(): set_runtime(k,v)
            except Exception:
                raise HardeningError('Falló la aplicación y la reversión; usar consola y snapshot root')
            snapshot.unlink(missing_ok=True)
            raise HardeningError('Aplicación falló; configuración anterior restaurada')
        print('Aplicación limitada completada. ID de respaldo: '+operation_id)
        print('Verifica servicios afectados. Para revertir, usa --rollback '+operation_id)


def rollback(operation_id):
    import fcntl  # Linux-only; rollback requires operator confirmation
    if not re.fullmatch('[0-9a-f]{32}',operation_id):raise HardeningError('ID de respaldo inválido')
    require_operator('rollback')
    folder=secure_state()
    with (folder/'lock').open('a+b') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        snapshot=folder/('pending-'+operation_id+'.json')
        if not snapshot.is_file() or snapshot.is_symlink(): raise HardeningError('Respaldo no encontrado')
        if snapshot.stat().st_size>16384: raise HardeningError('Respaldo inválido')
        state=json.loads(snapshot.read_text())
        if state.get('operation_id')!=operation_id or state.get('version')!=1:
            raise HardeningError('Estado de respaldo incoherente')
        current_raw=MANAGED.read_bytes() if MANAGED.is_file() and not MANAGED.is_symlink() else b''
        if hashlib.sha256(current_raw).hexdigest()!=state['new_config_sha256']:
            raise HardeningError('Archivo de sysctl cambió desde aplicación; no pisar cambios ajenos')
        original_b64=state['original_config_b64']
        old=base64.b64decode(original_b64,validate=True) if original_b64 is not None else None
        previous=state['previous_runtime']
        if not isinstance(previous,dict) or any(k not in CONTROLS or not re.fullmatch(r'\d{1,3}',v) for k,v in previous.items()):
            raise HardeningError('Respaldo contiene valores inesperados')
        if old is None: MANAGED.unlink()
        else: atomic_write(MANAGED,old)
        for k,v in previous.items(): set_runtime(k,v)
        final=folder/('completed-'+operation_id+'.json')
        os.replace(snapshot,final)
        print('Hardening revertido según respaldo; comprueba compatibilidad y reinicio futuro.')


def main(argv=None):
    p=argparse.ArgumentParser(description='Hardening opt-in Debian/Ubuntu: auditar/planificar sin mutación')
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--list',action='store_true',help='Lista de controles admitidos')
    g.add_argument('--plan',action='store_true',help='Muestra cambios propuestos, nunca aplica')
    g.add_argument('--apply',metavar='CONTROL[,CONTROL...]',help='Aplica solo controles permitidos con confirmación interactiva root')
    g.add_argument('--rollback',metavar='ID',help='Restaura un respaldo pendiente con confirmación root')
    a=p.parse_args(argv)
    try:
        if a.list:
            for k,(v,impact) in CONTROLS.items(): print(f'{k} -> {v}: {impact}')
        elif a.plan: plan()
        elif a.apply: apply(parse_controls(a.apply))
        else: rollback(a.rollback)
    except (HardeningError,OSError,ValueError,subprocess.TimeoutExpired) as exc:
        print('ERROR: '+str(exc),file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':sys.exit(main())
