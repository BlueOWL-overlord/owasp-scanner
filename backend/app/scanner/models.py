from typing import Optional, List
from datetime import datetime
from enum import Enum
from sqlmodel import Field, SQLModel, Relationship
import json


class ScanStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"
    UNKNOWN = "UNKNOWN"


class Scan(SQLModel, table=True):
    __tablename__ = "scans"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    filename: str
    original_filename: str
    status: ScanStatus = Field(default=ScanStatus.PENDING)
    error_message: Optional[str] = None
    report_path: Optional[str] = None
    total_vulnerabilities: int = Field(default=0)
    critical_count: int = Field(default=0)
    high_count: int = Field(default=0)
    medium_count: int = Field(default=0)
    low_count: int = Field(default=0)
    source: str = Field(default="upload")  # upload | azure | jenkins | aws
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class Vulnerability(SQLModel, table=True):
    __tablename__ = "vulnerabilities"

    id: Optional[int] = Field(default=None, primary_key=True)
    scan_id: int = Field(foreign_key="scans.id", index=True)
    dependency_name: str
    dependency_version: Optional[str] = None
    dependency_file: Optional[str] = None
    cve_id: str
    severity: Severity = Field(default=Severity.UNKNOWN)
    cvss_v2: Optional[float] = None
    cvss_v3: Optional[float] = None
    description: str = Field(default="")
    references: Optional[str] = None  # JSON string
    cwe_ids: Optional[str] = None     # JSON string
    ai_analysis: Optional[str] = None
    ai_is_false_positive: Optional[bool] = None
    ai_confidence: Optional[float] = None
    ai_reasoning: Optional[str] = None
    is_suppressed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def get_references(self) -> List[dict]:
        if self.references:
            return json.loads(self.references)
        return []

    def get_cwe_ids(self) -> List[str]:
        if self.cwe_ids:
            return json.loads(self.cwe_ids)
        return []


# API response models

class VulnerabilityRead(SQLModel):
    id: int
    scan_id: int
    dependency_name: str
    dependency_version: Optional[str]
    dependency_file: Optional[str]
    cve_id: str
    severity: Severity
    cvss_v2: Optional[float]
    cvss_v3: Optional[float]
    description: str
    references: Optional[str]
    cwe_ids: Optional[str]
    ai_analysis: Optional[str]
    ai_is_false_positive: Optional[bool]
    ai_confidence: Optional[float]
    ai_reasoning: Optional[str]
    is_suppressed: bool
    created_at: datetime


class ScanRead(SQLModel):
    id: int
    user_id: int
    filename: str
    original_filename: str
    status: ScanStatus
    error_message: Optional[str]
    total_vulnerabilities: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    source: str
    created_at: datetime
    completed_at: Optional[datetime]


class ScanWithVulnerabilities(ScanRead):
    vulnerabilities: List[VulnerabilityRead] = []


class AIAnalysisRequest(SQLModel):
    vulnerability_ids: List[int]
