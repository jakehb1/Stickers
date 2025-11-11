#!/bin/sh
set -eu

DEFAULT_API_BASE_URL="http://backend:8000"
API_BASE_URL="${API_BASE_URL:-$DEFAULT_API_BASE_URL}"
MINI_APP_API_BASE_URL="${MINI_APP_API_BASE_URL:-$API_BASE_URL}"
ADMIN_API_BASE_URL="${ADMIN_API_BASE_URL:-$API_BASE_URL}"

cat <<CONFIG > /usr/share/nginx/html/config.js
window.API_BASE_URL = "${MINI_APP_API_BASE_URL}";
CONFIG

cat <<CONFIG > /usr/share/nginx/html/admin/config.js
window.API_BASE_URL = "${ADMIN_API_BASE_URL}";
CONFIG

nginx -g 'daemon off;'
