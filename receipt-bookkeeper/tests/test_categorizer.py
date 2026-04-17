import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from backend.ocr.models import LineItem
from backend.categorizer.engine import categorize


@pytest.mark.parametrize("vendor,items,expected", [
    ("McDonald's Restaurant", [], "Meals & Entertainment"),
    ("Tim Hortons #1234", [], "Meals & Entertainment"),
    ("Starbucks Coffee", [], "Meals & Entertainment"),
    ("Uber Technologies Inc", [], "Travel & Transport"),
    ("Petro-Canada", [], "Travel & Transport"),
    ("BC Ferries", [], "Travel & Transport"),
    ("Staples Canada", [], "Office Supplies"),
    ("Best Buy Canada", [], "Office Supplies"),
    ("TELUS Communications", [], "Utilities & Software"),
    ("Shaw Communications", [], "Utilities & Software"),
    ("Microsoft Corporation", [], "Utilities & Software"),
    # Keyword fallback when vendor not in rules
    ("Unknown Store", [LineItem(description="coffee and muffin")], "Meals & Entertainment"),
    ("Random Vendor", [LineItem(description="parking fee downtown")], "Travel & Transport"),
    ("Some Shop", [LineItem(description="printer paper and ink toner")], "Office Supplies"),
    ("Tech Corp", [LineItem(description="cloud hosting subscription")], "Utilities & Software"),
    # Unclassified
    ("Unknown Vendor", [], "Unclassified"),
    (None, [], "Unclassified"),
    (None, [LineItem(description="miscellaneous items")], "Unclassified"),
])
def test_categorize(vendor, items, expected):
    assert categorize(vendor, items) == expected


def test_vendor_substring_match():
    assert categorize("A&W Canada #42", []) == "Meals & Entertainment"
    assert categorize("Shell Gas Station", []) == "Travel & Transport"


def test_keyword_takes_first_match():
    items = [LineItem(description="coffee subscription")]
    result = categorize("Unknown", items)
    assert result in ("Meals & Entertainment", "Utilities & Software")
