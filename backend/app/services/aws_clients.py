import os
from dataclasses import dataclass
from typing import Any

try:
    import boto3
except Exception:  # pragma: no cover - boto3 may not be available in local sandbox
    boto3 = None


@dataclass
class AwsClientBundle:
    transcribe: Any
    bedrock_runtime: Any
    polly: Any


def _use_mocks() -> bool:
    return os.getenv("USE_AWS_MOCKS", "true").lower() in {"1", "true", "yes"}


def _region() -> str:
    return os.getenv("AWS_REGION", "us-east-1")


class _StubClient:
    def __init__(self, service: str) -> None:
        self.service = service


def build_aws_clients() -> AwsClientBundle:
    if _use_mocks() or boto3 is None:
        return AwsClientBundle(
            transcribe=_StubClient("transcribe"),
            bedrock_runtime=_StubClient("bedrock-runtime"),
            polly=_StubClient("polly"),
        )

    session = boto3.Session(profile_name=os.getenv("AWS_PROFILE") or None, region_name=_region())
    return AwsClientBundle(
        transcribe=session.client("transcribe"),
        bedrock_runtime=session.client("bedrock-runtime"),
        polly=session.client("polly"),
    )

