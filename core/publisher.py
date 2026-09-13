"""Handles content publication to ScrapX Media without forward headers."""
from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any, List, Optional, Sequence

from telethon import TelegramClient, errors
from telethon.tl.custom.message import Message

logger = logging.getLogger("scrapx.publisher")


class MessagePublisher:
    """Publishes transformed news items to ScrapX Media."""

    def __init__(self, client: TelegramClient, destination_entity: Any, dry_run: bool = False):
        self.client = client
        self.destination = destination_entity
        self.dry_run = dry_run

    async def _execute_with_retry(self, coro_func, *args, **kwargs) -> Any:
        """Executes a Telegram API coroutine with automatic FloodWait handling."""
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            try:
                return await coro_func(*args, **kwargs)
            except errors.FloodWaitError as e:
                wait_time = e.seconds + 1
                logger.warning("FloodWait encountered: sleeping for %d seconds (attempt %d/%d)", wait_time, attempt, max_attempts)
                await asyncio.sleep(wait_time)
            except errors.RPCError as e:
                logger.error("Telegram RPC error on attempt %d: %s", attempt, e)
                if attempt == max_attempts:
                    raise
                await asyncio.sleep(2 * attempt)
            except Exception as e:
                logger.error("Unexpected error during publication on attempt %d: %s", attempt, e)
                if attempt == max_attempts:
                    raise
                await asyncio.sleep(2 * attempt)

    async def publish_text(self, text: str) -> Optional[int]:
        """Publishes a text-only message to ScrapX Media without forward headers."""
        if not text or not text.strip():
            logger.warning("Attempted to publish empty text message. Skipping.")
            return None

        if self.dry_run:
            logger.info("[DRY RUN] Would publish text to destination:\n%s", text)
            return 999999

        logger.info("Publishing text message to ScrapX Media (%d chars)...", len(text))
        sent = await self._execute_with_retry(
            self.client.send_message,
            entity=self.destination,
            message=text,
            link_preview=True,
        )
        logger.info("Successfully published text message (Dest ID: %s)", sent.id)
        return sent.id

    async def publish_single_media(self, message: Message, caption: Optional[str] = None) -> Optional[int]:
        """
        Publishes a single media item (photo, video, document) with an optional caption.
        Copies the content directly without generating a forward header.
        """
        if self.dry_run:
            logger.info("[DRY RUN] Would publish single media with caption:\n%s", caption or "<No Caption>")
            return 999999

        logger.info("Publishing single media to ScrapX Media (has caption: %s)...", bool(caption))
        caption_text = caption.strip() if caption and caption.strip() else None

        try:
            # First attempt: send media reference directly (fastest, preserves original file/quality)
            sent = await self._execute_with_retry(
                self.client.send_file,
                entity=self.destination,
                file=message.media,
                caption=caption_text,
            )
            logger.info("Successfully published single media (Dest ID: %s)", sent.id)
            return sent.id
        except Exception as err:
            logger.warning("Direct media reference send failed (%s). Falling back to download-and-upload...", err)
            with tempfile.TemporaryDirectory() as tmpdir:
                downloaded_file = await message.download_media(file=tmpdir)
                if not downloaded_file:
                    raise RuntimeError("Failed to download media for re-upload.")
                sent = await self._execute_with_retry(
                    self.client.send_file,
                    entity=self.destination,
                    file=downloaded_file,
                    caption=caption_text,
                )
                logger.info("Successfully published media via download fallback (Dest ID: %s)", sent.id)
                return sent.id

    async def publish_album(self, messages: Sequence[Message], caption: Optional[str] = None) -> Optional[int]:
        """
        Publishes a group of media items (album) as a unified publication.
        Ensures all media in the album are sent together rather than fragmented.
        """
        if not messages:
            return None

        if self.dry_run:
            logger.info(
                "[DRY RUN] Would publish album of %d media items with caption:\n%s",
                len(messages),
                caption or "<No Caption>",
            )
            return 999999

        logger.info("Publishing media album of %d items to ScrapX Media...", len(messages))
        caption_text = caption.strip() if caption and caption.strip() else None

        try:
            # Collect media objects
            media_list = [m.media for m in messages if m.media]
            if not media_list:
                logger.warning("No media found in album messages. Fallback to text.")
                if caption_text:
                    return await self.publish_text(caption_text)
                return None

            sent = await self._execute_with_retry(
                self.client.send_file,
                entity=self.destination,
                file=media_list,
                caption=caption_text,
            )
            # When Telethon sends an album, sent is a list of Message objects
            first_id = sent[0].id if isinstance(sent, list) and sent else getattr(sent, 'id', None)
            logger.info("Successfully published media album (Dest First ID: %s)", first_id)
            return first_id
        except Exception as err:
            logger.warning("Direct album send failed (%s). Falling back to download-and-upload album...", err)
            with tempfile.TemporaryDirectory() as tmpdir:
                downloaded_files = []
                for idx, m in enumerate(messages):
                    dest_path = Path(tmpdir) / f"media_{idx}"
                    f = await m.download_media(file=str(dest_path))
                    if f:
                        downloaded_files.append(f)

                if not downloaded_files:
                    raise RuntimeError("Failed to download any media for album fallback.")

                sent = await self._execute_with_retry(
                    self.client.send_file,
                    entity=self.destination,
                    file=downloaded_files,
                    caption=caption_text,
                )
                first_id = sent[0].id if isinstance(sent, list) and sent else getattr(sent, 'id', None)
                logger.info("Successfully published media album via fallback (Dest First ID: %s)", first_id)
                return first_id

