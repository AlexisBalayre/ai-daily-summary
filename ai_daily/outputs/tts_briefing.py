"""Text-to-speech briefing generation."""

import logging
import os
import shutil
from datetime import date
from pathlib import Path
from typing import Optional

import google.generativeai as genai
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

        # iCloud sync directory for phone access
        icloud_default = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "AI Daily Briefings"
        tts_output = os.getenv("TTS_OUTPUT_DIR", "")
        self.sync_dir = Path(tts_output) if tts_output else icloud_default

        genai.configure(api_key=config.llm.google_api_key)
        self.llm_model = genai.GenerativeModel(
            model_name=config.llm.model,
            system_instruction=self.SCRIPT_PROMPT,
        )

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
            response = await self.llm_model.generate_content_async(content)
        except Exception as e:
            logger.error(f"Google API error while generating script: {e}")
            return fallback_script

        if not response.text:
            logger.error("LLM response has no text")
            return fallback_script

        return response.text

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

        # Copy to iCloud sync directory
        sync_path = self._copy_to_sync_dir(audio_path, target_date)

        return audio_path, sync_path

    def _copy_to_sync_dir(self, audio_path: Path, target_date: date) -> Optional[Path]:
        """Copy audio to cloud sync directory for phone access."""
        try:
            self.sync_dir.mkdir(parents=True, exist_ok=True)
            sync_path = self.sync_dir / f"briefing_{target_date.isoformat()}.wav"
            shutil.copy2(audio_path, sync_path)
            logger.info(f"Audio copied to sync dir: {sync_path}")
            return sync_path
        except Exception as e:
            logger.warning(f"Failed to copy to sync dir: {e}")
            return None
