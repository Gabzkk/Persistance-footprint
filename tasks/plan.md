# Implementation Plan

1. Define configuration and telemetry contracts.
2. Test and implement Linux metric collection.
3. Test and implement rotating JSONL audit output.
4. Test and implement authenticated HTTPS delivery with bounded retry timing.
5. Add the service loop, hardened systemd unit, and explicit lifecycle scripts.
6. Execute the complete test, compile, and one-shot validation gates.
