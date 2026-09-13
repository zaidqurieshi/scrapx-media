"""Real-time event listener, album debouncer, and rule dispatcher."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from telethon import TelegramClient, events
from telethon.tl.custom.message import Message

from config.settings import Settings
from database.db_manager import DatabaseManager
from filters.base import BaseMessageFilter
from filters.faytuks import FaytuksFilter
from filters.first_squawk import FirstSquawkFilter
from .publisher import MessagePublisher

logger = logging.getLogger("scrapx.monitor")


class ChannelMonitor:
    """Listens to source channels, manages album buffering, transforms and dispatches messages."""

    def __init__(
        self,
        client: TelegramClient,
        publisher: MessagePublisher,
        db_manager: DatabaseManager,
        settings: Settings,
    ):
        self.client = client
        self.publisher = publisher
        self.db = db_manager
        self.settings = settings

        # Channel mapping: channel_id -> { "key": str, "name": str, "filter": BaseMessageFilter }
        self.channel_map: Dict[int, Dict[str, Any]] = {}

        # Album buffering: grouped_id -> list of Message objects
        self._album_buffers: Dict[int, List[Message]] = {}
        # Active debounce timer tasks: grouped_id -> asyncio.Task
        self._album_tasks: Dict[int, asyncio.Task] = {}

    def register_channel(
        self,
        channel_entity: Any,
        channel_key: str,
        display_name: str,
        filter_instance: BaseMessageFilter,
    ) -> None:
        """Registers a resolved source channel and its formatting filter."""
        channel_id = channel_entity.id
        self.channel_map[channel_id] = {
            "entity": channel_entity,
            "key": channel_key,
            "name": display_name,
            "filter": filter_instance,
        }
        logger.info(
            "Registered monitoring for channel: '%s' (ID: %s, Filter: %s)",
            display_name,
            channel_id,
            filter_instance.__class__.__name__,
        )

    def start_listening(self) -> None:
        """Attaches the event listener to registered source channels."""
        monitored_entities = [info["entity"] for info in self.channel_map.values()]
        if not monitored_entities:
            raise RuntimeError("No source channels registered for monitoring.")

        logger.info("Registering NewMessage listener for %d source channels...", len(monitored_entities))

        @self.client.on(events.NewMessage(chats=monitored_entities))
        async def on_new_message(event: events.NewMessage.Event):
            await self._handle_event(event)

        logger.info("Event listener active and waiting for new messages.")

    async def _handle_event(self, event: events.NewMessage.Event) -> None:
        """Internal router for incoming message events."""
        message: Message = event.message
        chat_id = event.chat_id

        # Normalize chat_id (handle negative peer IDs)
        channel_info = self.channel_map.get(chat_id)
        if not channel_info:
            # Try absolute value or without -100 prefix
            for registered_id, info in self.channel_map.items():
                if abs(chat_id) == abs(registered_id) or str(chat_id).endswith(str(registered_id)):
                    channel_info = info
                    break

        if not channel_info:
            logger.debug("Received event from unmapped chat ID: %s. Ignoring.", chat_id)
            return

        channel_key = channel_info["key"]
        channel_name = channel_info["name"]

        # Duplicate check before any processing
        if self.db.is_message_processed(channel_key, message.id):
            logger.debug(
                "Skipping already processed message ID %s from %s",
                message.id,
                channel_name,
            )
            return

        # Check if message is part of an album (media group)
        if message.grouped_id:
            await self._handle_album_item(message, channel_info)
        else:
            await self._handle_single_message(message, channel_info)

    async def _handle_album_item(self, message: Message, channel_info: Dict[str, Any]) -> None:
        """Buffers media group items and debounces publication until complete group is received."""
        grouped_id = message.grouped_id
        channel_key = channel_info["key"]

        logger.info(
            "Buffering album item (Msg ID: %s, Group ID: %s) from %s",
            message.id,
            grouped_id,
            channel_info["name"],
        )

        if grouped_id not in self._album_buffers:
            self._album_buffers[grouped_id] = []

        self._album_buffers[grouped_id].append(message)

        # Cancel existing debounce timer for this group
        if grouped_id in self._album_tasks:
            self._album_tasks[grouped_id].cancel()

        # Schedule debounced dispatch
        debounce_secs = self.settings.media_group_debounce_seconds
        task = asyncio.create_task(
            self._dispatch_album_after_debounce(grouped_id, channel_info, debounce_secs)
        )
        self._album_tasks[grouped_id] = task

    async def _dispatch_album_after_debounce(
        self,
        grouped_id: int,
        channel_info: Dict[str, Any],
        delay: float,
    ) -> None:
        """Waits for debounce delay, then processes and publishes the gathered album."""
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return  # Timer reset by incoming sibling item

        # Pop gathered messages
        messages = self._album_buffers.pop(grouped_id, [])
        self._album_tasks.pop(grouped_id, None)

        if not messages:
            return

        channel_key = channel_info["key"]
        channel_name = channel_info["name"]
        filter_inst: BaseMessageFilter = channel_info["filter"]

        # Sort messages by message ID to preserve sequence
        messages.sort(key=lambda m: m.id)
        logger.info(
            "Processing completed album (Group ID: %s) with %d items from %s",
            grouped_id,
            len(messages),
            channel_name,
        )

        # Extract caption from whichever item in the album contains text
        raw_caption = None
        for m in messages:
            if m.raw_text:
                raw_caption = m.raw_text
                break

        transformed_caption = filter_inst.process_text(raw_caption) if raw_caption else None

        try:
            dest_id = await self.publisher.publish_album(messages, caption=transformed_caption)
            # Record ALL messages in album as published
            for m in messages:
                self.db.mark_published(
                    source_channel=channel_key,
                    source_msg_id=m.id,
                    dest_channel=str(self.publisher.destination),
                    dest_msg_id=dest_id,
                    grouped_id=grouped_id,
                )
            logger.info("Successfully recorded album %s as published.", grouped_id)
        except Exception as e:
            logger.error("Failed to publish album %s: %s", grouped_id, e, exc_info=True)
            for m in messages:
                self.db.mark_failed(
                    source_channel=channel_key,
                    source_msg_id=m.id,
                    error_message=str(e),
                    grouped_id=grouped_id,
                )

    async def _handle_single_message(self, message: Message, channel_info: Dict[str, Any]) -> None:
        """Processes and publishes a single text or single media message."""
        channel_key = channel_info["key"]
        channel_name = channel_info["name"]
        filter_inst: BaseMessageFilter = channel_info["filter"]

        raw_text = message.raw_text or ""
        transformed_text = filter_inst.process_text(raw_text)

        logger.info(
            "Processing single message %s from %s (has media: %s)",
            message.id,
            channel_name,
            bool(message.media),
        )

        try:
            dest_id = None
            if message.media:
                # Media with or without caption
                dest_id = await self.publisher.publish_single_media(message, caption=transformed_text)
            else:
                # Text only
                if not transformed_text:
                    logger.warning("Message %s text became empty after filtering. Skipping.", message.id)
                    return
                dest_id = await self.publisher.publish_text(transformed_text)

            # Record success
            self.db.mark_published(
                source_channel=channel_key,
                source_msg_id=message.id,
                dest_channel=str(self.publisher.destination),
                dest_msg_id=dest_id,
            )
            logger.info("Successfully published and recorded message %s from %s.", message.id, channel_name)
        except Exception as e:
            logger.error("Failed to process message %s from %s: %s", message.id, channel_name, e, exc_info=True)
            self.db.mark_failed(
                source_channel=channel_key,
                source_msg_id=message.id,
                error_message=str(e),
            )

