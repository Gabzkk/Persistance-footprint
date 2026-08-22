import tempfile
import unittest
from pathlib import Path

from persistent_footprint.metrics import CpuSnapshot, MetricsCollector, parse_cpu_line, parse_meminfo, parse_net_dev


class MetricsParserTests(unittest.TestCase):
    def test_cpu_percent_uses_delta_busy_over_delta_total(self) -> None:
        previous = CpuSnapshot(total=1_000, idle=700)
        current = CpuSnapshot(total=1_200, idle=800)

        self.assertEqual(current.percent_since(previous), 50.0)

    def test_parse_cpu_line_counts_idle_and_total(self) -> None:
        snapshot = parse_cpu_line("cpu  100 20 30 400 10 5 5 0 0 0")

        self.assertEqual(snapshot.total, 570)
        self.assertEqual(snapshot.idle, 410)

    def test_parse_meminfo_calculates_available_usage(self) -> None:
        values = parse_meminfo("MemTotal: 1000 kB\nMemAvailable: 250 kB\nSwapTotal: 100 kB\nSwapFree: 40 kB\n")

        self.assertEqual(values["memory_total_bytes"], 1_024_000)
        self.assertEqual(values["memory_used_bytes"], 768_000)
        self.assertEqual(values["memory_used_percent"], 75.0)
        self.assertEqual(values["swap_used_bytes"], 61_440)

    def test_parse_net_dev_excludes_loopback(self) -> None:
        text = "Inter-| Receive | Transmit\n lo: 5 0 0 0 0 0 0 0 7 0 0 0 0 0 0 0\n eth0: 100 2 0 0 0 0 0 0 200 3 0 0 0 0 0 0\n"

        values = parse_net_dev(text)

        self.assertEqual(values, {"network_rx_bytes": 100, "network_tx_bytes": 200})


class LiveMetricsTests(unittest.TestCase):
    def test_collect_returns_allowlisted_host_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            collector = MetricsCollector(disk_paths=(Path(directory),))
            metrics = collector.collect()

        self.assertIn("uptime_seconds", metrics)
        self.assertIn("memory_used_percent", metrics)
        self.assertIn("disk", metrics)
        self.assertNotIn("processes", metrics)


if __name__ == "__main__":
    unittest.main()
