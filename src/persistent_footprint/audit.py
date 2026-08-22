from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping


_SENSITIVE_NAMES = frozenset({"authorization", "password", "secret", "token", "api_key", "apikey"})


class AuditError(RuntimeError):
    """Raised when an audit record cannot be persisted."""


def sanitize_event(value: Any, key: str = "") -> Any:
    if key.casefold() in _SENSITIVE_NAMES:
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(child_key): sanitize_event(child_value, str(child_key)) for child_key, child_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_event(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class AuditWriter:
    def __init__(self, path: Path, max_bytes: int, backups: int) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self.backups = backups

    def _rotate(self) -> None:
        oldest = Path(f"{self.path}.{self.backups}")
        oldest.unlink(missing_ok=True)
        for index in range(self.backups - 1, 0, -1):
            source = Path(f"{self.path}.{index}")
            if source.exists():
                source.replace(Path(f"{self.path}.{index + 1}"))
        if self.path.exists():
            self.path.replace(Path(f"{self.path}.1"))

    def write(self, event: Mapping[str, Any]) -> None:
        line = json.dumps(sanitize_event(event), separators=(",", ":"), sort_keys=True, ensure_ascii=False) + "\n"
        encoded = line.encode("utf-8")
        if len(encoded) > self.max_bytes:
            raise AuditError("audit record exceeds the configured file-size limit")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
            current_size = self.path.stat().st_size if self.path.exists() else 0
            if current_size and current_size + len(encoded) > self.max_bytes:
                self._rotate()
            descriptor = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o640)
            try:
                written = 0
                while written < len(encoded):
                    written += os.write(descriptor, encoded[written:])
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError as error:
            raise AuditError(f"cannot persist audit record: {error.strerror}") from error
