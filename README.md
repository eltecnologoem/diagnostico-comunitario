# Diagnóstico Comunitario

**Diagnóstico Linux abierto, reproducible y respetuoso de la privacidad.**

**Autor y responsable de la iniciativa:** [Eliezer Molina Méndez](https://eliezermolina.org)  
**Sitio del proyecto y divulgación:** [eliezermolina.org](https://eliezermolina.org)  
**Estado del repositorio:** fase de diseño y preparación del código comunitario; las funciones descritas a continuación constituyen objetivos, no funcionalidades ya certificadas.

## ¿Por qué nace este proyecto?

Diagnosticar un servidor Linux que deja de responder suele implicar conectarse por SSH, ejecutar múltiples comandos, revisar registros incompletos y tratar de reconstruir qué sucedió antes de una caída. Después de reiniciar, el sistema puede parecer normal y la evidencia más importante haberse perdido.

La situación es todavía más complicada cuando el administrador, un técnico externo y una herramienta de IA deben revisar el mismo incidente: cada uno recoge información distinta, con formatos incompatibles, y en ocasiones se comparten registros que contienen información sensible innecesaria.

**Diagnóstico Comunitario busca convertir esa recolección manual en un proceso seguro, estructurado y reutilizable.** La idea nació de una investigación real sobre un servidor Linux con interrupciones intermitentes y de la necesidad de comparar evidencias recogidas durante varios días.

## Qué pretendemos solucionar

- **Falta de evidencia:** disponer de una captura consistente del estado observable de CPU, RAM, swap, disco, red, firewall, servicios, SSH y eventos históricos disponibles.
- **Diagnósticos difíciles de comparar:** usar un esquema JSON versionado que permita comparar dos ejecuciones y detectar cambios relevantes.
- **Conclusiones precipitadas:** distinguir observaciones verificadas, datos desconocidos, hipótesis y acciones recomendadas; la ausencia de datos no demuestra ausencia de incidentes.
- **Exposición de información sensible:** mantener los datos completos bajo control del propietario y crear exportaciones compartibles mediante listas explícitas de campos permitidos.
- **Dependencia de una plataforma:** permitir el uso local sin cuentas y dejar que personas, visores, agentes de IA o herramientas como WHMCS consuman el mismo contrato de datos.

## Principios del proyecto

1. **Local primero.** El Bash guarda el JSON en el propio servidor. **No envía información a ningún destino por defecto.**
2. **Solo lectura durante el diagnóstico.** No repara, reinicia, instala paquetes, modifica red/firewall ni ejecuta órdenes remotas. Los cambios de instalación o programación, si se ofrecen, deberán ser explícitos y estar separados del diagnóstico.
3. **Privacidad por diseño.** El informe privado y la exportación compartible son objetos distintos; la copia pública se construye desde una lista cerrada de campos, no mediante tachado de un informe confidencial.
4. **Formato común, consumidores independientes.** El recolector no depende de WHMCS, una nube, una sesión web ni un agente de IA.
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

### WHMCS y servicios administrados

WHMCS será un consumidor opcional de reportes e historial, no un controlador remoto de los equipos. La recepción periódica mediante una API privada y el conector WHMCS se estudiarán como una fase posterior. **«Sin datos recibidos» no significa «servidor caído».** Una comprobación de disponibilidad externa debe ser independiente.

## Desarrollo con OpenAI Codex

Utilizaremos **Codex como asistente de ingeniería** para transformar las especificaciones en cambios pequeños, auditables y acompañados de pruebas. Codex podrá ayudar a:

- Analizar el Bash histórico y documentar qué hace realmente antes de reutilizarlo.
- Implementar módulos del colector, exportador seguro, visor y MCP siguiendo contratos versionados.
- Escribir pruebas automáticas y fixtures sintéticos, revisar calidad, detectar regresiones y proponer mejoras.
- Preparar commits y pull requests revisables, con explicaciones técnicas de decisiones, riesgos y resultados.

**Codex no sustituye la revisión humana.** Ninguna propuesta de Codex autoriza ejecutar remediaciones, instalar servicios, acceder a sistemas de terceros ni publicar datos de clientes. Las contribuciones automatizadas deben incluir evidencia de pruebas y pasar revisión antes de integrarse.

Las instrucciones operativas para colaboradores y agentes están en [`AGENTS.md`](AGENTS.md). Esta separación permite explicar el proyecto en el README sin convertirlo en una lista de órdenes de programación.

## Hoja de ruta orientativa

- **Hito 0 — Auditoría:** recuperar y revisar el recolector histórico de julio, su formato JSON y cualquier conector existente. Separar lo implementado de lo documentado.
- **Hito 1 — MVP local:** recolector de solo lectura, esquema JSON privado, exportador compartible por allowlist, visor local y comparación entre capturas.
- **Hito 2 — Integración con agentes:** MCP local con permisos restrictivos, pruebas de aislamiento y entradas no confiables.
- **Hito 3 — Vista temporal:** servicio optativo, autenticación por correo, expiración, borrado y pruebas de autorización cruzada.
- **Hito 4 — Administración:** API privada de ingesta periódica y evaluación del conector WHMCS.

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

Se aceptarán propuestas de arquitectura, esquemas, pruebas y mejoras mediante issues y pull requests una vez establecidas las guías de contribución. La licencia del código se elegirá y publicará antes de distribuir una primera versión open source; **que un repositorio sea público no concede por sí solo una licencia de reutilización**.

## Autoría y contacto

Creado e impulsado por **Eliezer Molina Méndez**, administrador de sistemas y desarrollador, como iniciativa para compartir herramientas prácticas de diagnóstico y conocimiento técnico con la comunidad.

- Proyecto y artículos: [https://eliezermolina.org](https://eliezermolina.org)
- Contacto: [contacto@eliezermolina.com](mailto:contacto@eliezermolina.com)

---

> **Diagnosticar mejor no significa ejecutar más comandos: significa recopilar evidencia confiable, interpretar sus límites y mantener al propietario en control de sus datos.**
