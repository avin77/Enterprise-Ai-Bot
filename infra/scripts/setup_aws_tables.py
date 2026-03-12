"""
infra/scripts/setup_aws_tables.py
Creates DynamoDB tables + S3 bucket required for Phase 01.
Run ONCE before ingesting PDFs.

Usage:
    python infra/scripts/setup_aws_tables.py --region ap-south-1
"""
import argparse
import boto3
from botocore.exceptions import ClientError


def create_faqs_table(dynamo, table_name: str) -> None:
    """Create voicebot_faqs table (PK: chunk_id). Idempotent."""
    try:
        dynamo.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": "chunk_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "chunk_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"  Created table: {table_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"  Table already exists: {table_name}")
        else:
            raise


def create_sessions_table(dynamo, table_name: str) -> None:
    """Create voicebot_sessions table (PK: session_id, SK: turn_number). Idempotent."""
    try:
        dynamo.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "session_id", "KeyType": "HASH"},
                {"AttributeName": "turn_number", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "session_id", "AttributeType": "S"},
                {"AttributeName": "turn_number", "AttributeType": "N"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"  Created table: {table_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"  Table already exists: {table_name}")
        else:
            raise


def create_s3_bucket(s3, bucket_name: str, region: str) -> None:
    """Create S3 bucket. Idempotent."""
    try:
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region},
            )
        print(f"  Created S3 bucket: {bucket_name}")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            print(f"  S3 bucket already exists: {bucket_name}")
        else:
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Create Phase 01 AWS tables and bucket")
    parser.add_argument("--region", default="ap-south-1")
    parser.add_argument("--bucket", default="voicebot-mvp-docs")
    args = parser.parse_args()

    dynamo = boto3.client("dynamodb", region_name=args.region)
    s3 = boto3.client("s3", region_name=args.region)

    print("Setting up Phase 01 AWS resources...")
    create_faqs_table(dynamo, "voicebot_faqs")
    create_sessions_table(dynamo, "voicebot_sessions")
    create_s3_bucket(s3, args.bucket, args.region)

    print("\nSetup complete. Next step:")
    print("  python -m knowledge.pipeline.run_ingest --pdf-dir data/pdfs/")


if __name__ == "__main__":
    main()
