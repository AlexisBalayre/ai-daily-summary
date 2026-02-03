"""Telegram bot for sending audio briefings."""

import logging
from pathlib import Path
from typing import Optional

import aiohttp

from ai_daily.config import config

logger = logging.getLogger(__name__)


class TelegramSender:
    """Send messages and audio files via Telegram bot."""

    API_BASE = "https://api.telegram.org/bot{token}"

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ):
        self.bot_token = bot_token or config.telegram.bot_token
        self.chat_id = chat_id or config.telegram.chat_id

    @property
    def enabled(self) -> bool:
        """Check if Telegram is configured."""
        return bool(self.bot_token and self.chat_id)

    def _get_url(self, method: str) -> str:
        """Get Telegram API URL for method."""
        return f"{self.API_BASE.format(token=self.bot_token)}/{method}"

    async def send_message(self, text: str) -> bool:
        """Send a text message.

        Args:
            text: Message text.

        Returns:
            True if sent successfully.
        """
        if not self.enabled:
            logger.warning("Telegram not configured, skipping message")
            return False

        url = self._get_url("sendMessage")
        data = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as resp:
                    if resp.status == 200:
                        logger.info("Telegram message sent")
                        return True
                    else:
                        error = await resp.text()
                        logger.error(f"Telegram API error: {error}")
                        return False
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    async def send_audio(
        self,
        audio_path: Path,
        caption: Optional[str] = None,
        title: Optional[str] = None,
    ) -> bool:
        """Send an audio file.

        Args:
            audio_path: Path to audio file.
            caption: Optional caption for the audio.
            title: Optional title for the audio.

        Returns:
            True if sent successfully.
        """
        if not self.enabled:
            logger.warning("Telegram not configured, skipping audio")
            return False

        if not audio_path.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return False

        url = self._get_url("sendAudio")
        data = aiohttp.FormData()
        data.add_field("chat_id", self.chat_id)

        if caption:
            data.add_field("caption", caption)
        if title:
            data.add_field("title", title)

        # Add audio file
        data.add_field(
            "audio",
            open(audio_path, "rb"),
            filename=audio_path.name,
            content_type="audio/wav",
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as resp:
                    if resp.status == 200:
                        logger.info(f"Telegram audio sent: {audio_path.name}")
                        return True
                    else:
                        error = await resp.text()
                        logger.error(f"Telegram API error: {error}")
                        return False
        except Exception as e:
            logger.error(f"Failed to send Telegram audio: {e}")
            return False
