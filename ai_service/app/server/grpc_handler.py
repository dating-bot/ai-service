from dataclasses import dataclass
from typing import final, override

from ai_service.app.server.utils.unary import unary
from gateway_api.v1 import gateway_pb2
from gateway_api.v1.gateway_grpc import GatewayServiceBase


@final
@dataclass(slots=True)
class GatewayServiceHandler(GatewayServiceBase):
    @override
    @unary
    async def Ping(self, request: gateway_pb2.PingRequest) -> gateway_pb2.PingResponse:
        del request
        return gateway_pb2.PingResponse(message="pong")
