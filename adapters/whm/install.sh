#!/usr/bin/env bash
set -euo pipefail

APP_CONF_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/appconfig/procwatch.conf"
CGI_SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cgi/procwatch"

APP_CONF_DST="/var/cpanel/apps/procwatch.conf"
CGI_DST_DIR="/usr/local/cpanel/whostmgr/docroot/cgi/procwatch"
CACHE_DIR="/var/cache/procwatch"

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: Please run as root." >&2
    exit 1
  fi
}

main() {
  require_root

  echo "[1/4] Creating cache dir: ${CACHE_DIR}"
  mkdir -p "${CACHE_DIR}"
  chmod 0755 "${CACHE_DIR}"

  echo "[2/4] Installing WHM AppConfig: ${APP_CONF_DST}"
  install -m 0644 "${APP_CONF_SRC}" "${APP_CONF_DST}"

  echo "[3/4] Installing CGI script: ${CGI_DST_DIR}"
  mkdir -p "${CGI_DST_DIR}"
  install -m 0755 "${CGI_SRC_DIR}/index.cgi" "${CGI_DST_DIR}/index.cgi"

  echo "[4/4] Registering AppConfig (WHM menu refresh)"
  /usr/local/cpanel/bin/register_appconfig "${APP_CONF_DST}" >/dev/null

  echo
  echo "Installed successfully. Open WHM -> ProcWatch."
}

main "$@"
