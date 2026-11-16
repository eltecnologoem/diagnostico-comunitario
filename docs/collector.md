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
