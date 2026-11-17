# Diagnóstico Comunitario sin Python — edición POSIX `sh`

**Autor:** Eliezer Molina Méndez · [eliezermolina.org](https://eliezermolina.org)  
**Estado:** prototipo comunitario para pruebas, solo lectura.

## Objetivo

Permitir que una persona ejecute una auditoría local de Debian/Ubuntu (y otras distribuciones Linux compatibles) con **una sola orden**, sin necesitar Python, `jq`, `pip`, `git` ni instalar paquetes. Basta disponer de los tres archivos del proyecto (`diagnostico.sh`, `bin/serverdiag.sh` y `bin/audit-extended.sh`) y las utilidades estándar presentes en la mayoría de distribuciones Linux: `/bin/sh`, `awk`, `tr`, `df`, `ps`, `date`, `mktemp`, `chmod`, etc.

**Importante:** el comando no requiere Git para ejecutarse. Puedes descargar el ZIP del repositorio desde GitHub con un navegador, extraerlo y ejecutar `sh diagnostico.sh`. La descarga es independiente del diagnóstico; **no se hace ninguna conexión de red durante la ejecución local**.

## Primer uso (Linux)

Desde la carpeta descargada:

```sh
sh -n diagnostico.sh             # Revisión de sintaxis
sh diagnostico.sh                # Diagnóstico completo
```

El comando realiza la captura básica y la auditoría extendida. No solicita contraseña, no instala, no edita `/etc`, no cambia SSH, no ejecuta `sudo`, no envía información y no activa tareas programadas.

### Diagnóstico parcial

```sh
sh diagnostico.sh --only system
sh diagnostico.sh --only memory,disk
sh diagnostico.sh --only database
sh diagnostico.sh --only processes
sh diagnostico.sh --only extended
sh diagnostico.sh --only disk,extended
sh diagnostico.sh --output-dir /ruta/privada
sh diagnostico.sh --help
```

`extended` ejecuta el **colector extendido completo**, que incluye comprobaciones de seguridad, procesos, red, NTP y señales de eventos. La selección `--only disk,extended` realiza exclusivamente la parte `disk` de la captura básica, **más la auditoría extendida completa**. No se presenta como una selección granular de la auditoría extendida.

## Resultados

Por defecto se genera una carpeta nueva bajo:

```text
$HOME/.local/state/diagnostico-comunitario/diagnostico-FECHA-XXXXXXXX/
├── basic.json      # Incluido cuando se elige una sección básica
├── extended.json   # Incluido en ejecución completa o si se elige extended
└── INFORME.md      # Resumen legible con reglas básicas y recomendaciones
```

El directorio de cada captura se crea con modo `0700` y los archivos con `0600`. El script evita sobrescribir resultados anteriores. Una ubicación personalizada se indica con `--output-dir`, que debe ser absoluta; **no cambia los permisos de la carpeta existente**.

- Los dos JSON conservan sus contratos originales: `schema_version: 1.0` y `extended-1.0`; no se fusionan en un formato incompatible.
- El informe Markdown solo resume señales predefinidas. No copia líneas de journal ni valores arbitrarios de archivos de configuración.
- `null` o `unavailable` significan **sin evidencia disponible**, no ausencia de incidente.
- Una regla simple no identifica necesariamente la causa raíz: siempre se deben corroborar hallazgos y contexto.

**Privacidad:** estos archivos contienen métricas reales y uno de los JSON puede incluir hostname e información operativa. Son **informes privados**. No se deben publicar ni pasar a un modelo externo en el modo de privacidad estricta. La protección por permisos del mismo usuario **no es suficiente para aislar Codex** si el agente se ejecuta con esa identidad; consultar `SECURITY.md`.

## ¿Qué ocurre si faltan herramientas?

El colector usa utilidades comunes del sistema y comprueba varias herramientas opcionales (por ejemplo `ss`, `systemctl`, `journalctl`, `findmnt`, `timedatectl`, `dpkg-query`, `timeout`, `sshd`). Si no existen o faltan permisos, registra `null`/`unavailable`. **No las instala** y no intenta escalar permisos. La disponibilidad de datos varía en contenedores, servidores mínimos y sistemas sin systemd.

## Diferencia con las herramientas Python

| Opción | Necesita Python | Uso |
|---|---|---|
| `sh diagnostico.sh` | **No** | Captura completa y resumen Markdown local |
| `sh bin/serverdiag.sh` | **No** | JSON básico, standalone descargable individualmente |
| `sh bin/audit-extended.sh` | **No** | JSON de auditoría extendida, standalone descargable individualmente |
| `python3 diagnostico.py` | Sí | Asistente SSH, HTML y análisis ampliado |
| `python3 tools/hardening.py --plan` | Sí | Plan opcional; las aplicaciones requieren confirmación independiente |
| `sh bin/serverdiag.sh --email` | Sí (solo SMTP opt-in) | Envío voluntario de una **copia compartible** |

`--email` **no está habilitado** en el modo `sh diagnostico.sh`. Tampoco se leen archivos `.env`: su mera existencia nunca activa una conexión.

## Pruebas

Durante el **desarrollo y la integración continua**, usamos Python para verificar contratos JSON y seguridad, pero **Python no es una dependencia de los scripts en producción**.

```sh
python3 -m unittest discover -s tests -v
```

Las pruebas comprueban: sintaxis POSIX, permisos, captura completa y parcial, informes válidos, ausencia de llamadas a Python, `jq` o comandos de red, y rechazo de parámetros incorrectos.

## Límites de la primera versión

- Está orientada a Linux; **no ejecuta Linux localmente en Windows/macOS**. Desde esas plataformas debe usarse un cliente/SSH a un Linux (función del asistente Python, por ahora).
- No realiza detección automática de causas, inventario exhaustivo de aplicaciones ni remediación. El Markdown aporta señales iniciales y preguntas de investigación.
- No autentica servidores remotos ni realiza comprobaciones de disponibilidad: no confundir con `diagnostico.py` o `bin/probe-connectivity.sh`.
- No se han completado pruebas en todas las distribuciones ni una auditoría independiente de seguridad.

Para informar vulnerabilidades: [SECURITY.md](../SECURITY.md).
