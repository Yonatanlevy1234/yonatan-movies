import asyncio
import logging
import os
import struct
from typing import AsyncGenerator, Dict, Optional

# Ensure an active event loop exists before importing pyrogram (Python 3.14 compatibility)
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from pyrogram import Client
from config import API_HASH, API_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL
import database as db

logger = logging.getLogger(__name__)


class TelegramStreamManager:
    """Manages Telegram MTProto client connection, peer resolution, and video range streaming using Pyrogram."""

    def __init__(self):
        self.api_id = API_ID
        self.api_hash = API_HASH
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.channel_id = TELEGRAM_CHANNEL
        self.client: Optional[Client] = None
        self._is_started = False
        self._lock = asyncio.Lock()

    async def start(self):
        """Starts Pyrogram Client session and resolves Telegram channel peer."""
        async with self._lock:
            if self._is_started:
                return
            try:
                session_dir = os.path.dirname(os.path.abspath(__file__))
                session_path = os.path.join(session_dir, "bot_session")

                self.client = Client(
                    name=session_path,
                    api_id=self.api_id,
                    api_hash=self.api_hash,
                    bot_token=self.bot_token,
                    workdir=session_dir,
                )
                logger.info("Starting Pyrogram bot client...")
                await self.client.start()
                self._is_started = True
                logger.info("Pyrogram bot client started successfully.")

                # Resolve channel peer cache
                try:
                    chat = await self.client.get_chat(self.channel_id)
                    logger.info(f"Resolved Telegram channel '{getattr(chat, 'title', 'Channel')}' (ID: {self.channel_id})")
                except Exception as pe:
                    logger.warning(f"Note on channel peer resolution: {pe}")

            except Exception as e:
                logger.warning(
                    f"Could not connect Pyrogram Client (will use fallback streamer): {e}"
                )
                self.client = None
                self._is_started = False

    async def stop(self):
        """Stops Pyrogram Client session."""
        async with self._lock:
            if self.client and self._is_started:
                try:
                    await self.client.stop()
                except Exception as e:
                    logger.error(f"Error stopping Pyrogram client: {e}")
                finally:
                    self.client = None
                    self._is_started = False

    async def sync_channel_movies(self) -> int:
        """Helper to scan and sync movies from channel."""
        if not self._is_started:
            await self.start()

        if not self.client:
            return 0

        synced_count = 0
        batch = []
        BATCH_SIZE = 200

        try:
            # Fetch channel messages in batches of 200 message IDs (Bot API compatible)
            for start_id in range(1, 1000000, 200):
                msg_ids = list(range(start_id, start_id + 200))
                try:
                    messages = await self.client.get_messages(chat_id=self.channel_id, message_ids=msg_ids)
                    if not messages:
                        continue
                    if not isinstance(messages, list):
                        messages = [messages]

                    empty_count = 0
                    for message in messages:
                        if not message or message.empty:
                            empty_count += 1
                            continue

                        media = message.video or message.document
                        if media:
                            if message.document and not (media.mime_type and 'video' in media.mime_type):
                                continue

                            raw_title = message.caption
                            if not raw_title and hasattr(media, "file_name") and media.file_name:
                                raw_title = media.file_name

                            if raw_title:
                                file_size = getattr(media, "file_size", 0)
                                duration = getattr(media, "duration", 0)
                                mime_type = getattr(media, "mime_type", "video/mp4") or "video/mp4"
                                file_name = getattr(media, "file_name", f"movie_{message.id}.mp4") or f"movie_{message.id}.mp4"

                                batch.append({
                                    "message_id": message.id,
                                    "raw_title": raw_title,
                                    "file_size": file_size,
                                    "duration": duration,
                                    "mime_type": mime_type,
                                    "file_name": file_name
                                })

                                if len(batch) >= BATCH_SIZE:
                                    synced_count += db.add_or_update_movies_batch(batch)
                                    batch = []

                    if empty_count >= 195 and start_id > 800000:
                        break

                except Exception:
                    pass

            if batch:
                synced_count += db.add_or_update_movies_batch(batch)

            logger.info(f"Sync completed successfully. Total synced: {synced_count} movies.")
            return synced_count
        except Exception as e:
            logger.error(f"Error syncing channel movies: {e}")
            return synced_count

    async def stream_file_range(
        self, message_id: int, start: int, end: int
    ) -> AsyncGenerator[bytes, None]:
        """Streams byte range [start, end] directly from Telegram message video using Pyrogram stream_media."""
        if not self._is_started:
            await self.start()

        if self.client and self._is_started:
            try:
                message = await self.client.get_messages(
                    chat_id=self.channel_id, message_ids=message_id
                )
                if message and (message.video or message.document):
                    CHUNK_SIZE = 1024 * 1024
                    start_chunk = start // CHUNK_SIZE
                    bytes_skip = start % CHUNK_SIZE
                    bytes_remaining = (end - start) + 1

                    chunk_idx = 0
                    async for chunk in self.client.stream_media(
                        message, offset=start_chunk
                    ):
                        if bytes_remaining <= 0:
                            break

                        if chunk_idx == 0 and bytes_skip > 0:
                            chunk = chunk[bytes_skip:]

                        if len(chunk) > bytes_remaining:
                            chunk = chunk[:bytes_remaining]

                        bytes_remaining -= len(chunk)
                        yield chunk
                        chunk_idx += 1
                    return
            except Exception as e:
                logger.error(
                    f"Error streaming from Telegram for message {message_id}: {e}"
                )

        async for chunk in self._generate_fallback_stream(start, end):
            yield chunk

    async def _generate_fallback_stream(
        self, start: int, end: int
    ) -> AsyncGenerator[bytes, None]:
        """Generates synthetic video stream data for testing and offline fallback."""
        total_requested = (end - start) + 1
        chunk_size = 64 * 1024

        header = (
            b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
            b"\x00\x00\x00\x08free"
            b"\x00\x00\x00\x10mdat"
            + b"\x00" * 32
        )

        sent = 0
        current_pos = start

        while sent < total_requested:
            to_read = min(chunk_size, total_requested - sent)

            if current_pos < len(header):
                chunk = header[current_pos : current_pos + to_read]
                if len(chunk) < to_read:
                    pad_len = to_read - len(chunk)
                    chunk += b"\x00" * pad_len
            else:
                chunk = b"\x00" * to_read

            yield chunk
            sent += len(chunk)
            current_pos += len(chunk)
            await asyncio.sleep(0.001)


telegram_streamer = TelegramStreamManager()
