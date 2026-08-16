#!/bin/sh
set -eu

template=/opt/token-station/http.conf.template
if [ "${TLS_ENABLED:-false}" = "true" ]; then
  cert="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
  key="/etc/letsencrypt/live/${DOMAIN}/privkey.pem"
  if [ ! -s "$cert" ] || [ ! -s "$key" ]; then
    echo "TLS_ENABLED=true but certificate files are missing" >&2
    exit 1
  fi
  template=/opt/token-station/https.conf.template
fi

envsubst '${DOMAIN}' < "$template" > /etc/nginx/conf.d/default.conf
exec nginx -g 'daemon off;'
