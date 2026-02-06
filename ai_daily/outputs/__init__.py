"""Output generators (newsletter, TTS, etc.)."""

from ai_daily.outputs.github_newsletter import GitHubNewsletterOutput
from ai_daily.outputs.newsletter import NewsletterOutput
from ai_daily.outputs.summary_generator import SummaryGenerator
from ai_daily.outputs.tts_briefing import TTSBriefingOutput

__all__ = ["GitHubNewsletterOutput", "NewsletterOutput", "SummaryGenerator", "TTSBriefingOutput"]
