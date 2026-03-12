# tests/infra/test_setup_aws_tables.py
from unittest.mock import MagicMock
from botocore.exceptions import ClientError
import pytest

from infra.scripts.setup_aws_tables import create_faqs_table, create_sessions_table, create_s3_bucket


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": ""}}, "operation")


def test_create_faqs_table_calls_create_table():
    dynamo = MagicMock()
    create_faqs_table(dynamo, "voicebot_faqs")
    dynamo.create_table.assert_called_once()
    call_kwargs = dynamo.create_table.call_args[1]
    assert call_kwargs["TableName"] == "voicebot_faqs"
    assert call_kwargs["BillingMode"] == "PAY_PER_REQUEST"


def test_create_faqs_table_ignores_already_exists():
    dynamo = MagicMock()
    dynamo.create_table.side_effect = _client_error("ResourceInUseException")
    # Should not raise
    create_faqs_table(dynamo, "voicebot_faqs")


def test_create_sessions_table_has_composite_key():
    dynamo = MagicMock()
    create_sessions_table(dynamo, "voicebot_sessions")
    call_kwargs = dynamo.create_table.call_args[1]
    key_names = {k["AttributeName"] for k in call_kwargs["KeySchema"]}
    assert "session_id" in key_names
    assert "turn_number" in key_names


def test_create_s3_bucket_uses_location_constraint_outside_us_east_1():
    s3 = MagicMock()
    create_s3_bucket(s3, "voicebot-mvp-docs", "ap-south-1")
    call_kwargs = s3.create_bucket.call_args[1]
    assert call_kwargs["CreateBucketConfiguration"]["LocationConstraint"] == "ap-south-1"


def test_create_s3_bucket_ignores_already_exists():
    s3 = MagicMock()
    s3.create_bucket.side_effect = _client_error("BucketAlreadyOwnedByYou")
    # Should not raise
    create_s3_bucket(s3, "voicebot-mvp-docs", "ap-south-1")
