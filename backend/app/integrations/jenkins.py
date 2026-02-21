"""Jenkins pipeline integration."""
import httpx
from typing import Optional


async def trigger_jenkins_job(
    jenkins_url: str,
    job_name: str,
    username: str,
    token: str,
    parameters: Optional[dict] = None,
) -> dict:
    """Trigger a Jenkins job build."""
    base = jenkins_url.rstrip("/")
    auth = (username, token)

    if parameters:
        url = f"{base}/job/{job_name}/buildWithParameters"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, auth=auth, params=parameters)
            resp.raise_for_status()
    else:
        url = f"{base}/job/{job_name}/build"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, auth=auth)
            resp.raise_for_status()

    queue_url = resp.headers.get("Location", "")
    return {"status": "triggered", "queue_url": queue_url, "job": job_name}


async def get_jenkins_jobs(jenkins_url: str, username: str, token: str) -> list:
    """List available Jenkins jobs."""
    url = f"{jenkins_url.rstrip('/')}/api/json?tree=jobs[name,url,color]"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, auth=(username, token))
        resp.raise_for_status()
        data = resp.json()
        return data.get("jobs", [])


async def get_jenkins_build_status(
    jenkins_url: str,
    job_name: str,
    build_number: int,
    username: str,
    token: str,
) -> dict:
    """Get status of a specific Jenkins build."""
    url = f"{jenkins_url.rstrip('/')}/job/{job_name}/{build_number}/api/json"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, auth=(username, token))
        resp.raise_for_status()
        return resp.json()
