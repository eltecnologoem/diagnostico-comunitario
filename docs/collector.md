# Colector comunitario — primer prototipo ejecutable (v0.1.0)

**Autor:** Eliezer Molina Méndez · [eliezermolina.org](https://eliezermolina.org)

> Prototipo para pruebas, sin certificación de compatibilidad entre distribuciones ni auditoría de seguridad completa.

## Ejecutar diagnóstico local, sin enviar datos

En un Linux, después de clonar el repositorio y revisar el script:

```sh
sh bin/serverdiag.sh
```

El colector crea en el directorio actual un archivo privado llamado `serverdiag-FECHA-PID.json`, con permisos `0600`. No usa Internet, no instala paquetes, no cambia servicios, no crea cron y no pide contraseñas.

Para guardar en una ubicación elegida:

```sh
sh bin/serverdiag.sh --output /ruta/privada/diagnostico.json
```

Alternativa: descargar el archivo individual (descarga optativa desde GitHub, ejecución siempre local):

```sh
curl -fL --output serverdiag.sh https://raw.githubusercontent.com/eltecnologoem/diagnostico-comunitario/main/bin/serverdiag.sh
sh -n serverdiag.sh
# Revisa el archivo y su procedencia antes de ejecutarlo
sh serverdiag.sh
```

**Evitar ejecutar códigos descargados mediante `curl | sh` sin revisarlos.**

El diagnóstico está diseñado para usuarios normales, sin elevación automática. Ejecutar como `root` no es obligatorio; incluso si se ejecuta como root, debe conservarse el JSON privado.

### Alcance v0.1.0

- Información Linux y kernel; uptime, CPU, carga, RAM y swap.
- Capacidad y ocupación del disco raíz.
- Indicadores de procesos `mysqld`/`mariadbd`/`sshd`.
- Presencia de clientes MySQL/MariaDB, y si hay un socket TCP en escucha local en el puerto 3306.
- Detección opcional por existencia de archivos en `/ruta/aplicacion/mysql/bin` (sin ejecutar binarios de esa carpeta).

Para lo último:

```sh
sh bin/serverdiag.sh --app-dir /usr/local/APP
```

**Limitaciones:** no consulta bases de datos, no recopila logs crudos, ni inspecciona todos los servicios. Si falta una herramienta, el resultado puede ser `null` o `unavailable`; eso no significa que el servicio esté detenido.

## Copia compartible sin identificadores

El exportador usa Python 3 (biblioteca estándar) en el equipo que exporta. No requiere red:

```sh
python3 tools/export-share.py ./serverdiag-FECHA-PID.json
```

Genera un JSON diferente `diagnostico-compartible-FECHA-ALEATORIO.json`. El archivo de salida no contiene hostname, ID del informe, IP, kernel, rutas de archivos, logs crudos ni variables de entorno. El exportador aplica una lista estricta de campos y falla si detecta un esquema desconocido o habilitación de información sensible. **El usuario sigue siendo responsable de revisar el JSON antes de subirlo a cualquier servicio.**

## Herramientas OPCIONALES con tráfico de red

Estas herramientas no se invocan automáticamente por el recolector.

### Diagnóstico de conectividad (ICMP y TCP)

```sh
sh bin/probe-connectivity.sh servidor.example.org 2222
```

La falta de respuesta no implica necesariamente una caída: también puede significar bloqueo ICMP, filtrado TCP o problema de ruta.

### Ejecutar el recolector por SSH sin instalarlo en destino

Debe existir acceso previamente autorizado y la identidad del servidor SSH ya debe estar verificada en `known_hosts`:

```sh
sh bin/remote-collect.sh admin servidor.example.org 2222 ~/.ssh/id_ed25519 ./remote-private.json
```

La técnica usa `ssh ... 'sh -s -- --stdout' < bin/serverdiag.sh` y devuelve el JSON privado al equipo de administración. El script se ejecuta remotamente en modo lectura, **pero el SSH sí crea una conexión saliente**; no es el modo local.

## Pruebas

```sh
python3 -m unittest discover -s tests -v
```

Las pruebas offline validan sintaxis POSIX, salida JSON, permisos, no sobrescritura y denegación de exportaciones inseguras. No equivalen a un pentest ni a certificación de compatibilidad en cada distribución. El siguiente paso es una matriz de pruebas en VMs Debian/Ubuntu y la auditoría del recolector histórico.

## Principios técnicos

- Ningún envío de datos por defecto.
- Nunca aceptar órdenes remotas desde visores o agentes.
- Sin cambios a red, firewall o servicios.
- Separar evidencia observada, hipótesis y recomendaciones.
- Un reporte ausente no prueba que un servidor esté caído.


## Selección de secciones (`--only`)

El recolector admite una lista separada por comas: `system`, `memory`, `disk`, `database`, `processes`. Cuando se omite `--only` se seleccionan todas. Las secciones no seleccionadas se omiten, con métricas `null` y estado `skipped` cuando corresponda. La identidad del equipo sigue apareciendo en el informe **privado**, pero el exportador no la copia a la versión compartible.

```sh
sh bin/serverdiag.sh --only system
sh bin/serverdiag.sh --only memory,disk
sh bin/serverdiag.sh --only database --app-dir /usr/local/APP
sh bin/serverdiag.sh --only processes --output ./procesos.json
```

El recolector no consulta bases de datos, no lee logs crudos ni ejecuta pruebas activas de conectividad de red. Las comprobaciones de `database` revisan la presencia de clientes, procesos y escucha TCP local, no el éxito de autenticación ni la salud real del motor.

## Envío voluntario por correo electrónico (SMTP)

**Desactivado por defecto.** No se configura con `source .env` ni con ninguna forma de ejecución de shell: el programa Python lee el archivo como texto y solo admite claves conocidas. El envío se activa únicamente con `--email` y requiere Python 3.

```sh
cp .env.example .env
chmod 600 .env
nano .env
```

Contenido de ejemplo:

```dotenv
SMTP_HOST=smtp.example.org
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=cuenta@example.org
SMTP_PASSWORD=CLAVE_O_PASSWORD_DE_APLICACION
MAIL_FROM=cuenta@example.org
MAIL_TO=destinatario@example.org
```

Selecciona `SMTP_SECURITY=starttls` para negociación TLS explícita o `SMTP_SECURITY=ssl` para TLS desde el principio, comúnmente en puerto 465. No existe un modo de transporte SMTP plano sin cifrado. El cliente comprueba los certificados mediante las raíces confiables del sistema y no intenta una conexión no cifrada como alternativa si TLS falla.

Ejemplo de ejecución:

```sh
sh bin/serverdiag.sh --only disk,memory --email
sh bin/serverdiag.sh --only database --email --env /ruta/privada/smtp.env
```

El informe completo se guarda en el servidor antes de intentar SMTP. El correo incluye **exclusivamente un JSON compartible construido por allowlist**, adjunto con nombre genérico, y sin hostname, IP, ID de ejecución, logs o rutas. La exportación falla si detecta un esquema inesperado o indicadores de contenido sensible. No se crea una copia temporal compartible en disco durante el envío.

### Seguridad y limitaciones

- Un `.env` con permisos de lectura para grupo u otros usuarios se rechaza. No lo incluyas en GitHub ni en tickets.
- El correo viaja usando TLS hasta el servidor SMTP, pero **no garantiza cifrado extremo a extremo** ni impide que el proveedor o los destinatarios vean el archivo compartible.
- Los campos numéricos permitidos pueden revelar información operacional agregada; revisa el destinatario y la política de privacidad.
- Cuando el servidor SMTP no responde o no autentica, el comando devuelve error y el **JSON privado permanece disponible localmente**. No hay reintentos autónomos ni tareas programadas.
- Con `--stdout` no es posible activar `--email`. La opción `--env` sin `--email` también se rechaza.
- La configuración solo se consulta al utilizar `--email`; la simple presencia de `.env` nunca provoca una conexión saliente.

### Pruebas adicionales

```sh
python3 -m unittest discover -s tests -v
```

El conjunto incluye comprobaciones de selección parcial, rechazo de opciones desconocidas, configuración de correo con permisos inseguros, rechazo de transporte sin TLS y adjuntos sin identificadores. Las pruebas SMTP utilizan un doble simulado; **no prueban entregabilidad real ni servidores de correo específicos**.
