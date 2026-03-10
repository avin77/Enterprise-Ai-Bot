#!/usr/bin/env python
"""
Load sample_faqs.json into DynamoDB voicebot-faq-knowledge table.

Usage:
    python knowledge/scripts/load_faqs.py
    python knowledge/scripts/load_faqs.py --table voicebot-faq-knowledge --region ap-south-1
    python knowledge/scripts/load_faqs.py --dry-run  (print items without writing)

Requires: AWS credentials configured (IAM role or ~/.aws/credentials)
Table must exist: aws dynamodb create-table --cli-input-json file://infra/dynamo_faq.json
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def load_faqs_to_dynamo(
    table_name: str,
    region: str,
    faq_path: str,
    dry_run: bool = False,
) -> int:
    """Load FAQs from JSON file into DynamoDB. Returns count of items written."""
    import boto3
    from datetime import datetime, timezone

    faq_data = json.loads(Path(faq_path).read_text())
    dynamo = boto3.client("dynamodb", region_name=region)

    items_written = 0
    batch = []

    for entry in faq_data:
        item = {
            "PutRequest": {
                "Item": {
                    "department":  {"S": entry.get("department", "general")},
                    "chunk_id":    {"S": entry.get("chunk_id", f"faq:{items_written}")},
                    "text":        {"S": entry.get("answer", "")[:4000]},
                    "source_doc":  {"S": entry.get("source_doc", "sample_faqs.json")},
                    "created_at":  {"S": datetime.now(timezone.utc).isoformat()},
                }
            }
        }
        # Note: embedding not set here — use knowledge/pipeline/embed.py for full ingest
        batch.append(item)

        if len(batch) == 25:  # DynamoDB BatchWriteItem limit
            if not dry_run:
                dynamo.batch_write_item(RequestItems={table_name: batch})
                print(f"  Wrote batch of {len(batch)} items")
            else:
                print(f"  [DRY RUN] Would write batch of {len(batch)} items")
            items_written += len(batch)
            batch = []

    # Write remaining items
    if batch:
        if not dry_run:
            dynamo.batch_write_item(RequestItems={table_name: batch})
            print(f"  Wrote final batch of {len(batch)} items")
        else:
            print(f"  [DRY RUN] Would write final batch of {len(batch)} items")
        items_written += len(batch)

    return items_written


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load FAQ data into DynamoDB")
    parser.add_argument("--table", default=os.getenv("KNOWLEDGE_TABLE", "voicebot-faq-knowledge"))
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "ap-south-1"))
    parser.add_argument("--faq-path", default="knowledge/data/local/sample_faqs.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"Loading FAQs from {args.faq_path} -> {args.table} ({args.region})")
    count = load_faqs_to_dynamo(args.table, args.region, args.faq_path, args.dry_run)
    print(f"Done. Items {'would be ' if args.dry_run else ''}written: {count}")
