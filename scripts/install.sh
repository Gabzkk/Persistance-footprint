#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
INSTALL_DIR="/opt/persistent-footprint"
CONFIG_DIR="/etc/persistent-footprint"
UNIT_PATH="/etc/systemd/system/persistent-footprint.service"

if [[ "${EUID}" -ne 0 ]]; then
  echo "install must run as root" >&2
  exit 1
fi

for command in install systemctl python3; do
  command -v "${command}" >/dev/null 2>&1 || {
    echo "required command not found: ${command}" >&2
    exit 1
  }
done

python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' || {
  echo "Python 3.11 or newer is required" >&2
  exit 1
}

install -d -m 0755 "${INSTALL_DIR}" "${INSTALL_DIR}/src" "${INSTALL_DIR}/src/persistent_footprint"
install -m 0644 "${PROJECT_DIR}/README.md" "${INSTALL_DIR}/README.md"
install -m 0644 "${PROJECT_DIR}/pyproject.toml" "${INSTALL_DIR}/pyproject.toml"
install -m 0644 "${PROJECT_DIR}"/src/persistent_footprint/*.py "${INSTALL_DIR}/src/persistent_footprint/"
install -d -m 0755 "${CONFIG_DIR}"

if [[ ! -e "${CONFIG_DIR}/config.json" ]]; then
  install -m 0644 "${PROJECT_DIR}/config.example.json" "${CONFIG_DIR}/config.json"
fi

if [[ ! -e "${CONFIG_DIR}/agent.env" ]]; then
  install -m 0600 /dev/null "${CONFIG_DIR}/agent.env"
fi

install -m 0644 "${PROJECT_DIR}/systemd/persistent-footprint.service" "${UNIT_PATH}"
systemctl daemon-reload
systemctl enable --now persistent-footprint.service
systemctl --no-pager --full status persistent-footprint.service
