from abc import ABC, abstractmethod
from .models import ReceiptData


class OCRBackend(ABC):
    @abstractmethod
    async def process(self, file_bytes: bytes, mime_type: str) -> ReceiptData:
        """Process raw file bytes and return structured receipt data."""
        ...
