"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 0, '', 'gateway_api/v1/gateway.proto')
_sym_db = _symbol_database.Default()
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1cgateway_api/v1/gateway.proto\x12\x0egateway_api.v1"\r\n\x0bPingRequest"\x1f\n\x0cPingResponse\x12\x0f\n\x07message\x18\x01 \x01(\t2S\n\x0eGatewayService\x12A\n\x04Ping\x12\x1b.gateway_api.v1.PingRequest\x1a\x1c.gateway_api.v1.PingResponseb\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'gateway_api.v1.gateway_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_PINGREQUEST']._serialized_start = 48
    _globals['_PINGREQUEST']._serialized_end = 61
    _globals['_PINGRESPONSE']._serialized_start = 63
    _globals['_PINGRESPONSE']._serialized_end = 94
    _globals['_GATEWAYSERVICE']._serialized_start = 96
    _globals['_GATEWAYSERVICE']._serialized_end = 179