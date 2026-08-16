#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

backup_dir="${BACKUP_DIR:-./backups}"
mkdir -p "$backup_dir"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
target="$backup_dir/token-station-$stamp.sql.gz"
docker compose exec -T postgres pg_dump -U token_station -d token_station --no-owner --no-privileges | gzip -9 > "$target"
chmod 600 "$target"
find "$backup_dir" -type f -name 'token-station-*.sql.gz' -mtime +7 -delete
echo "Backup created: $target"
