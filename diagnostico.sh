#!/bin/sh
# Portable launcher for Linux and macOS. Never source any dotenv file.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$here/diagnostico.py" "$@"
