import json
import tempfile
import unittest
from pathlib import Path

from persistent_footprint.audit import AuditWriter, sanitize_event


class AuditTests(unittest.TestCase):
    def test_sanitize_event_redacts_secret_named_fields_recursively(self) -> None:
        event = {"token": "top-secret", "nested": {"password": "hidden", "value": 7}}

        sanitized = sanitize_event(event)

        self.assertEqual(sanitized["token"], "[REDACTED]")
        self.assertEqual(sanitized["nested"]["password"], "[REDACTED]")
        self.assertEqual(sanitized["nested"]["value"], 7)

    def test_writer_emits_valid_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            writer = AuditWriter(path, max_bytes=1024, backups=2)
            writer.write({"event": "telemetry_sampled", "value": 1})

            record = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(record["event"], "telemetry_sampled")
        self.assertEqual(record["value"], 1)

    def test_writer_rotates_before_exceeding_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            writer = AuditWriter(path, max_bytes=120, backups=2)
            writer.write({"event": "a", "payload": "x" * 60})
            writer.write({"event": "b", "payload": "y" * 60})

            self.assertTrue(path.exists())
            self.assertTrue(path.with_suffix(".jsonl.1").exists())
            self.assertLessEqual(path.stat().st_size, 120)


if __name__ == "__main__":
    unittest.main()
