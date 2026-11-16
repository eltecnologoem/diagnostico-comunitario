#!/bin/sh
# Diagnóstico Comunitario - auditoría extendida Debian/Ubuntu, read-only.
# Diseñado para complementarse con serverdiag.sh; NO cambia configuración.
set -u
umask 077
LC_ALL=C
export LC_ALL

usage() {
  printf '%s\n' 'Uso: sh bin/audit-extended.sh [--stdout | --output ARCHIVO]' \
      'No requiere root ni ejecuta acciones de remediación.' \
      'No captura logs crudos, IP, hostnames ni credenciales.'
}
output=''
stdout_mode=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --stdout) stdout_mode=1; shift ;;
    --output) [ "$#" -ge 2 ] || { echo '--output requiere ruta' >&2; exit 2; }; output=$2; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo 'Parámetro no reconocido' >&2; exit 2 ;;
  esac
done
[ "$stdout_mode" -eq 0 ] || [ -z "$output" ] || { echo 'No combinar --stdout y --output' >&2; exit 2; }

# Bash/Python/other shells are not required on the diagnosed machine.
# A scalar is emitted only if proven in a closed allowlist; never emit raw command output.
num() { case "$1" in ''|*[!0-9]*) printf null ;; *) printf '%s' "$1" ;; esac; }
bool() { case "$1" in true|false) printf '%s' "$1" ;; *) printf null ;; esac; }
enum() { case "$1" in
  yes|no|prohibit-password|forced-commands-only|without-password|active|inactive|enabled|disabled|unknown|not_installed) printf '"%s"' "$1" ;;
  *) printf null;; esac; }

stamp=$(date -u +%Y%m%dT%H%M%SZ) || exit 1
now=$(date -u +%Y-%m-%dT%H:%M:%SZ) || exit 1
os_id='unknown'; os_version='unknown'
if [ -r /etc/os-release ]; then
  os_id=$(awk -F= '$1=="ID"{gsub(/\"/,"",$2);print $2;exit}' /etc/os-release | tr -cd 'A-Za-z0-9._-' | cut -c 1-40)
  os_version=$(awk -F= '$1=="VERSION_ID"{gsub(/\"/,"",$2);print $2;exit}' /etc/os-release | tr -cd 'A-Za-z0-9._-' | cut -c 1-40)
fi
[ -n "$os_id" ] || os_id='unknown'
[ -n "$os_version" ] || os_version='unknown'

inode_pct='null'; inode_status='unavailable'
if command -v df >/dev/null 2>&1; then
  v=$(df -Pi / 2>/dev/null | awk 'NR==2 {gsub(/%/,"",$5);if($5~/^[0-9]+$/)print $5}')
  if [ -n "$v" ]; then inode_pct=$(num "$v"); inode_status='collected'; fi
fi

root_readonly='null'; mount_status='unavailable'
if command -v findmnt >/dev/null 2>&1; then
  v=$(findmnt -no OPTIONS / 2>/dev/null)
  if [ -n "$v" ]; then
    case ",$v," in *,ro,*) root_readonly=true;; *) root_readonly=false;; esac
    mount_status='collected'
  fi
fi

zombie='null'; dstate='null'; ps_status='unavailable'
if command -v ps >/dev/null 2>&1; then
  v=$(ps -eo stat= 2>/dev/null | awk 'BEGIN{z=0;d=0} /^Z/{z++} /^D/{d++} END{printf "%d %d",z,d}')
  if [ -n "$v" ]; then
    zombie=$(num "${v%% *}"); dstate=$(num "${v#* }"); ps_status='collected'
  fi
fi

iface_count='null'; default_routes='null'; listeners='null'; net_status='unavailable'
if [ -d /sys/class/net ]; then
  iface_count=$(find /sys/class/net -mindepth 1 -maxdepth 1 -type l 2>/dev/null | awk 'END{print NR+0}')
  net_status='collected'
fi
if [ -r /proc/net/route ]; then
  default_routes=$(awk 'NR>1 && $2=="00000000"{n++} END{print n+0}' /proc/net/route)
  net_status='collected'
fi
if command -v ss >/dev/null 2>&1; then
  v=$(ss -H -ltn 2>/dev/null)
  rc=$?
  if [ "$rc" -eq 0 ]; then listeners=$(printf '%s\n' "$v" | awk 'NF>0{n++}END{print n+0}');net_status='collected';fi
fi

failed_services='null'; systemd_status='unavailable'
if command -v systemctl >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
  v=$(timeout 6 systemctl --failed --type=service --no-pager --no-legend --plain 2>/dev/null)
  rc=$?
  if [ "$rc" -eq 0 ]; then
    failed_services=$(printf '%s\n' "$v" | awk 'NF>0{n++} END{print n+0}')
    systemd_status='collected'
  fi
fi

ntp_sync='null'; ntp_status='unavailable'
if command -v timedatectl >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
  v=$(timeout 4 timedatectl show -p NTPSynchronized --value 2>/dev/null)
  case "$v" in yes) ntp_sync=true;ntp_status=collected;; no) ntp_sync=false;ntp_status=collected;; esac
fi

ssh_pass='null'; ssh_root='null'; ssh_pubkey='null'; ssh_empty='null'; ssh_x11='null'; ssh_status='unavailable'
sshd_bin=''
for candidate in /usr/sbin/sshd /sbin/sshd; do
  if [ -x "$candidate" ]; then sshd_bin=$candidate; break; fi
done
if [ -z "$sshd_bin" ]; then sshd_bin=$(command -v sshd 2>/dev/null || true); fi
if [ -n "$sshd_bin" ] && command -v timeout >/dev/null 2>&1; then
  # sshd -T reports effective global defaults, but Match sections can alter
  # per-connection behaviour. Never treat as proof of per-user policy.
  v=$(timeout 5 "$sshd_bin" -T 2>/dev/null)
  rc=$?
  if [ "$rc" -eq 0 ] && [ -n "$v" ]; then
    ssh_pass=$(printf '%s\n' "$v" | awk '$1=="passwordauthentication"{print $2;exit}')
    ssh_root=$(printf '%s\n' "$v" | awk '$1=="permitrootlogin"{print $2;exit}')
    ssh_pubkey=$(printf '%s\n' "$v" | awk '$1=="pubkeyauthentication"{print $2;exit}')
    ssh_empty=$(printf '%s\n' "$v" | awk '$1=="permitemptypasswords"{print $2;exit}')
    ssh_x11=$(printf '%s\n' "$v" | awk '$1=="x11forwarding"{print $2;exit}')
    ssh_status=collected
  fi
fi

apparmor='null'; apparmor_status='unavailable'
if [ -r /sys/module/apparmor/parameters/enabled ]; then
  v=$(cat /sys/module/apparmor/parameters/enabled 2>/dev/null)
  case "$v" in Y) apparmor=true;apparmor_status=collected;; N) apparmor=false;apparmor_status=collected;; esac
fi

unattended='null'; unattended_status='unavailable'; firewall='null'; firewall_status='unavailable'
if command -v dpkg-query >/dev/null 2>&1; then
  v=$(dpkg-query -W -f='${Status}' unattended-upgrades 2>/dev/null)
  case "$v" in 'install ok installed') unattended=true;unattended_status=collected;; *) unattended=false;unattended_status=collected;; esac
fi
if command -v ufw >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
  v=$(timeout 5 ufw status 2>/dev/null | sed -n '1p')
  case "$v" in 'Status: active') firewall='active';firewall_status=collected;; 'Status: inactive') firewall='inactive';firewall_status=collected;; esac
fi

# Bounded sample of *kernel* journal for incident triage. Raw lines never leave
# the pipe; only numeric counters are kept. No logging, backups or command output.
journal_status='unavailable'; sampled_oom='null'; sampled_io='null'; sampled_kernel_errors='null'
if command -v journalctl >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
  # Both commands must succeed. A failed or timed-out query MUST stay
  # unavailable; it must never produce a misleading count of zero incidents.
  if timeout 5 journalctl -b -k -n 1 --no-pager -o cat >/dev/null 2>&1; then
    if kernel_lines=$(timeout 8 journalctl -b -k -p 0..3 --since '-24 hours' -n 300 --no-pager -o cat 2>/dev/null); then
      counters=$(printf '%s\n' "$kernel_lines" | awk '
        NF>0 {n++; line=tolower($0);
          if (line ~ /out of memory|oom-killer|killed process/) oom++;
          if (line ~ /i\/o error|blk_update_request|nvme.*timeout|ext4-fs error|xfs.*corrupt/) io++ }
        END {printf "%d %d %d",oom+0,io+0,n+0}')
      # Do not store or print kernel_lines; only counts reach the JSON.
      kernel_lines=''
      set -- $counters
      if [ "$#" -eq 3 ]; then
        sampled_oom=$(num "$1"); sampled_io=$(num "$2"); sampled_kernel_errors=$(num "$3")
        journal_status='sampled'
      fi
    fi
  fi
fi

kptr='null'; dmesg='null'; hardlinks='null'; symlinks='null'
for pair in kernel/kptr_restrict kernel/dmesg_restrict fs/protected_hardlinks fs/protected_symlinks; do
  path=/proc/sys/$pair
  if [ -r "$path" ]; then
    val=$(cat "$path" 2>/dev/null)
    val=$(num "$val")
    case "$pair" in
      kernel/kptr_restrict) kptr=$val;;
      kernel/dmesg_restrict) dmesg=$val;;
      fs/protected_hardlinks) hardlinks=$val;;
      fs/protected_symlinks) symlinks=$val;;
    esac
  fi
done

# Never output arbitrary strings from journalctl or config files.
# Journal-based incident correlation is separate until a non-leaking bounded
# parser and provenance tests are available.
render() {
  cat <<EOFJSON
{
  "schema_version": "extended-1.0",
  "report_type": "private_extended",
  "collected_at": "$now",
  "os_family": "$os_id",
  "os_version": "$os_version",
  "storage": {"root_inode_used_percent": $(num "$inode_pct"), "root_read_only": $(bool "$root_readonly")},
  "process_health": {"zombie_count": $(num "$zombie"), "uninterruptible_count": $(num "$dstate"), "failed_systemd_services": $(num "$failed_services")},
  "network": {"interface_count": $(num "$iface_count"), "default_ipv4_routes": $(num "$default_routes"), "tcp_listening_socket_count": $(num "$listeners")},
  "time": {"ntp_synchronized": $(bool "$ntp_sync")},
  "incident_sample": {"kernel_error_entries": $(num "$sampled_kernel_errors"), "oom_mentions": $(num "$sampled_oom"), "io_error_mentions": $(num "$sampled_io"), "max_entries": 300, "window_hours": 24},
  "security": {
    "sshd_global_password_auth": $(enum "$ssh_pass"),
    "sshd_global_root_login": $(enum "$ssh_root"),
    "sshd_global_pubkey_auth": $(enum "$ssh_pubkey"),
    "sshd_global_empty_passwords": $(enum "$ssh_empty"),
    "sshd_global_x11_forwarding": $(enum "$ssh_x11"),
    "apparmor_kernel_enabled": $(bool "$apparmor"),
    "unattended_upgrades_installed": $(bool "$unattended"),
    "ufw_status": $(enum "$firewall"),
    "kernel_kptr_restrict": $(num "$kptr"),
    "kernel_dmesg_restrict": $(num "$dmesg"),
    "fs_protected_hardlinks": $(num "$hardlinks"),
    "fs_protected_symlinks": $(num "$symlinks")
  },
  "checks": {"inodes":"$inode_status","root_mount":"$mount_status","processes":"$ps_status","network":"$net_status","systemd":"$systemd_status","ntp":"$ntp_status","sshd":"$ssh_status","apparmor":"$apparmor_status","updates":"$unattended_status","firewall":"$firewall_status","kernel_journal":"$journal_status"},
  "privacy": {"raw_logs": false, "hostnames": false, "addresses": false, "environment": false, "secrets": false}
}
EOFJSON
}
if [ "$stdout_mode" -eq 1 ]; then
  render
else
  [ -n "$output" ] || output="./serverdiag-extended-$stamp-$$.json"
  temp=$(mktemp "$output.tmp.XXXXXXXX") || { echo 'No se pudo crear temporal' >&2; exit 1; }
  trap 'rm -f -- "$temp"' 0
  if ! render > "$temp"; then exit 1; fi
  if ! ln -- "$temp" "$output" 2>/dev/null; then
    echo 'No se puede crear el destino o ya existe' >&2; exit 1
  fi
  rm -f -- "$temp"; trap - 0
  printf 'Informe extendido local: %s\n' "$output"
fi
