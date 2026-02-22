import asyncio
import csv
import io
import os
import re
import uuid
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from sqlmodel import Session, select

MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB

from app.auth.models import User
from app.auth.utils import get_current_user
from app.config import settings
from app.database import get_session
from app.scanner.models import (
    Scan, ScanStatus, Vulnerability, ScanRead, ScanWithVulnerabilities,
    VulnerabilityRead, AIAnalysisRequest,
)
from app.scanner.owasp import run_dependency_check, is_supported_file
from app.ai.analyzer import analyze_vulnerabilities

router = APIRouter(prefix="/api/scans", tags=["scans"])


@router.post("/upload", response_model=ScanRead, status_code=202)
async def upload_and_scan(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if not is_supported_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported: jar, war, ear, zip, sar, apk, nupkg, egg, wheel, tar, gz",
        )

    # Read content first so we can check size before touching disk
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 500 MB)")

    # Use only the extension from the original name — never the filename itself
    ext = Path(file.filename).suffix.lower()
    safe_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_name)

    # Guard against path traversal
    upload_abs = os.path.abspath(settings.UPLOAD_DIR)
    file_abs   = os.path.abspath(file_path)
    if not file_abs.startswith(upload_abs + os.sep):
        raise HTTPException(status_code=400, detail="Invalid file path")

    with open(file_path, "wb") as f:
        f.write(content)

    # Create scan record
    scan = Scan(
        user_id=current_user.id,
        filename=safe_name,
        original_filename=file.filename,
        status=ScanStatus.PENDING,
        source="upload",
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)

    # Run OWASP DC in background
    background_tasks.add_task(run_dependency_check, scan.id, file_path, session)

    return scan


@router.get("/", response_model=List[ScanRead])
def list_scans(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    skip: int = 0,
    limit: int = 50,
):
    scans = session.exec(
        select(Scan)
        .where(Scan.user_id == current_user.id)
        .order_by(Scan.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return scans


@router.get("/{scan_id}", response_model=ScanWithVulnerabilities)
def get_scan(
    scan_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    scan = session.get(Scan, scan_id)
    if not scan or scan.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Scan not found")

    vulns = session.exec(
        select(Vulnerability).where(Vulnerability.scan_id == scan_id)
    ).all()

    result = ScanWithVulnerabilities(
        **scan.model_dump(),
        vulnerabilities=[VulnerabilityRead(**v.model_dump()) for v in vulns],
    )
    return result


@router.delete("/{scan_id}", status_code=204)
def delete_scan(
    scan_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    scan = session.get(Scan, scan_id)
    if not scan or scan.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Delete vulnerabilities
    vulns = session.exec(select(Vulnerability).where(Vulnerability.scan_id == scan_id)).all()
    for v in vulns:
        session.delete(v)

    session.delete(scan)
    session.commit()


@router.post("/{scan_id}/analyze", response_model=List[VulnerabilityRead])
async def ai_analyze(
    scan_id: int,
    request: AIAnalysisRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Run AI analysis on selected vulnerabilities to identify false positives."""
    scan = session.get(Scan, scan_id)
    if not scan or scan.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Scan not found")

    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="AI analysis not configured (missing ANTHROPIC_API_KEY)")

    vulns = session.exec(
        select(Vulnerability).where(
            Vulnerability.scan_id == scan_id,
            Vulnerability.id.in_(request.vulnerability_ids),
        )
    ).all()

    if not vulns:
        raise HTTPException(status_code=404, detail="No vulnerabilities found")

    updated = await analyze_vulnerabilities(vulns, scan.original_filename, session)
    return [VulnerabilityRead(**v.model_dump()) for v in updated]


@router.patch("/{scan_id}/vulnerabilities/{vuln_id}/suppress", response_model=VulnerabilityRead)
def suppress_vulnerability(
    scan_id: int,
    vuln_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    scan = session.get(Scan, scan_id)
    if not scan or scan.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Scan not found")

    vuln = session.get(Vulnerability, vuln_id)
    if not vuln or vuln.scan_id != scan_id:
        raise HTTPException(status_code=404, detail="Vulnerability not found")

    vuln.is_suppressed = not vuln.is_suppressed
    session.add(vuln)
    session.commit()
    session.refresh(vuln)
    return VulnerabilityRead(**vuln.model_dump())


@router.get("/{scan_id}/log", response_class=PlainTextResponse)
def get_scan_log(
    scan_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Return the raw OWASP DC console output for a scan (streams while running)."""
    scan = session.get(Scan, scan_id)
    if not scan or scan.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Scan not found")

    log_path = os.path.join(settings.REPORTS_DIR, str(scan_id), "scan.log")
    if not os.path.exists(log_path):
        status_msg = {
            "pending": "Scan is queued — log will appear when it starts.",
            "running": "Scan is starting up — log will appear shortly...",
        }.get(scan.status, "Log not available for this scan.")
        return PlainTextResponse(status_msg)

    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        return PlainTextResponse(f.read())


@router.get("/{scan_id}/export/csv")
def export_csv(
    scan_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Export scan vulnerabilities as a CSV file."""
    scan = session.get(Scan, scan_id)
    if not scan or scan.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Scan not found")

    vulns = session.exec(
        select(Vulnerability).where(Vulnerability.scan_id == scan_id)
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Dependency Name",
        "File Path",
        "Version",
        "CVE ID",
        "Severity",
        "CVSS V3 Score",
        "CVSS V2 Score",
        "Remediation Suggestion",
        "AI Analysis",
        "False Positive",
        "Suppressed",
    ])

    for v in vulns:
        # Build remediation suggestion from AI analysis or a standard NVD link
        if v.ai_analysis:
            remediation = v.ai_analysis
        else:
            remediation = (
                f"Update {v.dependency_name} to the latest patched version. "
                f"Review the advisory at https://nvd.nist.gov/vuln/detail/{v.cve_id}"
            )

        if v.ai_is_false_positive is True:
            fp_label = "Yes"
        elif v.ai_is_false_positive is False:
            fp_label = "No"
        else:
            fp_label = "Not analysed"

        writer.writerow([
            v.dependency_name,
            v.dependency_file or "",
            v.dependency_version or "",
            v.cve_id,
            v.severity,
            v.cvss_v3 if v.cvss_v3 is not None else "",
            v.cvss_v2 if v.cvss_v2 is not None else "",
            remediation,
            v.ai_reasoning or "",
            fp_label,
            "Yes" if v.is_suppressed else "No",
        ])

    output.seek(0)
    # Strip to safe ASCII chars only, then RFC 5987-encode for the header
    ascii_name = re.sub(r'[^\w\s.-]', '_', scan.original_filename)[:60]
    filename   = f"scan-{scan_id}-{ascii_name}.csv"
    encoded    = quote(filename, safe='')
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


@router.get("/{scan_id}/report")
def download_report(
    scan_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    scan = session.get(Scan, scan_id)
    if not scan or scan.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Scan not found")
    if not scan.report_path or not os.path.exists(scan.report_path):
        raise HTTPException(status_code=404, detail="Report not available")

    return FileResponse(
        scan.report_path,
        media_type="application/json",
        filename=f"scan-{scan_id}-report.json",
    )
