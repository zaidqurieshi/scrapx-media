"""Telethon client wrapper with secure session management and reconnection."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

from telethon import TelegramClient, errors
from telethon.sessions import StringSession

from config.settings import Settings

logger = logging.getLogger("scrapx.client")


class TelegramClientManager:
    """Encapsulates Telethon client lifecycle, authentication, and entity resolution."""

    def __init__(self, settings: Settings):
        self.settings = settings
        if settings.telegram_string_session:
            session_target = StringSession(settings.telegram_string_session)
            self.session_path = Path("string_session")
            logger.info("Using Telethon StringSession from environment variable.")
        else:
            self.session_path = self._resolve_session_path(settings.telegram_session_name)
            session_target = str(self.session_path)

        self.client = TelegramClient(
            session_target,
            api_id=settings.telegram_api_id,
            api_hash=settings.telegram_api_hash,
            connection_retries=10,
            retry_delay=5,
            auto_reconnect=True,
        )
        self._resolved_entities: Dict[Union[int, str], Any] = {}

    def _resolve_session_path(self, session_name: str) -> Path:
        """Stores session file securely inside data directory."""
        data_dir = Path(self.settings.database_path).parent
        data_dir.mkdir(parents=True, exist_ok=True)
        # If session_name is already a path, use it; otherwise place in data_dir
        if "/" in session_name or "\\" in session_name:
            return Path(session_name)
        return data_dir / session_name

    async def start(self) -> TelegramClient:
        """Starts the Telethon client, prompting for phone/code if not yet authorized."""
        logger.info("Initializing Telegram client (Session: %s)...", self.session_path.name)
        await self.client.start()
        me = await self.client.get_me()
        user_display = f"{me.first_name} (@{me.username})" if me.username else me.first_name
        logger.info("Successfully authenticated Telegram client as: %s (ID: %s)", user_display, me.id)
        return self.client

    async def resolve_entity(self, target: Union[int, str]) -> Any:
        """Resolves a channel handle or ID to a Telegram peer entity with caching."""
        if target in self._resolved_entities:
            return self._resolved_entities[target]

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                entity = await self.client.get_entity(target)
                self._resolved_entities[target] = entity
                logger.info("Resolved entity '%s' -> %s (ID: %s)", target, getattr(entity, 'title', 'Channel'), entity.id)
                return entity
            except errors.FloodWaitError as e:
                logger.warning("FloodWait of %d seconds while resolving %s", e.seconds, target)
                await asyncio.sleep(e.seconds + 1)
            except Exception as e:
                logger.error("Attempt %d/%d failed to resolve entity '%s': %s", attempt, max_retries, target, e)
                if attempt == max_retries:
                    raise
                await asyncio.sleep(2)

    async def stop(self) -> None:
        """Gracefully disconnects the client."""
        if self.client.is_connected():
            logger.info("Disconnecting Telegram client...")
            await self.client.disconnect()
            logger.info("Telegram client disconnected.")

