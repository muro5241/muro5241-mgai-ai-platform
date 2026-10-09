from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from .models import Control, Model

MODELS = [
    {
        "id": "nvidia/llama-3.1-nemotron-70b-instruct",
        "name": "Llama 3.1 Nemotron · 70B",
        "license_name": "Llama 3.1 Community License",
        "license_url": "https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/LICENSE",
    },
    {
        "id": "nvidia/llama-3.1-nemotron-51b-instruct",
        "name": "Llama 3.1 Nemotron · 51B",
        "license_name": "Llama 3.1 Community License",
        "license_url": "https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/LICENSE",
    },
]


def seed(db):
    with db.sessions.begin() as session:
        session.execute(insert(Control).values(id=1).on_conflict_do_nothing())
        for model in MODELS:
            session.execute(insert(Model).values(**model).on_conflict_do_nothing())


def list_models(session):
    return session.scalars(
        select(Model).where(Model.enabled.is_(True)).order_by(Model.name)
    ).all()
