# Política de seguridad — Diagnóstico Comunitario

Este proyecto está en **fase de prototipo comunitario**. Aún no hay una versión estable ni una auditoría integral de seguridad. El equipo agradece las notificaciones responsables sobre posibles fallos.

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
