# Integración segura con Codex — diseño y límites de privacidad

> **Estado: diseño propuesto, NO implementado.** No hay actualmente un ejecutor aislado, broker de credenciales ni herramienta MCP de diagnóstico instalada por este repositorio. El Bash y las utilidades existentes no ofrecen por sí mismos estas garantías.

## 1. Dos requisitos que no deben confundirse

1. **Codex puede solicitar un diagnóstico sin manejar credenciales.** Un ejecutor local confiable realiza la conexión y la recolección.
2. **Ningún dato real del servidor sale hacia Codex ni hacia su modelo.** Un analizador determinista local procesa el informe completo; Codex solo puede recibir la confirmación operacional mínima de ejecución (por ejemplo: *finalizado*, *no disponible*, *error de autorización*), sin KPI, hallazgos, identificadores ni información derivada del estado del servidor.

**No es posible que Codex analice por sí mismo un diagnóstico real y, simultáneamente, garantizar que Codex nunca reciba datos de ese diagnóstico.** Si el modelo externo interpreta métricas o conclusiones reales, ya existe transmisión de información técnica. Tal modo sería una función diferente, explícitamente autorizada, y no estaría cubierto por la garantía de privacidad estricta.

Un «MCP local» tampoco implica «modelo local»: el contenido retornado por el MCP a Codex puede formar parte del contexto enviado al modelo.

## 2. Arquitectura de confianza

```text
USUARIO
  |
  | autorización para diagnosticar un destino preaprobado
  v
CODEX (contenedor/usuario restringido; sin claves ni datos reales)
  |
  | herramienta: request_diagnostic(target_alias)
  v
BROKER LOCAL DE CONFIANZA (servicio independiente, otro UID)
  |-- Configuración protegida (fuera de workspace Codex)
  |-- Credencial SSH de mínimo privilegio / host key fijada
  |-- Allowlist de destinos y comandos, sin shell arbitraria
  |-- Ejecutor del colector fijado a versión/hash verificado
  |-- Reporte privado -> almacenamiento local 0700/0600
  |-- Analizador determinista local (sin red externa)
  |-- Visor privado local accesible solo al usuario
  |
  +--> A Codex: {status: "completed"} (sin contenido diagnóstico)
```

La herramienta debe impedir controlar puerto, hostname, usuario SSH, ruta del script o argumentos de shell de forma arbitraria. Codex envía **solo un alias opaco previamente registrado** y, como mucho, una sección de diagnóstico de un enum cerrado.

### Aislamiento mínimo verificable

- Codex ejecutado como usuario distinto o en contenedor separado, sin montar directorio de credenciales ni capturas, sin acceso al entorno del broker, a `/proc` de otros usuarios ni a sockets privilegiados. No basta un `chmod 600` si Codex comparte UID root/propietario, puede usar `sudo` o tiene acceso a Docker socket.
- Broker con identidad propia y controles de sistema operativo, no ejecuta código arbitrario proporcionado por Codex.
- Canal broker–Codex de permisos mínimos (p. ej. socket Unix con ACL y mensajes estructurados), sin endpoints abiertos a redes públicas.
- SSH con clave de alcance mínimo y usuario dedicado no-root, sin sudo, con `StrictHostKeyChecking=yes`, `known_hosts` preparado fuera del agente. Restringir PTY/túneles/forwarding y, en una versión endurecida, una *forced command* fija del lado remoto. **Una forced command no es compatible directamente con ejecutar código arbitrario por heredoc; requiere recolector instalado y comando fijo autorizado.**
- No entregar al modelo stdout/stderr del recolector o de SSH, reportes, nombres de archivos privados, rutas de usuario, códigos arbitrarios de error ni secretos. Errores con categorías cerradas.
- Deshabilitar `--email`, probes activos de red no aprobados, upload HTTP y actualizaciones remotas desde el modo seguro.
- Registros de auditoría locales mínimos (hora, ID opaco del trabajo y estado), sin destino, datos de cliente, secretos ni diagnóstico.

## 3. Credenciales en variables de entorno: uso correcto

El usuario puede definir la conexión mediante un fichero de configuración privado **del broker**, cargado por el sistema operativo o un almacén de secretos **solo en el proceso del broker**. No poner estos valores en el `.env` de la raíz del repositorio si Codex tiene acceso al workspace.

Ejemplo **solo de diseño**, no implementado:

```dotenv
# Archivo fuera del repositorio: /etc/serverdiag-broker/targets.d/lab-01.env
SD_SSH_HOST=192.0.2.10
SD_SSH_PORT=2222
SD_SSH_USER=diagnostic
SD_SSH_IDENTITY_FILE=/etc/serverdiag-broker/keys/lab-01
SD_SSH_KNOWN_HOSTS=/etc/serverdiag-broker/known_hosts
SD_TARGET_ALIAS=lab-01
```

No guardar contraseñas SSH en texto claro si puede usarse autenticación con clave. Los valores anteriores son datos de ejemplo, no deben copiarse con credenciales reales al repositorio.

El broker debe validar configuración sin ejecutarla como shell; las variables no pueden transformarse en comandos o argumentos SSH arbitrarios. El fichero, la llave y su directorio deben pertenecer al usuario protegido del broker y no ser legibles por Codex.

**Prohibido:** suministrar `SD_SSH_PASSWORD`, claves privadas o el contenido de `.env` a Codex, colocar secretos en prompts o emplear `source .env` bajo una shell que Codex pueda controlar.

## 4. Flujo de uso previsto

1. Usuario obtiene el repositorio y revisa código, firma/hash de versión y política de seguridad.
2. Usuario configura el broker de confianza **fuera** del workspace Codex, registra un alias y autoriza explícitamente el servidor.
3. Usuario inicia Codex en un entorno restringido y le da el repositorio de código, **sin montar secretos ni informes reales**.
4. Codex solicita `request_diagnostic(target_alias="lab-01", section="system")`. La llamada es ilustrativa; **esta herramienta todavía no existe**.
5. Broker valida alias, autorización, límites y huella SSH; ejecuta el colector en modo lectura con el usuario de mínimo privilegio.
6. Broker guarda el JSON privado exclusivamente de forma local, ejecuta el análisis determinista y presenta el informe completo al usuario desde un visor local separado.
7. Codex recibe únicamente un estado genérico. **Si el usuario necesita que Codex interprete el resultado real, tendrá que aceptar un modo diferente con divulgación de datos y consentimiento informado.**

## 5. Qué puede hacerse hoy (sin garantías de broker)

El prototipo ofrece `sh bin/serverdiag.sh` para diagnóstico local y `sh bin/remote-collect.sh` para SSH opt-in, pero **ambos deben ejecutarse manualmente fuera del entorno Codex si contienen información real**. No colocar credenciales ni informes en el repositorio que se entrega a Codex.

La instrucción «Codex lee variables de entorno, establece SSH, captura JSON y lo analiza» **no corresponde al modo A** y no debe anunciarse como seguro. Aunque se oculten campos después, un stdout, traceback, comando shell o herramienta MCP puede haber entregado ya información al modelo.

## 6. Pruebas de salida obligatorias

- [ ] Codex no puede leer variables `SD_SSH_*`, claves ni `.env` del broker (incluidos `/proc`, entorno y archivos).
- [ ] Codex no puede leer el directorio con diagnósticos privados ni logs SSH.
- [ ] Solo los aliases y secciones de allowlist se aceptan; destinos arbitrarios, argumentos de shell o rutas se rechazan.
- [ ] El broker no devuelve en resultados o errores ni un único hostname, IP, versión, KPI, hallazgo o dato privado del destino.
- [ ] Control de red impide al agente enviar datos del servidor a destinatarios externos.
- [ ] SSH verifica huella del servidor y usa credencial restringida, sin sudo ni shell remota arbitraria.
- [ ] Pruebas con credenciales falsas, rutas señuelo y *prompt injection* muestran que Codex no puede acceder a ellas.
- [ ] Se verifica que los campos reales nunca llegan al historial de Codex, herramientas, logs ni archivos de trabajo.
- [ ] Se prueba el comportamiento ante fallo parcial, timeout, clave revocada, servidor desconocido o rechazo de autorización, sin mostrar detalles sensibles.
- [ ] La revisión de seguridad ocurre antes de presentar el modo como implementado.

## 7. Referencias técnicas

- OpenAI — Sandbox security: https://developers.openai.com/api/docs/guides/agents-api/environments/security
- OpenAI — MCP connections: https://developers.openai.com/api/docs/guides/agents-api/tools/mcp
- OpenAI — OpenAI-hosted sandboxes: https://developers.openai.com/api/docs/guides/agents-api/environments/openai-hosted
- OpenAI — Secure tool/MCP risks: https://developers.openai.com/api/docs/guides/tools-connectors-mcp

**Proyecto:** Diagnóstico Comunitario — Eliezer Molina Méndez — https://eliezermolina.org
