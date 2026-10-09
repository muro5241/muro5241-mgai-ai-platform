from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from .models import Control, Model

DEFAULT_MODEL_ID = "nvidia/nemotron-3-super-120b-a12b"
RETIRED_MODEL_IDS = ("nvidia/llama-3.1-nemotron-70b-instruct",)

MODELS = [
    {
        "id": DEFAULT_MODEL_ID,
        "name": "NVIDIA Nemotron 3 Super · 120B A12B",
        "license_name": "NVIDIA Nemotron Open Model License",
        "license_url": "https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-nemotron-open-model-license/",
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
        # Retain historical jobs and pricing; never dispatch new work to the 404 model.
        session.execute(
            update(Model).where(Model.id.in_(RETIRED_MODEL_IDS)).values(enabled=False)
        )
        for model in MODELS:
            session.execute(insert(Model).values(**model).on_conflict_do_nothing())


def list_models(session):
    return session.scalars(
        select(Model)
        .where(Model.enabled.is_(True), Model.id.not_in(RETIRED_MODEL_IDS))
        .order_by((Model.id == DEFAULT_MODEL_ID).desc(), Model.name)
    ).all()


def generation_options(model_id):
    # The real Turkish test used non-reasoning mode. Keep the bounded output budget
    # for visible text instead of consuming it on hidden reasoning.
    return (
        {"chat_template_kwargs": {"enable_thinking": False}}
        if model_id == DEFAULT_MODEL_ID
        else {}
    )
