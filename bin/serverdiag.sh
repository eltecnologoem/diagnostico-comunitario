#!/bin/sh
# Diagnostico Comunitario - recolector Linux local, POSIX sh.
# No instala, no envia red, no cambia configuracion ni servicios.
set -u
umask 077
LC_ALL=C
export LC_ALL

usage() {
  cat <<'EOF'
Uso:
  sh bin/serverdiag.sh [--output ARCHIVO] [--app-dir RUTA]
  sh bin/serverdiag.sh --stdout [--app-dir RUTA]

Por defecto crea ./serverdiag-<UTC>-<PID>.json con permisos 0600.
--stdout escribe SOLO JSON a stdout (util para 'ssh ... sh -s -- --stdout').
--app-dir inspecciona opcionalmente RUTA/mysql/bin en modo lectura.
No ejecuta ping/ssh/curl/wget/nc ni instala paquetes.
EOF
}

output=''
stdout_mode=0
app_dir=''
while [ "$#" -gt 0 ]; do
  case "$1" in
    --output)
      [ "$#" -ge 2 ] || { echo 'Falta ruta en --output' >&2; exit 2; }
      output=$2; shift 2 ;;
    --stdout) stdout_mode=1; shift ;;
    --app-dir)
      [ "$#" -ge 2 ] || { echo 'Falta ruta en --app-dir' >&2; exit 2; }
      app_dir=$2; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Parametro desconocido: $1" >&2; usage >&2; exit 2 ;;
  esac
done
[ "$stdout_mode" -eq 0 ] || [ -z "$output" ] || { echo 'No combinar --stdout y --output' >&2; exit 2; }
[ -z "$app_dir" ] || [ -d "$app_dir" ] || { echo 'La carpeta de --app-dir no existe' >&2; exit 2; }

# Cadenas JSON restringidas a ASCII sin comillas ni controles.
safe_id() { printf '%s' "$1" | tr -cd 'A-Za-z0-9._:/+@-'; }
num_or_null() {
  case "$1" in
    ''|*[!0-9]*) printf 'null' ;;
    *) printf '%s' "$1" ;;
  esac
}
float_or_null() {
  case "$1" in
    ''|*[!0-9.]*) printf 'null' ;;
    *.*.*) printf 'null' ;;
    *)
      if printf '%s' "$1" | awk 'BEGIN {ok=0} /^[0-9]+([.][0-9]+)?$/ {ok=1} END {exit !ok}'; then
        printf '%s' "$1"
      else
        printf 'null'
      fi ;;
  esac
}
bool_from_binary() { if command -v "$1" >/dev/null 2>&1; then printf true; else printf false; fi; }

utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ') || exit 1
stamp=$(date -u '+%Y%m%dT%H%M%SZ') || exit 1
if [ -r /proc/sys/kernel/random/uuid ]; then
  run_id=$(tr -cd 'A-Fa-f0-9-' < /proc/sys/kernel/random/uuid | cut -c 1-36)
else
  run_id=$(date -u +%s)-$$
fi
hostname_id=$(safe_id "$(hostname 2>/dev/null || printf 'unknown')" | cut -c 1-255)
[ -n "$hostname_id" ] || hostname_id='unknown'
os_id='unknown'
if [ -r /etc/os-release ]; then
  os_id=$(awk -F= '$1=="ID" {gsub(/"/,"",$2); print $2;exit}' /etc/os-release)
fi
os_id=$(safe_id "$os_id" | cut -c 1-48)
[ -n "$os_id" ] || os_id='unknown'
kernel_id=$(safe_id "$(uname -r 2>/dev/null || printf 'unknown')" | cut -c 1-120)
[ -n "$kernel_id" ] || kernel_id='unknown'
if [ "$(id -u)" = 0 ]; then priv='root'; else priv='unprivileged'; fi

uptime_s=null
if [ -r /proc/uptime ]; then
  uptime_s=$(awk '{printf "%.0f",$1;exit}' /proc/uptime 2>/dev/null || printf null)
fi
cpu_cores=$(getconf _NPROCESSORS_ONLN 2>/dev/null || printf null)
load_1m=null
if [ -r /proc/loadavg ]; then load_1m=$(awk '{print $1;exit}' /proc/loadavg); fi

mem_total=null; mem_available=null; swap_total=null; swap_free=null
mem_status=unavailable
if [ -r /proc/meminfo ]; then
  mem_line=$(awk '
    /^MemTotal:/ {t=$2}
    /^MemAvailable:/ {a=$2}
    /^SwapTotal:/ {s=$2}
    /^SwapFree:/ {f=$2}
    END {if(t>0) printf "%.0f %.0f %.0f %.0f",t*1024,a*1024,s*1024,f*1024}
  ' /proc/meminfo)
  if [ -n "$mem_line" ]; then
    set -- $mem_line; mem_total=$1; mem_available=$2; swap_total=$3; swap_free=$4
    mem_status=collected
  fi
fi

root_total=null; root_used=null; root_available=null; root_used_pct=null
disk_status=unavailable
if command -v df >/dev/null 2>&1; then
  df_line=$(df -Pk / 2>/dev/null | awk 'NR==2 && $2~/^[0-9]+$/ && $3~/^[0-9]+$/ && $4~/^[0-9]+$/ {gsub(/%/,"",$5); if($5~/^[0-9]+$/) printf "%.0f %.0f %.0f %s", $2*1024,$3*1024,$4*1024,$5}')
  if [ -n "$df_line" ]; then
    set -- $df_line; root_total=$1; root_used=$2; root_available=$3; root_used_pct=$4
    disk_status=collected
  fi
fi

mysql_client=$(bool_from_binary mysql)
mariadb_client=$(bool_from_binary mariadb)
mysql_process_count=null
ssh_process_count=null
process_status=unavailable
if command -v ps >/dev/null 2>&1; then
  process_line=$(ps -eo comm= 2>/dev/null | awk '
    {p=$1;sub(/^.*\//,"",p);if(p=="mysqld"||p=="mariadbd") m++;if(p=="sshd") s++}
    END {printf "%d %d",m+0,s+0}' )
  if [ -n "$process_line" ]; then
    set -- $process_line; mysql_process_count=$1; ssh_process_count=$2
    process_status=collected
  fi
fi

tcp_3306_listening=null
listeners_status=unavailable
if command -v ss >/dev/null 2>&1; then
  ss_line=$(ss -H -ltn 2>/dev/null)
  ss_exit=$?
  if [ "$ss_exit" -eq 0 ]; then
    tcp_3306_listening=$(printf '%s\n' "$ss_line" | awk '{if($4 ~ /:3306$/) found=1} END {print found?"true":"false"}')
    listeners_status=collected
  fi
fi

embedded_mysql_present=null
if [ -n "$app_dir" ]; then
  embedded_mysql_present=false
  if [ -x "$app_dir/mysql/bin/mysqld" ] || [ -x "$app_dir/mysql/bin/mariadbd" ] || [ -x "$app_dir/mysql/bin/mysql" ]; then
    embedded_mysql_present=true
  fi
fi

findings='[]'
if [ "$root_used_pct" != null ] && [ "$root_used_pct" -ge 90 ] 2>/dev/null; then
  findings='[{"code":"disk_root_high","severity":"warning","metric":"disk.root.used_percent","value":'"$root_used_pct"',"unit":"percent","threshold":90}]'
fi

render() {
cat <<EOF
{
  "schema_version":"1.0",
  "report_type":"private",
  "run_id":"$run_id",
  "collected_at":"$utc",
  "source":{"hostname":"$hostname_id","os_id":"$os_id","kernel":"$kernel_id","privilege_level":"$priv"},
  "metrics":{
    "system":{"uptime_seconds":$(num_or_null "$uptime_s"),"cpu_cores":$(num_or_null "$cpu_cores"),"load_1m":$(float_or_null "$load_1m")},
    "memory":{"total_bytes":$(num_or_null "$mem_total"),"available_bytes":$(num_or_null "$mem_available"),"swap_total_bytes":$(num_or_null "$swap_total"),"swap_free_bytes":$(num_or_null "$swap_free")},
    "disk_root":{"total_bytes":$(num_or_null "$root_total"),"used_bytes":$(num_or_null "$root_used"),"available_bytes":$(num_or_null "$root_available"),"used_percent":$(num_or_null "$root_used_pct")},
    "database":{"mysql_client_available":$mysql_client,"mariadb_client_available":$mariadb_client,"mysql_process_count":$(num_or_null "$mysql_process_count"),"tcp_3306_listening":$tcp_3306_listening,"embedded_mysql_present":$embedded_mysql_present},
    "processes":{"sshd_process_count":$(num_or_null "$ssh_process_count")}
  },
  "checks":{"meminfo":"$mem_status","disk_root":"$disk_status","process_list":"$process_status","tcp_listeners":"$listeners_status"},
  "findings":$findings,
  "privacy":{"contains_operational_identifiers":true,"contains_raw_logs":false,"contains_environment_variables":false,"sensitive_sharing_enabled":false}
}
EOF
}

if [ "$stdout_mode" -eq 1 ]; then
  render
else
  if [ -z "$output" ]; then output="./serverdiag-$stamp-$$.json"; fi
  [ ! -d "$output" ] || { echo 'La salida es una carpeta' >&2; exit 2; }
  temp=$(mktemp "$output.tmp.XXXXXXXX") || { echo 'No pude crear el temporal de reporte' >&2; exit 1; }
  trap 'rm -f -- "$temp"' 0
  trap 'exit 130' 2
  trap 'exit 143' 15
  if ! render > "$temp"; then echo 'Error generando JSON' >&2; exit 1; fi
  if ! ln -- "$temp" "$output" 2>/dev/null; then
    echo 'No se puede crear la salida (ya existe o sin permisos)' >&2; exit 1
  fi
  rm -f -- "$temp"
  trap - 0
  printf 'Reporte local: %s\n' "$output"
fi
