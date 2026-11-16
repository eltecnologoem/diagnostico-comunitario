#!/bin/sh
# Opt-in: mando del recolector por stdin SSH, sin instalar en remoto.
# Autenticacion host key estricta; NO accept-new por defecto.
set -u
umask 077
usage() { echo 'Uso: sh bin/remote-collect.sh USUARIO HOST PUERTO LLAVE_PRIVADA ARCHIVO_SALIDA' >&2; }
[ "$#" -eq 5 ] || { usage; exit 2; }
user=$1; host=$2; port=$3; key=$4; output=$5
case "$user" in ''|*[!A-Za-z0-9_-]*) echo 'Usuario inválido' >&2; exit 2;; esac
case "$host" in ''|*[!A-Za-z0-9.:-]*) echo 'Host inválido' >&2; exit 2;; esac
case "$port" in ''|*[!0-9]*) echo 'Puerto inválido' >&2; exit 2;; esac
[ "$port" -ge 1 ] && [ "$port" -le 65535 ] || { echo 'Puerto fuera de rango' >&2; exit 2; }
[ -r "$key" ] || { echo 'La clave privada no es legible' >&2; exit 2; }
[ ! -e "$output" ] || { echo 'La salida ya existe' >&2; exit 2; }
command -v ssh >/dev/null 2>&1 || { echo 'Falta ssh local' >&2; exit 2; }
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
collector="$base/serverdiag.sh"
[ -r "$collector" ] || { echo 'No encuentro serverdiag.sh junto al script' >&2; exit 1; }
temp=$(mktemp "${output}.tmp.XXXXXXXX") || exit 1
trap 'rm -f -- "$temp"' 0
trap 'exit 130' 2
trap 'exit 143' 15
if ! ssh -T -p "$port" -i "$key" -o BatchMode=yes -o IdentitiesOnly=yes \
    -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ClearAllForwardings=yes \
    -o ControlMaster=no "$user@$host" 'sh -s -- --stdout' < "$collector" > "$temp"; then
  echo 'SSH falló; se descartó el archivo temporal' >&2
  exit 1
fi
[ -s "$temp" ] || { echo 'SSH devolvió un reporte vacío' >&2; exit 1; }
if command -v python3 >/dev/null 2>&1; then
  python3 -m json.tool "$temp" >/dev/null 2>&1 || { echo 'Respuesta SSH no es JSON válido' >&2; exit 1; }
fi
if ! ln -- "$temp" "$output" 2>/dev/null; then echo 'Destino ya existe o no puede crearse' >&2; exit 1; fi
rm -f -- "$temp"; trap - 0
printf 'Reporte privado remoto guardado localmente: %s\n' "$output"
