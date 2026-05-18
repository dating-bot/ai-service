from pydantic import BaseModel, Field


class AIConfig(BaseModel):
    nsfw_threshold: float = Field(default=0.7)
    embedding_size: int = Field(default=1536)
    low_confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
