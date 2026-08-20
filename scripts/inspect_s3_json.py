"""Parse and print JSON objects from an S3 bucket without modifying them."""

import argparse
import json
import os
from typing import Any

import boto3
from dotenv import load_dotenv

load_dotenv()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect JSON files in an S3 bucket")
    parser.add_argument("--bucket", default=os.getenv("S3_BUCKET", "chargenow-tweets"))
    parser.add_argument("--prefix", default=os.getenv("S3_PREFIX", ""))
    parser.add_argument("--profile", default=os.getenv("AWS_PROFILE", "chargenow"))
    parser.add_argument("--region", default=os.getenv("S3_REGION", "eu-central-1"))
    parser.add_argument(
        "--full",
        action="store_true",
        help="Print the complete parsed JSON payload instead of only its data records",
    )
    return parser.parse_args()


def result_count(payload: dict[str, Any]) -> int:
    data = payload.get("data", [])
    if isinstance(data, list):
        return len(data)
    return int(payload.get("meta", {}).get("result_count", 0))


def main() -> None:
    args = parse_args()
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    client = session.client("s3")
    paginator = client.get_paginator("list_objects_v2")

    inspected = 0
    records = 0
    for page in paginator.paginate(Bucket=args.bucket, Prefix=args.prefix):
        for item in page.get("Contents", []):
            key = item["Key"]
            if not key.lower().endswith(".json"):
                continue
            response = client.get_object(Bucket=args.bucket, Key=key)
            raw_payload = response["Body"].read()
            try:
                payload = json.loads(raw_payload)
            except json.JSONDecodeError as error:
                print(f"INVALID JSON: {key}: {error}")
                continue
            if not isinstance(payload, dict):
                print(f"SKIPPED non-object JSON: {key}")
                continue

            count = result_count(payload)
            inspected += 1
            records += count
            print(f"{key}: {count} result(s)")
            if args.full:
                print(json.dumps(payload, indent=2, sort_keys=True))
            else:
                for record in payload.get("data", []):
                    print(json.dumps(record, sort_keys=True))

    print(f"Inspected {inspected} JSON file(s), {records} result(s)")


if __name__ == "__main__":
    main()
