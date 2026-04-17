from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import settings, ALLOWED_MIME_TYPES
from .ocr.models import ExportRow, derive_gst
from .ocr.google_docai import GoogleDocAIBackend
from .categorizer.engine import categorize
from .export.excel import build_xlsx
from .export.csv_export import build_csv

app = FastAPI(title="Receipt Bookkeeper")

_ocr_backend: GoogleDocAIBackend | None = None


def get_ocr_backend() -> GoogleDocAIBackend:
    global _ocr_backend
    if _ocr_backend is None:
        if not settings.google_docai_project_id or not settings.google_docai_processor_id:
            raise HTTPException(
                status_code=503,
                detail="OCR backend not configured. Set GOOGLE_DOCAI_PROJECT_ID and GOOGLE_DOCAI_PROCESSOR_ID.",
            )
        _ocr_backend = GoogleDocAIBackend(
            project_id=settings.google_docai_project_id,
            location=settings.google_docai_location,
            processor_id=settings.google_docai_processor_id,
        )
    return _ocr_backend


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/receipts/upload", response_model=list[ExportRow])
async def upload_receipts(files: list[UploadFile] = File(...)):
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    results: list[ExportRow] = []

    for upload in files:
        if upload.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{upload.content_type}'. Allowed: JPEG, PNG, PDF.",
            )

        file_bytes = await upload.read()
        if len(file_bytes) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File '{upload.filename}' exceeds {settings.max_file_size_mb} MB limit.",
            )

        backend = get_ocr_backend()
        receipt = await backend.process(file_bytes, upload.content_type)
        receipt = derive_gst(receipt)

        category = categorize(receipt.vendor_name, receipt.line_items)
        description = ", ".join(
            item.description for item in receipt.line_items[:5]
        ) or "See receipt"

        results.append(ExportRow(
            date=str(receipt.transaction_date) if receipt.transaction_date else None,
            category=category,
            description=description,
            vendor=receipt.vendor_name,
            gst=receipt.gst_amount,
            total=receipt.total,
            base_amount=receipt.subtotal,
        ))

    return results


@app.post("/api/receipts/export/xlsx")
async def export_xlsx(rows: list[ExportRow]):
    xlsx_bytes = build_xlsx(rows)
    return StreamingResponse(
        BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=receipts.xlsx"},
    )


@app.post("/api/receipts/export/csv")
async def export_csv(rows: list[ExportRow]):
    csv_text = build_csv(rows)
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=receipts.csv"},
    )


# Serve frontend static files — must be last so API routes take priority
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="static")
