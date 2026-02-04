#!/usr/bin/env bash
set -euo pipefail

# ProcWatch WHM uninstaller

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_CONF_SRC="${SCRIPT_DIR}/appconfig/procwatch.conf"

CGI_DST_DIR="/usr/local/cpanel/whostmgr/docroot/cgi/procwatch"
ICON_DST="/usr/local/cpanel/whostmgr/docroot/addon_plugins/procwatch.png"
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
  if [[ -x "/usr/local/cpanel/bin/unregister_appconfig" ]]; then
    /usr/local/cpanel/bin/unregister_appconfig "${APP_CONF_SRC}" >/dev/null || true
  fi

  echo "[2/4] Removing CGI dir: ${CGI_DST_DIR}"
  rm -rf "${CGI_DST_DIR}"

  echo "[3/4] Removing icon: ${ICON_DST}"
  rm -f "${ICON_DST}"

  echo "[4/4] Removing cache dir: ${CACHE_DIR}"
  rm -rf "${CACHE_DIR}"

  echo
  echo "Uninstalled successfully."
}

main "$@"
