"""Generate local-only secrets. Existing files are never overwritten."""

import base64
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / ".env"
password, app_password = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
content = f"""POSTGRES_PASSWORD={password}
APP_DB_PASSWORD={app_password}
MIGRATION_DATABASE_URL=postgresql+psycopg://mgai_owner:{password}@postgres:5432/mgai
DATABASE_URL=postgresql+psycopg://mgai_app:{app_password}@postgres:5432/mgai
DATA_ENCRYPTION_KEY={key}
PUBLIC_BASE_URL=http://127.0.0.1:8080
LOCAL_DEV=true
NVIDIA_API_KEY=
COMMERCIAL_MODE=false
COMMERCIAL_AGREEMENT_REFERENCE=
GLOBAL_DAILY_REQUESTS=100
GLOBAL_DAILY_USD_LIMIT=5.00
FORWARDED_ALLOW_IPS=127.0.0.1
"""
try:
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
except FileExistsError:
    raise SystemExit(
        "Existing .env preserved; use host secret settings or edit your protected local file."
    ) from None
with os.fdopen(fd, "w") as output:
    output.write(content)
print(
    "Local .env generated with mode 0600. No NVIDIA key or administrator password was invented."
)
