# Persistent Footprint Specification

## Objective

Build a transparent Linux host-monitoring agent for authorized recovery validation. It must collect CPU, memory, disk, load, uptime, and aggregate network counters; retain structured local audit evidence; optionally forward batches to one configured HTTPS endpoint; start at boot with systemd; and uninstall cleanly.

## Assumptions

- Target systems use Linux, systemd, and Python 3.11 or newer.
- Installation is explicit and performed by an administrator.
- The central collector accepts JSON over HTTPS with an optional bearer token.
- Telemetry contains host-level metrics only. It never captures process memory, file contents, input events, credentials, or packet payloads.
- The service identity and logs remain visible to administrators.

## Commands

| Purpose | Command |
|---|---|
| Test | `python3 -m unittest discover -s tests -v` |
| Static compile check | `python3 -m compileall -q src tests` |
| One sample | `PYTHONPATH=src python3 -m persistent_footprint --config config.example.json --once` |
| Install | `sudo ./scripts/install.sh` |
| Remove | `sudo ./scripts/uninstall.sh` |

## Project Structure

- `src/persistent_footprint/`: collection, validation, audit storage, HTTPS delivery, and service loop.
- `tests/`: deterministic unit and localhost integration tests.
- `systemd/`: hardened boot service.
- `scripts/`: explicit install and uninstall operations.
- `docs/`: specification and threat model.

## Code Style

Python uses typed dataclasses, standard-library dependencies, explicit exception types, JSON events with stable names, and bounded I/O.

```python
event = {
    "event": "telemetry_sampled",
    "correlation_id": correlation_id,
    "timestamp": timestamp,
    "metrics": metrics,
}
```

## Testing Strategy

- Unit tests cover configuration rejection, Linux metric parsing, redaction, log rotation, and retry backoff.
- Integration tests use a localhost HTTP server only and verify delivery payloads and authorization headers.
- A one-shot execution validates real host collection without installing the systemd unit.

## Boundaries

- Always: require HTTPS for non-loopback collectors, bound timeouts and files, redact authorization data, use least-privilege systemd controls.
- Ask first: adding telemetry fields, new external integrations, elevated capabilities, or remote control.
- Never: hide the service, capture content or credentials, execute remote commands, disable TLS verification, or delete user data.

## Success Criteria

- A one-shot run writes a valid `telemetry_sampled` JSON event.
- Continuous mode survives transient collector failures using bounded exponential backoff.
- Audit files rotate before exceeding the configured byte limit and retain a fixed number of archives.
- A hardened systemd unit starts the agent on boot and restarts only on failure.
- The uninstall script stops, disables, and removes only files installed by this project.
- The full test suite and Python compile check pass.
