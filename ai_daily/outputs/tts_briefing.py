"""Text-to-speech briefing generation."""

import logging
import os
import re
import shutil
from datetime import date
from pathlib import Path
from typing import Optional

from google import genai
from google.genai.types import GenerateContentConfig
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

Output rules (the text is fed directly to a TTS model, which sings or adds
jingles when it meets anything that isn't plain speech):
- Plain spoken sentences ONLY. No markdown, no headings, no bullet points,
  no asterisks, underscores, backticks, or hashes.
- No emoji, no URLs, no code, no tables.
- Spell things out: say "version three" not "v3", "and" not "&",
  "percent" not "%". Expand abbreviations into words.
- Use normal sentence punctuation (. , ? !) only.

Output the script as plain text, ready to be read aloud."""

    def __init__(self):
        self.summary_generator = SummaryGenerator()
        self.output_dir = config.data_dir / "briefings"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # iCloud sync directory for phone access
        icloud_default = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "AI Daily Briefings"
        tts_output = os.getenv("TTS_OUTPUT_DIR", "")
        self.sync_dir = Path(tts_output) if tts_output else icloud_default

        self.client = genai.Client(api_key=config.llm.google_api_key)
        self.model = config.llm.model

        self.tts_model = None
        self.voice_state = None

    def _init_tts(self, voice: Optional[str] = None):
        """Initialize TTS model lazily."""
        if not POCKET_TTS_AVAILABLE:
            raise RuntimeError("Pocket TTS not installed. Run: pip install pocket-tts")

        if voice is None:
            voice = config.tts.voice

        if self.tts_model is None:
            load_kwargs = {
                "temp": config.tts.temp,
                "eos_threshold": config.tts.eos_threshold,
            }
            if config.tts.noise_clamp is not None:
                load_kwargs["noise_clamp"] = config.tts.noise_clamp
            self.tts_model = TTSModel.load_model(**load_kwargs)
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
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=content,
                config=GenerateContentConfig(
                    system_instruction=self.SCRIPT_PROMPT,
                ),
            )
        except Exception as e:
            logger.error(f"Google API error while generating script: {e}")
            return fallback_script

        if not response.text:
            logger.error("LLM response has no text")
            return fallback_script

        return self._clean_script_for_tts(response.text)

    @staticmethod
    def _clean_script_for_tts(text: str) -> str:
        """Strip anything the TTS model vocalizes as noise or a jingle.

        Non-speech tokens (markdown, emoji, URLs, symbols) are the main trigger
        for hallucinated singing, so we remove them even though the prompt also
        forbids them — the model occasionally emits them anyway.
        """
        # Normalize typographic punctuation to ASCII first, so the symbol strip
        # below keeps contractions intact — otherwise a curly apostrophe in
        # "we'll" is removed and it becomes "well", changing how it's spoken.
        text = text.translate(
            str.maketrans(
                {
                    "’": "'", "‘": "'", "“": '"', "”": '"',
                    "–": "-", "—": "-", "…": "...",
                }
            )
        )
        # Drop URLs first (before punctuation stripping splits them).
        text = re.sub(r"https?://\S+|www\.\S+", "", text)
        # Remove markdown emphasis/structure characters.
        text = re.sub(r"[*_`#>|~]", "", text)
        # Strip leading list markers on any line.
        text = re.sub(r"(?m)^\s*[-•]\s+", "", text)
        # Keep letters, digits, whitespace, and plain sentence punctuation; drop
        # emoji and other symbols (covers the astral emoji planes too).
        text = re.sub(r"[^\w\s.,;:!?'\"()\-]", "", text, flags=re.UNICODE)
        text = re.sub(r"[\U0001F000-\U0001FAFF☀-➿]", "", text)
        # Collapse whitespace runs and blank lines.
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{2,}", "\n", text)
        return text.strip()

    async def generate(
        self,
        session: Session,
        target_date: Optional[date] = None,
        voice: Optional[str] = None
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
            audio = self.tts_model.generate_audio(
                self.voice_state, script, frames_after_eos=config.tts.frames_after_eos
            )
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
