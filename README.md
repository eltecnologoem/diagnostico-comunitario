# Diagnóstico Comunitario

**Diagnóstico Linux abierto, reproducible y respetuoso de la privacidad.**

**Autor y responsable de la iniciativa:** [Eliezer Molina Méndez](https://eliezermolina.org)  
**Sitio del proyecto y divulgación:** [eliezermolina.org](https://eliezermolina.org)  
**Estado del repositorio:** fase de diseño y preparación del código comunitario; las funciones descritas a continuación constituyen objetivos, no funcionalidades ya certificadas.

## Consola interactiva opcional — v0.5 (laboratorio)

La edición POSIX `sh` incorpora **tres opciones independientes** que no requieren Python, `jq`, `dialog` ni `whiptail`. Sin opciones, la ejecución conserva el modo discreto anterior.

```sh
sh diagnostico.sh                          # ejecución normal y salida breve
sh diagnostico.sh --show                   # resumen ordenado en la consola
sh diagnostico.sh --menu                   # menú de secciones (terminal interactiva)
sh diagnostico.sh --progress               # indicador de avance
sh diagnostico.sh --menu --show --progress  # experiencia interactiva completa
sh diagnostico.sh --only memory,disk --show
```

En el menú puedes ingresar **`2,3,6`** para memoria, disco y auditoría extendida. La selección inválida o cancelar no genera capturas. `--menu` requiere terminal real y no puede combinarse con `--only`.

`--show` presenta **métricas y hallazgos básicos ordenados**, sin volcar el JSON ni los registros; `--progress` usa una animación simple solo cuando hay terminal, y muestra líneas normales si la salida está redirigida. **Las métricas son datos reales:** activa `--show` únicamente desde una terminal de confianza; no envíes su stdout a Codex en modo de privacidad estricta.

[Guía de menú, consola y progreso](docs/interfaz-consola.md) · [Pruebas de interacción](tests/test_shell_interactive.py).

## Diagnóstico sin Python: un solo comando `sh`

**Recomendado para principiantes en Debian/Ubuntu y otras distribuciones Linux compatibles.** La edición shell no requiere Python, `pip`, `jq`, una cuenta, correo ni instalar paquetes adicionales. Utiliza `/bin/sh` y herramientas habituales de Linux.

Descarga el repositorio como ZIP desde GitHub, extráelo y, dentro de su carpeta, ejecuta:

```sh
sh diagnostico.sh
```

**Diagnóstico por partes:**

```sh
sh diagnostico.sh --only disk,memory
sh diagnostico.sh --only system
sh diagnostico.sh --only database
sh diagnostico.sh --only processes
sh diagnostico.sh --only extended
sh diagnostico.sh --only disk,extended
sh diagnostico.sh --help
```

`extended` ejecuta la auditoría avanzada completa (seguridad, red, procesos y eventos); no instala ni aplica hardening. Para elegir otra carpeta de salida:

```sh
sh diagnostico.sh --output-dir /ruta/privada
```

**Qué obtienes:** una carpeta privada bajo `$HOME/.local/state/diagnostico-comunitario/` con `basic.json`, `extended.json` e `INFORME.md` (los JSON dependen de las secciones seleccionadas). Se crean archivos de solo acceso para el propietario. **No existe envío a Internet ni ejecución remota en este comando.**

La versión shell es la opción **sin dependencias adicionales obligatorias**. Las utilidades `diagnostico.py`, correo SMTP, interfaz HTML e integración asistida por SSH se mantienen separadas y pueden requerir Python o configuración específica. La ejecución local sigue requiriendo Linux; desde Windows o macOS se podrá utilizar el asistente SSH opcional.

[Guía de uso de la versión shell](docs/diagnostico-shell-sin-dependencias.md) · [Código POSIX sh](diagnostico.sh) · [Pruebas automatizadas](tests/test_shell_entrypoint.py)

**Estado:** prototipo para pruebas, no auditado para producción. Los informes completos son privados y pueden incluir información real del servidor; no subirlos a GitHub ni entregarlos a Codex en modo de privacidad estricta.

## Auditoría extendida y hardening v0.3.0 (laboratorio)

Esta ampliación añade **diagnóstico de fallos de Linux y evaluación de hardening** para Debian/Ubuntu, sin cambiar el servidor durante la recolección. Es independiente del recolector básico y de cualquier función de inteligencia artificial. No es una auditoría CIS ni un sustituto de pruebas de penetración.

**Auditar en Debian/Ubuntu local:**

```bash
python3 diagnostico.py auditar --local
```

**Auditar un servidor Linux remoto (desde Windows, macOS o Linux, con perfil SSH previamente aprobado):**

```bash
python3 diagnostico.py auditar --perfil servidor-01
```

**Alternativa Bash directa en Linux, sin Python en el servidor:**

```bash
sh bin/audit-extended.sh
```

La auditoría observa inodos, filesystem raíz read-only, procesos bloqueados/zombies, fallos de systemd, indicadores básicos de red, NTP, políticas globales SSH, AppArmor, actualizaciones y controles de sysctl. También incluye **una muestra limitada de errores del kernel** (hasta 300 entradas/24 h), contando referencias a OOM y errores I/O **sin incluir las líneas originales**. Cuando faltan datos, usa `null` o `unavailable`, nunca un cero inventado.

El asistente genera **JSON y HTML privados**, sin scripts ni recursos externos, en el directorio de datos privado del usuario. Los archivos completos no deben entregarse a Codex ni publicarse en GitHub.

### Hardening: revisar antes de aplicar

**Solo para un operador experimentado**, con consola de recuperación y evaluación de compatibilidad:

```bash
python3 tools/hardening.py --list
python3 tools/hardening.py --plan
```

Estas órdenes **son de lectura**. La aplicación es otra acción, separada del diagnóstico, disponible exclusivamente desde una terminal interactiva autorizada como root en Debian/Ubuntu; exige escribir una confirmación literal, crea un respaldo y permite rollback. Se limita a cuatro sysctls aprobados: `fs.protected_hardlinks`, `fs.protected_symlinks`, `kernel.dmesg_restrict` y `kernel.kptr_restrict`.

**No habilita ni deshabilita SSH, firewall, servicios, cuentas, actualizaciones o paquetes.** No ejecutar cambios de hardening por Codex ni permitirle acceder a datos reales del diagnóstico.

- [Guía de auditoría extendida y hardening](docs/auditoria-hardening.md)
- [Baseline por prioridades para Debian y Ubuntu](docs/hardening-baseline-debian-ubuntu.md)
- [Script de auditoría read-only](bin/audit-extended.sh)
- [Analizador local extendido](tools/analyze-extended.py)
- [Hardening opt-in con respaldo y reversión](tools/hardening.py)
- [Pruebas sintéticas y de rollback](tests/test_extended_hardening.py)
- [Política de seguridad](SECURITY.md)

**Estado:** prototipo en evaluación. El SSH real, el hardening en hosts productivos y el aislamiento de credenciales frente a Codex siguen pendientes de validación independiente.

## Nueva edición asistida v0.2.0 (laboratorio)

**Para usuarios sin experiencia:** un asistente local en Python 3 (biblioteca estándar) configura conexiones SSH, ejecuta el colector comunitario, interpreta métricas mediante reglas deterministas y abre un informe HTML privado sin conexión a servicios externos.

**Linux/macOS — instalación y primer uso:**

```sh
git clone https://github.com/eltecnologoem/diagnostico-comunitario.git
cd diagnostico-comunitario
python3 diagnostico.py
```

**Windows — PowerShell (necesita Python 3 y OpenSSH):**

```powershell
git clone https://github.com/eltecnologoem/diagnostico-comunitario.git
cd diagnostico-comunitario
py -3 diagnostico.py
```

El asistente solicita solo los datos necesarios: alias, host/IP, puerto SSH, usuario y autenticación por ssh-agent, llave (ruta local) o contraseña interactiva. **No guarda contraseñas**. La conexión exige una huella SSH conocida y verificada; no desactiva el control de identidad.

Una vez configurado, desde **una terminal local de confianza, no dentro del entorno de Codex**:

```sh
python3 diagnostico.py ejecutar --perfil servidor-01
python3 diagnostico.py ejecutar --perfil servidor-01 --only memory,disk
python3 diagnostico.py ejecutar --local              # solo Linux
python3 diagnostico.py guias                     # guías públicas sin datos reales
python3 diagnostico.py guias --codigo DC-DISK-001
```

Los archivos JSON y HTML se guardan fuera del checkout, en un directorio privado de la cuenta del usuario. El análisis local consulta **20 guías**: 10 reglas automáticas y 10 procedimientos de investigación manual. No ejecuta reparaciones.

**Codex:** hemos preparado una Skill en [`.agents/skills/diagnostico-comunitario/SKILL.md`](.agents/skills/diagnostico-comunitario/SKILL.md) para explicar procedimientos sin solicitar credenciales o resultados reales. **No hay todavía un broker de aislamiento automatizado:** Codex no debe ejecutar la captura real si comparte acceso con las credenciales y diagnósticos. La Skill no impide técnicamente que un agente con permisos de sistema lea archivos privados.

- [Guía de primeros pasos](docs/guia-principiantes.md)
- [Modelo de seguridad y límites](docs/seguridad-modelo.md)
- [Catálogo de conocimiento](knowledge/catalog.json)
- [Suite de pruebas](tests/test_diagnostico_app.py)

**Estado:** prototipo para laboratorio; SSH real multiplataforma y aislamiento frente a agentes todavía no certificados.

## Primer prototipo ejecutable: diagnóstico local

Ya está disponible un **prototipo v0.1.0 para pruebas**. En Linux, desde el repositorio clonado y tras revisar el script:

```sh
sh bin/serverdiag.sh
```

Crea un JSON privado en el directorio actual, con permisos `0600` y **sin realizar conexiones salientes**. También puedes descargar únicamente el script para inspeccionarlo:

```sh
curl -fL --output serverdiag.sh https://raw.githubusercontent.com/eltecnologoem/diagnostico-comunitario/main/bin/serverdiag.sh
sh -n serverdiag.sh
sh serverdiag.sh
```

Para generar un JSON compartible (sin host, IP, ID persistente ni logs) usando Python 3 local:

```sh
python3 tools/export-share.py serverdiag-FECHA-PID.json
```

La guía completa incluye recolección SSH **optativa** mediante stdin, pruebas de conectividad separadas y una suite de pruebas:

- [Instrucciones y límites del recolector](docs/collector.md)
- [Colector local POSIX sh](bin/serverdiag.sh)
- [Exportador seguro](tools/export-share.py)
- [Pruebas offline](tests/test_collector.py)

**Estado:** código inicial funcional de laboratorio; aún no es una edición auditada o certificada para servidores de producción.

## Uso rápido: comando de diagnóstico

Clona el repositorio, revisa el script y ejecútalo desde Linux (POSIX `sh`). **No requiere cuenta, SMTP ni acceso a Internet.** Por defecto no envía nada:

```bash
git clone https://github.com/eltecnologoem/diagnostico-comunitario.git
cd diagnostico-comunitario
sh -n bin/serverdiag.sh
sh bin/serverdiag.sh
```

Se genera `serverdiag-FECHA-PID.json` en la carpeta actual, con permisos privados `0600`.

### Diagnóstico parcial: `--only`

Puedes ejecutar únicamente las comprobaciones que interesan, separando las secciones con comas:

```bash
sh bin/serverdiag.sh --only system
sh bin/serverdiag.sh --only memory,disk
sh bin/serverdiag.sh --only database
sh bin/serverdiag.sh --only processes
sh bin/serverdiag.sh --only system,memory,disk,database,processes
sh bin/serverdiag.sh --only disk --output ./mi-diagnostico.json
```

| Sección | Qué comprueba |
|---|---|
| `system` | Kernel/identidad básica, tiempo encendido, CPU y carga |
| `memory` | Memoria RAM y swap |
| `disk` | Tamaño y ocupación de la partición raíz |
| `database` | Clientes MySQL/MariaDB disponibles, procesos y escucha TCP 3306 |
| `processes` | Recuento de procesos SSH (`sshd`) |

**Importante:** una sección excluida no se ejecuta: sus métricas quedan en `null` y sus comprobaciones en `skipped` cuando corresponde. La identificación mínima de origen sigue apareciendo en el JSON **privado**, independientemente de `--only`. El exportador compartible elimina esos identificadores.

Opciones adicionales:

```bash
sh bin/serverdiag.sh --help
sh bin/serverdiag.sh --stdout                    # JSON privado por stdout; no envía nada
sh bin/serverdiag.sh --app-dir /usr/local/APP     # verifica binarios MySQL embebidos
```

### Envío de reporte por correo (opcional y explícito)

El correo **no está habilitado por defecto**. Requiere Python 3, acceso a un SMTP con TLS y una configuración privada `.env`. El original privado se queda en el equipo; **solo se adjunta una copia compartible con campos permitidos**. No se adjuntan logs, hostname, IP ni variables de entorno.

1. Prepara el archivo de configuración:

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

2. Completa los campos de `.env` (ejemplo; sustituye por datos reales):

```dotenv
SMTP_HOST=smtp.example.org
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=cuenta@example.org
SMTP_PASSWORD=CLAVE_DE_APLICACION
MAIL_FROM=cuenta@example.org
MAIL_TO=destinatario@example.org
```

`SMTP_SECURITY` admite `starttls` o `ssl`; para SSL suele utilizarse el puerto 465. Nunca se permite SMTP sin cifrado. Usa una contraseña de aplicación cuando el proveedor lo requiera. El archivo `.env` **no se ejecuta como código shell** y se rechaza si puede leerlo otro usuario (permisos distintos de 0600).

3. Ejecuta un diagnóstico con envío expreso:

```bash
sh bin/serverdiag.sh --only system,memory,disk --email
```

Alternativamente, indica otro archivo de credenciales:

```bash
sh bin/serverdiag.sh --only database --email --env /ruta/privada/correo.env
```

Si SMTP falla, **el informe privado ya generado no se elimina** y el comando termina con error. Los datos salen únicamente cuando se indica `--email`. El correo convencional no garantiza cifrado extremo a extremo: usa un buzón cuyo propietario deba recibir esas métricas.

Consulta [la documentación técnica y las limitaciones](docs/collector.md). El envío SMTP es un mecanismo de **salida opt-in**, no monitoreo ni distribución automática a terceros.

## ¿Por qué nace este proyecto?

Diagnosticar un servidor Linux que deja de responder suele implicar conectarse por SSH, ejecutar múltiples comandos, revisar registros incompletos y tratar de reconstruir qué sucedió antes de una caída. Después de reiniciar, el sistema puede parecer normal y la evidencia más importante haberse perdido.

La situación es todavía más complicada cuando el administrador, un técnico externo y una herramienta de IA deben revisar el mismo incidente: cada uno recoge información distinta, con formatos incompatibles, y en ocasiones se comparten registros que contienen información sensible innecesaria.

**Diagnóstico Comunitario busca convertir esa recolección manual en un proceso seguro, estructurado y reutilizable.** La idea nació de una investigación real sobre un servidor Linux con interrupciones intermitentes y de la necesidad de comparar evidencias recogidas durante varios días.

## Qué pretendemos solucionar

- **Falta de evidencia:** disponer de una captura consistente del estado observable de CPU, RAM, swap, disco, red, firewall, servicios, SSH y eventos históricos disponibles.
- **Diagnósticos difíciles de comparar:** usar un esquema JSON versionado que permita comparar dos ejecuciones y detectar cambios relevantes.
- **Conclusiones precipitadas:** distinguir observaciones verificadas, datos desconocidos, hipótesis y acciones recomendadas; la ausencia de datos no demuestra ausencia de incidentes.
- **Exposición de información sensible:** mantener los datos completos bajo control del propietario y crear exportaciones compartibles mediante listas explícitas de campos permitidos.
- **Dependencia de una plataforma:** permitir el uso local sin cuentas y ofrecer un contrato de datos abierto para personas, visores, agentes de IA y herramientas comunitarias independientes.

## Principios del proyecto

1. **Local primero.** El Bash guarda el JSON en el propio servidor. **No envía información a ningún destino por defecto.**
2. **Solo lectura durante el diagnóstico.** No repara, reinicia, instala paquetes, modifica red/firewall ni ejecuta órdenes remotas. Los cambios de instalación o programación, si se ofrecen, deberán ser explícitos y estar separados del diagnóstico.
3. **Privacidad por diseño.** El informe privado y la exportación compartible son objetos distintos; la copia pública se construye desde una lista cerrada de campos, no mediante tachado de un informe confidencial.
4. **Formato común, consumidores independientes.** El recolector no depende de una nube, una cuenta, una sesión web ni un agente de IA.
5. **Evidencia antes de inferencias.** Cada hallazgo debe señalar el dato, la hora y las limitaciones que lo sustentan.
6. **Sin accesos ocultos.** El visor y el MCP no pueden enviar comandos al servidor diagnosticado ni solicitar credenciales SSH.

## Modos previstos

| Modo | Comportamiento esperado | ¿Sale información del servidor? |
|---|---|---|
| **Diagnóstico local** | Recolector Bash → JSON privado → visor local | No, por defecto. |
| **Compartir voluntariamente** | Exportador seguro → revisión del usuario → carga al visor temporal | Solo el JSON compartible autorizado. |
| **Monitoreo autogestionado** | Capturas periódicas enviadas a una instancia propia, con credencial restringida | Sí, únicamente cuando el administrador lo configura. |

### Visor temporal opcional

Se estudia una vista temporal en `preview-diagnosis.eliezermolina.org`. La propuesta contempla retención de 24 horas, borrado anticipado y acceso validado por correo y sesión/código de un solo uso. **El enlace identifica el reporte, pero no autoriza el acceso por sí mismo.** No se anunciará como servicio operativo hasta superar pruebas de privacidad y autorización.

### MCP local y agentes de IA

El primer MCP previsto será **local y de solo lectura**, con herramientas para listar capturas, consultar métricas, recuperar hallazgos y comparar dos momentos. No ejecutará comandos ni accederá a rutas fuera de una carpeta autorizada. Si el usuario conecta el MCP a un modelo externo, deberá revisar qué datos se transmiten a ese modelo: un MCP local no implica necesariamente inferencia local.

### Monitoreo autogestionado (fase posterior)

Se estudiará una API privada y autoalojable para recibir capturas periódicas desde servidores autorizados mediante credenciales limitadas a escritura. Esta capacidad será independiente del diagnóstico local y no requerirá un sistema comercial de gestión. El administrador controlará su instancia y los períodos de retención. **«Sin datos recibidos» no significa «servidor caído».** Para comprobar disponibilidad real se necesitará una señal externa e independiente.

### Uso seguro con Codex: privacidad estricta

**Importante:** la versión actual permite generar diagnósticos locales, pero **todavía no implementa un ejecutor seguro para Codex**. No entregues a Codex un entorno con llaves SSH, credenciales SMTP, variables de conexión o JSON reales del servidor.

Para mantener una política de **cero datos reales enviados al modelo**, Codex debe utilizar únicamente código, documentación y ejemplos sintéticos. La integración futura permitirá que Codex **solicite** un diagnóstico por alias a un broker local independiente, pero nunca leer sus secretos ni recibir el informe o hallazgos reales. Un analizador local separado procesará el JSON y mostrará las conclusiones al propietario.

Guardar credenciales en `.env` no las protege frente a un agente que pueda leer dicho archivo o ejecutar comandos en el mismo entorno. También el resultado de una herramienta MCP puede entrar en el contexto de un modelo externo.

Consulta la [política de seguridad](SECURITY.md) y el [diseño del flujo Codex aislado](docs/codex-secure-workflow.md), ambos normativos para el trabajo con datos reales.

## Desarrollo con OpenAI Codex

Utilizaremos **Codex como asistente de ingeniería** para transformar las especificaciones en cambios pequeños, auditables y acompañados de pruebas. Codex podrá ayudar a:

- Analizar el Bash histórico y documentar qué hace realmente antes de reutilizarlo.
- Implementar módulos del colector, exportador seguro, visor y MCP siguiendo contratos versionados.
- Escribir pruebas automáticas y fixtures sintéticos, revisar calidad, detectar regresiones y proponer mejoras.
- Preparar commits y pull requests revisables, con explicaciones técnicas de decisiones, riesgos y resultados.

**Codex no sustituye la revisión humana.** Ninguna propuesta de Codex autoriza ejecutar remediaciones, instalar servicios, acceder a sistemas de terceros ni publicar datos de clientes. Las contribuciones automatizadas deben incluir evidencia de pruebas y pasar revisión antes de integrarse.

Las instrucciones operativas para colaboradores y agentes están en [`AGENTS.md`](AGENTS.md). Esta separación permite explicar el proyecto en el README sin convertirlo en una lista de órdenes de programación.

## Hoja de ruta orientativa

- **Hito 0 — Auditoría:** recuperar y revisar el recolector histórico de julio y su formato JSON. Separar lo implementado de lo documentado y confirmar el comportamiento de solo lectura.
- **Hito 1 — MVP local:** recolector de solo lectura, esquema JSON privado, exportador compartible por allowlist, visor local y comparación entre capturas.
- **Hito 2 — Integración con agentes:** MCP local con permisos restrictivos, pruebas de aislamiento y entradas no confiables.
- **Hito 3 — Vista temporal:** servicio optativo, autenticación por correo, expiración, borrado y pruebas de autorización cruzada.
- **Hito 4 — Monitoreo autogestionado:** evaluar una API privada de ingesta periódica y un historial autoalojable, sin dependencias de plataformas comerciales.

Ningún hito se considerará terminado solamente porque exista una interfaz o una demostración visual.

## Seguridad y responsabilidad

- Nunca subir informes reales, credenciales, claves privadas, variables de entorno o datos de clientes a issues o pull requests.
- Usar direcciones y dominios de ejemplo en pruebas; no copiar configuraciones de servidores de producción.
- Un diagnóstico no equivale a garantía de disponibilidad, auditoría de seguridad ni prueba concluyente de causa raíz.
- Informar expresamente las comprobaciones no ejecutadas por falta de permisos o herramientas.
- No habilitar por defecto subidas, telemetría, actualización remota o instalación de tareas programadas.

La política de divulgación de vulnerabilidades se documentará en `SECURITY.md` antes de la primera publicación de código ejecutable.

## Estado actual y contribuciones

Este repositorio comienza como **punto de coordinación público**. El código de julio debe recuperarse, revisarse y probarse antes de incorporarlo: no asumimos que exista una edición comunitaria lista para producción.

Se aceptarán propuestas de arquitectura, esquemas, pruebas y mejoras mediante issues y pull requests una vez establecidas las guías de contribución. El proyecto se distribuye bajo la **[Apache License, Version 2.0](LICENSE)**. Puedes usar, modificar y redistribuir el código —incluso comercialmente— cumpliendo sus condiciones, incluyendo la conservación de avisos legales y la atribución correspondiente. Las contribuciones deberán respetar esta licencia.

## Autoría y contacto

Creado e impulsado por **Eliezer Molina Méndez**, administrador de sistemas y desarrollador, como iniciativa para compartir herramientas prácticas de diagnóstico y conocimiento técnico con la comunidad.

- Proyecto y artículos: [https://eliezermolina.org](https://eliezermolina.org)
- Contacto: [contacto@eliezermolina.com](mailto:contacto@eliezermolina.com)

---

> **Diagnosticar mejor no significa ejecutar más comandos: significa recopilar evidencia confiable, interpretar sus límites y mantener al propietario en control de sus datos.**
