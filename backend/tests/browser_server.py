"""Loopback test server only: real PostgreSQL/worker/UI, mocked NVIDIA contract."""

import asyncio
import os
from contextlib import asynccontextmanager, suppress

import httpx
from conftest import PASSWORD, FakeNvidia

from mgai.app import create_app
from mgai.bootstrap import create_admin
from mgai.config import Settings
from mgai.worker import process_one

settings = Settings(
    database_url=os.environ["MGAI_TEST_DATABASE_URL"],
    encryption_key=os.environ["MGAI_TEST_ENCRYPTION_KEY"],
    public_base_url=os.environ["MGAI_TEST_ORIGIN"],
    nvidia_api_key="test-provider-api-key",
)
app = create_app(
    settings, httpx.AsyncClient(transport=httpx.MockTransport(FakeNvidia().handler))
)
original = app.router.lifespan_context


@asynccontextmanager
async def lifespan(app):
    async with original(app):
        create_admin(app.state.db, "admin@example.test", "Test Admin", PASSWORD)

        async def loop():
            while True:
                await process_one(app.state.db, settings, app.state.provider)
                await asyncio.sleep(0.1)

        task = asyncio.create_task(loop())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


app.router.lifespan_context = lifespan
