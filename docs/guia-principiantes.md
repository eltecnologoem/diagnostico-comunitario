# Empezar con Diagnóstico Comunitario v0.2 (laboratorio)

**Objetivo:** diagnosticar un servidor Linux sin compartir claves, hostname ni capturas con servicios externos. El informe se visualiza **en tu propia computadora**, con reglas deterministas y 20 guías de consulta.

## Requisitos

- Python 3.9 o superior en el equipo donde se ejecuta el asistente.
- Linux si deseas diagnosticar la misma computadora. Desde Windows o macOS, el asistente permite diagnosticar un servidor Linux remoto mediante OpenSSH.
- Cuenta SSH autorizada, preferiblemente con permisos limitados, con acceso a `/proc`, `df`, `ps` y `ss` según la configuración del servidor.
- Clona y revisa el repositorio. No ejecutes scripts descargados a ciegas. No hagas pruebas en servidores ajenos.

## Inicio en tres pasos

**Linux o macOS** (terminal de confianza):

```sh
git clone https://github.com/eltecnologoem/diagnostico-comunitario.git
cd diagnostico-comunitario
python3 diagnostico.py
```

**Windows** (PowerShell, terminal de confianza):

```powershell
git clone https://github.com/eltecnologoem/diagnostico-comunitario.git
cd diagnostico-comunitario
py -3 diagnostico.py
```

El asistente te preguntará si el diagnóstico es `local` o `ssh`. Para SSH solicita: alias, IP/host, puerto, usuario y método de autenticación. Si seleccionas `key`, escribe la ruta absoluta de la llave privada existente, **no su contenido**. No guarda contraseñas.

### Primera conexión SSH

El runner exige `StrictHostKeyChecking=yes`. Si todavía no conoces la clave pública del servidor, verifica la huella con el proveedor o por consola autorizada **antes** de aceptarla en una sesión SSH manual. Una vez almacenada la clave validada en `known_hosts`, regresa al asistente.

Las credenciales o perfiles se conservan fuera del checkout. Nunca deben copiarse a Codex.

## Ejecutar

```sh
python3 diagnostico.py ejecutar --local
python3 diagnostico.py ejecutar --perfil servidor-01
python3 diagnostico.py ejecutar --perfil servidor-01 --only disk,memory
python3 diagnostico.py ejecutar --perfil servidor-01 --no-abrir
python3 diagnostico.py guias
python3 diagnostico.py guias --codigo DC-DISK-001
```

Desde Windows utiliza `py -3` en lugar de `python3` cuando corresponda. El informe HTML se abre en el navegador como archivo local sin scripts ni recursos externos. Los JSON y HTML privados se almacenan fuera del repositorio, con permisos restrictivos en sistemas POSIX. No existe subida ni envío SMTP desde este asistente.

La opción `--only` acepta `system,memory,disk,database,processes`; una sección no seleccionada queda sin datos.

## Ayuda de Codex sin compartir datos

Pega a Codex esta solicitud **sin nombres de servidor ni métricas**:

> Ayúdame a usar Diagnóstico Comunitario en modo privado. Tengo el repositorio y ejecutaré el asistente en mi propia terminal. Explícame cómo usar el catálogo de guías, sin solicitarme datos reales ni credenciales.

Codex puede explicar las guías públicas y ayudarte a entender verificaciones generales. **No puede analizar automáticamente el JSON real y mantener al mismo tiempo la garantía de que ningún dato real sale hacia el modelo.** El análisis real se realiza localmente; si más adelante necesitas otro modo con intercambio de métricas, deberá ser explícito y claramente distinto.

## Qué debe entender el usuario

- El diagnóstico local es de solo lectura, pero genera archivos privados y carga los comandos de inspección.
- La conexión SSH remota se realiza mediante autorización expresa; ninguna tarea periódica se instala.
- Un hallazgo indica evidencia y verificaciones sugeridas, no causa raíz confirmada.
- El prototipo no lee logs, SMART, inodos, DNS, estado real de apps ni historial histórico sin datos adecuados.
- No ejecutes comandos de corrección sin entender su efecto, contar con backup y aprobar la intervención.

## Estado

Versión **0.2.0 de laboratorio**. El modo de integración automática «Codex solicita SSH y solo recibe estado» exige un broker aislado con cuentas/ACLs del sistema operativo. **Todavía no está implementado ni certificado.**
