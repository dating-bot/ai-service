import os
from time import sleep

from prometheus_client import CollectorRegistry, multiprocess, start_http_server


def _build_registry() -> CollectorRegistry:
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return registry


def main() -> None:
    port = int(os.getenv("AI_SERVICE_METRICS_PORT", "9109"))
    start_http_server(port=port, registry=_build_registry())
    while True:
        sleep(3600)


if __name__ == "__main__":
    main()
