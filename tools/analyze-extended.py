#!/usr/bin/env python3
"""Reglas deterministas locales para diagnósticos extendidos.

No llama a modelos ni servicios remotos y no ejecuta reparaciones.
No imprimir diagnósticos en stdout: el HTML/JSON son privados.
"""
from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
import stat
import sys

MAX_REPORT_BYTES = 64 * 1024

SCHEMA = {
    'storage': {'root_inode_used_percent', 'root_read_only'},
    'process_health': {'zombie_count', 'uninterruptible_count', 'failed_systemd_services'},
    'network': {'interface_count', 'default_ipv4_routes', 'tcp_listening_socket_count'},
    'time': {'ntp_synchronized'},
    'incident_sample': {'kernel_error_entries', 'oom_mentions', 'io_error_mentions', 'max_entries', 'window_hours'},
    'security': {
        'sshd_global_password_auth', 'sshd_global_root_login', 'sshd_global_pubkey_auth',
        'sshd_global_empty_passwords', 'sshd_global_x11_forwarding',
        'apparmor_kernel_enabled', 'unattended_upgrades_installed', 'ufw_status',
        'kernel_kptr_restrict', 'kernel_dmesg_restrict',
        'fs_protected_hardlinks', 'fs_protected_symlinks'
    }
}
CHECKS = {'inodes', 'root_mount', 'processes', 'network', 'systemd', 'ntp',
          'sshd', 'apparmor', 'updates', 'firewall', 'kernel_journal'}
RULES = {
  'DC-INC-101': ('high', 'Mensajes compatibles con OOM en muestra kernel', 'Revisar presión de memoria, cgroups y registros locales; la muestra no prueba causa raíz.'),
  'DC-INC-102': ('high', 'Mensajes compatibles con errores de I/O', 'Verificar discos, filesystem y almacenamiento remoto antes de tareas destructivas.'),
  'DC-INC-103': ('warning', 'Numerosos mensajes de error del kernel', 'Revisar eventos kernel en consola privada; la muestra está limitada y no es completa.'),
  'DC-STOR-101': ('critical', 'Filesystem raíz montado en solo lectura', 'Comprobar fallos de disco y sistema de archivos antes de plantear reparaciones; revisar backups y ventana de mantenimiento.'),
  'DC-STOR-102': ('high', 'Inodos casi agotados', 'Investigar cantidad de ficheros, colas y temporales sin borrar automáticamente.'),
  'DC-PROC-101': ('warning', 'Servicios systemd fallidos', 'Revisar unidades concretas y logs desde la consola privada; no reiniciar en bloque.'),
  'DC-PROC-102': ('warning', 'Procesos en estado ininterrumpible', 'Correlacionar con almacenamiento, NFS y bloqueos de I/O.'),
  'DC-PROC-103': ('info', 'Procesos zombie numerosos', 'Comprobar proceso padre y patrón temporal; un zombie aislado no demuestra fallo.'),
  'DC-NET-101': ('info', 'Sin ruta IPv4 por defecto', 'Confirmar si el servidor es deliberadamente IPv6-only o solo de red interna.'),
  'DC-TIME-101': ('warning', 'NTP no sincronizado', 'Revisar servicio de sincronización y fuentes de tiempo sin cambiar reloj automáticamente.'),
  'DC-SSH-101': ('high', 'SSH permite contraseñas vacías', 'Deshabilitar acceso con contraseñas vacías tras verificar configuración efectiva y alternativas de acceso.'),
  'DC-SSH-102': ('warning', 'Root SSH permitido', 'Evaluar cuentas administrativas con claves y consola alternativa antes de restringir root.'),
  'DC-SSH-103': ('warning', 'Contraseñas SSH permitidas', 'Migrar a llaves/MFA solo tras comprobar accesos y plan de recuperación.'),
  'DC-SSH-104': ('info', 'X11Forwarding habilitado', 'Verificar si el servidor necesita X11 forwarding; desactivarlo solo si no es necesario.'),
  'DC-HARD-101': ('warning', 'Unattended-upgrades no instalado', 'Revisar política de parches y ventanas. Instalado no equivale a configurado ni ejecutándose.'),
  'DC-HARD-102': ('info', 'AppArmor no habilitado en kernel', 'Verificar compatibilidad, perfiles, contenedores y servicios antes de activarlo.'),
  'DC-HARD-103': ('info', 'UFW inactivo', 'No supone ausencia de firewall: comprobar nftables, iptables y controles de red externos.'),
  'DC-HARD-104': ('info', 'Restricción de punteros de kernel insuficiente', 'Evaluar kernel.kptr_restrict=2; puede afectar diagnóstico y trazas.'),
  'DC-HARD-105': ('warning', 'Buffer de mensajes de kernel accesible', 'Evaluar kernel.dmesg_restrict=1; puede limitar recolección de logs por usuarios sin privilegios.'),
  'DC-HARD-106': ('warning', 'Protección de enlaces duros deshabilitada', 'Evaluar fs.protected_hardlinks=1 tras comprobar compatibilidad.'),
  'DC-HARD-107': ('warning', 'Protección de enlaces simbólicos deshabilitada', 'Evaluar fs.protected_symlinks=1 tras comprobar compatibilidad.'),
}


def _boolean_or_null(v):
    return v is None or isinstance(v, bool)


def validate(report):
    if not isinstance(report, dict) or set(report) != {'schema_version', 'report_type', 'collected_at',
                                                       'os_family','os_version', 'storage',
                                                       'process_health', 'network', 'time', 'incident_sample',
                                                       'security', 'checks', 'privacy'}:
        raise ValueError('Estructura de reporte extendido no reconocida')
    if report['schema_version'] != 'extended-1.0' or report['report_type'] != 'private_extended':
        raise ValueError('Esquema extendido incompatible')
    for category, fields in SCHEMA.items():
        obj = report[category]
        if not isinstance(obj, dict) or set(obj) != fields:
            raise ValueError('Campos inválidos en ' + category)
    checks = report['checks']
    if not isinstance(checks,dict) or set(checks) != CHECKS:
        raise ValueError('Estados de comprobación inválidos')
    if any(x not in ('collected','unavailable','skipped','sampled') for x in checks.values()):
        raise ValueError('Estado de comprobación desconocido')
    privacy = report['privacy']
    if privacy != {'raw_logs':False,'hostnames':False,'addresses':False,'environment':False,'secrets':False}:
        raise ValueError('Política de privacidad incompatible')
    for key in ('root_read_only',):
        if not _boolean_or_null(report['storage'][key]): raise ValueError('Valor booleano inválido')
    for key in ('ntp_synchronized',):
        if not _boolean_or_null(report['time'][key]): raise ValueError('Valor booleano inválido')
    for key in ('apparmor_kernel_enabled','unattended_upgrades_installed'):
        if not _boolean_or_null(report['security'][key]): raise ValueError('Valor booleano inválido')
    if report['security']['ufw_status'] not in (None,'active','inactive'):
        raise ValueError('Estado de UFW inválido')
    for group in ('storage','process_health','network','security','incident_sample'):
        for key,value in report[group].items():
            if key.startswith('sshd_') or key in ('ufw_status','root_read_only','apparmor_kernel_enabled','unattended_upgrades_installed'):
                continue
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError('Métrica numérica inválida: ' + key)
    valid_ssh = (None,'yes','no','prohibit-password','forced-commands-only','without-password')
    if any(report['security'][k] not in valid_ssh for k in ('sshd_global_password_auth', 'sshd_global_root_login', 'sshd_global_pubkey_auth','sshd_global_empty_passwords','sshd_global_x11_forwarding')):
        raise ValueError('Valor SSH inválido')
    if not isinstance(report['collected_at'],str) or len(report['collected_at'])>35:
        raise ValueError('Fecha inválida')
    for key in ('os_family','os_version'):
        if not isinstance(report[key],str) or len(report[key])>40 or not all(c.isascii() and (c.isalnum() or c in '._-') for c in report[key]):
            raise ValueError('Información de distro inválida')
    return report


def analyze(report):
    report = validate(report)
    found = []
    def add(code, evidence):
        severity, title, guidance = RULES[code]
        found.append({'code':code,'severity':severity,'title':title,'evidence':evidence,'guidance':guidance,
                      'interpretation':'observación, no causa confirmada'})
    storage=report['storage'];proc=report['process_health']; net=report['network'];time=report['time'];sec=report['security'];sample=report['incident_sample']
    if sample['oom_mentions'] is not None and sample['oom_mentions']>0: add('DC-INC-101',f"Menciones OOM en últimos 300 errores kernel / 24h: {sample['oom_mentions']}")
    if sample['io_error_mentions'] is not None and sample['io_error_mentions']>0: add('DC-INC-102',f"Menciones I/O error en muestra: {sample['io_error_mentions']}")
    if sample['kernel_error_entries'] is not None and sample['kernel_error_entries']>=30: add('DC-INC-103',f"Mensajes kernel error en muestra: {sample['kernel_error_entries']}")
    if storage['root_read_only'] is True: add('DC-STOR-101','Mount raíz informa read-only')
    if storage['root_inode_used_percent'] is not None and storage['root_inode_used_percent']>=90:
        add('DC-STOR-102',f"Inodos raíz utilizados: {storage['root_inode_used_percent']}%")
    if proc['failed_systemd_services'] is not None and proc['failed_systemd_services']>0:
        add('DC-PROC-101',f"Unidades systemd fallidas: {proc['failed_systemd_services']}")
    if proc['uninterruptible_count'] is not None and proc['uninterruptible_count']>=5:
        add('DC-PROC-102',f"Procesos estado D: {proc['uninterruptible_count']}")
    if proc['zombie_count'] is not None and proc['zombie_count']>=10:
        add('DC-PROC-103',f"Procesos zombie: {proc['zombie_count']}")
    if net['default_ipv4_routes'] == 0: add('DC-NET-101','Rutas IPv4 por defecto: 0')
    if time['ntp_synchronized'] is False: add('DC-TIME-101','NTP: no sincronizado')
    if sec['sshd_global_empty_passwords']=='yes': add('DC-SSH-101','PermitEmptyPasswords yes (salida sshd -T)')
    if sec['sshd_global_root_login']=='yes': add('DC-SSH-102','PermitRootLogin yes (global)')
    if sec['sshd_global_password_auth']=='yes': add('DC-SSH-103','PasswordAuthentication yes (global)')
    if sec['sshd_global_x11_forwarding']=='yes': add('DC-SSH-104','X11Forwarding yes (global)')
    if sec['unattended_upgrades_installed'] is False: add('DC-HARD-101','Paquete unattended-upgrades no instalado')
    if sec['apparmor_kernel_enabled'] is False: add('DC-HARD-102','AppArmor deshabilitado en kernel')
    if sec['ufw_status']=='inactive': add('DC-HARD-103','UFW inactivo (otros firewalls posibles)')
    if sec['kernel_kptr_restrict'] is not None and sec['kernel_kptr_restrict'] < 1:
        add('DC-HARD-104',f"kernel.kptr_restrict={sec['kernel_kptr_restrict']}")
    if sec['kernel_dmesg_restrict'] == 0: add('DC-HARD-105','kernel.dmesg_restrict=0')
    if sec['fs_protected_hardlinks'] == 0: add('DC-HARD-106','fs.protected_hardlinks=0')
    if sec['fs_protected_symlinks'] == 0: add('DC-HARD-107','fs.protected_symlinks=0')
    order={'critical':0,'high':1,'warning':2,'info':3}
    found.sort(key=lambda f:(order[f['severity']],f['code']))
    return {'findings':found,'unknown_checks':[k for k,v in report['checks'].items() if v=='unavailable'],
            'message': 'Hallazgos orientativos que requieren validación' if found else 'Sin hallazgos detectados en las comprobaciones disponibles'}


def render_html(report, result):
    def h(s): return html.escape(str(s),quote=True)
    blocks=[]
    for x in result['findings']:
        blocks.append('<article><h3>'+h(x['code'])+' — '+h(x['title'])+'</h3>'
          '<p><strong>Severidad:</strong> '+h(x['severity'])+'</p>'
          '<p><strong>Evidencia observada:</strong> '+h(x['evidence'])+'</p>'
          '<p><strong>Qué verificar:</strong> '+h(x['guidance'])+'</p>'
          '<p>Correlación y umbrales no prueban causa raíz. Ninguna acción fue ejecutada.</p></article>')
    return ("<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'; form-action 'none'; base-uri 'none'\">"
        "<title>Diagnóstico Comunitario · Auditoría extendida</title>"
        "<style>body{font:16px system-ui;max-width:920px;margin:2em auto;padding:0 1em;color:#1e293b}"
        "article{border:1px solid #a3a3a3;border-radius:9px;padding:1em;margin:1em 0}"
        ".notice{background:#f1f5f9;padding:1em;border-radius:9px}</style></head><body>"
        "<h1>Auditoría extendida — informe local y privado</h1>"
        "<p class='notice'>No se enviaron datos a servicios externos. Esta auditoría solo observa, no aplica hardening.</p>"
        "<p>Familia OS: "+h(report['os_family'])+" · Versión: "+h(report['os_version'])
        +" · UTC: "+h(report['collected_at'])+"</p>"
        "<h2>Hallazgos y recomendaciones</h2>"+("".join(blocks) if blocks else '<p>Sin alertas para los indicadores disponibles.</p>')
        +"<h2>Comprobaciones no disponibles</h2><p>"+h(', '.join(result['unknown_checks']) or 'Ninguna')+"</p>"
        "<p>Campos desconocidos se representan como null y requieren validación en el servidor;"
        " nunca interpretar desconocido como ausencia de riesgo.</p></body></html>")


def exclusive_write(path:Path, data:bytes):
    flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,'O_NOFOLLOW',0)
    fd=os.open(path,flags,0o600)
    with os.fdopen(fd,'wb') as f: f.write(data)


def main(argv=None):
    p=argparse.ArgumentParser(description='Analiza un informe extendido privadamente y sin modificar servicios')
    p.add_argument('json_file',type=Path)
    p.add_argument('--output',type=Path,help='Ruta HTML nueva; obligatorio para flujo automatizado sin stdout')
    args=p.parse_args(argv)
    try:
        if not args.json_file.is_file() or args.json_file.stat().st_size>MAX_REPORT_BYTES:
            raise ValueError('Archivo inválido o demasiado grande')
        report=json.loads(args.json_file.read_text(encoding='utf-8'))
        result=analyze(report)
        destination=args.output or args.json_file.with_suffix('.html')
        if destination.resolve()==args.json_file.resolve(): raise ValueError('Salida igual a entrada')
        os.umask(0o077)
        exclusive_write(destination,render_html(report,result).encode('utf-8'))
        print('Auditoría local completada. Informe HTML privado disponible en el destino seleccionado.')
        return 0
    except (OSError,ValueError,TypeError) as e:
        # Do not leak report contents or arbitrary filesystem paths.
        print('Error: no fue posible validar o generar el informe privado.',file=sys.stderr)
        return 1

if __name__=='__main__': raise SystemExit(main())
