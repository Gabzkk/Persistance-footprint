#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/persistent-footprint"
CONFIG_DIR="/etc/persistent-footprint"
UNIT_PATH="/etc/systemd/system/persistent-footprint.service"
PURGE_DATA=false

if [[ "${1:-}" == "--purge-data" ]]; then
  PURGE_DATA=true
elif [[ $# -gt 0 ]]; then
  echo "usage: $0 [--purge-data]" >&2
  exit 2
fi

if [[ "${EUID}" -ne 0 ]]; then
  echo "uninstall must run as root" >&2
  exit 1
fi

systemctl disable --now persistent-footprint.service 2>/dev/null || true
rm -f -- "${UNIT_PATH}"
rm -rf -- "${INSTALL_DIR}"
systemctl daemon-reload
systemctl reset-failed persistent-footprint.service 2>/dev/null || true

if [[ "${PURGE_DATA}" == true ]]; then
  rm -rf -- "${CONFIG_DIR}" "/var/lib/persistent-footprint" "/var/log/persistent-footprint"
  echo "service, configuration, spool, and audit data removed"
else
  echo "service removed; configuration and recovery evidence retained"
fi
