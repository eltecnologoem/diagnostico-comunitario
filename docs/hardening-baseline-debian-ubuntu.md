# Baseline de hardening — Debian y Ubuntu Server

**Proyecto:** Diagnóstico Comunitario · **Autor:** Eliezer Molina Méndez  
**Estado:** guía comunitaria de referencia, pendiente de pruebas en sistemas reales. No constituye certificación CIS, STIG, auditoría legal ni plantilla que deba aplicarse ciegamente.

Este documento establece **qué evaluar y cómo decidir**, no ejecuta cambios. El comando `python3 diagnostico.py auditar` toma evidencia en solo lectura y `python3 tools/hardening.py --plan` muestra únicamente cuatro sysctls conservadores/contextuales. Los demás controles requieren cambios manuales, comprobación de dependencias y respaldo.

## Orden de implantación

| Prioridad | Dominio | Comprobación en solo lectura | Riesgo y precaución |
|---|---|---|---|
| P0 | Acceso de recuperación | Consola del proveedor, recuperación, snapshots y backup restaurable | Nunca modificar SSH/firewall sin vía alternativa |
| P0 | Identidad SSH | `sshd -t` y `sshd -T`; revisar reglas `Match` de cada usuario | `sshd -T` global no describe todas las excepciones |
| P0 | Parches críticos | `apt list --upgradable`, versión de paquetes, avisos de seguridad del proveedor | No instalar ni reiniciar automáticamente desde el diagnóstico |
| P0 | Servicios expuestos | `ss -ltn`, inventario de sockets y políticas del firewall activo | UFW inactivo no significa tráfico desprotegido |
| P1 | Autenticación | Acceso root, claves autorizadas, sudo, MFA si procede | No deshabilitar contraseñas antes de probar llaves |
| P1 | MAC | Estado AppArmor y perfiles cargados, compatibilidad del workload | Activación/enforce puede romper servicios |
| P1 | Actualizaciones | `unattended-upgrades`: instalado, configurado y registros de ejecución | Tener el paquete instalado no demuestra que esté activo |
| P1 | Registros | Retención del journal, alertas de OOM, I/O, procesos y errores de aplicación | No exportar logs crudos a Codex/modelos |
| P1 | Endurecimiento kernel | `fs.protected_*`, `kernel.dmesg_restrict`, `kernel.kptr_restrict` | Ajustar por necesidades de observabilidad |
| P1 | Copias | Cifrado, respaldo desconectado/inmutable y restauración probada | Un backup sin prueba de restauración no es una garantía |
| P2 | Segmentación | Firewall perimetral, ACL, VLAN y acceso administrativo separado | Cambios remotos pueden provocar pérdida de conexión |
| P2 | Límite de recursos | ulimits, cgroups, cuotas, inodos, archivos abiertos, OOM y presión | Ajustes deben basarse en consumos reales |
| P2 | Protección de servicios | TLS, listas de acceso, cuentas de servicio y mínimos privilegios | Específico para cada software |
| P2 | Auditoría y respuesta | `auditd` si procede, reglas locales y correlación de incidentes | Impacto en almacenamiento y privacidad |
| P2 | Integridad | Paquetes firmados, repositorios APT confiables, inventario y cambios | Repositorios de terceros requieren revisión |

### Comprobaciones privadas de referencia

Los comandos siguientes **no están integrados en el reporte compartible**. Si el administrador los ejecuta para investigar, las salidas se consideran **datos privados**: pueden contener nombres, direcciones, rutas, cuentas y detalles de seguridad.

```bash
# Validación de sintaxis y configuración efectiva SSH (requiere permisos adecuados):
sudo sshd -t
sudo sshd -T
# Para reglas Match, completar el contexto real del usuario y dirección autorizada:
sudo sshd -T -C user=usuario,host=servidor,addr=192.0.2.10

# Listeners, servicios y registro de arranque:
ss -ltn
systemctl --failed --type=service --no-pager
journalctl -b -p err --no-pager

# Estado de control de acceso y actualizaciones:
aa-status
apt list --upgradable
dpkg-query -W unattended-upgrades

# Reglas de filtrado activas (si existen, no limitarse a UFW):
sudo nft list ruleset
sudo ufw status verbose

# Perfil kernel actual:
sysctl fs.protected_hardlinks fs.protected_symlinks kernel.dmesg_restrict kernel.kptr_restrict
```

**Advertencia:** no copiar estas salidas a Codex en el modo de privacidad estricta. El analizador local debe trabajar con métricas, estados validados y códigos de evaluación; no necesita enviar registros sin procesar.

## Cambios de acceso SSH

Antes de cualquier modificación:

1. Probar el inicio de sesión con una **segunda sesión** usando la llave/usuario final.
2. Verificar acceso de consola fuera de banda y un backup de la configuración.
3. Inspeccionar `Include` y reglas `Match`, no solo una línea aislada de `/etc/ssh/sshd_config`.
4. Comprobar sintaxis con `sshd -t` después del cambio propuesto.
5. Aplicar en mantenimiento, verificar nueva conexión y dejar una vía de recuperación abierta hasta confirmar el acceso.
6. Si falla, revertir inmediatamente desde consola. No modificar puerto, autenticación o PermitRootLogin desde un agente sin autorización independiente.

La auditoría actual solo **detecta** configuraciones globales potencialmente riesgosas y nunca modifica `sshd_config`.

## Firewall y exposición de red

Comprobar primero si el sistema usa nftables, iptables, UFW, firewalld, un firewall de nube o filtrado aguas arriba. **No inferir ausencia de filtrado porque UFW esté inactivo.** Definir explícitamente flujos SSH de gestión, servicios públicos, monitoreo y salida.

El prototipo no aplica reglas de firewall. Un instalador de reglas necesitaría un mecanismo comprobado de rollback temporizado, comprobación fuera de banda y validación de rutas; estas garantías **todavía no están implementadas**.

## Actualizaciones y mantenimiento

No confundir «unattended-upgrades instalado» con «actualización funcionando». Validar las políticas APT, paquetes pendientes, logs del automatismo, orígenes autorizados, exclusiones y política de reinicio de kernel. Para servicios críticos, acordar primero ventana y rollback; un reinicio automático puede producir indisponibilidad.

## AppArmor, contenedores y Proxmox

Comprobar si el host es una VM, contenedor o hypervisor. Las métricas del kernel, memoria, servicios y AppArmor pueden representar el host y no el contenedor. Un control puede no estar disponible por diseño; jamás clasificarlo «incumplido» por falta de acceso. Revisar perfiles por servicio antes de activar enforcement.

En hosts Proxmox, plataformas de streaming, appliances y kernels personalizados, **no forzar sysctls de depuración ni controles MAC sin pruebas**.

## Endurecimiento sysctl limitado

La única función de cambios implementada hasta ahora es `tools/hardening.py`; exige autorización manual y crea estado para reversión. Puede configurar exclusivamente:

- `fs.protected_hardlinks=1`
- `fs.protected_symlinks=1`
- `kernel.dmesg_restrict=1`
- `kernel.kptr_restrict=2`

```bash
python3 tools/hardening.py --plan
# Acción modificadora: ejecutar solo en una consola de mantenimiento confiable:
sudo python3 tools/hardening.py --apply fs.protected_hardlinks,fs.protected_symlinks
```

La aplicación y reversión no se invocan desde Codex, MCP, SSH del runner ni automatizaciones. Aunque exista un TTY y no aparezcan variables SSH, **el operador debe garantizar acceso de recuperación real**. Una segunda configuración sysctl ajena puede prevalecer tras reinicio; comprobar estado efectivo y orden de configuración en el host.

## Evidencias y cierre del cambio

Guardar en un sistema controlado: instante UTC, operador, baseline anterior, alcance autorizado, controles evaluados, conflictos detectados, validación post-cambio, resultado, ID de respaldo y procedimiento de reversión. Los nombres de equipos y credenciales nunca se publican en el repositorio ni en capturas de CI.

Si no hay suficiente evidencia para una recomendación, indicar `sin datos`. Si un cambio es potencialmente disruptivo, posponerlo hasta contar con consola y una ventana acordada.

## Fuentes oficiales

- Debian Security Manual: https://www.debian.org/doc/manuals/securing-debian-manual/
- Ubuntu Server security: https://ubuntu.com/server/docs/explanation/security/security_suggestions/
- Ubuntu automatic updates: https://ubuntu.com/server/docs/how-to/software/automatic-updates/
- Ubuntu OpenSSH: https://ubuntu.com/server/docs/how-to/security/openssh-server/
- Linux kernel sysctl fs: https://docs.kernel.org/admin-guide/sysctl/fs.html
- Linux kernel sysctl kernel: https://www.kernel.org/doc/html/latest/admin-guide/sysctl/kernel.html
- OpenSSH sshd_config(5): https://man7.org/linux/man-pages/man5/sshd_config.5.html

[Volver a la guía de auditoría](auditoria-hardening.md) · [Política de seguridad](../SECURITY.md)
