"""Main entry point for running the full pipeline."""

import asyncio
import logging
from datetime import UTC, datetime

from ai_daily.db import get_session, init_db
from ai_daily.db.seed import seed_sources
from ai_daily.etl import ETLPipeline
from ai_daily.etl.extractors.gmail import GmailExtractor
from ai_daily.outputs import NewsletterOutput, TTSBriefingOutput

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_daily_pipeline():
    """Run the complete daily pipeline."""
    logger.info("Starting AI Daily pipeline...")

    # Initialize database if needed
    init_db()
    seed_sources()

    # Run ETL
    pipeline = ETLPipeline()
    metrics = await pipeline.run_all()
    logger.info(f"ETL complete: {metrics}")

    # Generate and send newsletter
    with get_session() as session:
        # Get Gmail service from extractor
        gmail_extractor = GmailExtractor()

        newsletter = NewsletterOutput(gmail_service=gmail_extractor.service)
        await newsletter.send(session, target_date=datetime.now(UTC).date())
        logger.info("Newsletter sent")

        # Generate TTS briefing (optional)
        try:
            tts = TTSBriefingOutput()
            audio_path, sync_path = await tts.generate(
                session, target_date=datetime.now(UTC).date()
            )
            logger.info(f"TTS briefing generated: {audio_path}")
            if sync_path:
                logger.info(f"TTS synced to: {sync_path}")
        except Exception as e:
            logger.warning(f"TTS generation skipped: {e}")

    logger.info("Daily pipeline complete!")


def main():
    """Run the pipeline."""
    asyncio.run(run_daily_pipeline())


if __name__ == "__main__":
    main()
