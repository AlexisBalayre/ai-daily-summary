import asyncio
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

from lib.gmail_client import GmailClient
from lib.newsletter_processor import NewsletterProcessor
from lib.utils import (
    logger,
    save_individual_email,
    send_ai_daily_newsletter,
    send_github_hot_repositories_newsletter,
)
from lib.github_scraper import GithubScraper

# Load environment variables
load_dotenv()


async def main():
    try:
        gmail_client = GmailClient()
        processor = NewsletterProcessor()
        logger.info("Starting AI-Daily newsletter processing...")

        # Step 1: Collect all unprocessed emails and save them
        emails = await gmail_client.read_emails(process_all=True)
        if not emails:
            logger.info("No new emails found")
            logger.info("Retrieving processed email from the 24 hours...")
            from_date = datetime.now() - timedelta(days=2)
            to_date = datetime.now()
            logger.info(f"Retrieving processed email from {from_date} to {to_date}...")
            articles = processor.load_articles_from_files(from_date, to_date)
            if not articles:
                logger.error("No processed emails found in the last 24 hours")
                return
        else:
            logger.info(f"Processing {len(emails)} emails...")
            for email in emails:
                save_individual_email(email, processed=False)

            # Step 2: Process new emails into structured articles
            articles = await processor.process_emails(emails)
            if not articles:
                logger.error("Failed to process emails into articles")
                return

        # Step 3: Generate daily newsletter summary
        if articles:
            logger.info(f"Processed {len(articles)} articles")
            newsletter_content = await processor.generate_daily_summary(articles)
            if newsletter_content is None:
                logger.error("Failed to generate newsletter summary")
                return

            recipients = os.getenv("NEWSLETTER_RECIPIENTS")
            today_date = datetime.now().strftime("%B %d, %Y")
            if send_ai_daily_newsletter(
                gmail_client.service,
                f"AI-Daily Newsletter - {today_date}",
                newsletter_content,
                recipients,
            ):
                logger.info("Newsletter sent successfully")
            else:
                logger.error("Failed to send newsletter")
        else:
            logger.error("No articles to process")

    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}", exc_info=True)

    try:
        github_scraper = GithubScraper()
        gmail_client = GmailClient()
        logger.info("Starting GitHub Hot Repositories newsletter processing...")
        trending_repositories = github_scraper.fetch_trending_repositories()
        explore_repositories = github_scraper.fetch_explore_repositories()

        if trending_repositories or explore_repositories:
            recipients = os.getenv("NEWSLETTER_RECIPIENTS")
            today_date = datetime.now().strftime("%B %d, %Y")
            if send_github_hot_repositories_newsletter(
                gmail_client.service,
                f"GitHub Hot Repositories - {today_date}",
                trending_repositories,
                explore_repositories,
                recipients,
            ):
                logger.info("GitHub newsletter sent successfully")
            else:
                logger.error("Failed to send GitHub newsletter")
        else:
            logger.error("No repositories to process")
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
