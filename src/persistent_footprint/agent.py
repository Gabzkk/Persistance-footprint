from __future__ import annotations

import socket
import uuid
from datetime import UTC, datetime
from typing import Protocol

from .audit import AuditWriter
from .delivery import DeliveryError, TelemetryDelivery
from .metrics import MetricsCollector
from .spool import SpoolQueue


class Collector(Protocol):
    def collect(self) -> dict: ...


class Delivery(Protocol):
    enabled: bool

    def send(self, event: dict) -> int: ...


class RecoveryAgent:
    def __init__(
        self,
        collector: Collector,
        audit: AuditWriter,
        delivery: Delivery,
        spool: SpoolQueue,
    ) -> None:
        self.collector = collector
        self.audit = audit
        self.delivery = delivery
        self.spool = spool

    @staticmethod
    def _event(metrics: dict) -> dict:
        return {
            "schema_version": 1,
            "event": "telemetry_sampled",
            "correlation_id": str(uuid.uuid4()),
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "host_id": socket.gethostname(),
            "metrics": metrics,
        }

    def flush_spool(self) -> int:
        delivered = 0
        while self.delivery.enabled:
            item = self.spool.peek()
            if item is None:
                break
            self.delivery.send(item.event)
            self.spool.acknowledge(item.path)
            delivered += 1
        return delivered

    def run_once(self) -> str:
        event = self._event(self.collector.collect())
        self.audit.write(event)
        if not self.delivery.enabled:
            return "local_only"
        try:
            self.flush_spool()
            self.delivery.send(event)
            return "delivered"
        except DeliveryError as error:
            self.spool.enqueue(event)
            self.audit.write({
                "schema_version": 1,
                "event": "delivery_deferred",
                "correlation_id": event["correlation_id"],
                "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
                "error_type": type(error).__name__,
            })
            return "spooled"


def build_agent(config) -> RecoveryAgent:
    return RecoveryAgent(
        collector=MetricsCollector(config.disk_paths),
        audit=AuditWriter(config.audit.path, config.audit.max_bytes, config.audit.backups),
        delivery=TelemetryDelivery(config.delivery),
        spool=SpoolQueue(config.spool.directory, config.spool.max_files),
    )
