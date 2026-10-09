import json
import os
import secrets
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
from cryptography.fernet import Fernet

root = Path(__file__).resolve().parents[1]
docker = ["docker"]
if os.getenv("MGAI_DOCKER_CONFIG"):
    docker += ["--config", os.environ["MGAI_DOCKER_CONFIG"]]
project = "mgai-smoke-" + secrets.token_hex(4)
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
base = f"http://127.0.0.1:{port}"
with tempfile.TemporaryDirectory(prefix="mgai-compose-") as directory:
    path = Path(directory)
    pg = path / "pgdata"
    pg.mkdir()
    password, app_password, admin_password = (
        secrets.token_urlsafe(30),
        secrets.token_urlsafe(30),
        secrets.token_urlsafe(24),
    )
    envfile = path / "runtime.env"
    fd = os.open(envfile, os.O_CREAT | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(
            f"POSTGRES_PASSWORD={password}\nAPP_DB_PASSWORD={app_password}\nMIGRATION_DATABASE_URL=postgresql+psycopg://mgai_owner:{password}@postgres:5432/mgai\nDATABASE_URL=postgresql+psycopg://mgai_app:{app_password}@postgres:5432/mgai\nDATA_ENCRYPTION_KEY={Fernet.generate_key().decode()}\nPUBLIC_BASE_URL={base}\nLOCAL_DEV=true\nNVIDIA_API_KEY=\nCOMMERCIAL_MODE=false\n"
        )
    override = path / "override.yaml"
    override.write_text(
        "services:\n  postgres:\n    volumes:\n      - type: bind\n        source: "
        + str(pg)
        + '\n        target: /var/lib/postgresql/data\n  api:\n    ports: !override ["127.0.0.1:'
        + str(port)
        + ':8000"]\n'
    )
    compose = docker + [
        "compose",
        "--project-name",
        project,
        "--env-file",
        str(envfile),
        "-f",
        str(root / "compose.yaml"),
        "-f",
        str(override),
    ]
    try:
        with open("/tmp/mgai-compose-smoke.log", "w") as log:
            subprocess.run(
                compose + ["up", "-d", "--no-build", "--wait", "--wait-timeout", "120"],
                check=True,
                stdout=log,
                stderr=subprocess.STDOUT,
                cwd=root,
            )
        r = subprocess.run(
            compose
            + [
                "exec",
                "-T",
                "api",
                "python",
                "-m",
                "mgai.bootstrap",
                "--email",
                "smoke@example.test",
                "--name",
                "Smoke Admin",
                "--password-file",
                "/dev/stdin",
            ],
            input=admin_password.encode(),
            check=True,
            capture_output=True,
        )
        with httpx.Client(base_url=base) as client:
            assert client.get("/ready").json() == {
                "ready": True,
                "database": True,
                "worker": True,
                "nvidia_configured": False,
            }
            html = client.get("/")
            assert html.status_code == 200 and "MGAI AI Platform" in html.text
            assert (
                client.post(
                    "/api/auth/login",
                    headers={"Origin": base},
                    json={"email": "smoke@example.test", "password": admin_password},
                ).status_code
                == 200
            )
            session = client.get("/api/auth/me").json()
            assert session["user"]["role"] == "admin"
            headers = {
                "Origin": base,
                "X-CSRF-Token": session["csrf_token"],
                "Idempotency-Key": "container-smoke-key-0001",
            }
            created = client.post(
                "/api/workspaces",
                headers=headers,
                json={
                    "name": "Container Workspace",
                    "description": "Independent smoke test",
                },
            )
            assert created.status_code == 201
            workspace_id = created.json()["id"]
            result = client.post(
                "/api/jobs",
                headers=headers,
                json={
                    "workspace_id": workspace_id,
                    "model_id": "nvidia/llama-3.1-nemotron-70b-instruct",
                    "messages": [
                        {"role": "user", "content": "No provider key available"}
                    ],
                },
            )
            assert result.status_code == 503 and client.get("/api/jobs").json() == []
            assert client.get("/api/admin/overview").status_code == 200
        api_id = subprocess.check_output(
            compose + ["ps", "-q", "api"], text=True
        ).strip()
        inspect = json.loads(
            subprocess.check_output(docker + ["inspect", api_id], text=True)
        )[0]
        assert (
            inspect["Config"]["User"] == "10001:10001"
            and inspect["HostConfig"]["ReadonlyRootfs"]
        )
        runtime_keys = {e.split("=", 1)[0] for e in inspect["Config"]["Env"]}
        assert not runtime_keys.intersection(
            {"APP_DB_PASSWORD", "MIGRATION_DATABASE_URL", "POSTGRES_PASSWORD"}
        )
        subprocess.run(
            compose + ["restart", "api", "worker"], check=True, capture_output=True
        )
        with httpx.Client(base_url=base) as client:
            for _ in range(100):
                try:
                    if client.get("/ready").status_code == 200:
                        break
                except httpx.RequestError:
                    pass
                time.sleep(0.2)
            else:
                raise RuntimeError("Restart did not become ready")
            assert (
                client.post(
                    "/api/auth/login",
                    headers={"Origin": base},
                    json={"email": "smoke@example.test", "password": admin_password},
                ).status_code
                == 200
            )
            assert any(
                w["id"] == workspace_id for w in client.get("/api/workspaces").json()
            )
        print(
            "Compose PostgreSQL/migrations/worker/API/frontend/admin/login/workspace PASS"
        )
        print("No-key generation rejects honestly; no vendor call PASS")
        print("Non-root/read-only runtime and owner-credential isolation PASS")
        print("API/worker restart with persistent PostgreSQL workspace PASS")
    except Exception as exc:
        print("::error::" + str(exc).replace("\n", " "))
        for line in Path("/tmp/mgai-compose-smoke.log").read_text().splitlines()[-30:]:
            print("::error::" + line)
        # Logs contain service diagnostics, never an environment dump.
        print(Path("/tmp/mgai-compose-smoke.log").read_text())
        logs = subprocess.run(
            compose + ["logs", "--tail", "30"],
            check=False,
            capture_output=True,
            text=True,
        )
        for line in logs.stdout.splitlines()[-60:]:
            print("::error::" + line)
        raise
    finally:
        subprocess.run(
            compose + ["down", "-v", "--remove-orphans"],
            check=False,
            capture_output=True,
        )
        # This unique directory contains only generated smoke-test data. Remove it via
        # a root container because PostgreSQL owns its files; never touch real volumes.
        subprocess.run(
            docker
            + [
                "run",
                "--rm",
                "--user",
                "0",
                "--entrypoint",
                "sh",
                "-v",
                str(pg) + ":/cleanup",
                "postgres:17-bookworm",
                "-c",
                "find /cleanup -mindepth 1 -maxdepth 1 -exec rm -rf {} +",
            ],
            check=False,
            capture_output=True,
        )
