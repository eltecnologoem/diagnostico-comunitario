# Diagnóstico Comunitario: auditoría extendida y hardening para Debian/Ubuntu

**Versión de trabajo:** v0.3.0 — laboratorio. **Autor:** Eliezer Molina Méndez — https://eliezermolina.org

## Principios

1. Diagnosticar no implica modificar. `auditar` y `bin/audit-extended.sh` **solo recopilan evidencia**; no instalan, reinician, alteran SSH/red/firewall ni se conectan a Internet.
2. El informe extendido se genera localmente o en un Linux autorizado mediante **SSH por stdin**, y se guarda en el equipo que ejecuta el asistente, fuera del repositorio.
3. No incluye hostname, IP, nombre de usuario, credenciales, rutas o logs completos. **Sí contiene datos reales operativos** (servicios fallidos, estado SSH, controles del kernel) y sigue siendo **privado**. Nunca lo pases a Codex remoto sin consentimiento informado.
4. Los hallazgos son señales que requieren corroboración. `null` significa *sin datos*, no *seguro* ni *ausencia de incidencia*.
5. Las remediaciones son independientes: requieren confirmación expresa y no son invocadas por el agente Codex.

## Diagnóstico extendido

En Debian/Ubuntu **local**:

```bash
python3 diagnostico.py auditar --local
```

En un Linux remoto con perfil SSH configurado:

```bash
python3 diagnostico.py auditar --perfil servidor-01
```

Solo Bash POSIX sobre el Linux diagnosticado:

```bash
sh bin/audit-extended.sh
sh bin/audit-extended.sh --output ./auditoria-privada.json
```

El asistente genera dos archivos privados `auditoria-FECHA-ID.json` y `auditoria-FECHA-ID.html` en el directorio protegido de la cuenta. No imprime el informe en la consola de Codex.

### Comprobaciones

| Área | Evidencia observada | Limitación |
|---|---|---|
| Almacenamiento | Porcentaje de inodos raíz y montaje raíz read-only | No sustituye SMART ni `fsck`; no toca dispositivos |
| Procesos | Recuento de procesos zombie/D y unidades systemd fallidas | No interpreta causas ni revela nombres de servicios |
| Red | Nº interfaces, rutas IPv4 por defecto y sockets TCP escuchando | No detecta conectividad externa ni IPs; IPv6-only puede ser normal |
| Hora | Estado `NTPSynchronized` informado por systemd | Puede faltar en contenedores |
| SSH | Resultados globales de `sshd -T` para contraseña, root, llaves, contraseñas vacías y X11 | `Match` puede cambiar políticas para conexiones concretas |
| Seguridad | Kernel AppArmor, paquete unattended-upgrades, UFW, cuatro sysctls | Tener paquete instalado no implica estar actualizado; UFW inactivo no significa sin firewall |
| Incidentes | Conteos de mensajes OOM, I/O y errores kernel | Solo muestra limitada a 300 entradas de error en 24 horas, sin logs crudos; no permite concluir ausencia de fallos |

Si una comprobación no puede ejecutarse, su estado es `unavailable`. En el conteo del journal se informa `sampled`; ausencia de coincidencias dentro de la muestra **no** equivale a ausencia de incidentes.

## Hardening: separar plan de cambios

El auditor presenta **recomendaciones**, nunca aplica cambios. Un módulo independiente ofrece una remediación acotada a cuatro sysctls del kernel. Antes de tocar un servidor, verifica copias de seguridad, acceso de consola, requisitos de los servicios y un plan de reversión.

```bash
python3 tools/hardening.py --list
python3 tools/hardening.py --plan
```

Estas dos órdenes **no requieren root y no modifican el equipo**.

### Aplicación explícita (solo si el operador lo decide)

Desde una **consola de mantenimiento confiable** con privilegios de root (no desde Codex, MCP ni el runner SSH):

```bash
sudo python3 tools/hardening.py --apply fs.protected_hardlinks,fs.protected_symlinks
```

El programa obliga a escribir literalmente `APLICAR HARDENING LOCAL`. Rechaza sesiones SSH detectadas y ejecuciones sin TTY. **Esto no demuestra por sí solo que la consola sea física:** sigue siendo responsabilidad del operador comprobar que existe un acceso de recuperación.

El módulo no toca `sshd_config`, SSH, `ufw`, `nftables`, rutas, `apt`, `systemd` ni cuentas de usuarios. Solo permite estos valores:

| Parámetro | Valor | Riesgo / observación |
|---|---|---|
| `fs.protected_hardlinks` | `1` | Puede afectar software legado que use hardlinks entre usuarios |
| `fs.protected_symlinks` | `1` | Puede modificar el comportamiento de symlinks en directorios sticky |
| `kernel.dmesg_restrict` | `1` | Usuarios sin CAP_SYSLOG pierden acceso directo a mensajes de kernel |
| `kernel.kptr_restrict` | `2` | Puede limitar depuración, trazas y herramientas de observabilidad |

El aplicador crea `/etc/sysctl.d/99-diagnostico-comunitario.conf` solo si no existe un archivo ajeno con el mismo nombre, y guarda un snapshot root-only en `/var/lib/diagnostico-comunitario/hardening/` antes de tocar la configuración. La persistencia futura también depende del orden y otros ficheros sysctl del sistema.

**No se permite apilar operaciones** hasta revertir la anterior; facilita rollback seguro en el prototipo. Las pruebas automáticas simulan cambios sin escribir sysctls reales.

### Reversión

Guarda el ID que muestra el aplicador:

```bash
sudo python3 tools/hardening.py --rollback ID_DEL_RESPALDO
```

Se exige `REVERTIR HARDENING LOCAL`. Antes de sobrescribir, verifica que el archivo actual coincide con el hash del que instaló; si otro administrador lo modificó, **se detiene sin pisar esos cambios**. Restablece valores anteriores del kernel y el archivo gestionado. Una reversión es una operación sensible: conserva consola fuera de banda y verifica servicios después.

## Reglas y seguridad operacional

- **Nunca desactivar por defecto** `PasswordAuthentication`, `PermitRootLogin` o cambiar puertos SSH: puede bloquear la administración remota.
- **Nunca activar reglas de firewall automáticamente** antes de comprobar acceso a consola y rutas necesarias.
- En hipervisores Proxmox, appliances, servidores de streaming y hosts con contenedores, evaluar las restricciones del kernel contra el uso real antes de aplicar.
- Un nivel `info` es una recomendación contextual y no constituye una vulnerabilidad confirmada.
- El informe HTML escapa cadenas y no carga scripts, CDN ni recursos de red; ambos archivos siguen siendo privados.
- Un archivo `.env` visible por Codex no protege las credenciales. Esta herramienta no elimina la necesidad del broker aislado descrito en `docs/codex-secure-workflow.md`.

## Fuentes de referencia

- Ubuntu: https://ubuntu.com/server/docs/explanation/security/security_suggestions/
- Ubuntu: https://ubuntu.com/server/docs/how-to/software/automatic-updates/
- Ubuntu OpenSSH: https://ubuntu.com/server/docs/how-to/security/openssh-server/
- Debian: https://www.debian.org/doc/manuals/securing-debian-manual/
- Linux kernel sysctl `fs`: https://docs.kernel.org/admin-guide/sysctl/fs.html
- Linux kernel sysctl `kernel`: https://www.kernel.org/doc/html/latest/admin-guide/sysctl/kernel.html
- OpenSSH `sshd_config(5)`: https://man7.org/linux/man-pages/man5/sshd_config.5.html

## Validación

```bash
sh -n bin/audit-extended.sh
python3 -m unittest discover -s tests -v
```

El estado actual es **prototipo**, no hardening certificado CIS ni auditoría de conformidad. Las pruebas de campo en Debian/Ubuntu, especialmente SSH, AppArmor y sysctl con workloads de clientes, siguen pendientes.
