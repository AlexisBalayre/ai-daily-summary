"""Text-to-speech briefing generation."""

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI, APIError
from sqlalchemy.orm import Session

from ai_daily.config import config
from ai_daily.db import DailySummary
from ai_daily.outputs.summary_generator import SummaryGenerator

logger = logging.getLogger(__name__)

# Pocket TTS import (may not be available)
try:
    from pocket_tts import TTSModel
    import scipy.io.wavfile
    POCKET_TTS_AVAILABLE = True
except ImportError:
    POCKET_TTS_AVAILABLE = False


class TTSBriefingOutput:
    """Generate audio briefings from daily summaries."""

    SCRIPT_PROMPT = """Convert this newsletter summary into a natural, conversational script
for a 2-3 minute audio briefing.

Guidelines:
- Start with a brief greeting and date
- Use conversational language, not formal writing
- Include natural transitions between topics
- End with a brief sign-off
- Keep it concise - aim for about 400-500 words

Output the script as plain text, ready to be read aloud."""

    def __init__(self):
        self.summary_generator = SummaryGenerator()
        self.output_dir = config.data_dir / "briefings"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if config.llm.provider == "ollama":
            self.llm_client = AsyncOpenAI(
                base_url=config.llm.ollama_base_url,
                api_key="ollama"
            )
        else:
            self.llm_client = AsyncOpenAI()

        self.tts_model = None
        self.voice_state = None

    def _init_tts(self, voice: str = "alba"):
        """Initialize TTS model lazily."""
        if not POCKET_TTS_AVAILABLE:
            raise RuntimeError("Pocket TTS not installed. Run: pip install pocket-tts")

        if self.tts_model is None:
            self.tts_model = TTSModel.load_model()
            try:
                self.voice_state = self.tts_model.get_state_for_audio_prompt(voice)
            except Exception as e:
                logger.error(f"Failed to initialize voice state for voice '{voice}': {e}")
                self.tts_model = None
                raise

    async def generate_script(self, summary: DailySummary) -> str:
        """Generate spoken script from summary."""
        content = f"""Summary: {summary.summary_text}

Key Facts:
{chr(10).join(f'- {fact}' for fact in (summary.key_facts or []))}"""

        fallback_script = f"Here is your daily briefing. {summary.summary_text}"

        try:
            response = await self.llm_client.chat.completions.create(
                model=config.llm.model,
                messages=[
                    {"role": "system", "content": self.SCRIPT_PROMPT},
                    {"role": "user", "content": content}
                ],
            )
        except APIError as e:
            logger.error(f"OpenAI API error while generating script: {e}")
            return fallback_script

        if not response.choices:
            logger.error("LLM response contained no choices")
            return fallback_script

        message_content = response.choices[0].message.content
        if message_content is None:
            logger.error("LLM response message content is None")
            return fallback_script

        return message_content

    async def generate(
        self,
        session: Session,
        target_date: Optional[date] = None,
        voice: str = "alba"
    ) -> Path:
        """Generate audio briefing.

        Args:
            session: Database session.
            target_date: Date to generate briefing for.
            voice: Pocket TTS voice name.

        Returns:
            Path to generated audio file.
        """
        if target_date is None:
            target_date = date.today()

        # Get or generate summary
        summary = await self.summary_generator.generate(session, target_date)

        # Generate script
        script = await self.generate_script(summary)

        # Save script for reference
        script_path = self.output_dir / f"{target_date.isoformat()}_script.txt"
        try:
            script_path.write_text(script)
        except OSError as e:
            logger.error(f"Failed to write script to {script_path}: {e}")
            raise

        # Generate audio
        self._init_tts(voice)
        try:
            audio = self.tts_model.generate_audio(self.voice_state, script)
        except Exception as e:
            logger.error(f"Failed to generate TTS audio: {e}")
            raise

        # Save audio
        audio_path = self.output_dir / f"{target_date.isoformat()}_briefing.wav"
        try:
            scipy.io.wavfile.write(str(audio_path), self.tts_model.sample_rate, audio.numpy())
        except OSError as e:
            logger.error(f"Failed to write audio file to {audio_path}: {e}")
            raise

        return audio_path
