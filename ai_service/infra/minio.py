from contextlib import AbstractAsyncContextManager
from typing import cast

import aioboto3
from botocore.config import Config
from pydantic import BaseModel, Field


class MinIOConfig(BaseModel):
    endpoint: str = Field(description="MinIO endpoint (host:port)")
    access_key: str = Field(description="Access key")
    secret_key: str = Field(description="Secret key")
    bucket: str = Field(description="Bucket name with profile photos")
    secure: bool = Field(default=False, description="Use HTTPS")

    @property
    def endpoint_url(self) -> str:
        scheme = "https" if self.secure else "http"
        return f"{scheme}://{self.endpoint}"


def provide_aioboto3_session() -> aioboto3.Session:
    return aioboto3.Session()


def create_s3_client(*, session: aioboto3.Session, config: MinIOConfig) -> AbstractAsyncContextManager[object]:
    return cast(
        "AbstractAsyncContextManager[object]",
        session.client(
            "s3",
            endpoint_url=config.endpoint_url,
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_key,
            region_name="us-east-1",
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        ),
    )
