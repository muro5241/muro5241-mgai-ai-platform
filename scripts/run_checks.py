"""Use a disposable real PostgreSQL container by default; never substitute SQLite."""

import argparse
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psycopg

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument(
    "--external",
    action="store_true",
    help="CI PostgreSQL only; database name must start with mgai_test",
)
parser.add_argument(
    "--backend-only",
    action="store_true",
    help="Frontend must already be built for browser tests",
)
args = parser.parse_args()
env = {**os.environ}
container = None
docker = ["docker"]
if os.getenv("MGAI_DOCKER_CONFIG"):
    docker += ["--config", os.environ["MGAI_DOCKER_CONFIG"]]
try:
    if args.external:
        owner = env["MGAI_TEST_ADMIN_DATABASE_URL"]
        url = env["MGAI_TEST_DATABASE_URL"]
        from sqlalchemy.engine import make_url

        if not make_url(owner).database.startswith("mgai_test") or not make_url(
            url
        ).database.startswith("mgai_test"):
            raise SystemExit("Refusing non-test external database")
        app_password = make_url(url).password
    else:
        container = "mgai-checks-" + secrets.token_hex(5)
        password, app_password = secrets.token_urlsafe(30), secrets.token_urlsafe(30)
        with tempfile.TemporaryDirectory(prefix="mgai-postgres-") as directory:
            path = Path(directory) / "db.env"
            fd = os.open(path, os.O_CREAT | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(
                    f"POSTGRES_USER=mgai_owner\nPOSTGRES_DB=mgai_test\nPOSTGRES_PASSWORD={password}\n"
                )
            subprocess.run(
                docker
                + [
                    "run",
                    "-d",
                    "--name",
                    container,
                    "--env-file",
                    str(path),
                    "-p",
                    "127.0.0.1::5432",
                    "postgres:17-bookworm",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
            )
        port = subprocess.check_output(
            docker
            + [
                "inspect",
                "--format",
                '{{(index (index .NetworkSettings.Ports "5432/tcp") 0).HostPort}}',
                container,
            ],
            text=True,
        ).strip()
        owner = f"postgresql+psycopg://mgai_owner:{password}@127.0.0.1:{port}/mgai_test"
        url = f"postgresql+psycopg://mgai_app:{app_password}@127.0.0.1:{port}/mgai_test"
    for _ in range(100):
        try:
            with psycopg.connect(
                owner.replace("postgresql+psycopg://", "postgresql://"),
                connect_timeout=1,
            ):
                pass
            break
        except psycopg.OperationalError:
            time.sleep(0.2)
    else:
        raise SystemExit("PostgreSQL did not become ready")
    env.update(
        DATABASE_URL=owner,
        APP_DB_PASSWORD=app_password,
        MGAI_TEST_DATABASE_URL=url,
        MGAI_TEST_ADMIN_DATABASE_URL=owner,
    )
    subprocess.run(
        [sys.executable, "-m", "mgai.migrate"],
        cwd=root / "backend",
        env=env,
        check=True,
    )
    if not args.backend_only:
        for command in (["npm", "ci"], ["npm", "run", "build"], ["npm", "test"]):
            subprocess.run(command, cwd=root / "frontend", env=env, check=True)
    subprocess.run(
        [sys.executable, "-m", "ruff", "check", "."],
        cwd=root / "backend",
        env=env,
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        cwd=root / "backend",
        env=env,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--cov=mgai",
            "--cov-report=term-missing",
            "--cov-fail-under=85",
        ],
        cwd=root / "backend",
        env=env,
        check=True,
    )
finally:
    if container:
        subprocess.run(
            docker + ["rm", "-f", "-v", container],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
