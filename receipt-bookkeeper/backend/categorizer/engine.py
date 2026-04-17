from typing import Optional
from ..ocr.models import LineItem
from .rules import VENDOR_RULES, KEYWORD_RULES

UNCLASSIFIED = "Unclassified"


def categorize(vendor: Optional[str], line_items: list[LineItem]) -> str:
    if vendor:
        vendor_lower = vendor.lower()
        for pattern, category in VENDOR_RULES.items():
            if pattern in vendor_lower:
                return category

    all_text = " ".join(item.description.lower() for item in line_items)
    for keyword, category in KEYWORD_RULES.items():
        if keyword in all_text:
            return category

    return UNCLASSIFIED
