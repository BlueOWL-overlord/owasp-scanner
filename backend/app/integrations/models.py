import base64
import hashlib
import json
import secrets
from typing import Optional, Any, Dict
from datetime import datetime
from enum import Enum
from sqlmodel import Field, SQLModel
from cryptography.fernet import Fernet, InvalidToken

# Fields whose values are encrypted at rest
_SENSITIVE_KEYS = {"pat", "token", "secret_access_key", "password", "api_key"}


def _fernet() -> Fernet:
    from app.config import settings
    key_material = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_material))


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
    config: str = Field(default="{}")  # JSON with sensitive values encrypted
    webhook_token: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None

    def get_config(self) -> dict:
        """Return config dict with sensitive fields decrypted."""
        raw = json.loads(self.config)
        f = _fernet()
        result = {}
        for k, v in raw.items():
            if k in _SENSITIVE_KEYS and v and isinstance(v, str):
                try:
                    result[k] = f.decrypt(v.encode()).decode()
                except (InvalidToken, Exception):
                    result[k] = v  # backwards-compat: plain text (not yet encrypted)
            else:
                result[k] = v
        return result

    def set_config(self, data: dict):
        """Encrypt sensitive fields and store as JSON."""
        f = _fernet()
        to_store = {}
        for k, v in data.items():
            if k in _SENSITIVE_KEYS and v and isinstance(v, str):
                to_store[k] = f.encrypt(v.encode()).decode()
            else:
                to_store[k] = v
        self.config = json.dumps(to_store)


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
    webhook_token: str
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
