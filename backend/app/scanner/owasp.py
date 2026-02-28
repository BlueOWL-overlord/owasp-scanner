import asyncio
import json
import os
import platform
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from xml.etree import ElementTree as ET

from sqlmodel import Session, select

from app.config import settings
from app.scanner.models import Scan, ScanStatus, Vulnerability, Severity

_IS_WINDOWS = platform.system() == "Windows"


def _build_env() -> dict:
    """
    Return a copy of os.environ with Java guaranteed to be on PATH.

    Uvicorn's worker process may not inherit the machine PATH that was updated
    when Java was installed (especially with --reload). We resolve JAVA_HOME
    from settings or by scanning common Windows install locations, then prepend
    its bin/ directory to PATH before spawning dependency-check.
    """
    env = os.environ.copy()
    java_home = (settings.JAVA_HOME or "").strip()

    if _IS_WINDOWS and (not java_home or not os.path.isdir(java_home)):
        # Common Windows JDK installation bases – try newest first
        for base in [
            r"C:\Program Files\Eclipse Adoptium",
            r"C:\Program Files\Microsoft",
            r"C:\Program Files\Java",
            r"C:\Program Files\Amazon Corretto",
        ]:
            if not os.path.isdir(base):
                continue
            for entry in sorted(os.listdir(base), reverse=True):
                candidate = os.path.join(base, entry)
                if os.path.isfile(os.path.join(candidate, "bin", "java.exe")):
                    java_home = candidate
                    break
            if java_home:
                break

    if java_home and os.path.isdir(java_home):
        java_bin = os.path.join(java_home, "bin")
        env["JAVA_HOME"] = java_home
        env["PATH"] = java_bin + os.pathsep + env.get("PATH", "")

    return env


def _run_dc_sync(cmd, scan_id: int, log_path: str, shell: bool = False) -> tuple:
    """
    Execute dependency-check synchronously; returns (stdout, stderr, returncode).

    Uses Popen + readline so output is streamed to the backend console in
    real-time (visible in the terminal window) AND written to scan.log so the
    frontend can poll it while the scan is running.

    Using subprocess (blocking) inside run_in_executor avoids the
    asyncio.create_subprocess_exec NotImplementedError on Windows when uvicorn
    runs with --reload (SelectorEventLoop instead of ProactorEventLoop).
    """
    prefix = f"[Scan #{scan_id}]"
    lines  = []

    # Merge stderr into stdout so we capture everything in order
    with open(log_path, "w", encoding="utf-8", buffering=1) as log_file:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_build_env(),
            shell=shell,
        )

        for raw_line in proc.stdout:
            line = raw_line.rstrip("\n")
            print(f"{prefix} {line}", flush=True)   # live console output
            log_file.write(line + "\n")              # persisted for frontend
            lines.append(line)

        proc.wait()

    stdout = "\n".join(lines)
    return stdout, "", proc.returncode


SUPPORTED_EXTENSIONS = {
    ".jar", ".war", ".ear", ".zip", ".sar", ".apk", ".nupkg",
    ".egg", ".wheel", ".tar", ".gz", ".tgz",
}


def is_supported_file(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in SUPPORTED_EXTENSIONS


async def run_dependency_check(scan_id: int, file_path: str, session: Session):
    """Run OWASP Dependency Check as a subprocess and parse results."""
    scan = session.get(Scan, scan_id)
    if not scan:
        return

    scan.status = ScanStatus.RUNNING
    session.add(scan)
    session.commit()

    report_dir = os.path.join(settings.REPORTS_DIR, str(scan_id))
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "dependency-check-report.json")
    log_path    = os.path.join(report_dir, "scan.log")

    cmd = [
        settings.OWASP_DC_PATH,
        "--scan", file_path,
        "--format", "JSON",
        "--out", report_dir,
        "--prettyPrint",
        "--disableOssIndex",    # requires Sonatype credentials
        "--disableYarnAudit",   # requires yarn CLI
        "--disableNodeAudit",   # requires npm CLI
        "--disableNodeJS",      # no Node.js package scanning needed
    ]

    if settings.OWASP_DC_DATA_DIR:
        cmd += ["--data", settings.OWASP_DC_DATA_DIR]

    if settings.NVD_API_KEY:
        cmd += ["--nvdApiKey", settings.NVD_API_KEY]

    # On Windows, .bat files cannot be executed directly by subprocess — they
    # require the shell.  Building a quoted command string and using shell=True
    # avoids the classic "C:Program is not recognized" error that occurs when
    # cmd /c receives a path with spaces and strips the outer quotes.
    use_shell = False
    if _IS_WINDOWS and settings.OWASP_DC_PATH.lower().endswith(".bat"):
        cmd = subprocess.list2cmdline(cmd)
        use_shell = True

    try:
        loop = asyncio.get_event_loop()
        stdout, stderr, returncode = await loop.run_in_executor(
            None, lambda: _run_dc_sync(cmd, scan_id, log_path, shell=use_shell)
        )

        # Always verify the report was produced.  If it is missing the scan
        # failed silently (e.g. wrong DC path, Java error, disk-full) even if
        # OWASP DC exited with a "success-like" code such as 1 (vulns found) —
        # which is also what cmd.exe returns when it cannot find a program.
        if not os.path.exists(report_path):
            detail = (stdout.strip() or f"exit code {returncode}")[:800]
            raise RuntimeError(
                f"dependency-check produced no report (exit {returncode}). "
                f"Check OWASP_DC_PATH and that Java is available.\n{detail}"
            )

        # DC exit codes: 0=clean, 1=vulns found, 2=analysis errors (non-fatal),
        # 4=update warnings; anything else with a report is treated as a warning.
        if returncode not in (0, 1, 2, 4):
            detail = (stdout.strip() or f"exit code {returncode}")[:400]
            raise RuntimeError(f"dependency-check failed (exit {returncode}): {detail}")

        # Parse results
        vulns = _parse_report(report_path, scan_id)

        with Session(session.bind) as s:
            scan = s.get(Scan, scan_id)
            for v in vulns:
                s.add(v)

            scan.status = ScanStatus.COMPLETED
            scan.report_path = report_path
            scan.completed_at = datetime.utcnow()
            scan.total_vulnerabilities = len(vulns)
            scan.critical_count = sum(1 for v in vulns if v.severity == Severity.CRITICAL)
            scan.high_count = sum(1 for v in vulns if v.severity == Severity.HIGH)
            scan.medium_count = sum(1 for v in vulns if v.severity == Severity.MEDIUM)
            scan.low_count = sum(1 for v in vulns if v.severity == Severity.LOW)
            s.add(scan)
            s.commit()

    except Exception as exc:
        msg = str(exc).strip()
        if not msg:
            # Some exceptions (e.g. NotImplementedError) have no message text
            msg = (f"{type(exc).__name__}: no message — verify Java is installed "
                   f"and OWASP_DC_PATH is correct ({settings.OWASP_DC_PATH})")
        with Session(session.bind) as s:
            scan = s.get(Scan, scan_id)
            scan.status = ScanStatus.FAILED
            scan.error_message = msg[:1000]
            scan.completed_at = datetime.utcnow()
            s.add(scan)
            s.commit()
    finally:
        # Clean up uploaded file
        if os.path.exists(file_path):
            os.remove(file_path)


def _parse_report(report_path: str, scan_id: int) -> List[Vulnerability]:
    """Parse OWASP DC JSON report into Vulnerability objects."""
    vulns = []

    if not os.path.exists(report_path):
        return vulns

    with open(report_path) as f:
        data = json.load(f)

    dependencies = data.get("dependencies", [])

    for dep in dependencies:
        dep_name = dep.get("fileName", "unknown")
        dep_file = dep.get("filePath", "")
        dep_packages = dep.get("packages", [])

        # Try to get version from packages
        dep_version = None
        for pkg in dep_packages:
            if "id" in pkg:
                parts = pkg["id"].split(":")
                if len(parts) >= 3:
                    dep_version = parts[-1]
                    break

        for vuln in dep.get("vulnerabilities", []):
            severity_str = vuln.get("severity", "UNKNOWN").upper()
            try:
                severity = Severity(severity_str)
            except ValueError:
                severity = Severity.UNKNOWN

            cvss_v2 = None
            cvss_v3 = None
            cvssv2 = vuln.get("cvssv2", {})
            cvssv3 = vuln.get("cvssv3", {})
            if cvssv2:
                cvss_v2 = cvssv2.get("score")
            if cvssv3:
                cvss_v3 = cvssv3.get("baseScore")

            refs = [
                {"url": r.get("url", ""), "name": r.get("name", "")}
                for r in vuln.get("references", [])
            ]
            cwes = vuln.get("cwes", [])

            v = Vulnerability(
                scan_id=scan_id,
                dependency_name=dep_name,
                dependency_version=dep_version,
                dependency_file=dep_file,
                cve_id=vuln.get("name", "UNKNOWN"),
                severity=severity,
                cvss_v2=cvss_v2,
                cvss_v3=cvss_v3,
                description=vuln.get("description", ""),
                references=json.dumps(refs),
                cwe_ids=json.dumps(cwes),
            )
            vulns.append(v)

    return vulns
