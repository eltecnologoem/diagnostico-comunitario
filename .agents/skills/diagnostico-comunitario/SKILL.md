---
name: diagnostico-comunitario
version: 0.2.0
summary: Guía a un usuario para obtener diagnóstico Linux y ayuda de resolución sin entregar al modelo datos privados.
description: Actívala cuando un usuario pida investigar un servidor Linux lento, sin conexión o con errores de disco, memoria, servicios o MySQL mediante Diagnóstico Comunitario. Usa únicamente guías públicas y datos sintéticos; no leas ni ejecutes diagnósticos reales desde Codex.
---

# Diagnóstico Comunitario para Codex — modo de privacidad estricta

**Esta skill es operativa como guía, no proporciona una conexión SSH segura desde Codex.** La conexión real se hace en una ventana local de confianza abierta por el usuario y aislada de la sesión de Codex. No afirmar que existe broker de credenciales, MCP remoto ni acceso a diagnósticos privado desde Codex.

## Flujo al ayudar a principiantes

1. Comprueba que la persona quiere diagnosticar un Linux propio o autorizado y que tiene el repositorio disponible.
2. Explica cómo abrir **una terminal local fuera de la sesión de Codex**. Si ya tiene el repositorio: `python3 diagnostico.py` (Linux/macOS) o `py -3 diagnostico.py` (Windows). La primera ejecución inicia el asistente de conexión.
3. No solicites que pegue contraseñas, llaves, contenido de `.env`, IP privadas, usuarios reales ni el contenido de `profiles.json`.
4. El usuario configura un alias, host/puerto y método `ssh-agent`, llave o contraseña interactiva en el runner **local**, que guarda perfiles fuera del repositorio.
5. Para SSH, explica cómo verificar la huella del servidor mediante un canal independiente antes de su primer acceso. No recomendar `StrictHostKeyChecking=no` ni `sshpass`.
6. El usuario ejecuta en su terminal local `python3 diagnostico.py ejecutar --perfil ALIAS` o `--local`. Se abre un informe HTML privado offline. Ni el JSON ni el HTML se incorporan al contexto de Codex.
7. Puedes ayudar a entender **conceptos generales** consultando `knowledge/catalog.json`, la documentación pública y comandos de solo lectura de las guías. No solicites al usuario que copie resultados reales a Codex en modo estricto.
8. Si el usuario desea interpretación generativa de métricas reales por Codex, explica que se requiere cambiar a un futuro modo separado de consentimiento explícito y divulgación mínima; ese modo **no está implementado**.

## Herramientas y rutas prohibidas

- **NO** leer, listar ni buscar `~/.local/state/diagnostico-comunitario`, `%LOCALAPPDATA%/DiagnosticoComunitario`, `~/Library/Application Support/DiagnosticoComunitario`, ni sus contenidos. Incluye `profiles.json`, `reports/*.json`, `reports/*.html` y cualquier credencial.
- **NO** invocar `ssh`, `remote-collect.sh`, `bin/probe-connectivity.sh` o `diagnostico.py ejecutar` contra servidores reales desde el entorno de Codex: si Codex comparte UID, no existe garantía de privacidad.
- **NO** leer procesos, variables de entorno de autenticación, agentes SSH, claves privadas ni archivos `.env`.
- **NO** usar salida de consola, MCP, screenshots ni extractos de logs con datos del servidor como sustituto de la política.
- **NO** ejecutar reparaciones ni cambios de firewall, reinicios, borrados o ajustes de sistema sin un procedimiento separado y autorización.

## Comandos seguros para Codex dentro del repositorio

- `python3 diagnostico.py --help`
- `python3 diagnostico.py guias`
- `python3 diagnostico.py guias --codigo DC-DISK-001`
- `python3 -m unittest discover -s tests -v` (solo fixtures sintéticos y en workspace aislado)

La línea `diagnostico.py estado` devuelve únicamente un estado genérico y tampoco demuestra que Codex esté aislado. Las instrucciones de esta skill **no son una frontera técnica**: solo un sandbox/usuario separado y permisos reales proporcionan aislamiento.

## Qué decir al usuario al terminar

Indica si la herramienta está disponible, qué pasos seguir en su terminal privada y qué guía general puede consultar; no informes que has visto su diagnóstico si no tuviste acceso (en modo estricto no lo tienes).

## Auditoría extendida y hardening (v0.3)

- Puede explicar las guías **públicas** de `docs/auditoria-hardening.md` y las diferencias entre auditoría, plan y cambios de hardening.
- No ejecutar `tools/hardening.py --apply` ni `--rollback`; esas acciones requieren operador y consola de confianza, no una decisión del modelo.
- No solicitar ni leer resultados privados de `bin/audit-extended.sh` ni reproducir detalles reales de un host en el prompt.
- Recomendar al operador que lance desde una terminal fuera de Codex: `python3 diagnostico.py auditar --local` o `--perfil ALIAS`; los informes se visualizan localmente.
- El estado `null` / `unavailable` **no** demuestra cumplimiento de medidas de seguridad.
- No prescribir cambios de SSH/firewall sin verificar accesos de respaldo, dependencias y rollback.
