from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
from pathlib import Path

from .agent import build_agent
from .audit import AuditError
from .config import ConfigError, load_config
from .delivery import DeliveryError, retry_delay
from .metrics import MetricsError
from .spool import SpoolError


def _log(event: str, level: str = "info", **fields: object) -> None:
    record = {"event": event, "level": level, **fields}
    print(json.dumps(record, separators=(",", ":"), sort_keys=True), flush=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transparent Linux recovery telemetry agent")
    parser.add_argument("--config", type=Path, required=True, help="path to the JSON configuration")
    parser.add_argument("--once", action="store_true", help="collect one sample and exit")
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = load_config(args.config)
        agent = build_agent(config)
    except ConfigError as error:
        _log("configuration_rejected", "error", error=str(error))
        return 2

    stop = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    _log("agent_started", interval_seconds=config.interval_seconds, delivery_enabled=agent.delivery.enabled)
    attempt = 0
    while not stop.is_set():
        try:
            outcome = agent.run_once()
            _log("collection_cycle_completed", outcome=outcome)
            attempt = attempt + 1 if outcome == "spooled" else 0
        except (AuditError, MetricsError, SpoolError, DeliveryError) as error:
            attempt += 1
            _log("collection_cycle_failed", "error", error_type=type(error).__name__)
        if args.once:
            return 0 if attempt == 0 else 1
        delay = retry_delay(attempt, cap_seconds=config.interval_seconds) if attempt else config.interval_seconds
        stop.wait(delay)
    _log("agent_stopped")
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
