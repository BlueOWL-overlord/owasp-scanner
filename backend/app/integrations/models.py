from typing import Optional, Any, Dict
from datetime import datetime
from enum import Enum
from sqlmodel import Field, SQLModel
import json


class IntegrationType(str, Enum):
    AZURE = "azure"
    JENKINS = "jenkins"
    AWS = "aws"


class Integration(SQLModel, table=True):
    __tablename__ = "integrations"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    name: str
    type: IntegrationType
    config: str = Field(default="{}")  # JSON
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None

    def get_config(self) -> dict:
        return json.loads(self.config)

    def set_config(self, data: dict):
        self.config = json.dumps(data)


class IntegrationCreate(SQLModel):
    name: str
    type: IntegrationType
    config: Dict[str, Any]


class IntegrationRead(SQLModel):
    id: int
    user_id: int
    name: str
    type: IntegrationType
    config: Dict[str, Any]
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]


class TriggerScanRequest(SQLModel):
    integration_id: int
    # Azure-specific
    organization: Optional[str] = None
    project: Optional[str] = None
    pipeline_id: Optional[str] = None
    # Jenkins-specific
    job_name: Optional[str] = None
    # AWS-specific
    pipeline_name: Optional[str] = None
    region: Optional[str] = None


class WebhookPayload(SQLModel):
    source: str  # azure | jenkins | aws
    project_name: str
    artifact_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
