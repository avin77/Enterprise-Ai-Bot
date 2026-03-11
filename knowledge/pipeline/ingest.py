# knowledge/pipeline/ingest.py
"""
PDF text extraction and chunking for DynamoDB FAQ ingestion.
Chunk target: ~300 words (~400 tokens at 1.3 tokens/word)
Overlap: ~40 words (~50 tokens)
"""
from __future__ import annotations

import re
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    pdfplumber = None  # type: ignore

_DEPT_MAP = {
    "permit": "planning", "zoning": "planning", "building": "planning",
    "tax": "finance", "payment": "finance", "vendor": "finance", "budget": "finance",
    "election": "elections", "voter": "elections",
    "emergency": "emergency", "flood": "emergency",
    "court": "courts", "fee": "courts",
    "road": "public-works", "traffic": "public-works", "pothole": "public-works",
    "recycl": "utilities", "waste": "utilities", "water": "utilities", "trash": "utilities",
    "park": "parks", "recreation": "parks",
    "sheriff": "sheriff", "police": "sheriff",
    "hr": "hr", "employee": "hr", "benefit": "hr",
    "snap": "human-services", "food": "human-services", "senior": "human-services",
}


def _infer_department(filename: str) -> str:
    lower = filename.lower()
    for keyword, dept in _DEPT_MAP.items():
        if keyword in lower:
            return dept
    return "general"


def extract_chunks_from_pdf(
    pdf_path: str,
    chunk_words: int = 300,
    overlap_words: int = 40,
) -> list[dict]:
    """
    Extract text from PDF and split into overlapping chunks.
    Returns list of dicts with: text, source_doc, chunk_id, department.
    All required RAG-01 metadata fields included.

    Args:
        pdf_path: path to PDF file
        chunk_words: target words per chunk (default 300 words ~400 tokens)
        overlap_words: word overlap between chunks (default 40 words ~50 tokens)

    Returns:
        list of dicts with keys: text, source_doc, chunk_id, department, page_ref
    """
    if pdfplumber is None:
        raise ImportError("pdfplumber required: pip install pdfplumber")

    source_doc = Path(pdf_path).name
    department = _infer_department(source_doc)

    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    full_text = re.sub(r"\s+", " ", full_text).strip()
    words = full_text.split()

    chunks = []
    i = 0
    while i < len(words):
        chunk_slice = words[i: i + chunk_words]
        if len(chunk_slice) >= 20:  # skip tiny trailing fragments
            chunk_text = " ".join(chunk_slice)
            chunk_id = f"{source_doc}:chunk:{len(chunks)}"
            chunks.append({
                "text": chunk_text,
                "source_doc": source_doc,
                "chunk_id": chunk_id,
                "department": department,
                "page_ref": None,  # Phase 1: no page ref; Phase 4 populates this
            })
        i += chunk_words - overlap_words

    return chunks
