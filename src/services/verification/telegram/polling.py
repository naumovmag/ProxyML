import asyncio
import contextlib
import logging
import uuid

import httpx

from src.db.engine import async_session_factory
from src.services.verification.telegram.linking import process_telegram_start

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


class TelegramPollingManager:
    """Manages long-polling asyncio tasks per telegram verification channel."""

    def __init__(self) -> None:
        self._tasks: dict[uuid.UUID, asyncio.Task] = {}

    async def start(self, channel_id: uuid.UUID, bot_token: str) -> None:
        """Start polling task for a channel (idempotent)."""
        if channel_id in self._tasks and not self._tasks[channel_id].done():
            return
        task = asyncio.create_task(self._run(channel_id, bot_token))
        self._tasks[channel_id] = task
        logger.info("Telegram polling started for channel %s", channel_id)

    async def stop(self, channel_id: uuid.UUID) -> None:
        task = self._tasks.pop(channel_id, None)
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        logger.info("Telegram polling stopped for channel %s", channel_id)

    async def stop_all(self) -> None:
        for cid in list(self._tasks.keys()):
            await self.stop(cid)

    async def _run(self, channel_id: uuid.UUID, bot_token: str) -> None:
        """Long-polling loop for a single channel."""
        offset = 0
        backoff = 1
        async with httpx.AsyncClient(timeout=35.0) as client:
            while True:
                try:
                    resp = await client.post(
                        f"{TELEGRAM_API}/bot{bot_token}/getUpdates",
                        json={"offset": offset, "timeout": 25, "allowed_updates": ["message"]},
                    )
                    data = resp.json()
                    if not data.get("ok"):
                        desc = data.get("description", "")
                        logger.error("Telegram polling error for channel %s: %s", channel_id, desc)
                        if "Conflict" in desc or "webhook" in desc.lower():
                            logger.error(
                                "Stopping polling for channel %s due to conflict", channel_id
                            )
                            return
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 30)
                        continue
                    backoff = 1
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        await self._process_update(channel_id, update)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.exception(
                        "Telegram polling loop error for channel %s: %s", channel_id, e
                    )
                    await asyncio.sleep(min(backoff, 30))
                    backoff = min(backoff * 2, 30)

    async def _process_update(self, channel_id: uuid.UUID, update: dict) -> None:
        message = update.get("message", {})
        text = message.get("text", "")
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        if not text.startswith("/start ") or not chat_id:
            return
        code = text.split(" ", 1)[1].strip()
        if not code:
            return
        async with async_session_factory() as session:
            try:
                await process_telegram_start(session, chat_id, code)
            except Exception as e:
                logger.exception("process_telegram_start failed: %s", e)


# Module-level singleton (lifetime = application process)
telegram_polling_manager = TelegramPollingManager()
