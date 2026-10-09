import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.engine import make_url

from mgai.config import Settings

ROOT = Path(__file__).resolve().parents[2]


def clear_config(monkeypatch):
    for key in (
        "DATABASE_URL",
        "DATA_ENCRYPTION_KEY",
        "DATA_ENCRYPTION_SECRET",
        "PUBLIC_BASE_URL",
        "RENDER_EXTERNAL_URL",
        "PGHOST",
        "MGAI_DB_APP_PASSWORD",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "synthetic-config-test-key")


def test_render_runtime_uses_app_role_and_actual_https_origin(monkeypatch):
    clear_config(monkeypatch)
    secret = "synthetic-encryption-test-secret-32-chars"
    password = "synthetic/app@password:with+symbols"
    monkeypatch.setenv("PGHOST", "private-db.example.test")
    monkeypatch.setenv("PGDATABASE", "mgai")
    monkeypatch.setenv("MGAI_DB_APP_PASSWORD", password)
    monkeypatch.setenv("DATA_ENCRYPTION_SECRET", secret)
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://assigned.example.test/")
    settings = Settings.from_env()
    settings.validate()
    url = make_url(settings.database_url)
    assert url.username == "mgai_app" and url.password == password
    assert url.query["sslmode"] == "require"
    assert settings.public_base_url == "https://assigned.example.test"
    assert settings.cookie_name == "__Host-mgai_session"
    assert settings.encryption_key == Settings.from_env().encryption_key
    assert Fernet(settings.encryption_key.encode())
    assert secret not in repr(settings) and password not in repr(settings)
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://custom.example.test")
    assert Settings.from_env().public_base_url == "https://custom.example.test"


def test_managed_url_and_existing_fernet_key_are_preserved(monkeypatch):
    clear_config(monkeypatch)
    key = Fernet.generate_key().decode()
    monkeypatch.setenv(
        "DATABASE_URL", "postgres://app:synthetic-password@localhost/mgai"
    )
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", key)
    monkeypatch.setenv("DATA_ENCRYPTION_SECRET", "ignored-when-explicit-key-is-present")
    settings = Settings.from_env()
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.encryption_key == key


def test_generated_secret_cannot_be_short(monkeypatch):
    clear_config(monkeypatch)
    monkeypatch.setenv("DATA_ENCRYPTION_SECRET", "too-short")
    with pytest.raises(ValueError, match="32 random"):
        Settings.from_env()


def test_production_generator_preserves_existing_keys_and_uses_private_file(tmp_path):
    output = tmp_path / "private.env"
    command = [
        sys.executable,
        str(ROOT / "scripts/init_production_env.py"),
        "--hostname",
        "mgai.actualdomain.com",
        "--email",
        "owner@actualdomain.com",
        "--output",
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0
    content = output.read_text()
    assert output.stat().st_mode & 0o777 == 0o600
    assert "LOCAL_DEV=false" in content and "NVIDIA_API_KEY=\n" in content
    values = dict(line.split("=", 1) for line in content.splitlines())
    assert Fernet(values["DATA_ENCRYPTION_KEY"].encode())
    assert values["DATA_ENCRYPTION_KEY"] not in result.stdout
    assert values["POSTGRES_PASSWORD"] not in result.stdout
    again = subprocess.run(command, capture_output=True, text=True)
    assert again.returncode != 0 and output.read_text() == content


def test_render_blueprint_keeps_owner_credentials_in_migration_task():
    import yaml

    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text())
    services = {item["name"]: item for item in blueprint["services"]}
    for name in ("mgai-api", "mgai-worker"):
        env = services[name]["envVars"]
        assert not any(
            e.get("key")
            in {"DATABASE_URL", "MIGRATION_DATABASE_URL", "POSTGRES_PASSWORD"}
            for e in env
        )
        assert not any(
            e.get("fromDatabase", {}).get("property")
            in {"connectionString", "password", "user"}
            for e in env
        )
        assert any(
            e.get("key") == "NVIDIA_API_KEY" and e.get("sync") is False for e in env
        )
    assert services["mgai-api"]["healthCheckPath"] == "/ready"
    assert services["mgai-worker"]["dockerCommand"] == "python -m mgai.worker"
    assert (
        services["mgai-migrations"]["envVars"][0]["fromDatabase"]["property"]
        == "connectionString"
    )
    assert blueprint["databases"][0]["ipAllowList"] == []
    assert all(service["autoDeploy"] is False for service in services.values())
