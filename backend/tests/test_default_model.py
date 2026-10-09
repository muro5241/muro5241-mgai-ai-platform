import asyncio

from conftest import request_body
from sqlalchemy import create_engine, select

from mgai.models import Job, Model
from mgai.registry import DEFAULT_MODEL_ID, RETIRED_MODEL_IDS, seed
from mgai.worker import process_one


def test_api_and_omitted_selection_use_verified_default(
    client, auth, db, settings, vendor
):
    models = client.get("/api/models").json()
    assert models[0]["id"] == DEFAULT_MODEL_ID
    assert models[0]["is_default"] is True
    assert models[0]["access_verified"] is False  # Do not manufacture live evidence.
    body = request_body(client)
    del body["model_id"]
    response = client.post("/api/jobs", headers=auth, json=body)
    assert response.status_code == 202
    assert response.json()["model_id"] == DEFAULT_MODEL_ID
    assert asyncio.run(process_one(db, settings, client.app.state.provider))
    import json

    payload = json.loads(vendor.requests[-1].content)
    assert payload["model"] == DEFAULT_MODEL_ID
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}


def test_old_model_stays_disabled_and_history_is_preserved(client, auth, db):
    body = request_body(client)
    response = client.post("/api/jobs", headers=auth, json=body)
    assert response.status_code == 202
    job_id = response.json()["id"]
    old_id = RETIRED_MODEL_IDS[0]
    with db.sessions.begin() as session:
        session.add(
            Model(
                id=old_id,
                name="Legacy 70B",
                license_name="Llama 3.1",
                license_url="https://example.test/license",
            )
        )
        session.flush()
        session.get(Job, job_id).model_id = old_id
    seed(db)
    seed(db)
    with db.sessions() as session:
        assert session.get(Model, old_id).enabled is False
        assert session.get(Job, job_id).model_id == old_id
        assert (
            len(
                session.scalars(select(Model).where(Model.id == DEFAULT_MODEL_ID)).all()
            )
            == 1
        )
    assert old_id not in {m["id"] for m in client.get("/api/models").json()}
    body["model_id"] = old_id
    headers = {**auth, "Idempotency-Key": "retired-model-request-0001"}
    assert client.post("/api/jobs", headers=headers, json=body).status_code == 422
    # Even a stale operator action cannot make the retired endpoint dispatchable.
    with db.sessions.begin() as session:
        session.get(Model, old_id).enabled = True
    assert client.post("/api/jobs", headers=headers, json=body).status_code == 422


def test_populated_initial_schema_upgrades_without_deleting_model(
    database_urls, tmp_path, monkeypatch
):
    # A dedicated real PostgreSQL database; never downgrade the app/test database.
    import secrets

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from sqlalchemy.engine import make_url

    name = "mgai_test_migration_" + secrets.token_hex(5)
    owner = make_url(database_urls[1])
    admin = create_engine(owner, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    migration_url = owner.set(database=name)
    monkeypatch.setenv(
        "DATABASE_URL", migration_url.render_as_string(hide_password=False)
    )
    engine = create_engine(migration_url)
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "3485dbc0c4b1")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO models (id,name,provider,license_name,license_url,enabled,access_verified,commercial_approved) VALUES (:id,'Legacy','nvidia','Llama','https://example.test',true,false,false)"
                ),
                {"id": RETIRED_MODEL_IDS[0]},
            )
        command.upgrade(config, "head")
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT enabled,catalog_present FROM models WHERE id=:id"),
                {"id": RETIRED_MODEL_IDS[0]},
            ).one()
            assert row == (False, False)
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()
