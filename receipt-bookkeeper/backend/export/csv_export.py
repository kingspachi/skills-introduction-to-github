import csv
from io import StringIO
from ..ocr.models import ExportRow

FIELDNAMES = [
    "date",
    "category",
    "description",
    "vendor",
    "gst",
    "total_incl_gst",
    "base_amount",
]


def build_csv(rows: list[ExportRow]) -> str:
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=FIELDNAMES)
    writer.writeheader()
    for row in rows:
        writer.writerow({
            "date": str(row.date) if row.date else "",
            "category": row.category,
            "description": row.description,
            "vendor": row.vendor or "",
            "gst": str(row.gst) if row.gst is not None else "",
            "total_incl_gst": str(row.total) if row.total is not None else "",
            "base_amount": str(row.base_amount) if row.base_amount is not None else "",
        })
    return buf.getvalue()
