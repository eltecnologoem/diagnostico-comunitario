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
  sh diagnostico.sh --show                 # resumen en la consola
  sh diagnostico.sh --menu                 # selección interactiva
  sh diagnostico.sh --progress             # animación si hay terminal
  sh diagnostico.sh --menu --show --progress
  sh diagnostico.sh --output-dir /ruta/privada
  sh diagnostico.sh --help

Secciones: system, memory, disk, database, processes, extended, all.
  - Sin --only: realiza diagnóstico básico + auditoría extendida.
  - Con --only: recopila únicamente las secciones seleccionadas del
    colector básico; 'extended' añade la auditoría extendida completa.
  - 'extended' abarca almacenamiento, procesos, red, SSH, NTP y hardening.

Resultados: carpeta privada nueva con basic.json, extended.json (si aplica)
  e INFORME.md. Por defecto no imprime datos del servidor por stdout.
  --show     Presenta un resumen tabulado sin hostname, IP ni logs crudos.
  --menu     Menú opcional para elegir una o varias secciones (TTY requerido).
  --progress Indicador animado en TTY; texto simple al redirigir salida.
  El progreso se imprime en stderr, nunca en el JSON.
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
show_results=0
interactive_menu=0
progress=0
only_supplied=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --only)
      [ "$#" -ge 2 ] || { echo 'Falta lista de secciones' >&2; exit 2; }
      only=$2
      only_supplied=1
      shift 2 ;;
    --show) show_results=1; shift ;;
    --menu) interactive_menu=1; shift ;;
    --progress) progress=1; shift ;;
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

# Menú POSIX sh: entrada delimitada y enumerada; jamás evaluar como shell.
# Debe completarse ANTES de crear carpetas o ejecutar un recolector.
menu_select() {
  [ -t 0 ] && [ -t 1 ] || {
    echo '--menu requiere una terminal interactiva (stdin y stdout TTY)' >&2
    return 2
  }
  printf '\nDiagnóstico Comunitario — menú de secciones\n'
  printf '%s\n' \
    '  1) Sistema: CPU, carga y uptime' \
    '  2) Memoria: RAM y swap' \
    '  3) Disco: almacenamiento raíz' \
    '  4) Bases de datos: MySQL/MariaDB' \
    '  5) Procesos: SSH y estado' \
    '  6) Auditoría extendida: red, SSH, NTP y hardening (solo lectura)' \
    '  7) Todas las secciones' \
    '  0) Cancelar'
  printf 'Selecciona una o varias opciones (ejemplo 2,3,6): '
  IFS= read -r answer || { echo 'No se recibió una selección' >&2; return 2; }
  [ "${#answer}" -le 80 ] || { echo 'Selección demasiado larga' >&2; return 2; }
  # Permitir espacios en la lista, pero no comandos, rangos ni caracteres de control.
  answer=$(printf '%s' "$answer" | tr -d ' ') || return 2
  case "$answer" in
    ''|,*|*,|*,,*|*[!0-9,]*) echo 'Selección inválida' >&2; return 2 ;;
  esac
  old_ifs=$IFS
  IFS=,
  set -- $answer
  IFS=$old_ifs
  choices=''
  seen_all=0
  for choice do
    case "$choice" in
      0)
        [ "$#" -eq 1 ] || { echo 'Cancelar debe elegirse solo' >&2; return 2; }
        printf 'Operación cancelada por el usuario.\n'
        exit 0 ;;
      7) seen_all=1 ;;
      1) part=system ;;
      2) part=memory ;;
      3) part=disk ;;
      4) part=database ;;
      5) part=processes ;;
      6) part=extended ;;
      *) echo "Opción no disponible: $choice" >&2; return 2 ;;
    esac
    if [ "$choice" != 7 ]; then
      case ",$choices," in
        *,"$part",*) : ;;
        *) if [ -z "$choices" ]; then choices=$part; else choices=$choices,$part; fi ;;
      esac
    fi
  done
  if [ "$seen_all" -eq 1 ]; then
    [ "$#" -eq 1 ] || { echo 'Todas (7) debe elegirse sin otras opciones' >&2; return 2; }
    only=all
  else
    only=$choices
  fi
  printf 'Secciones seleccionadas: %s\n\n' "$only"
}

if [ "$interactive_menu" -eq 1 ]; then
  [ "$only_supplied" -eq 0 ] || { echo 'No combinar --menu y --only' >&2; exit 2; }
  menu_select || exit 2
fi

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
current_pid=''
cleanup_child() {
  if [ -n "$current_pid" ]; then
    kill "$current_pid" 2>/dev/null || :
    wait "$current_pid" 2>/dev/null || :
    current_pid=''
  fi
}
trap 'cleanup_child; exit 130' INT
trap 'cleanup_child; exit 143' TERM
error() {
  cleanup_child
  echo "No se completó el diagnóstico. Revisa los permisos de las herramientas y la carpeta privada." >&2
  exit 1
}

# Animación solo si --progress y stderr es TTY; si está redirigido,
# imprime un estado puntual sin códigos ANSI o retornos de carro.
progress_step=0
progress_total=1
[ -z "$basic_sections" ] || progress_total=$((progress_total+1))
[ "$run_extended" -eq 0 ] || progress_total=$((progress_total+1))
progress_begin() {
  progress_step=$((progress_step+1))
  progress_label=$1
  if [ "$progress" -eq 1 ]; then
    if [ -t 2 ]; then
      printf '\r[%s/%s] %s ... ' "$progress_step" "$progress_total" "$progress_label" >&2
    else
      printf '[%s/%s] %s ...\n' "$progress_step" "$progress_total" "$progress_label" >&2
    fi
  fi
}
progress_done() {
  if [ "$progress" -eq 1 ]; then
    if [ -t 2 ]; then
      printf '\r[%s/%s] %s ... OK                               \n' "$progress_step" "$progress_total" "$progress_label" >&2
    else
      printf '[%s/%s] %s: OK\n' "$progress_step" "$progress_total" "$progress_label" >&2
    fi
  fi
}

capture_step() {
  description=$1
  destination=$2
  shift 2
  progress_begin "$description"
  if [ "$progress" -eq 1 ] && [ -t 2 ]; then
    "$@" > "$destination" 2>/dev/null &
    current_pid=$!
    frame=0
    while kill -0 "$current_pid" 2>/dev/null; do
      case "$frame" in
        0) symbol='|' ;;
        1) symbol='/' ;;
        2) symbol='-' ;;
        *) symbol='\' ;;
      esac
      printf '\r[%s/%s] %s ... %s' "$progress_step" "$progress_total" "$description" "$symbol" >&2
      frame=$(((frame+1)%4))
      # `sleep 1` mantiene compatibilidad POSIX (sin decimales obligatorios).
      sleep 1
    done
    if wait "$current_pid"; then
      current_pid=''
      progress_done
      return 0
    fi
    current_pid=''
    printf '\r[%s/%s] %s ... ERROR\n' "$progress_step" "$progress_total" "$description" >&2
    return 1
  fi
  if "$@" > "$destination" 2>/dev/null; then
    progress_done
    return 0
  fi
  return 1
}

if [ -n "$basic_sections" ]; then
  # --stdout evita que el colector genere un archivo en el checkout.
  capture_step 'Recopilando diagnóstico básico' "$report_dir/basic.json" \
    sh "$basic_script" --only "$basic_sections" --stdout || error
fi
if [ "$run_extended" -eq 1 ]; then
  capture_step 'Ejecutando auditoría extendida' "$report_dir/extended.json" \
    sh "$extended_script" --stdout || error
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

# Extraer solo literales cerrados y conocidos de los JSON del propio colector.
# Nunca imprimir texto arbitrario de un JSON (hostname, ruta, logs, etc.).
literal_field() {
  [ -f "$2" ] || { printf 'null'; return; }
  awk -v field="$1" '
    {
      needle="\"" field "\"[[:space:]]*:[[:space:]]*"
      if(match($0,needle)) {
        rem=substr($0,RSTART+RLENGTH)
        if(match(rem,/^(true|false|null)([,}[:space:]]|$)/)) {
          v=substr(rem,1,RLENGTH)
          sub(/[,}[:space:]].*$/, "", v)
          print v; found=1; exit
        }
        if(match(rem,/^\"(yes|no|active|inactive|enabled|disabled|not_installed|prohibit-password|forced-commands-only|without-password)\"/)) {
          v=substr(rem,2,RLENGTH-2)
          print v; found=1; exit
        }
      }
    }
    END {if(!found)print "null"}
  ' "$2"
}

# Markdown privado sin hostname, rutas, usuarios ni registros crudos.
progress_begin 'Preparando resumen local'
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
progress_done

chmod 600 -- "$report_dir"/*.json "$report_dir/INFORME.md" 2>/dev/null || error

section_was_collected() {
  case ",$basic_sections," in
    *,"$1",*) return 0 ;;
    *) return 1 ;;
  esac
}

show_console_summary() {
  # Print ONLY allowlisted data, in a stable layout. The console itself is
  # a disclosure surface: use only in a trusted terminal, not Codex/CI.
  printf '\n============================================================\n'
  printf ' DIAGNÓSTICO COMUNITARIO  |  RESUMEN LOCAL\n'
  printf '============================================================\n'
  printf ' Secciones: %s\n' "$only"
  printf '%-34s %s\n' 'Indicador' 'Valor'
  printf '%-34s %s\n' '----------------------------------' '----------------'
  if section_was_collected system; then
    printf '\n[Sistema]\n'
    printf '%-34s %s\n' 'Uptime (segundos)' "$(status_report "$(number_field uptime_seconds "$basic")")"
    printf '%-34s %s\n' 'CPU (núcleos)' "$(status_report "$(number_field cpu_cores "$basic")")"
    printf '%-34s %s\n' 'Carga promedio 1 min' "$(status_report "$(number_field load_1m "$basic")")"
  fi
  if section_was_collected memory; then
    printf '\n[Memoria]\n'
    printf '%-34s %s\n' 'RAM disponible' "$(percent_report "$mem_free_pct")"
  fi
  if section_was_collected disk; then
    printf '\n[Disco]\n'
    printf '%-34s %s\n' 'Disco raíz ocupado' "$(percent_report "$root_used")"
  fi
  if section_was_collected database; then
    printf '\n[Base de datos]\n'
    printf '%-34s %s\n' 'Procesos MySQL/MariaDB' "$(status_report "$(number_field mysql_process_count "$basic")")"
    printf '%-34s %s\n' 'Puerto 3306 (escucha local)' "$(status_report "$(literal_field tcp_3306_listening "$basic")")"
  fi
  if section_was_collected processes; then
    printf '\n[Procesos]\n'
    printf '%-34s %s\n' 'Procesos SSHD' "$(status_report "$(number_field sshd_process_count "$basic")")"
  fi
  if [ "$run_extended" -eq 1 ]; then
    printf '\n[Estabilidad y eventos]\n'
    printf '%-34s %s\n' 'Inodos raíz ocupados' "$(percent_report "$inode_used")"
    printf '%-34s %s\n' 'Servicios systemd fallidos' "$(status_report "$failed")"
    printf '%-34s %s\n' 'Menciones OOM (muestra 24 h)' "$(status_report "$oom")"
    printf '%-34s %s\n' 'Menciones I/O (muestra 24 h)' "$(status_report "$io_errors")"
    printf '\n[Seguridad — configuración global]\n'
    printf '%-34s %s\n' 'SSH contraseña (global)' "$(status_report "$(literal_field sshd_global_password_auth "$extended")")"
    printf '%-34s %s\n' 'SSH root (global)' "$(status_report "$(literal_field sshd_global_root_login "$extended")")"
    printf '%-34s %s\n' 'AppArmor kernel habilitado' "$(status_report "$(literal_field apparmor_kernel_enabled "$extended")")"
    printf '%-34s %s\n' 'Sincronización NTP' "$(status_report "$(literal_field ntp_synchronized "$extended")")"
    printf '%-34s %s\n' 'UFW (no representa todo firewall)' "$(status_report "$(literal_field ufw_status "$extended")")"
    printf '%-34s %s\n' 'Kernel dmesg_restrict' "$(status_report "$(number_field kernel_dmesg_restrict "$extended")")"
  fi
  printf '\n[Interpretación inicial]\n'
  printf '%-34s %s\n' 'Señales básicas para investigar' "$signals"
  if [ "$root_used" != null ] && [ "$root_used" -ge 90 ] 2>/dev/null; then
    printf '%s\n' '- Atención: disco raíz con ocupación elevada.'
  fi
  if [ "$inode_used" != null ] && [ "$inode_used" -ge 90 ] 2>/dev/null; then
    printf '%s\n' '- Atención: inodos raíz con ocupación elevada.'
  fi
  if [ "$mem_free_pct" != null ] && [ "$mem_free_pct" -le 10 ] 2>/dev/null; then
    printf '%s\n' '- Atención: baja memoria disponible; investigar contexto.'
  fi
  if [ "$failed" != null ] && [ "$failed" -gt 0 ] 2>/dev/null; then
    printf '%s\n' '- Atención: servicios systemd fallidos.'
  fi
  if [ "$oom" != null ] && [ "$oom" -gt 0 ] 2>/dev/null; then
    printf '%s\n' '- Atención: menciones OOM en muestra reciente.'
  fi
  if [ "$io_errors" != null ] && [ "$io_errors" -gt 0 ] 2>/dev/null; then
    printf '%s\n' '- Atención: menciones de errores de I/O recientes.'
  fi
  printf '%s\n' 'La ausencia de alertas NO garantiza que el servidor esté sano.'
  printf '%s\n' 'Para recomendaciones y evidencias, abre INFORME.md en tu equipo.'
  printf '============================================================\n'
}

[ "$show_results" -eq 0 ] || show_console_summary
printf 'Diagnóstico finalizado.\nCarpeta privada: %s\nArchivo legible: INFORME.md\n' "$report_dir"
