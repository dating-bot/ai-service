from collections.abc import AsyncGenerator
from urllib.parse import quote, quote_plus

import aio_pika
from pydantic import BaseModel, Field


class RabbitMQConfig(BaseModel):
    host: str = Field(description="Host")
    port: int = Field(default=5672, description="Port")
    username: str = Field(description="Username")
    password: str = Field(description="Password")
    vhost: str = Field(default="/", description="Virtual host")

    @property
    def dsn(self) -> str:
        safe_password = quote_plus(self.password)
        path = "/" if self.vhost in ("", "/") else "/" + quote(self.vhost, safe="")
        return f"amqp://{self.username}:{safe_password}@{self.host}:{self.port}{path}"


async def provide_rabbitmq_connection(config: RabbitMQConfig) -> AsyncGenerator[aio_pika.abc.AbstractRobustConnection]:
    connection = await aio_pika.connect_robust(config.dsn)
    try:
        yield connection
    finally:
        await connection.close()
