"""Extract plain text from uploaded resume / job description files."""
import io
import re
from pathlib import Path

from config_loader import load_config


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(filename: str, data: bytes) -> str:
    """Return cleaned text from a PDF, DOCX or TXT file given as bytes."""
    ext = Path(filename).suffix.lower()
    allowed = load_config()["input"]["allowed_extensions"]
    if ext not in allowed:
        raise ValueError(f"Unsupported file type '{ext}'. Allowed: {', '.join(allowed)}")

    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    elif ext == ".docx":
        from docx import Document
        doc = Document(io.BytesIO(data))
        text = "\n".join(p.text for p in doc.paragraphs)
    else:
        text = data.decode("utf-8", errors="ignore")

    text = clean_text(text)
    if not text:
        raise ValueError("No readable text found in the file (scanned PDFs are not supported).")
    return text


def truncate(text: str) -> str:
    limit = load_config()["input"]["max_chars"]
    return text[:limit]
