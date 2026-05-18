import asyncio
import signal

import grpclib.server
import structlog

from ai_service import infra
from ai_service.app.consumers.events_consumer import EventsConsumer
from ai_service.app.server import di
from ai_service.app.server.grpc_handler import GatewayServiceHandler
from ai_service.app.server.health import create_health_service
from ai_service.app.server.utils.logger import configure_logger
from ai_service.infra.tracing import setup_tracing

log = structlog.stdlib.get_logger("ai_service.server")


async def run_grpc_server(handler: GatewayServiceHandler, config: infra.GrpcServerConfig) -> None:
    server = grpclib.server.Server([handler, create_health_service()])
    await server.start(config.host, config.port)
    log.info("gRPC server started", host=config.host, port=config.port)

    try:
        await server.wait_closed()
    except asyncio.CancelledError:
        log.info("gRPC server cancelled, shutting down")
        server.close()
        await server.wait_closed()


async def main() -> None:
    config = await di.container.get(infra.GlobalConfig)

    configure_logger(json_mode=False, log_level="DEBUG" if config.debug else "INFO")
    setup_tracing(service_name="ai-service")
    log.info("Starting ai-service")

    grpc_handler_instance = await di.container.get(GatewayServiceHandler)
    events_consumer = await di.container.get(EventsConsumer)
    grpc_config = await di.container.get(infra.GrpcServerConfig)

    shutdown_event = asyncio.Event()

    def signal_handler() -> None:
        log.info("Shutdown signal received, stopping server")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    grpc_task = asyncio.create_task(run_grpc_server(grpc_handler_instance, grpc_config))
    consumer_task = asyncio.create_task(events_consumer.run())
    log.info("gRPC server task started")
    log.info("Events consumer task started")

    try:
        _ = await shutdown_event.wait()
    except KeyboardInterrupt:
        log.info("Keyboard interrupt received")
    finally:
        log.info("Stopping server")
        _ = grpc_task.cancel()
        await events_consumer.stop()
        _ = await asyncio.gather(grpc_task, consumer_task, return_exceptions=True)
        await di.container.close()
        log.info("Server stopped")


if __name__ == "__main__":
    asyncio.run(main())
