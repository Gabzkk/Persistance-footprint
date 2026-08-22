# Persistent Footprint

Persistent Footprint is a transparent Linux host-monitoring service for recovery validation. It records allowlisted resource metrics in JSONL, optionally forwards them to an authenticated HTTPS collector, retains failed deliveries in a bounded disk spool, and starts on boot through a hardened systemd unit.

It does not capture process memory, file contents, keystrokes, credentials, network payloads, or remote commands.

## Requirements

- Linux with `/proc`
- systemd
- Python 3.11 or newer
- Root access for installation only

The runtime has no third-party Python dependencies.

## Validation Before Installation

```bash
cd /home/sunburnz/Documents/RandomProjects/Persistance-footprint
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
mkdir -p runtime/audit runtime/spool
python3 - <<'PY'
import json
from pathlib import Path

config = json.loads(Path("config.example.json").read_text())
config["audit"]["path"] = "runtime/audit/audit.jsonl"
config["spool"]["directory"] = "runtime/spool"
Path("runtime/config.json").write_text(json.dumps(config, indent=2) + "\n")
PY
PYTHONPATH=src python3 -m persistent_footprint --config runtime/config.json --once
```

The one-shot run prints `collection_cycle_completed` and writes one `telemetry_sampled` record to `runtime/audit/audit.jsonl`.

## Configure Central Delivery

Set `delivery.endpoint` in `config.example.json` or, after installation, `/etc/persistent-footprint/config.json`:

```json
{
  "delivery": {
    "endpoint": "https://audit.example.org/v1/telemetry",
    "timeout_seconds": 10,
    "token_env": "PERSISTENT_FOOTPRINT_TOKEN",
    "ca_file": null,
    "max_payload_bytes": 262144
  }
}
```

Store the credential outside JSON in `/etc/persistent-footprint/agent.env`, mode `0600`:

```text
PERSISTENT_FOOTPRINT_TOKEN=replace-with-the-issued-token
```

The collector must return a `2xx` response. Remote endpoints must use HTTPS with normal certificate verification. Plain HTTP is accepted only on loopback for integration tests.

## Install and Operate

```bash
sudo ./scripts/install.sh
systemctl status persistent-footprint.service
journalctl -u persistent-footprint.service --since today
sudo systemctl restart persistent-footprint.service
```

The service runs as a systemd dynamic user. Local evidence is stored under `/var/log/persistent-footprint/`; deferred deliveries are stored under `/var/lib/persistent-footprint/spool/`.

## Remove

```bash
sudo ./scripts/uninstall.sh
```

The default removal retains configuration and recovery evidence. To remove those exact project-owned paths as well:

```bash
sudo ./scripts/uninstall.sh --purge-data
```

## Event Contract

```json
{
  "schema_version": 1,
  "event": "telemetry_sampled",
  "correlation_id": "0c097f0f-a9eb-4a35-9573-afc55c08fd85",
  "timestamp": "2026-08-22T10:15:30.125+00:00",
  "host_id": "recovery-node-01",
  "metrics": {
    "cpu_used_percent": 17.2,
    "memory_used_percent": 42.8,
    "network_rx_bytes": 1928374,
    "network_tx_bytes": 918273,
    "uptime_seconds": 86401.3,
    "disk": []
  }
}
```

Every audit line is an independent JSON object. Sensitive field names are recursively redacted before persistence. Active and archived audit files are bounded by `max_bytes` and `backups`; the retry spool is bounded by `max_files`.

## Recovery Validation Checklist

1. Run the unit and integration suite.
2. Execute one-shot mode and validate the JSONL record.
3. Configure a staging HTTPS collector and verify a `2xx` delivery.
4. Stop the collector and confirm new files appear in the spool.
5. Restore the collector and confirm the spool drains oldest-first.
6. Reboot the staging host and verify `systemctl is-active persistent-footprint.service` returns `active`.
7. Record timestamps for the reboot and first post-boot `telemetry_sampled` event as the recovery interval.
