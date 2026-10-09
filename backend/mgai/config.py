import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.fernet import Fernet


@dataclass(frozen=True)
class Settings:
    database_url: str = field(repr=False)
    encryption_key: str = field(repr=False)
    public_base_url: str = "https://localhost"
    nvidia_api_key: str = field(default="", repr=False)
    local_dev: bool = False
    commercial_mode: bool = False
    commercial_agreement_reference: str = ""
    global_daily_requests: int = 100
    global_daily_usd_limit: str = "5.00"
    static_dir: str = str(Path(__file__).resolve().parents[2] / "frontend" / "dist")

    @classmethod
    def from_env(cls):
        return cls(
            database_url=os.getenv("DATABASE_URL", ""),
            encryption_key=os.getenv("DATA_ENCRYPTION_KEY", ""),
            public_base_url=os.getenv("PUBLIC_BASE_URL", "https://localhost"),
            nvidia_api_key=os.getenv("NVIDIA_API_KEY", ""),
            local_dev=os.getenv("LOCAL_DEV", "false").lower() == "true",
            commercial_mode=os.getenv("COMMERCIAL_MODE", "false").lower() == "true",
            commercial_agreement_reference=os.getenv(
                "COMMERCIAL_AGREEMENT_REFERENCE", ""
            ),
            global_daily_requests=int(os.getenv("GLOBAL_DAILY_REQUESTS", "100")),
            global_daily_usd_limit=os.getenv("GLOBAL_DAILY_USD_LIMIT", "5.00"),
            static_dir=os.getenv(
                "STATIC_DIR", cls.__dataclass_fields__["static_dir"].default
            ),
        )

    def validate(self):
        from decimal import Decimal

        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use PostgreSQL with psycopg")
        try:
            Fernet(self.encryption_key.encode())
        except (ValueError, TypeError):
            raise ValueError(
                "DATA_ENCRYPTION_KEY must be a securely generated persistent Fernet key"
            ) from None
        origin = urlsplit(self.public_base_url)
        if (
            (
                origin.scheme != "https"
                and not (
                    self.local_dev
                    and origin.scheme == "http"
                    and origin.hostname in ("127.0.0.1", "localhost")
                )
            )
            or not origin.hostname
            or origin.username
            or origin.password
            or origin.path
            or origin.query
            or origin.fragment
        ):
            raise ValueError(
                "PUBLIC_BASE_URL must be an HTTPS origin; LOCAL_DEV permits loopback HTTP only"
            )
        if self.nvidia_api_key and any(
            not 33 <= ord(c) <= 126 for c in self.nvidia_api_key
        ):
            raise ValueError(
                "NVIDIA_API_KEY must contain printable ASCII without whitespace"
            )
        if (
            self.commercial_mode
            and len(self.commercial_agreement_reference.strip()) < 12
        ):
            raise ValueError(
                "Commercial mode needs a verified NVIDIA service agreement reference"
            )
        if (
            not 1 <= self.global_daily_requests <= 10000
            or Decimal(self.global_daily_usd_limit) <= 0
        ):
            raise ValueError("Invalid server spending limits")

    @property
    def cookie_name(self):
        return "mgai_session" if self.local_dev else "__Host-mgai_session"
