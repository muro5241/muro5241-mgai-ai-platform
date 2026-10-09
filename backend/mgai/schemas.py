from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Strict(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}


class Login(Strict):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128, repr=False)
    # Password whitespace is meaningful. Never strip it before hashing.
    model_config = {"extra": "forbid", "str_strip_whitespace": False}


class Register(Login):
    name: str = Field(min_length=2, max_length=80)
    invitation: str = Field(min_length=20, max_length=100, repr=False)


class PasswordChange(Strict):
    current_password: str = Field(min_length=12, max_length=128, repr=False)
    new_password: str = Field(min_length=12, max_length=128, repr=False)
    model_config = {"extra": "forbid", "str_strip_whitespace": False}


class WorkspaceCreate(Strict):
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=500)


class Message(Strict):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class Generate(Strict):
    workspace_id: str = Field(min_length=36, max_length=36)
    model_id: str = Field(min_length=3, max_length=150)
    messages: list[Message] = Field(min_length=1, max_length=12)
    max_tokens: int = Field(default=1024, ge=64, le=2048)
    temperature: float = Field(default=0.5, ge=0, le=1)
    kind: Literal["text", "chat"] = "text"

    @model_validator(mode="after")
    def bounded(self):
        if (
            sum(len(m.content) for m in self.messages) > 12000
            or self.messages[-1].role != "user"
        ):
            raise ValueError(
                "Messages must end with a user message and total at most 12000 characters"
            )
        return self


class Invite(Strict):
    email: str = Field(min_length=3, max_length=254)


class UserUpdate(Strict):
    active: bool | None = None
    role: Literal["admin", "member"] | None = None
    daily_request_limit: int | None = Field(default=None, ge=1, le=1000)
    daily_token_limit: int | None = Field(default=None, ge=2048, le=1_000_000)


class CreditGrant(Strict):
    amount: int = Field(ge=1, le=10000)
    reason: str = Field(min_length=5, max_length=200)


class ModelUpdate(Strict):
    enabled: bool | None = None
    commercial_approved: bool | None = None
    price_input: Decimal | None = Field(default=None, ge=0, le=1000)
    price_output: Decimal | None = Field(default=None, ge=0, le=1000)
    pricing_reference: str | None = Field(default=None, min_length=12, max_length=500)
