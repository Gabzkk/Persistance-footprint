import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from persistent_footprint.config import DeliveryConfig
from persistent_footprint.delivery import DeliveryError, TelemetryDelivery, retry_delay


class _CaptureHandler(BaseHTTPRequestHandler):
    body = b""
    authorization = ""

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        type(self).body = self.rfile.read(length)
        type(self).authorization = self.headers.get("Authorization", "")
        self.send_response(202)
        self.end_headers()

    def log_message(self, _format: str, *_args: object) -> None:
        return


class DeliveryTests(unittest.TestCase):
    def setUp(self) -> None:
        _CaptureHandler.body = b""
        _CaptureHandler.authorization = ""
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _CaptureHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_posts_json_with_bearer_token(self) -> None:
        endpoint = f"http://127.0.0.1:{self.server.server_port}/events"
        delivery = TelemetryDelivery(DeliveryConfig(endpoint=endpoint, timeout_seconds=2, token_env="TEST_AGENT_TOKEN"), environ={"TEST_AGENT_TOKEN": "secret-value"})

        status = delivery.send({"event": "telemetry_sampled", "value": 9})

        self.assertEqual(status, 202)
        self.assertEqual(json.loads(_CaptureHandler.body), {"event": "telemetry_sampled", "value": 9})
        self.assertEqual(_CaptureHandler.authorization, "Bearer secret-value")

    def test_rejects_payload_over_limit(self) -> None:
        endpoint = f"http://127.0.0.1:{self.server.server_port}/events"
        delivery = TelemetryDelivery(DeliveryConfig(endpoint=endpoint, max_payload_bytes=32))

        with self.assertRaisesRegex(DeliveryError, "payload"):
            delivery.send({"payload": "x" * 100})

    def test_retry_delay_is_exponential_and_capped(self) -> None:
        self.assertEqual(retry_delay(1, base_seconds=2, cap_seconds=30), 2)
        self.assertEqual(retry_delay(4, base_seconds=2, cap_seconds=30), 16)
        self.assertEqual(retry_delay(9, base_seconds=2, cap_seconds=30), 30)


if __name__ == "__main__":
    unittest.main()
