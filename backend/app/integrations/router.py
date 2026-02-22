import json
import logging
import uuid
import os
import asyncio
from datetime import datetime
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.auth.models import User
from app.auth.utils import get_current_user
from app.config import settings
from app.database import get_session
from app.integrations.models import (
    Integration, IntegrationCreate, IntegrationRead,
    IntegrationType, TriggerScanRequest, WebhookPayload,
)
from app.integrations.azure import trigger_azure_pipeline, get_azure_pipelines
from app.integrations.jenkins import trigger_jenkins_job, get_jenkins_jobs
from app.integrations.aws import trigger_codepipeline, list_codepipelines
from app.scanner.models import Scan, ScanStatus, ScanRead
from app.scanner.owasp import run_dependency_check

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.post("/", response_model=IntegrationRead, status_code=201)
def create_integration(
    data: IntegrationCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    integration = Integration(
        user_id=current_user.id,
        name=data.name,
        type=data.type,
    )
    integration.set_config(data.config)
    session.add(integration)
    session.commit()
    session.refresh(integration)
    return _to_read(integration)


@router.get("/", response_model=List[IntegrationRead])
def list_integrations(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    integrations = session.exec(
        select(Integration).where(Integration.user_id == current_user.id)
    ).all()
    return [_to_read(i) for i in integrations]


@router.delete("/{integration_id}", status_code=204)
def delete_integration(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    integration = session.get(Integration, integration_id)
    if not integration or integration.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Integration not found")
    session.delete(integration)
    session.commit()


@router.post("/{integration_id}/trigger", response_model=dict)
async def trigger_pipeline(
    integration_id: int,
    request: TriggerScanRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Trigger a CI/CD pipeline to run OWASP dependency check."""
    integration = session.get(Integration, integration_id)
    if not integration or integration.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Integration not found")

    config = integration.get_config()

    try:
        if integration.type == IntegrationType.AZURE:
            result = await trigger_azure_pipeline(
                org_url=config.get("org_url", ""),
                project=request.project or config.get("project", ""),
                pipeline_id=request.pipeline_id or config.get("pipeline_id", ""),
                pat=config.get("pat", ""),
            )
        elif integration.type == IntegrationType.JENKINS:
            result = await trigger_jenkins_job(
                jenkins_url=config.get("url", ""),
                job_name=request.job_name or config.get("default_job", ""),
                username=config.get("username", ""),
                token=config.get("token", ""),
            )
        elif integration.type == IntegrationType.AWS:
            result = await trigger_codepipeline(
                pipeline_name=request.pipeline_name or config.get("pipeline_name", ""),
                region=request.region or config.get("region", "us-east-1"),
                access_key_id=config.get("access_key_id", ""),
                secret_access_key=config.get("secret_access_key", ""),
            )
        else:
            raise HTTPException(status_code=400, detail="Unknown integration type")

        integration.last_used_at = datetime.utcnow()
        session.add(integration)
        session.commit()

        return {"status": "triggered", "result": result}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("trigger_pipeline error for integration %s: %s", integration_id, exc, exc_info=True)
        raise HTTPException(status_code=502, detail="Failed to trigger pipeline")


@router.post("/{integration_id}/list-resources", response_model=dict)
async def list_resources(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """List available pipelines/jobs for an integration."""
    integration = session.get(Integration, integration_id)
    if not integration or integration.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Integration not found")

    config = integration.get_config()

    try:
        if integration.type == IntegrationType.AZURE:
            resources = await get_azure_pipelines(
                org_url=config.get("org_url", ""),
                project=config.get("project", ""),
                pat=config.get("pat", ""),
            )
        elif integration.type == IntegrationType.JENKINS:
            resources = await get_jenkins_jobs(
                jenkins_url=config.get("url", ""),
                username=config.get("username", ""),
                token=config.get("token", ""),
            )
        elif integration.type == IntegrationType.AWS:
            resources = await list_codepipelines(
                region=config.get("region", "us-east-1"),
                access_key_id=config.get("access_key_id", ""),
                secret_access_key=config.get("secret_access_key", ""),
            )
        else:
            resources = []

        return {"resources": resources}
    except Exception as exc:
        logger.error("list_resources error for integration %s: %s", integration_id, exc, exc_info=True)
        raise HTTPException(status_code=502, detail="Failed to list resources")


# Webhook endpoint — CI/CD pipelines POST results here
@router.post("/webhook/{token}", response_model=ScanRead, status_code=202)
async def webhook_receive(
    token: str,
    payload: WebhookPayload,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """
    Webhook endpoint for CI/CD systems to submit scan artifacts.
    The token identifies the integration; requests with an unknown token are rejected.
    """
    # C1: Look up integration by its unique webhook token
    integration = session.exec(
        select(Integration).where(Integration.webhook_token == token)
    ).first()

    if not integration:
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    scan = Scan(
        user_id=integration.user_id,
        filename=f"webhook_{payload.project_name}",
        original_filename=payload.project_name,
        status=ScanStatus.PENDING,
        source=payload.source,
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)

    # If artifact URL provided, download and scan it
    if payload.artifact_url:
        background_tasks.add_task(
            _download_and_scan, scan.id, payload.artifact_url, session
        )

    return scan


async def _download_and_scan(scan_id: int, artifact_url: str, session: Session):
    """Download artifact from URL and run dependency check."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.get(artifact_url)
            resp.raise_for_status()

        # Use only extension from URL — never embed URL segments in filename (path traversal)
        url_basename = artifact_url.split("/")[-1].split("?")[0]
        ext = os.path.splitext(url_basename)[1].lower() or ".jar"
        file_path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4()}{ext}")

        with open(file_path, "wb") as f:
            f.write(resp.content)

        with Session(session.bind) as s:
            await run_dependency_check(scan_id, file_path, s)

    except Exception as exc:
        logger.error("_download_and_scan error for scan %s: %s", scan_id, exc, exc_info=True)
        with Session(session.bind) as s:
            scan = s.get(Scan, scan_id)
            if scan:
                scan.status = ScanStatus.FAILED
                scan.error_message = "Failed to download or scan artifact"
                s.add(scan)
                s.commit()


def _to_read(integration: Integration) -> IntegrationRead:
    config = integration.get_config()
    # Mask sensitive fields before returning to client
    safe_config = {
        k: ("***" if k in {"pat", "token", "secret_access_key", "password"} else v)
        for k, v in config.items()
    }
    return IntegrationRead(
        id=integration.id,
        user_id=integration.user_id,
        name=integration.name,
        type=integration.type,
        config=safe_config,
        webhook_token=integration.webhook_token,
        is_active=integration.is_active,
        created_at=integration.created_at,
        last_used_at=integration.last_used_at,
    )
