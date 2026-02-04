#!/usr/bin/env bash
set -euo pipefail

# ProcWatch WHM installer
#
# - Registers a WHM AppConfig entry (adds a left-menu item)
# - Installs the CGI script (UI + JSON endpoint)
# - Installs an icon (48x48 PNG) under addon_plugins
# - Creates a small cache directory
#
# Docs:
# - https://api.docs.cpanel.net/guides/quickstart-development-guide/tutorial-create-a-whm-plugin/
# - https://api.docs.cpanel.net/guides/quickstart-development-guide/tutorial-register-a-whm-plugin-with-appconfig/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

APP_CONF_SRC="${SCRIPT_DIR}/appconfig/procwatch.conf"
CGI_SRC_DIR="${SCRIPT_DIR}/cgi/procwatch"
ICON_SRC="${SCRIPT_DIR}/icon/procwatch.png"

CGI_DST_DIR="/usr/local/cpanel/whostmgr/docroot/cgi/procwatch"
ICON_DST_DIR="/usr/local/cpanel/whostmgr/docroot/addon_plugins"
CACHE_DIR="/var/cache/procwatch"

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: Please run as root." >&2
    exit 1
  fi
}

require_cpanel() {
  if [[ ! -x "/usr/local/cpanel/bin/register_appconfig" ]]; then
    echo "ERROR: cPanel/WHM not detected. Missing /usr/local/cpanel/bin/register_appconfig" >&2
    exit 1
  fi
}

main() {
  require_root
  require_cpanel

  echo "[1/5] Creating cache dir: ${CACHE_DIR}"
  mkdir -p "${CACHE_DIR}"
  chmod 0755 "${CACHE_DIR}"

  echo "[2/5] Installing icon to: ${ICON_DST_DIR}"
  mkdir -p "${ICON_DST_DIR}"
  install -m 0644 "${ICON_SRC}" "${ICON_DST_DIR}/procwatch.png"

  echo "[3/6] Installing CGI scripts to: ${CGI_DST_DIR}"
  mkdir -p "${CGI_DST_DIR}"
  install -m 0755 "${CGI_SRC_DIR}/index.cgi" "${CGI_DST_DIR}/index.cgi"
  install -m 0755 "${CGI_SRC_DIR}/metrics.cgi" "${CGI_DST_DIR}/metrics.cgi"
  install -m 0644 "${CGI_SRC_DIR}/VERSION" "${CGI_DST_DIR}/VERSION"

  echo "[4/6] Installing Template Toolkit interface"
  mkdir -p "/usr/local/cpanel/whostmgr/docroot/templates/procwatch"
  install -m 0644 "${SCRIPT_DIR}/templates/procwatch/index.tmpl" "/usr/local/cpanel/whostmgr/docroot/templates/procwatch/index.tmpl"

  echo "[5/6] Registering AppConfig (adds WHM menu item)"
  /usr/local/cpanel/bin/register_appconfig "${APP_CONF_SRC}" >/dev/null

  echo "[6/6] Done"
  echo
  echo "Installed successfully."
  echo "- Log into WHM and open: ProcWatch"
}

main "$@"
