# Interfaz de consola opcional — Diagnóstico Comunitario

**Autor:** Eliezer Molina Méndez · <https://eliezermolina.org>  
**Estado:** prototipo de laboratorio, Linux, POSIX `sh`; sin Python, `jq`, `dialog`, `whiptail` ni paquetes adicionales.

La nueva interfaz permite elegir entre el comportamiento discreto predeterminado y tres mejoras optativas: mostrar un resumen legible, seleccionar áreas mediante un menú y ver el avance de la recolección.

## Comandos de uso

```sh
sh diagnostico.sh                           # Igual que antes: captura local y salida breve
sh diagnostico.sh --show                    # Presenta los resultados ordenados en consola
sh diagnostico.sh --menu                    # Menú interactivo de secciones
sh diagnostico.sh --progress                # Avance en terminal; sin animación si no hay TTY
sh diagnostico.sh --menu --show --progress   # Experiencia interactiva completa
sh diagnostico.sh --only memory,disk --show  # Solo las secciones seleccionadas
sh diagnostico.sh --only extended --show --progress
sh diagnostico.sh --output-dir /ruta/privada --show
```

### `--show`: resumen ordenado

Muestra tablas legibles agrupadas por **sistema**, **memoria**, **disco**, **bases de datos**, **procesos**, **eventos** y **configuración de seguridad** según las secciones elegidas. Incluye reglas básicas para señalar ocupación alta, OOM, servicios fallidos y errores de I/O observados. La herramienta no imprime logs crudos, hostnames, direcciones IP ni campos arbitrarios del JSON. La falta de información se muestra como `sin datos`, nunca como evidencia de que todo está bien.

**Privacidad:** el resumen incluye métricas reales y puede almacenarse en el historial de un terminal o sesión grabada. Solo utilizar `--show` desde una **terminal de confianza**, no desde un agente Codex remoto o un servicio que archive stdout. La salida estándar predeterminada conserva su comportamiento discreto.

### `--menu`: selección interactiva

El menú muestra opciones numeradas y admite una o varias separadas por comas: `2,3,6` ejecuta memoria, disco y auditoría extendida. Opciones válidas: `1` sistema, `2` memoria, `3` disco, `4` base de datos, `5` procesos, `6` extendido, `7` todo, `0` cancelar. `0` y `7` deben seleccionarse individualmente. Si el usuario cancela o escribe una selección inválida, **no se inicia la recolección ni se crean reportes**.

`--menu` exige stdin y stdout conectados a terminal real (`TTY`). Si se invoca desde cron, tuberías o herramientas no interactivas, devuelve un error en lugar de bloquearse solicitando entrada. No se puede combinar `--menu` con `--only`; elegir un modo explícito.

### `--progress`: avance opcional

Mientras trabaja cada colector, muestra un indicador visual simple `| / - \\` en `stderr`, junto con el número de etapa. El resumen de resultados permanece independiente. Cuando `stderr` no es terminal, escribe **líneas normales** sin caracteres de control ni colores ANSI. En el modo sin `--progress`, el comando no muestra progreso ni animación.

El indicador muestra actividad y etapas **no el porcentaje real ni un tiempo restante estimado**. No se instala ningún paquete extra. No altera ni ejecuta remediaciones, SSH, correo ni conexiones salientes.

## Archivos generados

La ubicación predeterminada sigue siendo `~/.local/state/diagnostico-comunitario/diagnostico-FECHA-XXXXXXXX/` y contiene `INFORME.md` y los JSON correspondientes a la selección. El directorio privado se crea con permisos `0700` y los archivos con `0600`. **La UI no reemplaza ni expone automáticamente esos archivos**.

## Comprobaciones antes de anunciar disponibilidad estable

```sh
sh -n diagnostico.sh
python3 -m unittest discover -s tests -v  # Python solo para el entorno de QA
```

La suite prueba modo discreto, pantalla parcial, resumen extendido, interacción TTY real, cancelación, opciones repetidas, rechazo de entrada arbitraria y comportamiento de progreso sin TTY. Quedan pendientes las pruebas de terminales reales diversas, BusyBox `ash` y entornos mínimos.

[Volver al README](../README.md) · [Seguridad](../SECURITY.md)
