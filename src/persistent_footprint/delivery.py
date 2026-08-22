from __future__ import annotations

import json
import os
import ssl
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import DeliveryConfig


class DeliveryError(RuntimeError):
    """Raised when a telemetry batch cannot be delivered safely."""


def retry_delay(attempt: int, base_seconds: float = 2, cap_seconds: float = 300) -> float:
    if attempt < 1:
        raise ValueError("attempt must be at least 1")
    return min(cap_seconds, base_seconds * (2 ** (attempt - 1)))


class TelemetryDelivery:
    def __init__(self, config: DeliveryConfig, environ: Mapping[str, str] | None = None) -> None:
        self.config = config
        self.environ = os.environ if environ is None else environ

    @property
    def enabled(self) -> bool:
        return self.config.endpoint is not None

    def send(self, event: Mapping[str, Any]) -> int:
        if not self.config.endpoint:
            raise DeliveryError("delivery endpoint is not configured")
        payload = json.dumps(event, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")
        if len(payload) > self.config.max_payload_bytes:
            raise DeliveryError("telemetry payload exceeds the configured limit")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "persistent-footprint/1.0",
        }
        token = self.environ.get(self.config.token_env)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(self.config.endpoint, data=payload, headers=headers, method="POST")
        context = ssl.create_default_context(cafile=str(self.config.ca_file) if self.config.ca_file else None)
        try:
            with urlopen(request, timeout=self.config.timeout_seconds, context=context) as response:
                status = response.status
                if status < 200 or status >= 300:
                    raise DeliveryError(f"collector returned HTTP {status}")
                return status
        except HTTPError as error:
            raise DeliveryError(f"collector returned HTTP {error.code}") from error
        except (URLError, TimeoutError, OSError) as error:
            reason = getattr(error, "reason", error)
            raise DeliveryError(f"collector connection failed: {type(reason).__name__}") from error
