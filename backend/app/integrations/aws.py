"""AWS CodePipeline integration."""
import json
from typing import Optional

import httpx


async def trigger_codepipeline(
    pipeline_name: str,
    region: str,
    access_key_id: str,
    secret_access_key: str,
) -> dict:
    """
    Start an AWS CodePipeline execution via the AWS REST API.
    Uses AWS Signature Version 4 for authentication.
    """
    import hmac
    import hashlib
    import datetime

    method = "POST"
    service = "codepipeline"
    host = f"codepipeline.{region}.amazonaws.com"
    endpoint = f"https://{host}/"

    payload = json.dumps({"name": pipeline_name})

    now = datetime.datetime.utcnow()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    canonical_headers = f"content-type:application/x-amz-json-1.1\nhost:{host}\nx-amz-date:{amz_date}\n"
    signed_headers = "content-type;host;x-amz-date"
    payload_hash = hashlib.sha256(payload.encode()).hexdigest()

    canonical_request = (
        f"{method}\n/\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
    )

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = (
        f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n"
        + hashlib.sha256(canonical_request.encode()).hexdigest()
    )

    def sign(key, msg):
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    signing_key = sign(
        sign(
            sign(
                sign(f"AWS4{secret_access_key}".encode(), date_stamp),
                region,
            ),
            service,
        ),
        "aws4_request",
    )
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    auth_header = (
        f"AWS4-HMAC-SHA256 Credential={access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    headers = {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Date": amz_date,
        "Authorization": auth_header,
        "X-Amz-Target": "CodePipeline_20150709.StartPipelineExecution",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(endpoint, headers=headers, content=payload)
        resp.raise_for_status()
        return resp.json()


async def list_codepipelines(
    region: str,
    access_key_id: str,
    secret_access_key: str,
) -> list:
    """List AWS CodePipelines in a region."""
    import hmac
    import hashlib
    import datetime

    method = "POST"
    service = "codepipeline"
    host = f"codepipeline.{region}.amazonaws.com"
    endpoint = f"https://{host}/"
    payload = "{}"

    now = datetime.datetime.utcnow()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    canonical_headers = f"content-type:application/x-amz-json-1.1\nhost:{host}\nx-amz-date:{amz_date}\n"
    signed_headers = "content-type;host;x-amz-date"
    payload_hash = hashlib.sha256(payload.encode()).hexdigest()
    canonical_request = f"{method}\n/\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = (
        f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n"
        + hashlib.sha256(canonical_request.encode()).hexdigest()
    )

    def sign(key, msg):
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    signing_key = sign(sign(sign(sign(f"AWS4{secret_access_key}".encode(), date_stamp), region), service), "aws4_request")
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    auth_header = (
        f"AWS4-HMAC-SHA256 Credential={access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    headers = {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Date": amz_date,
        "Authorization": auth_header,
        "X-Amz-Target": "CodePipeline_20150709.ListPipelines",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(endpoint, headers=headers, content=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("pipelines", [])
