from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


class ConfigError(ValueError):
    """Raised when an agent configuration violates its contract."""


@dataclass(frozen=True)
class AuditConfig:
    path: Path = Path("/var/log/persistent-footprint/audit.jsonl")
    max_bytes: int = 10 * 1024 * 1024
    backups: int = 5


@dataclass(frozen=True)
class DeliveryConfig:
    endpoint: str | None = None
    timeout_seconds: float = 10.0
    token_env: str = "PERSISTENT_FOOTPRINT_TOKEN"
    ca_file: Path | None = None
    max_payload_bytes: int = 256 * 1024


@dataclass(frozen=True)
class SpoolConfig:
    directory: Path = Path("/var/lib/persistent-footprint/spool")
    max_files: int = 1_000


@dataclass(frozen=True)
class AgentConfig:
    interval_seconds: float = 60.0
    disk_paths: tuple[Path, ...] = (Path("/"),)
    audit: AuditConfig = field(default_factory=AuditConfig)
    delivery: DeliveryConfig = field(default_factory=DeliveryConfig)
    spool: SpoolConfig = field(default_factory=SpoolConfig)


def _require_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{field_name} must be a JSON object")
    return value


def _reject_unknown(data: Mapping[str, Any], allowed: set[str], context: str = "configuration") -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(f"unknown {context} field: {unknown[0]}")


def _positive_number(value: object, field_name: str, minimum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < minimum:
        raise ConfigError(f"{field_name} must be at least {minimum:g}")
    return float(value)


def _positive_int(value: object, field_name: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ConfigError(f"{field_name} must be an integer of at least {minimum}")
    return value


def _optional_path(value: object, field_name: str) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field_name} must be a non-empty path")
    return Path(value)


def _validate_endpoint(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ConfigError("delivery.endpoint must be a URL or null")
    parsed = urlparse(value)
    loopback = parsed.hostname in {"127.0.0.1", "::1", "localhost"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
        raise ConfigError("delivery.endpoint must use HTTPS; HTTP is restricted to loopback testing")
    if parsed.username or parsed.password or not parsed.hostname:
        raise ConfigError("delivery.endpoint must not contain credentials and must include a host")
    if parsed.fragment:
        raise ConfigError("delivery.endpoint must not contain a fragment")
    return value


def load_config(path: Path) -> AgentConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigError(f"cannot read configuration: {error.strerror}") from error
    except json.JSONDecodeError as error:
        raise ConfigError(f"invalid JSON at line {error.lineno}, column {error.colno}") from error
    data = _require_mapping(raw, "configuration")
    _reject_unknown(data, {"interval_seconds", "disk_paths", "audit", "delivery", "spool"})

    interval = _positive_number(data.get("interval_seconds", 60), "interval_seconds", 1)
    disk_paths_raw = data.get("disk_paths", ["/"])
    if not isinstance(disk_paths_raw, list) or not disk_paths_raw or any(not isinstance(item, str) or not item for item in disk_paths_raw):
        raise ConfigError("disk_paths must be a non-empty array of paths")

    audit_data = _require_mapping(data.get("audit", {}), "audit")
    _reject_unknown(audit_data, {"path", "max_bytes", "backups"}, "audit")
    audit_path = _optional_path(audit_data.get("path", "/var/log/persistent-footprint/audit.jsonl"), "audit.path")
    if audit_path is None:
        raise ConfigError("audit.path cannot be null")
    audit = AuditConfig(
        path=audit_path,
        max_bytes=_positive_int(audit_data.get("max_bytes", 10 * 1024 * 1024), "audit.max_bytes", 1024),
        backups=_positive_int(audit_data.get("backups", 5), "audit.backups", 1),
    )

    delivery_data = _require_mapping(data.get("delivery", {}), "delivery")
    _reject_unknown(delivery_data, {"endpoint", "timeout_seconds", "token_env", "ca_file", "max_payload_bytes"}, "delivery")
    token_env = delivery_data.get("token_env", "PERSISTENT_FOOTPRINT_TOKEN")
    if not isinstance(token_env, str) or not token_env.isidentifier():
        raise ConfigError("delivery.token_env must be a valid environment variable name")
    delivery = DeliveryConfig(
        endpoint=_validate_endpoint(delivery_data.get("endpoint")),
        timeout_seconds=_positive_number(delivery_data.get("timeout_seconds", 10), "delivery.timeout_seconds", 1),
        token_env=token_env,
        ca_file=_optional_path(delivery_data.get("ca_file"), "delivery.ca_file"),
        max_payload_bytes=_positive_int(delivery_data.get("max_payload_bytes", 256 * 1024), "delivery.max_payload_bytes", 1024),
    )

    spool_data = _require_mapping(data.get("spool", {}), "spool")
    _reject_unknown(spool_data, {"directory", "max_files"}, "spool")
    spool_directory = _optional_path(spool_data.get("directory", "/var/lib/persistent-footprint/spool"), "spool.directory")
    if spool_directory is None:
        raise ConfigError("spool.directory cannot be null")

    return AgentConfig(
        interval_seconds=interval,
        disk_paths=tuple(Path(item) for item in disk_paths_raw),
        audit=audit,
        delivery=delivery,
        spool=SpoolConfig(
            directory=spool_directory,
            max_files=_positive_int(spool_data.get("max_files", 1_000), "spool.max_files", 1),
        ),
    )
