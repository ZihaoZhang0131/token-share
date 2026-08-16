#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

archive="${1:-}"
if [ -z "$archive" ] || [ ! -f "$archive" ]; then
  echo "Usage: CONFIRM_RESTORE=yes $0 /path/to/backup.sql.gz" >&2
  exit 1
fi
if [ "${CONFIRM_RESTORE:-no}" != "yes" ]; then
  echo "Restore replaces data in the token_station database. Set CONFIRM_RESTORE=yes to continue." >&2
  exit 1
fi
gzip -t "$archive"
docker compose stop api nginx
docker compose exec -T postgres psql -U token_station -d postgres -v ON_ERROR_STOP=1 \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='token_station' AND pid <> pg_backend_pid();" \
  -c "DROP DATABASE IF EXISTS token_station;" \
  -c "CREATE DATABASE token_station OWNER token_station;"
gzip -dc "$archive" | docker compose exec -T postgres psql -U token_station -d token_station -v ON_ERROR_STOP=1
docker compose up -d api nginx
echo "Restore completed from: $archive"
