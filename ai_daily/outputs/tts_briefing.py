"""Text-to-speech briefing generation."""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from ai_daily.config import config
from ai_daily.db import DailySummary
from ai_daily.outputs.summary_generator import SummaryGenerator

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
            self.voice_state = self.tts_model.get_state_for_audio_prompt(voice)

    async def generate_script(self, summary: DailySummary) -> str:
        """Generate spoken script from summary."""
        content = f"""Summary: {summary.summary_text}

Key Facts:
{chr(10).join(f'- {fact}' for fact in (summary.key_facts or []))}"""

        response = await self.llm_client.chat.completions.create(
            model=config.llm.model,
            messages=[
                {"role": "system", "content": self.SCRIPT_PROMPT},
                {"role": "user", "content": content}
            ],
        )

        return response.choices[0].message.content

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
        script_path.write_text(script)

        # Generate audio
        self._init_tts(voice)
        audio = self.tts_model.generate_audio(self.voice_state, script)

        # Save audio
        audio_path = self.output_dir / f"{target_date.isoformat()}_briefing.wav"
        scipy.io.wavfile.write(str(audio_path), self.tts_model.sample_rate, audio.numpy())

        return audio_path
