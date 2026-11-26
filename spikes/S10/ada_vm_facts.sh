#!/usr/bin/env bash
# S10, the Ada platform (changes/2026-11-26-ada/plan.md; ada D2.3). The owner runs this on an Ada VM and sends back
# its output. It prints generic facts and exit codes only. It opens no key file and reads nothing under ~/.ssh; it
# prints no host name, account, path or URL, and its output passes through a filter that replaces the user name, the
# host name, the home folder and every value given below, in case a program prints one.
# Usage: bash spikes/S10/ada_vm_facts.sh [--ssh-host ALIAS] [--work-area PATH] [--model-url URL] [--dft-url URL]
#                                        [--no-network]
#   --ssh-host ALIAS   how this VM's own SSH configuration names a SCARF login node (tested with BatchMode, no prompt)
#   --work-area PATH   the user's SCARF work area, if it may be mounted on this VM
#   --model-url URL    a model endpoint Ada might use (HTTP status only)
#   --dft-url URL      a goldilocks-dft service Ada might use (HTTP status only)
#   --no-network       skip the HTTPS checks of item 3
# Needs bash 3.2 or later; every other program is optional and reported as absent if missing.

set -u
ssh_host="" work_area="" model_url="" dft_url="" network=1

usage() { sed -n 's/^# \{0,1\}//; 6,12p' "$0"; }
while [ $# -gt 0 ]; do
  case $1 in
    --ssh-host) ssh_host=${2-}; shift 2 || { usage; exit 2; } ;;
    --work-area) work_area=${2-}; shift 2 || { usage; exit 2; } ;;
    --model-url) model_url=${2-}; shift 2 || { usage; exit 2; } ;;
    --dft-url) dft_url=${2-}; shift 2 || { usage; exit 2; } ;;
    --no-network) network=0; shift ;;
    -h | --help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done

have() { command -v "$1" >/dev/null 2>&1; }
yesno() { if "$@" >/dev/null 2>&1; then echo yes; else echo no; fi; }
limit() {  # limit <seconds> <command...>: the command, stopped after <seconds> where `timeout` exists
  local seconds=$1; shift
  if have timeout; then timeout "$seconds" "$@"; else "$@"; fi
}
say() { printf '%s: %s\n' "$1" "${2:-unknown}"; }
section() { printf '\n== %s\n' "$1"; }
on_path() {  # on_path <folder>: yes if the folder is on PATH
  case ":$PATH:" in
    *":$1:"*) echo yes ;;
    *) echo no ;;
  esac
}
remote() { limit 30 ssh -o BatchMode=yes -o ConnectTimeout=10 -- "$ssh_host" "$@" </dev/null 2>/dev/null; }
cluster_kind() {  # reads `scontrol show config` on stdin; prints scarf, other or unknown, never the name itself
  awk -F= '/^ClusterName/ { gsub(/[[:space:]]/, "", $2); n = tolower($2) }
           END { if (n == "") print "unknown"; else if (n == "scarf") print "scarf"; else print "other" }'
}

facts() {
  printf 'S10 facts, script version 1, %s (UTC)\n' "$(date -u +%Y-%m-%d)"

  section "1. One user per VM"
  local os=""
  if [ -r /etc/os-release ]; then os=$(. /etc/os-release && echo "${PRETTY_NAME:-}"); fi
  [ -n "$os" ] || os="$(uname -s) $(have sw_vers && sw_vers -productVersion)"
  say "operating system" "$os"
  say "architecture" "$(uname -m)"
  say "virtualisation" "$(have systemd-detect-virt && systemd-detect-virt 2>/dev/null)"
  say "CPUs" "$( (have nproc && nproc) || getconf _NPROCESSORS_ONLN 2>/dev/null)"
  if [ -r /proc/meminfo ]; then
    say "memory (GiB)" "$(awk '/^MemTotal:/ { printf "%.1f", $2 / 1048576 }' /proc/meminfo)"
  else
    say "memory (GiB)" "$(sysctl -n hw.memsize 2>/dev/null | awk '{ printf "%.1f", $1 / 1073741824 }')"
  fi
  say "disk in the home folder, free of total (GiB)" \
    "$(df -Pk "$HOME" 2>/dev/null | awk 'NR == 2 { printf "%.1f of %.1f", $4 / 1048576, $2 / 1048576 }')"
  [ -r /proc/uptime ] && say "up for (days)" "$(awk '{ printf "%.1f", $1 / 86400 }' /proc/uptime)"
  say "login sessions now" "$(who 2>/dev/null | wc -l | tr -d ' ')"
  say "distinct users logged in now" "$(who 2>/dev/null | awk '{ print $1 }' | sort -u | wc -l | tr -d ' ')"
  [ -r /etc/passwd ] && say "local accounts with a user ID of 1000 or more" \
    "$(awk -F: '$3 >= 1000 && $3 < 65534' /etc/passwd | wc -l | tr -d ' ')"
  [ -d /home ] && say "folders under /home" "$(find /home -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')"
  say "NVIDIA GPUs" "$(if have nvidia-smi; then nvidia-smi -L 2>/dev/null | wc -l | tr -d ' '; else echo 0; fi)"

  section "2. How SCARF is reached"
  local p
  for p in sbatch squeue sacct scancel sinfo scontrol; do say "$p on the VM" "$(yesno have "$p")"; done
  if have sinfo; then say "Slurm version (VM)" "$(limit 20 sinfo --version 2>/dev/null)"; fi
  if have scontrol; then say "cluster name (VM)" "$(limit 20 scontrol show config 2>/dev/null | cluster_kind)"; fi
  if have squeue; then limit 20 squeue --me -h >/dev/null 2>&1; say "squeue --me (VM), exit code" "$?"; fi
  say "ssh client" "$(if have ssh; then ssh -V 2>&1 | awk '{ print $1 }' | tr -d ','; else echo absent; fi)"
  say "SSH agent socket set" "$(if [ -n "${SSH_AUTH_SOCK:-}" ]; then echo yes; else echo no; fi)"
  ssh_ok=no
  if [ -n "$ssh_host" ] && have ssh; then
    remote true; local code=$?
    say "ssh in batch mode (no prompt), exit code" "$code"
    if [ "$code" -eq 0 ]; then
      ssh_ok=yes
      say "remote login shell" "$(remote printenv SHELL | awk -F/ '{ print $NF }')"
      remote sbatch --version >/dev/null; say "sbatch over ssh, exit code" "$?"
      say "Slurm version (SSH)" "$(remote sinfo --version)"
      say "cluster name (SSH)" "$(remote scontrol show config | cluster_kind)"
    fi
  else
    say "ssh to SCARF" "not tested (no --ssh-host)"
  fi
  if [ -n "$work_area" ]; then
    say "work area exists on the VM" "$(yesno test -d "$work_area")"
    say "work area writable from the VM" "$(yesno test -w "$work_area")"
    if [ "$(uname -s)" = Linux ]; then say "work area file system" "$(stat -f -c %T "$work_area" 2>/dev/null)"; fi
  else
    say "work area on the VM" "not tested (no --work-area)"
  fi
  for p in rsync scp sftp; do say "$p" "$(yesno have "$p")"; done
  if have rsync; then
    say "rsync version" "$(rsync --version 2>/dev/null | grep -oE 'rsync +version [0-9][0-9.]*' | awk 'NR == 1 { print $NF }')"
  fi

  section "3. What the VM can install and reach"
  say "python3" "$(if have python3; then python3 -c 'import platform; print(platform.python_version())'; else echo absent; fi)"
  say "pip for python3" "$(yesno python3 -m pip --version)"
  say "uv" "$(if have uv; then uv --version 2>/dev/null | awk '{ print $2 }'; else echo absent; fi)"
  say "~/.local/bin on PATH" "$(on_path "$HOME/.local/bin")"
  for p in docker podman apptainer singularity; do say "$p" "$(yesno have "$p")"; done
  if have docker; then limit 15 docker info >/dev/null 2>&1; say "docker info, exit code" "$?"; fi
  if have podman; then limit 15 podman info >/dev/null 2>&1; say "podman info, exit code" "$?"; fi
  say "proxy variables set" "$(if [ -n "${https_proxy:-}${HTTPS_PROXY:-}${http_proxy:-}${HTTP_PROXY:-}" ]; then echo yes; else echo no; fi)"
  if [ "$network" -eq 0 ]; then
    say "HTTPS checks" "skipped (--no-network)"
  elif ! have curl; then
    say "HTTPS checks" "skipped (no curl)"
  else
    local name url code
    while read -r name url; do
      [ -n "$url" ] || continue
      code=$(curl -sS -o /dev/null -m 15 -w '%{http_code}' "$url" 2>/dev/null)
      if [ "${code:-000}" = 000 ]; then code="000 (no answer)"; fi
      say "HTTP status, $name" "$code"
    done <<EOF
PyPI https://pypi.org/simple/
PyPI-files https://files.pythonhosted.org/
GitHub https://github.com/
GHCR https://ghcr.io/v2/
uv-installer https://astral.sh/uv/install.sh
model-endpoint $model_url
goldilocks-dft $dft_url
EOF
  fi

  section "4. How the user reaches a web app in the VM"
  say "graphical session" "$(if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then echo yes; else echo no; fi)"
  for p in firefox chromium chromium-browser google-chrome; do say "$p" "$(yesno have "$p")"; done
  say "can listen on 127.0.0.1" "$(yesno python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); s.listen()')"

  section "5. Slurm on SCARF"
  local route=none
  if have scontrol && have sacct; then route=VM; elif [ "$ssh_ok" = yes ]; then route=SSH; fi
  say "route" "$route"
  if [ "$route" != none ]; then
    local config jobs
    if [ "$route" = VM ]; then
      config=$(limit 20 scontrol show config 2>/dev/null)
      jobs=$(limit 60 sacct -X -n -P -S 2015-01-01 -o Submit 2>/dev/null)
    else
      config=$(remote scontrol show config)
      jobs=$(remote sacct -X -n -P -S 2015-01-01 -o Submit)
    fi
    say "MinJobAge" "$(printf '%s\n' "$config" | awk -F= '/^MinJobAge/ { sub(/^[[:space:]]+/, "", $2); print $2 }')"
    local oldest
    oldest=$(printf '%s\n' "$jobs" | grep -E '^[0-9]{4}-[0-9]{2}' | sort | head -n 1 | cut -c1-7)
    say "oldest job sacct shows (year-month)" "${oldest:-none}"
  fi

  section "Answer by hand"
  echo "1. Does this VM persist between logins, and does anyone else use it?"
  echo "4. How do you open a web page served inside the VM: a browser in the VM, Ada's proxy, or a forwarded port?"
  echo "5. How long does SCARF's accounting keep finished jobs, and where is that stated?"
  echo "Where should the model and goldilocks-dft run for Ada: inside each VM, or as services the VM reaches?"
}

redact() {  # replaces each value in REDACT_1..REDACT_9 with its label, as plain text, never as a pattern
  awk 'BEGIN {
         n = split("<user> <user> <host> <host> <home> <ssh-host> <work-area> <model-url> <dft-url>", label, " ")
         for (i = 1; i <= n; i++) value[i] = ENVIRON["REDACT_" i]
       }
       {
         for (i = 1; i <= n; i++) {
           if (length(value[i]) < 2) continue
           out = ""; line = $0
           while ((at = index(line, value[i])) > 0) {
             out = out substr(line, 1, at - 1) label[i]; line = substr(line, at + length(value[i]))
           }
           $0 = out line
         }
         print
       }'
}

host=$(hostname 2>/dev/null || uname -n)
export REDACT_1="$(id -un 2>/dev/null)" REDACT_2="${USER:-}" REDACT_3="$host" REDACT_4="${host%%.*}" \
  REDACT_5="$HOME" REDACT_6="$ssh_host" REDACT_7="$work_area" REDACT_8="$model_url" REDACT_9="$dft_url"
facts 2>&1 | redact
