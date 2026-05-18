from pydantic import BaseModel, Field


class GrpcServerConfig(BaseModel):
    host: str = Field(description="Host")
    port: int = Field(description="Port")
