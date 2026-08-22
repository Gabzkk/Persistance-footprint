import json
import tempfile
import unittest
from pathlib import Path

from persistent_footprint.spool import SpoolQueue


class SpoolQueueTests(unittest.TestCase):
    def test_enqueue_and_peek_preserve_fifo_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            queue = SpoolQueue(Path(directory), max_files=5)
            first = queue.enqueue({"sequence": 1})
            queue.enqueue({"sequence": 2})

            item = queue.peek()

            self.assertIsNotNone(item)
            self.assertEqual(item.path, first)
            self.assertEqual(item.event, {"sequence": 1})

    def test_enqueue_prunes_oldest_files_at_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            queue = SpoolQueue(Path(directory), max_files=2)
            queue.enqueue({"sequence": 1})
            queue.enqueue({"sequence": 2})
            queue.enqueue({"sequence": 3})

            sequences = [json.loads(path.read_text())["sequence"] for path in queue.paths()]

        self.assertEqual(sequences, [2, 3])

    def test_acknowledge_removes_only_selected_item(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            queue = SpoolQueue(Path(directory), max_files=5)
            first = queue.enqueue({"sequence": 1})
            queue.enqueue({"sequence": 2})

            queue.acknowledge(first)

            self.assertEqual(len(queue.paths()), 1)


if __name__ == "__main__":
    unittest.main()
