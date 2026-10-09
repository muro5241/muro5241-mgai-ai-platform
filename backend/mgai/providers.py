"""Explicit capability boundaries; media adapters are not implemented in this MVP."""

from dataclasses import dataclass
from typing import Protocol

import httpx

NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"


@dataclass
class ProviderError(Exception):
    code: str
    message: str
    uncertain: bool = False
    retry_after: int | None = None


class TextProvider(Protocol):
    async def models(self) -> set[str]: ...
    async def generate(self, model: str, payload: dict) -> dict: ...


class MediaProvider(Protocol):
    """Future implementations need private storage, signed delivery and modality quotas."""

    async def submit(self, model: str, modality: str, payload: dict) -> str: ...
    async def status(self, task_id: str) -> dict: ...


class NvidiaProvider:
    def __init__(self, settings, client):
        self.key = settings.nvidia_api_key
        self.client = client

    async def _request(self, method, path, payload=None):
        if not self.key:
            raise ProviderError(
                "not_configured", "NVIDIA API anahtarı sunucuda tanımlı değil."
            )
        try:
            response = await self.client.request(
                method,
                NVIDIA_BASE + path,
                headers={
                    "Authorization": "Bearer " + self.key,
                    "Accept": "application/json",
                },
                json=payload,
                timeout=httpx.Timeout(60, connect=10),
                follow_redirects=False,
            )
        except httpx.TimeoutException:
            raise ProviderError(
                "timeout",
                "NVIDIA yanıtı doğrulanamadı; otomatik tekrar yapılmadı.",
                uncertain=method == "POST",
            ) from None
        except httpx.RequestError:
            raise ProviderError(
                "connection",
                "NVIDIA bağlantısı kurulamadı; otomatik tekrar yapılmadı.",
                uncertain=method == "POST",
            ) from None
        if response.status_code == 429:
            value = response.headers.get("retry-after", "60")
            retry = (
                min(3600, max(1, int(value)))
                if value.isascii() and value.isdigit() and len(value) < 10
                else 60
            )
            raise ProviderError(
                "rate_limit",
                "NVIDIA hesap kotası veya hız sınırı doldu.",
                retry_after=retry,
            )
        if response.status_code in (401, 403):
            raise ProviderError(
                "credentials", "NVIDIA anahtarı veya model yetkisi doğrulanamadı."
            )
        if response.status_code != 200:
            raise ProviderError(
                "upstream",
                "NVIDIA isteği tamamlanamadı.",
                uncertain=method == "POST" and response.status_code >= 500,
            )
        if len(response.content) > 1_000_000:
            raise ProviderError(
                "invalid_response",
                "NVIDIA yanıtı sınırları aşıyor.",
                uncertain=method == "POST",
            )
        try:
            return response.json()
        except ValueError:
            raise ProviderError(
                "invalid_response",
                "NVIDIA yanıtı çözümlenemedi.",
                uncertain=method == "POST",
            ) from None

    async def models(self):
        data = await self._request("GET", "/models")
        try:
            return {m["id"] for m in data["data"] if isinstance(m["id"], str)}
        except (KeyError, TypeError):
            raise ProviderError(
                "invalid_response", "NVIDIA model listesi doğrulanamadı."
            ) from None

    async def generate(self, model, payload):
        data = await self._request(
            "POST", "/chat/completions", {"model": model, **payload, "stream": False}
        )
        try:
            choice = data["choices"][0]
            content = choice["message"]["content"]
            finish = choice["finish_reason"]
            if (
                not isinstance(content, str)
                or not content.strip()
                or len(content) > 32000
                or finish not in ("stop", "length")
            ):
                raise ValueError()
            usage = data.get("usage")
            if usage is not None:
                if not isinstance(usage, dict) or any(
                    type(usage.get(k)) is not int or not 0 <= usage[k] <= 1_000_000
                    for k in ("prompt_tokens", "completion_tokens")
                ):
                    raise ValueError()
                usage = {k: usage[k] for k in ("prompt_tokens", "completion_tokens")}
            return {
                "content": content,
                "model": model,
                "usage": usage,
                "truncated": finish == "length",
            }
        except (KeyError, IndexError, TypeError, AttributeError, ValueError):
            raise ProviderError(
                "invalid_response",
                "NVIDIA geçerli bir metin yanıtı döndürmedi.",
                uncertain=True,
            ) from None
