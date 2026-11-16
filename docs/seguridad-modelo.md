# Modelo de seguridad v0.2 — uso con Codex

## Activos

Llaves y credenciales SSH, hosts/usuarios, claves de servidor conocidas (`known_hosts`), JSON privados, HTML de resultados, metadatos de sistema y reglas de diagnóstico.

## Lo que implementamos

1. El asistente no utiliza servicios de nube, webhooks, LLM, SaaS ni correo.
2. `--local` invoca el colector Bash en el propio Linux; `--perfil` realiza **SSH explícito** a un Linux autorizado y envía el script por `stdin`.
3. OpenSSH se ejecuta con parámetros de hardening: `StrictHostKeyChecking=yes`, sin agent forwarding, sin port forwarding, sin `ProxyCommand` y sin configuración SSH heredada (`-F none`).
4. Los perfiles se almacenan fuera del repositorio; no contienen contraseñas, pero **sí datos sensibles de conexión**. El programa no los imprime en el JSON ni en los mensajes de éxito.
5. Los reportes se escriben en un directorio privado (POSIX 0700; archivos 0600). En Windows, la protección depende también de ACLs de la cuenta y del sistema.
6. El visor HTML local tiene CSP que impide JavaScript y recursos remotos; cualquier contenido recibido del servidor se escapa como texto.
7. El análisis local es determinista; las reglas no ejecutan reparaciones y nunca confunden `null` con 0.
8. Las guías de Codex solo usan conocimiento público/sintético, **sin acceder a archivos de diagnóstico**.

## Lo que NO está garantizado

- **No existe aislamiento real si Codex comparte UID/ACL con los archivos o puede ejecutar comandos con permisos del propietario**. Un `.env`, `profiles.json`, `.gitignore`, `AGENTS.md` o una Skill no son barrera de seguridad.
- Que el modelo **no reciba los datos reales** depende de mantenerlos fuera del workspace, herramientas y stdout/stderr accesibles a Codex; no ejecutar el diagnóstico real en la terminal del agente.
- SSH con contraseña interactiva puede requerir consola/TTY y debe usarse exclusivamente fuera de Codex; se recomienda `ssh-agent` y llaves restringidas.
- El colector remoto se ejecuta con los permisos del usuario SSH. El script transmite comandos por stdin, lo que otorga a la identidad SSH ejecución de shell remota. **Para un perfil de mayor seguridad**, debe implementarse en el futuro una `ForceCommand`/comando fijo del lado del servidor, incompatibles con ejecución arbitraria por heredoc.
- No se ha realizado pentest, auditoría de dependencias, firma de releases, matriz completa Windows/macOS/Linux ni prueba de resistencia a un servidor remoto malicioso que envíe salida ilimitada.
- La ausencia de telemetría propia no garantiza que un sistema operativo, shell, terminal o agente de terceros no registre comandos por su cuenta.

## Seguridad de uso

- No se deben ejecutar `ssh`, `--perfil` ni `diagnostico.py ejecutar` desde Codex en **modo estricto**.
- Usar una terminal separada y de confianza o implementar aislamiento OS real antes de permitir automatización.
- No subir JSON/HTML real a GitHub, Codex, logs de CI o correo; no copiar valores a prompts.
- Validar fingerprints SSH por fuente independiente, nunca `StrictHostKeyChecking=no`.
- Leer [SECURITY.md](../SECURITY.md) y [docs/codex-secure-workflow.md](codex-secure-workflow.md) para el diseño de un futuro broker.

## Pruebas de salida para broker automático futuro

Aislar procesos y filesystem (cuentas distintas), verificar denegación en `/proc`/ACL/archivos, denegar destinos arbitrarios, no devolver stdout/stderr del objetivo, validar permisos de socket local, usar una conexión autorizada por alias, probar ataques de inyección de comandos, verificar inexistencia de fugas en el contexto del modelo y auditar cada ejecución con datos minimizados.
