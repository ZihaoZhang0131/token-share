#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
docker compose --profile maintenance run --rm certbot renew --webroot --webroot-path /var/www/certbot --quiet
docker compose exec nginx nginx -s reload
