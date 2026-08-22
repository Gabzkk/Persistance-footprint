import json
import tempfile
import unittest
from pathlib import Path

from persistent_footprint.agent import RecoveryAgent
from persistent_footprint.audit import AuditWriter
from persistent_footprint.delivery import DeliveryError
from persistent_footprint.spool import SpoolQueue


class _Collector:
    def collect(self) -> dict:
        return {"cpu_used_percent": 12.5}


class _Delivery:
    enabled = True

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.events: list[dict] = []

    def send(self, event: dict) -> int:
        self.events.append(event)
        if self.fail:
            raise DeliveryError("offline")
        return 202


class RecoveryAgentTests(unittest.TestCase):
    def test_run_once_audits_and_delivers_sample(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            delivery = _Delivery()
            agent = RecoveryAgent(
                collector=_Collector(),
                audit=AuditWriter(root / "audit.jsonl", 4096, 2),
                delivery=delivery,
                spool=SpoolQueue(root / "spool", 10),
            )

            outcome = agent.run_once()
            record = json.loads((root / "audit.jsonl").read_text())

        self.assertEqual(outcome, "delivered")
        self.assertEqual(record["event"], "telemetry_sampled")
        self.assertEqual(len(delivery.events), 1)

    def test_run_once_spools_sample_when_delivery_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            agent = RecoveryAgent(
                collector=_Collector(),
                audit=AuditWriter(root / "audit.jsonl", 4096, 2),
                delivery=_Delivery(fail=True),
                spool=SpoolQueue(root / "spool", 10),
            )

            outcome = agent.run_once()

            self.assertEqual(outcome, "spooled")
            self.assertEqual(len(agent.spool.paths()), 1)


if __name__ == "__main__":
    unittest.main()
