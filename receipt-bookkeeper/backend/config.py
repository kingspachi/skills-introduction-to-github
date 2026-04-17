from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    google_docai_project_id: str = ""
    google_docai_location: str = "us"
    google_docai_processor_id: str = ""
    ocr_backend: Literal["google"] = "google"
    max_file_size_mb: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "application/pdf"}
