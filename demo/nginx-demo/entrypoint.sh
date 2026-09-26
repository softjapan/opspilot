#!/bin/sh
set -e

nginx -g 'daemon off;' &
NGINX_PID=$!

until curl -s -o /dev/null http://127.0.0.1/healthz; do
    sleep 0.2
done

# Generate demo traffic: /api/search proxies to a closed port, so this
# reliably produces a 502 in access.log and a connect-failure in error.log.
curl -s -o /dev/null http://127.0.0.1/api/search || true
curl -s -o /dev/null http://127.0.0.1/api/search || true

wait "$NGINX_PID"
