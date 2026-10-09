import json
import os
from pathlib import Path

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from mgai.app import create_app
from mgai.bootstrap import create_admin
from mgai.config import Settings
from mgai.database import Database
from mgai.models import Base, User, Workspace
from mgai.registry import MODELS, seed
from mgai.security import PASSWORDS

BASE = "https://mgai.example.test"
PASSWORD = "test-password-only-2026"
MODEL = MODELS[0]["id"]


@pytest.fixture(scope="session")
def database_urls():
    url, owner = (
        os.getenv("MGAI_TEST_DATABASE_URL"),
        os.getenv("MGAI_TEST_ADMIN_DATABASE_URL"),
    )
    if not url or not owner:
        path = Path("/workspace/.mgai-local/database.json")
        if not path.is_file():
            pytest.fail(
                "Real PostgreSQL required: run scripts/run_checks.py or set MGAI_TEST_*_DATABASE_URL"
            )
        config = json.loads(path.read_text())
        url, owner = config["database_url"], config["owner_url"]
    return url, owner


@pytest.fixture
def clean_database(database_urls):
    engine = create_engine(database_urls[1])
    names = ",".join('"' + table.name + '"' for table in Base.metadata.sorted_tables)
    with engine.begin() as c:
        c.execute(text("TRUNCATE " + names + " RESTART IDENTITY CASCADE"))
    engine.dispose()


@pytest.fixture
def settings(database_urls, clean_database):
    return Settings(
        database_url=database_urls[0],
        encryption_key=Fernet.generate_key().decode(),
        public_base_url=BASE,
        nvidia_api_key="test-provider-api-key",
    )


@pytest.fixture
def db(settings):
    db = Database(settings)
    seed(db)
    yield db
    db.close()


@pytest.fixture
def admin(db):
    return create_admin(db, "admin@example.test", "Test Admin", PASSWORD)


@pytest.fixture
def member(db):
    with db.sessions.begin() as s:
        user = User(
            email="member@example.test",
            name="Test Member",
            role="member",
            password_hash=PASSWORDS.hash(PASSWORD),
        )
        s.add(user)
        s.flush()
        workspace = Workspace(owner_id=user.id, name="Member Workspace")
        s.add(workspace)
        s.flush()
        return user.id, workspace.id


class FakeNvidia:
    """Simulated vendor contract; never live NVIDIA evidence."""

    def __init__(self):
        self.requests = []
        self.response = httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": "Bu bir test yanıtıdır; gerçek NVIDIA üretimi değildir."
                        },
                    }
                ],
                "usage": {"prompt_tokens": 80, "completion_tokens": 30},
            },
        )

    def handler(self, request):
        assert (
            request.url.host == "integrate.api.nvidia.com"
            and request.url.scheme == "https"
        )
        assert request.headers["authorization"] == "Bearer test-provider-api-key"
        self.requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": MODEL}]})
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["stream"] is False and 64 <= payload["max_tokens"] <= 2048
        assert payload["messages"][0]["role"] == "system"
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.fixture
def vendor():
    return FakeNvidia()


@pytest.fixture
def app(settings, vendor):
    return create_app(
        settings, httpx.AsyncClient(transport=httpx.MockTransport(vendor.handler))
    )


@pytest.fixture
def client(app, admin):
    with TestClient(app, base_url=BASE, follow_redirects=False) as client:
        yield client


def login(client, address="admin@example.test"):
    r = client.post(
        "/api/auth/login",
        headers={"Origin": BASE},
        json={"email": address, "password": PASSWORD},
    )
    assert r.status_code == 200, r.text
    data = client.get("/api/auth/me").json()
    return {
        "Origin": BASE,
        "X-CSRF-Token": data["csrf_token"],
        "Idempotency-Key": "test-request-key-0001",
    }


@pytest.fixture
def auth(client):
    return login(client)


def request_body(client, **updates):
    workspace = client.get("/api/workspaces").json()[0]["id"]
    return {
        "workspace_id": workspace,
        "model_id": MODEL,
        "messages": [
            {"role": "user", "content": "Türkçe kısa bir finans eğitimi senaryosu yaz."}
        ],
        **updates,
    }


def enqueue(client, auth, **updates):
    return client.post("/api/jobs", headers=auth, json=request_body(client, **updates))
