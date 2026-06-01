from pydantic_settings import BaseSettings
from typing import Optional


class ModelConfig(BaseSettings):
    api_key: str
    base_url: str
    model: str
    enabled: bool = True
    supports_anthropic_format: bool = True  # Anthropic atau OpenAI format


class Settings(BaseSettings):
    port: int = 8080
    host: str = "0.0.0.0"
    request_timeout: int = 30
    max_retries: int = 1

    # Model 1: GLM
    glm_api_key: str = ""
    glm_base_url: str = "https://api.z.ai/api/anthropic"
    glm_model: str = "GLM-4.7"
    glm_enabled: bool = True

    # Model 2: DataByte
    databyte_api_key: str = ""
    databyte_base_url: str = "https://ai.databyte.co.id/anthropic/v1"
    databyte_model: str = "databyte-m1"
    databyte_enabled: bool = True

    # Model 3: Konektika (Kimi) - OpenAI format
    konektika_api_key: str = ""
    konektika_base_url: str = "https://konektika.web.id/v1"
    konektika_model: str = "kimi-pro"
    konektika_enabled: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def get_models(self) -> list[ModelConfig]:
        models = []

        if self.glm_api_key and self.glm_enabled:
            models.append(ModelConfig(
                api_key=self.glm_api_key,
                base_url=self.glm_base_url,
                model=self.glm_model,
                enabled=True,
                supports_anthropic_format=True
            ))

        if self.databyte_api_key and self.databyte_enabled:
            models.append(ModelConfig(
                api_key=self.databyte_api_key,
                base_url=self.databyte_base_url,
                model=self.databyte_model,
                enabled=True,
                supports_anthropic_format=True
            ))

        if self.konektika_api_key and self.konektika_enabled:
            models.append(ModelConfig(
                api_key=self.konektika_api_key,
                base_url=self.konektika_base_url,
                model=self.konektika_model,
                enabled=True,
                supports_anthropic_format=False  # OpenAI format
            ))

        return models


def load_settings() -> Settings:
    settings = Settings()

    models = settings.get_models()

    if not models:
        print("\n[WARNING] Semua API key kosong atau model dinonaktifkan!")
        print("Set至少 satu API key di .env untuk menjalankan proxy.\n")

    return settings