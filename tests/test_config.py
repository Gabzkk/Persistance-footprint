import json
import tempfile
import unittest
from pathlib import Path

from persistent_footprint.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def write_config(self, payload: dict) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "config.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_loads_safe_defaults(self) -> None:
        config = load_config(self.write_config({}))

        self.assertEqual(config.interval_seconds, 60.0)
        self.assertEqual(config.audit.max_bytes, 10 * 1024 * 1024)
        self.assertIsNone(config.delivery.endpoint)

    def test_rejects_cleartext_remote_endpoint(self) -> None:
        path = self.write_config({"delivery": {"endpoint": "http://collector.example/api"}})

        with self.assertRaisesRegex(ConfigError, "HTTPS"):
            load_config(path)

    def test_allows_http_only_for_loopback_integration_testing(self) -> None:
        path = self.write_config({"delivery": {"endpoint": "http://127.0.0.1:8080/events"}})

        config = load_config(path)

        self.assertEqual(config.delivery.endpoint, "http://127.0.0.1:8080/events")

    def test_rejects_sub_second_sampling(self) -> None:
        with self.assertRaisesRegex(ConfigError, "interval_seconds"):
            load_config(self.write_config({"interval_seconds": 0.1}))

    def test_rejects_unknown_fields(self) -> None:
        with self.assertRaisesRegex(ConfigError, "unknown configuration field"):
            load_config(self.write_config({"command": "whoami"}))


if __name__ == "__main__":
    unittest.main()
