"""Optional real provider call: consumes account credits; never uses a fake key."""

import asyncio
import os

import httpx
import pytest

from mgai.providers import NvidiaProvider
from mgai.registry import DEFAULT_MODEL_ID, generation_options


@pytest.mark.skipif(
    not os.getenv("NVIDIA_API_KEY") or os.getenv("RUN_LIVE_NVIDIA") != "1",
    reason="Real NVIDIA generation needs secure NVIDIA_API_KEY and explicit RUN_LIVE_NVIDIA=1",
)
def test_real_nvidia_generation_once():
    # Other settings are not read by the provider; no fake auth or database is involved.
    class ProviderSettings:
        nvidia_api_key = os.environ.get("NVIDIA_API_KEY", "")

    async def run():
        async with httpx.AsyncClient() as client:
            provider = NvidiaProvider(ProviderSettings(), client)
            available = await provider.models()
            model = os.getenv("LIVE_NVIDIA_MODEL", DEFAULT_MODEL_ID)
            assert model in available, "Model is absent from the current live catalog"
            return await provider.generate(
                model,
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": "Türkçe üç cümleyle bileşik faizi ve riskini açıkla. Güncel veri uydurma.",
                        }
                    ],
                    "max_tokens": 128,
                    "temperature": 0.2,
                    "top_p": 0.9,
                    **generation_options(model),
                },
            )

    result = asyncio.run(run())
    assert result["content"].strip()
