import json
from datetime import datetime
from typing import Any

import boto3


class S3RawStore:
    def __init__(self, bucket: str, endpoint_url: str | None, region: str, aws_profile: str) -> None:
        self.bucket = bucket
        session = boto3.Session(profile_name=aws_profile)
        self.client = session.client("s3", endpoint_url=endpoint_url, region_name=region)

    def put_immutable(self, run_id: str, start: datetime, end: datetime, payload: dict[str, Any]) -> str:
        key = f"raw/extracted_at={datetime.utcnow():%Y-%m-%dT%H-%M-%SZ}/run_id={run_id}/chunk_start={start:%Y-%m-%dT%H-%M-%SZ}_{end:%Y-%m-%dT%H-%M-%SZ}.json"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(payload, separators=(",", ":")).encode(),
            ContentType="application/json",
            IfNoneMatch="*",
        )
        return key

    def read_json(self, key: str) -> dict[str, Any]:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return json.loads(response["Body"].read())
