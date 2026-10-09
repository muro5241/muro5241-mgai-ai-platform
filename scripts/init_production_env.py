"""Generate private Docker-host settings without copying NVIDIA credentials."""

import argparse
import base64
import os
import re
import secrets
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hostname", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / ".env.production",
    )
    args = parser.parse_args()
    host = args.hostname.lower()
    if not re.fullmatch(
        r"(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", host
    ) or host.endswith((".localhost", ".test", ".invalid", ".example")):
        parser.error("Actual public DNS hostname required, without scheme or path")
    if not re.fullmatch(r"[A-Za-z0-9._+%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", args.email):
        parser.error("Actual TLS contact email required")
    owner, app = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    content = f"""POSTGRES_PASSWORD={owner}
APP_DB_PASSWORD={app}
MIGRATION_DATABASE_URL=postgresql+psycopg://mgai_owner:{owner}@postgres:5432/mgai
DATABASE_URL=postgresql+psycopg://mgai_app:{app}@postgres:5432/mgai
DATA_ENCRYPTION_KEY={key}
PUBLIC_BASE_URL=https://{host}
MGAI_HOSTNAME={host}
MGAI_TLS_EMAIL={args.email}
LOCAL_DEV=false
NVIDIA_API_KEY=
COMMERCIAL_MODE=false
GLOBAL_DAILY_REQUESTS=100
GLOBAL_DAILY_USD_LIMIT=5.00
FORWARDED_ALLOW_IPS=172.30.86.10
"""
    try:
        fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise SystemExit(
            "Existing settings preserved; refusing to replace encryption keys"
        ) from None
    with os.fdopen(fd, "w") as output:
        output.write(content)
    print(
        "Private production configuration created (0600); NVIDIA key not copied or printed."
    )


if __name__ == "__main__":
    main()
