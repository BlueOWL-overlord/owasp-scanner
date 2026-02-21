"""
AI-powered false positive analysis using Claude Opus 4.6.
Analyzes OWASP Dependency Check vulnerabilities and identifies likely false positives.

Privacy: only sanitized 3rd-party library names and public CVE data are transmitted
to the Anthropic API. Project names, file paths, and internal identifiers are stripped
before any data leaves this server.
"""
import json
import os
import re
from typing import List

import anthropic
from sqlmodel import Session

from app.config import settings
from app.scanner.models import Vulnerability


# Matches the UUID prefix added by the upload handler:
# e.g. "3b7d9a1c-1234-5678-abcd-ef0123456789_original.war" → "original.war"
_UUID_PREFIX_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_',
    re.IGNORECASE,
)


def _sanitize_library_name(raw: str) -> str:
    """
    Strip any path components and internal upload prefixes from a filename so that
    only the bare 3rd-party library name is sent to the LLM.

    Examples
    --------
    /app/uploads/3b7d…_myapp.war/WEB-INF/lib/log4j-core-2.14.jar
        → log4j-core-2.14.jar

    3b7d9a1c-1234-5678-abcd-ef0123456789_spring-core-5.3.1.jar
        → spring-core-5.3.1.jar

    commons-io-2.11.0.jar
        → commons-io-2.11.0.jar  (unchanged)
    """
    # 1. Keep only the final path component
    name = os.path.basename(raw or "")
    # 2. Strip UUID upload prefix if present
    name = _UUID_PREFIX_RE.sub("", name)
    return name or "unknown-library"


def _build_safe_payload(vulns: List[Vulnerability]) -> list:
    """
    Build the vulnerability list that will be sent to the Anthropic API.

    Only includes:
      - Internal numeric ID (for correlating the response back to DB rows)
      - Sanitized 3rd-party library name and version
      - CVE ID, severity, CVSS scores, CWE IDs  (all public NVD data)
      - CVE description (public NVD data, truncated)

    Explicitly excluded:
      - Project / application name
      - Any file-system paths (upload dir, report dir, dependency_file)
      - UUID-prefixed filenames
      - Any other server-side identifiers
    """
    payload = []
    for v in vulns:
        payload.append({
            "id": v.id,
            "library_name": _sanitize_library_name(v.dependency_name or ""),
            "library_version": v.dependency_version or "unknown",
            "cve_id": v.cve_id,
            "severity": v.severity,
            "cvss_v2": v.cvss_v2,
            "cvss_v3": v.cvss_v3,
            "description": (v.description or "")[:2000],
            "cwe_ids": v.get_cwe_ids(),
        })
    return payload


SYSTEM_PROMPT = """You are a senior application security engineer specializing in software composition analysis (SCA) and dependency vulnerability assessment. You are an expert at identifying false positives in OWASP Dependency Check results.

Common false positive patterns you know well:
1. CVEs that affect a specific function/class NOT present in the scanned artifact
2. CVEs for vulnerabilities in server-side components when only client-side JARs are used
3. CVEs where the affected version range doesn't actually match (version detection errors)
4. Test/optional dependencies that don't ship in production
5. CVEs reported against a shaded/relocated dependency with a different package name
6. Platform-specific vulnerabilities (e.g., Linux-only) running on Windows deployments
7. CVEs that require specific configuration or environment not present in typical deployments
8. Incorrectly matched CPE identifiers causing wrong library attribution

For each vulnerability, analyze:
- The library name and version vs. the CVE's affected component
- Whether the CVE's attack vector is relevant to how the library is used
- CVSS score vs. actual exploitability in context
- Any known false positive patterns from the OWASP DC community

Return a structured JSON response."""


async def analyze_vulnerabilities(
    vulns: List[Vulnerability],
    project_name: str,          # received but NOT forwarded to the LLM
    session: Session,
) -> List[Vulnerability]:
    """Analyze vulnerabilities for false positives using Claude.

    The ``project_name`` parameter is intentionally ignored when building the
    LLM payload to prevent internal project/company names from being transmitted
    to the Anthropic API.
    """
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    # Build a payload that contains ONLY sanitized library names + public CVE data.
    # No project names, no file paths, no internal identifiers.
    safe_payload = _build_safe_payload(vulns)

    user_message = f"""Analyze these OWASP Dependency Check vulnerabilities.

Note: only library names and public CVE data are provided below.

Vulnerabilities to analyze:
{json.dumps(safe_payload, indent=2)}

For each vulnerability, determine:
1. Is this likely a false positive? (true/false)
2. Your confidence level (0.0 to 1.0)
3. Brief reasoning (2-3 sentences max)
4. Overall risk summary

Return ONLY valid JSON in this exact format:
{{
  "analyses": [
    {{
      "id": <vulnerability_id>,
      "is_false_positive": <true/false>,
      "confidence": <0.0-1.0>,
      "reasoning": "<brief explanation>",
      "risk_summary": "<1 sentence risk summary>"
    }}
  ],
  "overall_assessment": "<overall risk summary>"
}}"""

    stream = client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    full_text = ""
    async with stream as s:
        final = await s.get_final_message()
        for block in final.content:
            if block.type == "text":
                full_text = block.text
                break

    # Parse Claude's response
    try:
        json_str = full_text
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        result = json.loads(json_str)
        analyses = {a["id"]: a for a in result.get("analyses", [])}

        for v in vulns:
            if v.id in analyses:
                a = analyses[v.id]
                v.ai_is_false_positive = a.get("is_false_positive", False)
                v.ai_confidence = a.get("confidence", 0.5)
                v.ai_reasoning = a.get("reasoning", "")
                v.ai_analysis = a.get("risk_summary", "")
                session.add(v)

        session.commit()
        for v in vulns:
            session.refresh(v)

    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        for v in vulns:
            v.ai_analysis = f"Analysis available but could not be parsed: {str(exc)[:200]}"
            v.ai_reasoning = full_text[:500]
            session.add(v)
        session.commit()

    return vulns
