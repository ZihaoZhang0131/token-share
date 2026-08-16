#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
if [ ! -f .env ]; then
  echo "Missing .env. Copy .env.example and replace all CHANGE_ME values." >&2
  exit 1
fi
set -a
. ./.env
set +a
: "${DOMAIN:?DOMAIN is required}"
: "${LETSENCRYPT_EMAIL:?LETSENCRYPT_EMAIL is required}"

TLS_ENABLED=false docker compose up -d --build postgres redis api nginx
docker compose --profile maintenance run --rm certbot certonly \
  --webroot --webroot-path /var/www/certbot \
  --domain "$DOMAIN" \
  --email "$LETSENCRYPT_EMAIL" \
  --agree-tos --non-interactive --no-eff-email

tmp_file=".env.tls.$$"
awk 'BEGIN { found=0 } /^TLS_ENABLED=/ { print "TLS_ENABLED=true"; found=1; next } { print } END { if (!found) print "TLS_ENABLED=true" }' .env > "$tmp_file"
mv "$tmp_file" .env
docker compose up -d --force-recreate nginx
echo "HTTPS enabled for https://$DOMAIN"
