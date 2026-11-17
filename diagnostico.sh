#!/bin/sh
# Diagnóstico Comunitario — ejecución completa sin Python, jq, red ni paquetes extra.
# Autor: Eliezer Molina Méndez — https://eliezermolina.org
# Diagnóstico de solo lectura: NO aplica hardening ni modifica servicios.
set -eu
umask 077
LC_ALL=C
export LC_ALL

usage() {
  cat <<'EOF'
Diagnóstico Comunitario — modo POSIX sh, sin Python ni instalaciones.

Uso:
  sh diagnostico.sh
  sh diagnostico.sh --only disk,memory
  sh diagnostico.sh --only extended
  sh diagnostico.sh --only disk,extended
  sh diagnostico.sh --output-dir /ruta/privada
  sh diagnostico.sh --help

Secciones: system, memory, disk, database, processes, extended, all.
  - Sin --only: realiza diagnóstico básico + auditoría extendida.
  - Con --only: recopila únicamente las secciones seleccionadas del
    colector básico; 'extended' añade la auditoría extendida completa.
  - 'extended' abarca almacenamiento, procesos, red, SSH, NTP y hardening.

Resultados: carpeta privada nueva con basic.json, extended.json (si aplica)
  e INFORME.md. No imprime datos del servidor por stdout.
  Por defecto se guarda fuera del repositorio en:
    $HOME/.local/state/diagnostico-comunitario

No envía correo, ni usa SSH, curl, wget, pip, Python o jq.
Los recolectores requieren Linux y los comandos estándar disponibles.
El envío opcional SMTP y el asistente interactivo son herramientas separadas.
EOF
}

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P) || exit 1
basic_script=$here/bin/serverdiag.sh
extended_script=$here/bin/audit-extended.sh

only=all
base_parent=''
while [ "$#" -gt 0 ]; do
  case "$1" in
    --only)
      [ "$#" -ge 2 ] || { echo 'Falta lista de secciones' >&2; exit 2; }
      only=$2
      shift 2 ;;
    --output-dir)
      [ "$#" -ge 2 ] || { echo 'Falta ruta de salida' >&2; exit 2; }
      base_parent=$2
      shift 2 ;;
    --help|-h) usage; exit 0 ;;
    --email)
      echo 'El modo sin Python no envía correo. La opción SMTP es independiente y requiere Python 3.' >&2
      exit 2 ;;
    *) echo "Parámetro no reconocido: $1" >&2; usage >&2; exit 2 ;;
  esac
done

# No ejecutar acciones incompatibles ni pedir instalar nada.
[ -f "$basic_script" ] || { echo 'Falta bin/serverdiag.sh junto al repositorio' >&2; exit 1; }
[ -f "$extended_script" ] || { echo 'Falta bin/audit-extended.sh junto al repositorio' >&2; exit 1; }
[ "$(uname -s 2>/dev/null)" = Linux ] || {
  echo 'El modo de diagnóstico local funciona únicamente en Linux.' >&2
  exit 2
}

basic_sections=''
run_extended=0
case "$only" in
  all)
    basic_sections='system,memory,disk,database,processes'
    run_extended=1 ;;
  ''|,*|*,|*,,*|*[!a-z,]*)
    echo 'Lista --only inválida' >&2; exit 2 ;;
  *)
    old_ifs=$IFS
    IFS=,
    set -- $only
    IFS=$old_ifs
    for section do
      case "$section" in
        system|memory|disk|database|processes)
          if [ -z "$basic_sections" ]; then
            basic_sections=$section
          else
            basic_sections=$basic_sections,$section
          fi ;;
        extended) run_extended=1 ;;
        *) echo "Sección no admitida: $section" >&2; exit 2 ;;
      esac
    done ;;
esac

# Informe fuera del checkout y permisos 0700/0600.
if [ -z "$base_parent" ]; then
  [ -n "${HOME:-}" ] || { echo 'HOME no está definido. Usa --output-dir RUTA' >&2; exit 2; }
  base_parent=$HOME/.local/state/diagnostico-comunitario
fi
case "$base_parent" in
  /*) ;;
  *) echo '--output-dir requiere una ruta absoluta' >&2; exit 2 ;;
esac
[ ! -L "$base_parent" ] || { echo 'Directorio de salida no puede ser symlink' >&2; exit 2; }
if [ ! -d "$base_parent" ]; then
  # No seguir enlaces al resolver carpeta final. Las carpetas ancestras
  # deberían pertenecer a la cuenta del usuario y estar protegidas.
  mkdir -p -- "$base_parent" || { echo 'No se pudo preparar carpeta privada' >&2; exit 1; }
fi
[ -d "$base_parent" ] && [ ! -L "$base_parent" ] || { echo 'Directorio privado inválido' >&2; exit 1; }
# No cambiar los permisos de un directorio existente del usuario (o de /tmp).
# mktemp -d crea un subdirectorio exclusivo con modo 0700.
stamp=$(date -u +%Y%m%dT%H%M%SZ) || exit 1
report_dir=$(mktemp -d "$base_parent/diagnostico-$stamp-XXXXXXXX") || { echo 'No se pudo reservar carpeta privada' >&2; exit 1; }

# En caso de error no mostrar salidas crudas de comandos ni datos del host.
# Mantener carpeta privada para inspección de fallos solo por el propietario.
error() {
  echo "No se completó el diagnóstico. Revisa los permisos de las herramientas y la carpeta privada." >&2
  exit 1
}
if [ -n "$basic_sections" ]; then
  # --stdout evita que el colector genere un archivo en el checkout.
  if ! sh "$basic_script" --only "$basic_sections" --stdout > "$report_dir/basic.json" 2>/dev/null; then
    error
  fi
fi
if [ "$run_extended" -eq 1 ]; then
  if ! sh "$extended_script" --stdout > "$report_dir/extended.json" 2>/dev/null; then
    error
  fi
fi

# Lee SOLO números de campos predefinidos del JSON emitido por nuestros
# colectores. No es un parser JSON general ni ejecuta los valores.
number_field() {
  [ -f "$2" ] || { printf 'null'; return; }
  awk -v field="$1" '
    {
      needle="\"" field "\"[[:space:]]*:[[:space:]]*"
      if (match($0,needle)) {
        rem=substr($0,RSTART+RLENGTH)
        if (match(rem,/^(null|[0-9]+([.][0-9]+)?)/)) {
          print substr(rem,RSTART,RLENGTH)
          found=1
          exit
        }
      }
    }
    END {if(!found)print "null"}
  ' "$2"
}

status_report() {
  value=$1
  if [ "$value" = null ]; then printf '%s' 'sin datos'; else printf '%s' "$value"; fi
}
percent_report() {
  value=$1
  if [ "$value" = null ]; then printf '%s' 'sin datos'; else printf '%s %%' "$value"; fi
}

basic=$report_dir/basic.json
extended=$report_dir/extended.json
root_used=$(number_field used_percent "$basic")
mem_total=$(number_field total_bytes "$basic")
mem_avail=$(number_field available_bytes "$basic")
inode_used=$(number_field root_inode_used_percent "$extended")
failed=$(number_field failed_systemd_services "$extended")
oom=$(number_field oom_mentions "$extended")
io_errors=$(number_field io_error_mentions "$extended")

# Operaciones aritméticas únicamente sobre enteros validados con awk.
mem_free_pct=null
case "$mem_total:$mem_avail" in
  null:*|*:null|0:*) ;;
  *) mem_free_pct=$(awk -v a="$mem_avail" -v t="$mem_total" 'BEGIN{if(t>0&&a>=0)printf "%.0f",100*a/t; else print "null"}') ;;
esac

# Markdown privado sin hostname, rutas, usuarios ni registros crudos.
{
  printf '# Diagnóstico Comunitario — informe local\n\n'
  printf 'Captura UTC: %s\n\n' "$(date -u '+%Y-%m-%d %H:%M:%SZ')"
  printf 'Este informe es PRIVADO. No se envían datos ni se aplican cambios.\n\n'
  printf '## Resumen del diagnóstico\n\n'
  printf '| Observación | Valor |\n|---|---:|\n'
  printf '| Disco raíz ocupado | %s |\n' "$(percent_report "$root_used")"
  printf '| RAM disponible | %s |\n' "$(percent_report "$mem_free_pct")"
  printf '| Inodos raíz ocupados | %s |\n' "$(percent_report "$inode_used")"
  printf '| Servicios systemd fallidos | %s |\n' "$(status_report "$failed")"
  printf '| Menciones OOM (muestra 24h) | %s |\n' "$(status_report "$oom")"
  printf '| Menciones de errores I/O (muestra 24h) | %s |\n' "$(status_report "$io_errors")"
  printf '\n## Señales para investigar\n\n'
  signals=0
  if [ "$root_used" != null ] && [ "$root_used" -ge 90 ] 2>/dev/null; then
    printf '%s\n' '- **Almacenamiento crítico:** verificar consumo de disco, crecimiento de logs y respaldos. No borrar archivos sin inventario.'
    signals=$((signals+1))
  fi
  if [ "$inode_used" != null ] && [ "$inode_used" -ge 90 ] 2>/dev/null; then
    printf '%s\n' '- **Inodos críticos:** revisar gran cantidad de archivos pequeños y sistemas de caché.'
    signals=$((signals+1))
  fi
  if [ "$mem_free_pct" != null ] && [ "$mem_free_pct" -le 10 ] 2>/dev/null; then
    printf '%s\n' '- **Memoria disponible reducida:** investigar presión de memoria; el porcentaje aislado no prueba OOM.'
    signals=$((signals+1))
  fi
  if [ "$failed" != null ] && [ "$failed" -gt 0 ] 2>/dev/null; then
    printf '%s\n' '- **Servicios fallidos:** consultar detalles localmente con `systemctl --failed` y logs del servicio afectado.'
    signals=$((signals+1))
  fi
  if [ "$oom" != null ] && [ "$oom" -gt 0 ] 2>/dev/null; then
    printf '%s\n' '- **OOM detectado en muestra limitada:** confirmar contexto y memoria del servicio antes de atribuir causa.'
    signals=$((signals+1))
  fi
  if [ "$io_errors" != null ] && [ "$io_errors" -gt 0 ] 2>/dev/null; then
    printf '%s\n' '- **Errores I/O referenciados:** considerar salud de volumen, hardware y almacenamiento remoto.'
    signals=$((signals+1))
  fi
  if [ "$signals" -eq 0 ]; then
    printf '%s\n' '- Ninguna alerta de las reglas básicas activadas; **esto no demuestra que el servidor esté sano**. Algunas comprobaciones podrían estar sin datos.'
  fi
  printf '\n## Evidencia detallada\n\n'
  [ -n "$basic_sections" ] && printf '%s\n' '- `basic.json`: CPU, memoria, almacenamiento raíz y/o procesos según las secciones seleccionadas.'
  [ "$run_extended" -eq 1 ] && printf '%s\n' '- `extended.json`: señales de estabilidad, red y hardening; datos incompletos aparecen como `null`.'
  printf '\n## Recomendaciones y límites\n\n'
  printf '%s\n' '- Confirmar hallazgos con registros y contexto locales antes de concluir la causa raíz.'
  printf '%s\n' '- Este comando no repara, no instala, no cambia firewall/SSH y no envía correos.'
  printf '%s\n' '- Revisar el informe completo desde la terminal de confianza; no entregar JSON privados a modelos externos por defecto.'
  printf '%s\n' '- Ejecutar `sh diagnostico.sh --only extended` para revisar políticas de hardening sin aplicar cambios.'
} > "$report_dir/INFORME.md" || error

chmod 600 -- "$report_dir"/*.json "$report_dir/INFORME.md" 2>/dev/null || error
printf 'Diagnóstico finalizado.\nCarpeta privada: %s\nArchivo legible: INFORME.md\n' "$report_dir"
