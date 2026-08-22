from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class SpoolError(RuntimeError):
    """Raised when retry storage cannot be read or written."""


@dataclass(frozen=True)
class SpoolItem:
    path: Path
    event: dict[str, Any]


class SpoolQueue:
    def __init__(self, directory: Path, max_files: int) -> None:
        self.directory = directory
        self.max_files = max_files

    def paths(self) -> list[Path]:
        if not self.directory.exists():
            return []
        return sorted(self.directory.glob("*.json"))

    def _prune(self) -> None:
        paths = self.paths()
        for path in paths[: max(0, len(paths) - self.max_files)]:
            path.unlink(missing_ok=True)

    def enqueue(self, event: Mapping[str, Any]) -> Path:
        payload = json.dumps(event, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")
        name = f"{time.time_ns():020d}-{uuid.uuid4().hex}.json"
        temporary: Path | None = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o750)
            path = self.directory / name
            temporary = self.directory / f".{name}.tmp"
            descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o640)
            try:
                os.write(descriptor, payload)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            temporary.replace(path)
            self._prune()
            return path
        except OSError as error:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            raise SpoolError(f"cannot persist retry event: {error.strerror}") from error

    def peek(self) -> SpoolItem | None:
        paths = self.paths()
        if not paths:
            return None
        path = paths[0]
        try:
            event = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SpoolError(f"cannot read retry event {path.name}: {type(error).__name__}") from error
        if not isinstance(event, dict):
            raise SpoolError(f"retry event {path.name} is not a JSON object")
        return SpoolItem(path=path, event=event)

    def acknowledge(self, path: Path) -> None:
        try:
            resolved = path.resolve(strict=True)
            directory = self.directory.resolve(strict=True)
            if resolved.parent != directory or resolved.suffix != ".json":
                raise SpoolError("refusing to acknowledge a path outside the spool")
            resolved.unlink()
        except FileNotFoundError:
            return
        except OSError as error:
            raise SpoolError(f"cannot acknowledge retry event: {error.strerror}") from error
