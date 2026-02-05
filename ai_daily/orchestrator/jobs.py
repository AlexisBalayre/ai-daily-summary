"""Job definitions for orchestrator."""

import logging
from datetime import date
from typing import Any, Dict

from ai_daily.db import get_session, init_db
from ai_daily.db.seed import seed_sources
from ai_daily.etl import ETLPipeline
from ai_daily.etl.extractors.gmail import GmailExtractor
from ai_daily.orchestrator.types import JobContext
from ai_daily.outputs import NewsletterOutput, TTSBriefingOutput

logger = logging.getLogger(__name__)


async def run_etl(context: JobContext) -> Dict[str, Any]:
    """Run ETL pipeline for all sources."""
    logger.info(f"Starting ETL job (run_id={context.run_id})")

    # Ensure database is ready
    init_db()
    seed_sources()

    pipeline = ETLPipeline()
    metrics = await pipeline.run_all()

    logger.info(f"ETL complete: {metrics}")
    return metrics


async def run_newsletter(context: JobContext) -> Dict[str, Any]:
    """Generate and send newsletter."""
    logger.info(f"Starting newsletter job (run_id={context.run_id})")

    with get_session() as session:
        gmail_extractor = GmailExtractor()
        newsletter = NewsletterOutput(gmail_service=gmail_extractor.service)

        success = await newsletter.send(session, target_date=date.today())

        return {
            "sent": success,
            "date": date.today().isoformat(),
        }


async def run_tts(context: JobContext) -> Dict[str, Any]:
    """Generate TTS audio briefing and sync to iCloud."""
    logger.info(f"Starting TTS job (run_id={context.run_id})")

    with get_session() as session:
        tts = TTSBriefingOutput()
        audio_path, sync_path = await tts.generate(session, target_date=date.today())

        return {
            "audio_path": str(audio_path),
            "sync_path": str(sync_path) if sync_path else None,
            "date": date.today().isoformat(),
        }


# Registry of available jobs
JOBS = {
    "etl": run_etl,
    "newsletter": run_newsletter,
    "tts": run_tts,
}
