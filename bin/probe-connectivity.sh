#!/bin/sh
# Opt-in: pruebas de red ACTIVAS, no forman parte de serverdiag.sh.
set -u
usage() { echo 'Uso: sh bin/probe-connectivity.sh HOST [PUERTO_SSH] (hace ping y conexiones TCP)' >&2; }
[ "$#" -ge 1 ] && [ "$#" -le 2 ] || { usage; exit 2; }
host=$1
port=${2:-22}
case "$host" in ''|*[!A-Za-z0-9.:-]*) echo 'Host no válido' >&2; exit 2;; esac
case "$port" in ''|*[!0-9]*) echo 'Puerto no válido' >&2; exit 2;; esac
[ "$port" -ge 1 ] && [ "$port" -le 65535 ] || { echo 'Puerto fuera de rango' >&2; exit 2; }

probe_port() {
  hp=$1
  if command -v nc >/dev/null 2>&1; then
    if nc -z -w 6 "$host" "$hp" >/dev/null 2>&1; then printf 'TCP %s: conectado\n' "$hp"; else printf 'TCP %s: sin conexión confirmada (cerrado/filtrado/ruta)\n' "$hp"; fi
  elif command -v bash >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
    if TARGET_HOST="$host" TARGET_PORT="$hp" timeout 6 bash -c 'exec 3<>"/dev/tcp/${TARGET_HOST}/${TARGET_PORT}"' >/dev/null 2>&1; then
      printf 'TCP %s: conectado\n' "$hp"
    else printf 'TCP %s: sin conexión confirmada (cerrado/filtrado/ruta)\n' "$hp"; fi
  else
    printf 'TCP %s: prueba omitida (nc o bash+timeout no disponible)\n' "$hp"
  fi
}

printf 'Destino: %s\n' "$host"
if command -v ping >/dev/null 2>&1; then
  if ping -c 3 -W 2 "$host" >/dev/null 2>&1; then
    echo 'ICMP: respuesta recibida'
  else
    echo 'ICMP: sin respuesta (no prueba por sí solo que esté caído)'
  fi
else
  echo 'ICMP: prueba omitida (ping no disponible)'
fi
probe_port "$port"
[ "$port" = 22 ] || probe_port 22
