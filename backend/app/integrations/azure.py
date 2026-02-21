"""Azure DevOps pipeline integration."""
import httpx
import base64
from typing import Optional


async def trigger_azure_pipeline(
    org_url: str,
    project: str,
    pipeline_id: str,
    pat: str,
    branch: str = "main",
    variables: Optional[dict] = None,
) -> dict:
    """Trigger an Azure DevOps pipeline run."""
    token = base64.b64encode(f":{pat}".encode()).decode()
    headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }
    url = f"{org_url.rstrip('/')}/{project}/_apis/pipelines/{pipeline_id}/runs?api-version=7.1"
    body = {
        "resources": {"repositories": {"self": {"refName": f"refs/heads/{branch}"}}},
        "variables": variables or {},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        return resp.json()


async def get_azure_pipelines(org_url: str, project: str, pat: str) -> list:
    """List available pipelines in an Azure DevOps project."""
    token = base64.b64encode(f":{pat}".encode()).decode()
    headers = {"Authorization": f"Basic {token}"}
    url = f"{org_url.rstrip('/')}/{project}/_apis/pipelines?api-version=7.1"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data.get("value", [])
