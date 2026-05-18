from pydantic import BaseModel, Field


class OpenAIConfig(BaseModel):
    enabled: bool = Field(default=False)
    api_key: str = Field(default="")
    provider: str = Field(default="openrouter")
    model: str = Field(default="openai/gpt-4o-mini")
    bio_model: str = Field(default="")
    nsfw_model: str = Field(default="openai/gpt-4.1-mini")
    embedding_model: str = Field(default="openai/text-embedding-3-small")
    embedding_dimensions: int = Field(default=1536)
    base_url: str = Field(default="https://openrouter.ai/api/v1")
    app_name: str = Field(default="dating-bot-ai-service")
    site_url: str = Field(default="")
    timeout_seconds: int = Field(default=15)
    circuit_breaker_enabled: bool = Field(default=True)
    circuit_breaker_failure_threshold: int = Field(default=5, ge=1)
    circuit_breaker_recovery_timeout_seconds: int = Field(default=30, ge=1)
    circuit_breaker_half_open_success_threshold: int = Field(default=2, ge=1)

    @property
    def resolved_bio_model(self) -> str:
        if self.bio_model:
            return self.bio_model
        return self.model

    @property
    def is_openrouter(self) -> bool:
        if self.provider.lower() == "openrouter":
            return True
        return "openrouter.ai" in self.base_url.lower()

    def request_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self.api_key}",
        }
        if self.is_openrouter:
            headers["X-Title"] = self.app_name
            if self.site_url:
                headers["HTTP-Referer"] = self.site_url
        return headers
