# Política de seguridad — Diagnóstico Comunitario

Este proyecto está en **fase de prototipo comunitario**. Aún no hay una versión estable ni una auditoría integral de seguridad. El equipo agradece las notificaciones responsables sobre posibles fallos.

## Política para uso con Codex y otros agentes de IA

**Regla principal: no entregar a Codex credenciales SSH, variables de entorno de conexión, archivos privados ni salidas de diagnóstico reales.** Esta restricción aplica tanto a prompts como a herramientas, consola, MCP y archivos del workspace.

- Codex puede **desarrollar y probar este código con datos sintéticos**. No puede recibir ni consultar las credenciales o informes reales del administrador.
- La presencia de una variable en un `.env` o en el entorno de un proceso **no la hace inaccesible al agente**: si Codex tiene permiso para leer ese entorno o ejecutar herramientas en él, puede acceder al valor. `.gitignore` y `AGENTS.md` **no sustituyen el aislamiento del sistema operativo**.
- La integración segura prevista requiere un **broker local separado**, ejecutándose con otra identidad y credenciales fuera del workspace de Codex. Solo acepta destinos preautorizados por alias y comandos de un catálogo cerrado.
- El broker debe guardar el diagnóstico privado y **analizarlo localmente**, sin enviarlo ni devolver métricas, hostnames, IP, identificadores, registros, hallazgos reales o credenciales al modelo. Codex podrá recibir únicamente un estado genérico de ejecución, sin datos derivados del servidor.
- Si se autoriza a Codex a leer un JSON real, incluso sanitizado, se abandona la **modalidad de privacidad estricta** y los datos mostrados al modelo pueden enviarse a un proveedor externo. Cualquier modalidad futura de divulgación debe ser explícita y separada.
- El modo seguro **no debe** ejecutar `--email`, herramientas de sondeo remoto no autorizadas, exportaciones HTTP ni scripts arbitrarios indicados por un agente.
- El prototipo actual **NO incluye todavía el broker ni el aislamiento de Codex**. Ejecutar `remote-collect.sh` desde Codex con una llave real, o permitirle leer `.env` e informes reales, no constituye uso seguro conforme a esta política.

Consulta el [diseño y checklist de aislamiento para Codex](docs/codex-secure-workflow.md). Su estado es **propuesto y pendiente de implementación y auditoría**. No presentamos esta arquitectura como garantía ya disponible.

## Auditoría extendida y hardening: límites obligatorios

- `bin/audit-extended.sh` y el comando `diagnostico.py auditar` son **exclusivamente de lectura**. Nunca pueden ejecutar reinicios, modificaciones del sistema, instalaciones o ajustes del firewall/SSH.
- Los valores de `sshd -T` describen la configuración global efectiva, **no las excepciones por `Match` ni la seguridad de cada usuario**. Un control `unavailable` o `null` jamás se considera conforme o seguro.
- Los conteos de journal son muestras limitadas; si la consulta falla, el valor debe ser `null` / `unavailable`, **no cero**. No exportar líneas crudas, nombres de usuarios o servicios, ni trazas.
- `tools/hardening.py` es una utilidad separada y potencialmente modificadora. `--plan` no modifica; `--apply` y `--rollback` solo se pueden usar en una terminal interactiva autorizada, desde Debian/Ubuntu, como root y con un plan de recuperación. **Nunca invocarlas desde Codex, MCP, SSH automatizado o jobs**.
- La aplicación está restringida a cuatro controles `sysctl`; no afecta por diseño `sshd_config`, UFW, nftables, rutas, APT, cuentas ni servicios. **La compatibilidad con el workload debe evaluarse antes de cualquier cambio**.
- Debe existir snapshot antes del cambio, registro de ID, comprobación de estado posterior y rollback verificable. Si el archivo gestionado fue modificado por un tercero, bloquear la reversión automática.
- Las pruebas actuales son de laboratorio con cambios simulados. No constituyen certificación CIS, prueba en servidores de producción ni garantía de ausencia de efectos colaterales.

Guía: [Auditoría extendida y hardening Debian/Ubuntu](docs/auditoria-hardening.md).

## Cómo reportar una vulnerabilidad de manera privada

**No publiques vulnerabilidades sin corregir, pruebas de explotación, credenciales ni diagnósticos reales en Issues, Discussions o pull requests públicos.**

Para comunicar una vulnerabilidad de forma privada:

1. Escribe a **contacto@eliezermolina.com**, con el asunto **`[SEGURIDAD] Diagnóstico Comunitario`** y un resumen de la vulnerabilidad. Esta dirección figura como contacto público del autor; el contenido del correo no se publica automáticamente en el repositorio.
2. Si GitHub tiene habilitada la función **Private Vulnerability Reporting** para este repositorio, puedes utilizar su formulario privado desde **Security → Advisories → Report a vulnerability**.
3. Evita enviar secretos, muestras reales de clientes o datos sensibles en el primer mensaje. Si se necesitan evidencias protegidas, coordina previamente con el mantenedor un canal adecuado.

**Advertencia:** el correo ordinario no garantiza cifrado extremo a extremo. El uso de la dirección anterior no debe interpretarse como una garantía criptográfica de confidencialidad.

## Qué incluir en el reporte

- Descripción clara del comportamiento observado y su impacto.
- Ruta o componente afectado (recolector Bash, exportador, SMTP opcional, SSH opcional, privacidad, scripts de pruebas).
- Commit o versión probada, distribución Linux y pasos mínimos para reproducirlo.
- Evidencia sintética, redactada y suficiente para reproducir el problema sin exponer datos reales.
- Cualquier mitigación o condición que reduzca el impacto.

## Alcance y versiones

| Rama o versión | Estado de seguridad |
| --- | --- |
| `main` | Prototipo en desarrollo; sin garantía de soporte ni estabilidad |
| Versiones estables | No publicadas todavía |

No existe actualmente un calendario garantizado de respuesta o corrección. Los reportes se revisarán según la disponibilidad del mantenedor y su criticidad. Cuando exista una corrección, se procurará documentar el impacto y dar crédito al investigador, si así lo desea.

## Divulgación responsable

Pedimos permitir la validación y la corrección antes de publicar detalles que faciliten ataques. No realices pruebas sobre servidores, cuentas o datos de terceros sin su autorización. No se autoriza el acceso no consentido a sistemas por el hecho de participar en este proyecto.

## Principios de seguridad

- El diagnóstico local **no realiza conexiones salientes por defecto**.
- El envío SMTP requiere activación expresa y solo transporta un reporte compartible sanitizado.
- Los informes privados pueden contener información sensible: no subirlos a GitHub ni adjuntarlos a reportes públicos.
- El diagnóstico y el MCP planeado son de solo lectura; no deben implementar remediación arbitraria ni acceso SSH oculto.
- Los hallazgos de seguridad se gestionan por el canal privado anterior, nunca mediante evidencia de producción publicada.

**Autor y mantenedor:** Eliezer Molina Méndez — https://eliezermolina.org
