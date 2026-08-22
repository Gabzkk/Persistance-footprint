from __future__ import annotations

import os
import platform
import shutil
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class MetricsError(RuntimeError):
    """Raised when mandatory Linux telemetry cannot be collected."""


@dataclass(frozen=True)
class CpuSnapshot:
    total: int
    idle: int

    def percent_since(self, previous: "CpuSnapshot") -> float | None:
        total_delta = self.total - previous.total
        idle_delta = self.idle - previous.idle
        if total_delta <= 0:
            return None
        busy = max(0, total_delta - idle_delta)
        return round(min(100.0, busy * 100.0 / total_delta), 2)


def parse_cpu_line(line: str) -> CpuSnapshot:
    fields = line.split()
    if not fields or fields[0] != "cpu" or len(fields) < 5:
        raise MetricsError("/proc/stat does not contain a valid aggregate CPU line")
    try:
        counters = [int(value) for value in fields[1:]]
    except ValueError as error:
        raise MetricsError("/proc/stat contains a non-numeric CPU counter") from error
    idle = counters[3] + (counters[4] if len(counters) > 4 else 0)
    return CpuSnapshot(total=sum(counters), idle=idle)


def parse_meminfo(text: str) -> dict[str, int | float]:
    values: dict[str, int] = {}
    for line in text.splitlines():
        name, separator, raw = line.partition(":")
        if not separator:
            continue
        token = raw.strip().split()[0]
        if token.isdigit():
            values[name] = int(token) * 1024
    if "MemTotal" not in values or "MemAvailable" not in values:
        raise MetricsError("/proc/meminfo is missing MemTotal or MemAvailable")
    total = values["MemTotal"]
    available = values["MemAvailable"]
    used = max(0, total - available)
    swap_total = values.get("SwapTotal", 0)
    swap_used = max(0, swap_total - values.get("SwapFree", 0))
    return {
        "memory_total_bytes": total,
        "memory_available_bytes": available,
        "memory_used_bytes": used,
        "memory_used_percent": round(used * 100.0 / total, 2) if total else 0.0,
        "swap_total_bytes": swap_total,
        "swap_used_bytes": swap_used,
    }


def parse_net_dev(text: str) -> dict[str, int]:
    received = 0
    transmitted = 0
    for line in text.splitlines():
        if ":" not in line:
            continue
        interface, raw = line.split(":", 1)
        if interface.strip() == "lo":
            continue
        fields = raw.split()
        if len(fields) < 9:
            raise MetricsError("/proc/net/dev contains an incomplete interface row")
        try:
            received += int(fields[0])
            transmitted += int(fields[8])
        except ValueError as error:
            raise MetricsError("/proc/net/dev contains a non-numeric counter") from error
    return {"network_rx_bytes": received, "network_tx_bytes": transmitted}


class MetricsCollector:
    def __init__(self, disk_paths: tuple[Path, ...] = (Path("/"),)) -> None:
        self.disk_paths = disk_paths
        self._previous_cpu: CpuSnapshot | None = None

    @staticmethod
    def _read(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError as error:
            raise MetricsError(f"cannot read {path}: {error.strerror}") from error

    def collect(self) -> dict[str, Any]:
        cpu = parse_cpu_line(self._read(Path("/proc/stat")).splitlines()[0])
        cpu_percent = cpu.percent_since(self._previous_cpu) if self._previous_cpu else None
        self._previous_cpu = cpu
        memory = parse_meminfo(self._read(Path("/proc/meminfo")))
        network = parse_net_dev(self._read(Path("/proc/net/dev")))
        try:
            uptime = float(self._read(Path("/proc/uptime")).split()[0])
            load_1m, load_5m, load_15m = os.getloadavg()
        except (ValueError, OSError, IndexError) as error:
            raise MetricsError("cannot parse Linux uptime or load average") from error

        disks: list[dict[str, int | float | str]] = []
        for path in self.disk_paths:
            try:
                usage = shutil.disk_usage(path)
            except OSError as error:
                raise MetricsError(f"cannot inspect disk path {path}: {error.strerror}") from error
            disks.append({
                "path": str(path),
                "total_bytes": usage.total,
                "used_bytes": usage.used,
                "free_bytes": usage.free,
                "used_percent": round(usage.used * 100.0 / usage.total, 2) if usage.total else 0.0,
            })

        return {
            "cpu_used_percent": cpu_percent,
            **memory,
            **network,
            "load_1m": round(load_1m, 3),
            "load_5m": round(load_5m, 3),
            "load_15m": round(load_15m, 3),
            "uptime_seconds": round(uptime, 2),
            "disk": disks,
            "host": {
                "hostname": socket.gethostname(),
                "machine": platform.machine(),
                "kernel": platform.release(),
            },
            "collected_monotonic_ns": time.monotonic_ns(),
        }
