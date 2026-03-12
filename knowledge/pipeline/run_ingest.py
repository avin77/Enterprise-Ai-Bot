"""
knowledge/pipeline/run_ingest.py
CLI: python -m knowledge.pipeline.run_ingest --pdf-dir data/pdfs/ --table voicebot_faqs --bucket voicebot-mvp-docs

Ingest PDFs: extract chunks → generate 384-dim embeddings → write to DynamoDB + upload to S3.
"""
from __future__ import annotations
import argparse
import datetime
import os
import struct
import boto3
from pathlib import Path
from knowledge.pipeline.ingest import extract_chunks_from_pdf

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def generate_embedding(text: str) -> list[float]:
    """Generate 384-dim embedding using all-MiniLM-L6-v2."""
    model = _get_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def _floats_to_bytes(floats: list[float]) -> bytes:
    """Pack float list as little-endian 32-bit floats (DynamoDB Binary)."""
    return struct.pack(f"<{len(floats)}f", *floats)


def build_dynamo_item(chunk: dict, embedding: list[float]) -> dict:
    """Build DynamoDB PutItem-ready dict for a FAQ chunk."""
    return {
        "chunk_id": {"S": chunk["chunk_id"]},
        "text": {"S": chunk["text"]},
        "source_doc": {"S": chunk["source_doc"]},
        "department": {"S": chunk["department"]},
        "page_ref": {"S": chunk.get("page_ref") or ""},
        "embedding": {"B": _floats_to_bytes(embedding)},
        "created_at": {"S": datetime.datetime.utcnow().isoformat() + "Z"},
    }


def upload_pdf_to_s3(pdf_path: str, bucket: str, region: str) -> str:
    """Upload PDF to S3 and return s3:// URI."""
    s3 = boto3.client("s3", region_name=region)
    key = f"pdfs/{Path(pdf_path).name}"
    s3.upload_file(pdf_path, bucket, key)
    uri = f"s3://{bucket}/{key}"
    print(f"  Uploaded: {uri}")
    return uri


def ingest_pdf(pdf_path: str, table: str, bucket: str, region: str) -> int:
    """
    Full ingest for one PDF: S3 upload → chunk extraction → embedding → DynamoDB write.
    Returns number of chunks written.
    """
    dynamo = boto3.client("dynamodb", region_name=region)
    upload_pdf_to_s3(pdf_path, bucket, region)
    chunks = extract_chunks_from_pdf(pdf_path)
    print(f"  Extracted {len(chunks)} chunks from {Path(pdf_path).name}")
    for i, chunk in enumerate(chunks):
        embedding = generate_embedding(chunk["text"])
        item = build_dynamo_item(chunk, embedding)
        dynamo.put_item(TableName=table, Item=item)
        if (i + 1) % 10 == 0:
            print(f"    Written {i + 1}/{len(chunks)} chunks...")
    print(f"  Done: {len(chunks)} chunks written to {table}")
    return len(chunks)


def main():
    parser = argparse.ArgumentParser(description="Ingest PDFs to DynamoDB + S3")
    parser.add_argument("--pdf-dir", default="data/pdfs", help="Directory containing PDFs")
    parser.add_argument("--table", default="voicebot_faqs", help="DynamoDB table name")
    parser.add_argument("--bucket", default="voicebot-mvp-docs", help="S3 bucket name")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "ap-south-1"))
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    pdfs = list(pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {pdf_dir}")
        return

    print(f"Found {len(pdfs)} PDFs to ingest:")
    total_chunks = 0
    for pdf in pdfs:
        print(f"\nIngesting: {pdf.name}")
        total_chunks += ingest_pdf(str(pdf), args.table, args.bucket, args.region)

    print(f"\nIngestion complete: {total_chunks} total chunks across {len(pdfs)} PDFs")


if __name__ == "__main__":
    main()
