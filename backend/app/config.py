import os
import platform
from pydantic_settings import BaseSettings
from pydantic import field_validator

_IS_WINDOWS = platform.system() == "Windows"
_HOME = os.path.expanduser("~")

# config.py lives at  <project>/backend/app/config.py
# The .env file lives at <project>/.env  (two levels up)
_THIS_DIR    = os.path.dirname(os.path.abspath(__file__))   # backend/app/
_BACKEND_DIR = os.path.dirname(_THIS_DIR)                   # backend/
_PROJECT_DIR = os.path.dirname(_BACKEND_DIR)                # project root (owasp-scanner/)


def _win(windows_val: str, linux_val: str) -> str:
    return windows_val if _IS_WINDOWS else linux_val


_WEAK_KEY = "change-me-in-production-use-random-32-chars"


class Settings(BaseSettings):
    SECRET_KEY: str = _WEAK_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if v == _WEAK_KEY or len(v) < 32:
            raise ValueError(
                "SECRET_KEY is not set or too short. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    DATABASE_URL: str = "sqlite:///./data/app.db"

    ANTHROPIC_API_KEY: str = ""

    # Path to OWASP Dependency Check CLI.
    # Windows: C:\dependency-check\bin\dependency-check.bat
    # Linux/Docker: /opt/dependency-check/bin/dependency-check.sh
    OWASP_DC_PATH: str = _win(
        r"C:\dependency-check\bin\dependency-check.bat",
        "/opt/dependency-check/bin/dependency-check.sh",
    )
    OWASP_DC_DATA_DIR: str = _win(
        r"C:\dependency-check-data",
        "/opt/dependency-check-data",
    )
    # NVD API key — dramatically speeds up the NVD database download.
    # Without a key: rate-limited to 1 request / 6 s (~hours for first download).
    # With a key:    50 requests / 30 s  (~10 min for first download).
    # Request a free key at: https://nvd.nist.gov/developers/request-an-api-key
    NVD_API_KEY: str = ""

    UPLOAD_DIR: str = _win(
        os.path.join(_HOME, "owasp-scanner", "uploads"),
        "/app/uploads",
    )
    REPORTS_DIR: str = _win(
        os.path.join(_HOME, "owasp-scanner", "reports"),
        "/app/reports",
    )

    # Optional: explicit JAVA_HOME so subprocess finds java even if PATH isn't inherited
    JAVA_HOME: str = _win(
        r"C:\Program Files\Eclipse Adoptium\jdk-21.0.10.7-hotspot",
        "",
    )

    # CI/CD Integration settings
    AZURE_ORG_URL: str = ""
    AZURE_PAT: str = ""

    JENKINS_URL: str = ""
    JENKINS_USER: str = ""
    JENKINS_TOKEN: str = ""

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"

    class Config:
        # Look for .env in: project root → backend/ → current dir (in that order)
        env_file = (
            os.path.join(_PROJECT_DIR, ".env"),
            os.path.join(_BACKEND_DIR, ".env"),
            ".env",
        )


settings = Settings()

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.REPORTS_DIR, exist_ok=True)
os.makedirs("data", exist_ok=True)
