#!/usr/bin/env bash
set -euo pipefail

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

  echo "[1/4] Unregistering AppConfig (if present)"
  if [[ -f "${APP_CONF_DST}" ]]; then
    /usr/local/cpanel/bin/unregister_appconfig "${APP_CONF_DST}" >/dev/null || true
  fi

  echo "[2/4] Removing AppConfig file"
  rm -f "${APP_CONF_DST}"

  echo "[3/4] Removing CGI dir"
  rm -rf "${CGI_DST_DIR}"

  echo "[4/4] Removing cache dir"
  rm -rf "${CACHE_DIR}"

  echo
  echo "Uninstalled successfully."
}

main "$@"
