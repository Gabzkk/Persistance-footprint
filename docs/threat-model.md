# Threat Model

## Trust Boundaries

1. The JSON configuration file crosses from administrator control into the agent.
2. Linux `/proc` and filesystem statistics cross from the kernel into the collector.
3. Telemetry crosses from the host to the configured HTTPS collector.
4. The bearer token crosses from the systemd environment file into the request header.

## Assets

- Collector credential.
- Integrity and availability of local audit evidence.
- Host availability.
- Accuracy of recovery-validation metrics.

## STRIDE Controls

| Threat | Control |
|---|---|
| Spoofing | HTTPS certificate verification and optional bearer authentication. |
| Tampering | TLS in transit, append-only JSONL events, restrictive file modes. |
| Repudiation | Stable event names, UTC timestamps, host ID, and correlation IDs. |
| Information disclosure | Metric allowlist; secrets never serialized or logged. |
| Denial of service | Bounded payloads, timeouts, capped backoff, bounded log rotation. |
| Elevation of privilege | Dynamic systemd user, no capabilities, no-new-privileges, read-only filesystem. |

## Abuse Cases

- A collector URL points to cleartext or an unexpected scheme: configuration loading fails.
- A collector stalls: the request times out and delivery retries with bounded exponential backoff.
- A log grows indefinitely: rotation caps active and archived files.
- A token appears in an error: errors are normalized and headers are never logged.
- A configuration attempts sub-second sampling: validation rejects the resource-exhaustion setting.
