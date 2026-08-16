#!/bin/sh
set -eu

fail=0
check_command() {
  if command -v "$1" >/dev/null 2>&1; then
    printf 'OK   %-18s %s\n' "$1" "$(command -v "$1")"
  else
    printf 'FAIL %-18s not installed\n' "$1"
    fail=1
  fi
}

echo "Token Station server preflight"
echo "------------------------------"
uname -a
echo
check_command docker
check_command curl
check_command openssl

if command -v docker >/dev/null 2>&1; then
  docker --version
  if docker compose version >/dev/null 2>&1; then
    echo "OK   docker compose     $(docker compose version --short)"
  else
    echo "FAIL docker compose     unavailable"
    fail=1
  fi
fi

cpu_count=$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 0)
memory_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
disk_kb=$(df -Pk . | awk 'NR==2 {print $4}')
echo "INFO CPU cores          $cpu_count (recommended: 2+)"
echo "INFO memory KiB         $memory_kb (recommended: 4194304+)"
echo "INFO free disk KiB      $disk_kb (recommended: 31457280+)"

for port in 80 443; do
  if command -v ss >/dev/null 2>&1 && ss -ltn "sport = :$port" | grep -q LISTEN; then
    echo "WARN port $port is already in use"
  else
    echo "OK   port $port          available"
  fi
done

if [ "$fail" -ne 0 ]; then
  echo "Preflight failed. Install the missing dependencies before deployment." >&2
  exit 1
fi
echo "Preflight completed. Review WARN and INFO lines before continuing."
