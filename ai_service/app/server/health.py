from typing import cast, override

from grpclib.const import Status
from grpclib.health.check import ServiceCheck
from grpclib.health.service import OVERALL, Health
from grpclib.health.v1.health_pb2 import HealthCheckRequest, HealthCheckResponse
from grpclib.server import Stream


async def _health_check() -> bool:
    return True


class LoggingHealth(Health):
    @override
    async def Check(self, stream: Stream[HealthCheckRequest, HealthCheckResponse]) -> None:
        request = await stream.recv_message()
        if request is None:
            return

        checks = self._checks.get(request.service)
        if checks is None:
            await stream.send_trailing_metadata(status=Status.NOT_FOUND)
            return

        status = HealthCheckResponse.ServingStatus.SERVING
        for check in checks:
            result: bool | None = cast("bool | None", await check()) if callable(check) else True
            if result is False:
                status = HealthCheckResponse.ServingStatus.NOT_SERVING
                break
            if result is None:
                status = HealthCheckResponse.ServingStatus.UNKNOWN

        await stream.send_message(HealthCheckResponse(status=status))


def create_health_service() -> LoggingHealth:
    health_check = ServiceCheck(_health_check, check_ttl=30.0, check_timeout=5.0)
    return LoggingHealth({OVERALL: [health_check]})
