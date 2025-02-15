import os
import json
import base64
import re
from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parsedate_to_datetime
import logging
from pathlib import Path
from functools import wraps
import asyncio
import aiohttp

from openai import AsyncOpenAI
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv
from requests.exceptions import RequestException


# Set up logging with rotating file handler
def setup_logging():
    from logging.handlers import RotatingFileHandler

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_dir / "newsletter_processor.log",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
    )
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Root logger setup
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


logger = setup_logging()

# Load environment variables
load_dotenv()

# Configuration
TEMPLATE_FILE = Path("email_template.html")


def load_template():
    if TEMPLATE_FILE.exists():
        with open(TEMPLATE_FILE, "r") as file:
            return file.read()
    else:
        raise FileNotFoundError("Email template file not found.")


def save_individual_email(
    email: dict, processed: bool = False, base_folder: str = None
) -> None:
    """
    Saves an individual email to a JSON file in the specified folder structure.
    The filename will be based on the date and a sanitized subject.

    Args:
        email (dict): Email dictionary containing subject, sender, date, etc.
        processed (bool): Whether the email has been processed by LLM
        base_folder (str): Optional base folder path for saving emails. If None, uses config paths.
    """
    try:
        # Determine the appropriate folder
        if base_folder is None:
            base_folder = str(
                config.PROCESSED_EMAILS_DIR if processed else config.RAW_EMAILS_DIR
            )

        # Create the emails directory if it doesn't exist
        os.makedirs(base_folder, exist_ok=True)

        # Extract date from email and parse it
        try:
            email_date = parsedate_to_datetime(email["date"])
            date_str = email_date.strftime("%Y%m%d")
        except:
            # Fallback to current date if parsing fails
            date_str = datetime.now().strftime("%Y%m%d")

        # Sanitize subject for filename
        subject = email["subject"]
        # Remove special characters and limit length
        safe_subject = re.sub(r"[^\w\s-]", "", subject)
        safe_subject = re.sub(r"\s+", "_", safe_subject)
        safe_subject = safe_subject[:50]  # Limit length to 50 characters

        # Create filename with date and subject
        filename = f"{date_str}_{safe_subject}.json"
        filepath = os.path.join(base_folder, filename)

        # Add timestamp and processing status
        email_copy = email.copy()
        email_copy["processed_timestamp"] = datetime.now().isoformat()
        email_copy["llm_processed"] = processed

        # Save email data to JSON file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(email_copy, f, indent=4, ensure_ascii=False)

        logger.info(f"Email saved successfully: {filepath}")

    except Exception as e:
        logger.error(f"Error saving individual email: {str(e)}")


def send_newsletter(service, subject, content, recipient):
    try:
        template = load_template()
        html_content = template.replace("{{date}}", datetime.now().strftime("%Y-%m-%d"))
        html_content = html_content.replace("{{summary}}", content.summary)
        html_content = html_content.replace("{{year}}", str(datetime.now().year))
        html_content = html_content.replace(
            "{{key_facts}}", "".join(f"<li>{fact}</li>" for fact in content.key_facts)
        )
        articles_html = "".join(
            f'<h3>{article.title}</h3><p>{article.content}</p><p>Source: {article.source} | <a href="{article.url}">Read more</a></p>'
            for article in content.articles
        )
        html_content = html_content.replace("{{articles}}", articles_html)

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["To"] = recipient
        message["From"] = "me"

        part = MIMEText(html_content, "html")
        message.attach(part)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True
    except Exception as e:
        logging.error(f"Failed to send newsletter: {e}")
        return False


# Configuration
@dataclass
class Config:
    SCOPES: List[str] = (
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    )
    DATA_DIR: Path = Path("data")
    PROCESSED_IDS_FILE: Path = DATA_DIR / "processed_ids.json"
    RAW_EMAILS_DIR: Path = DATA_DIR / "emails" / "raw"
    PROCESSED_EMAILS_DIR: Path = DATA_DIR / "emails" / "processed"
    CONFIG_FILE: Path = Path("config.json")
    TEMPLATE_FILE: Path = Path("email_template.html")

    def __post_init__(self):
        # Create necessary directories
        self.DATA_DIR.mkdir(exist_ok=True)
        self.RAW_EMAILS_DIR.mkdir(parents=True, exist_ok=True)
        self.PROCESSED_EMAILS_DIR.mkdir(parents=True, exist_ok=True)


config = Config()


def error_handler(func):
    """Decorator for handling errors and logging them appropriately"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return (
                await func(*args, **kwargs)
                if asyncio.iscoroutinefunction(func)
                else func(*args, **kwargs)
            )
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
            return None

    return wrapper


class GmailClient:
    def __init__(self):
        self.service = self._authenticate_gmail()

    def _authenticate_gmail(self):
        """Authenticates with Gmail API using OAuth 2.0"""
        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", config.SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_config(
                    {
                        "web": {
                            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                            "project_id": os.getenv("GOOGLE_PROJECT_ID"),
                            "auth_uri": os.getenv("GOOGLE_AUTH_URI"),
                            "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
                            "auth_provider_x509_cert_url": os.getenv(
                                "GOOGLE_AUTH_PROVIDER_X509_CERT_URL"
                            ),
                            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                            "redirect_uris": ["http://localhost:56450/"],
                        }
                    },
                    config.SCOPES,
                )
                creds = flow.run_local_server(port=56450)

            with open("token.json", "w") as token:
                token.write(creds.to_json())

        return build("gmail", "v1", credentials=creds)

    def _load_processed_ids(self) -> set:
        """Load the set of processed email IDs from file"""
        try:
            if config.PROCESSED_IDS_FILE.exists():
                with open(config.PROCESSED_IDS_FILE, "r") as f:
                    return set(json.load(f))
            return set()
        except Exception as e:
            logger.error(f"Error loading processed IDs: {e}")
            return set()

    def _load_whitelist(self) -> set:
        """Load the whitelist of email addresses from config"""
        try:
            if config.CONFIG_FILE.exists():
                with open(config.CONFIG_FILE, "r") as f:
                    config_data = json.load(f)
                    return set(config_data.get("whitelist", []))
            return set()
        except Exception as e:
            logger.error(f"Error loading whitelist: {e}")
            return set()

    def _update_processed_ids(self, processed_ids: set):
        """Update the processed IDs file"""
        try:
            with open(config.PROCESSED_IDS_FILE, "w") as f:
                json.dump(list(processed_ids), f, indent=4)
        except Exception as e:
            logger.error(f"Error updating processed IDs: {e}")

    @error_handler
    async def read_emails(self, process_all: bool = True) -> List[Dict]:
        """Reads emails from Gmail with improved error handling and async processing"""
        # Load processed IDs and whitelist
        processed_ids = self._load_processed_ids()
        whitelist = self._load_whitelist()

        # Fetch all email IDs without date restriction
        search_results = self.service.users().messages().list(userId="me").execute()
        messages = search_results.get("messages", [])

        if not messages:
            logger.info(f"No new emails found in the last {days_back} days")
            return []

        emails = []
        new_processed_ids = set()

        # Process emails in parallel using asyncio
        async def process_email(message):
            msg_id = message["id"]
            if msg_id in processed_ids:
                return None

            msg = (
                self.service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
            email_data = self._parse_email_message(msg, whitelist)

            if email_data:
                new_processed_ids.add(msg_id)
                return email_data
            return None

        # Process emails concurrently
        tasks = [process_email(message) for message in messages]
        results = await asyncio.gather(*tasks)

        # Filter out None results and update processed IDs
        emails = [email for email in results if email is not None]
        self._update_processed_ids(processed_ids.union(new_processed_ids))

        return emails

    def _parse_email_message(self, msg: Dict, whitelist: set) -> Optional[Dict]:
        """Parses a Gmail message into a structured format"""
        payload = msg["payload"]
        headers = {
            header["name"]: header["value"] for header in payload.get("headers", [])
        }

        sender = headers.get("From", "")
        sender_email = re.search(r"<(.+?)>", sender)
        sender_email = sender_email.group(1) if sender_email else sender.strip()

        if sender_email not in whitelist:
            return None

        body = self._extract_email_body(payload)

        return {
            "subject": headers.get("Subject", ""),
            "sender": sender,
            "date": headers.get("Date", ""),
            "snippet": msg.get("snippet", ""),
            "body": body,
        }

    def _extract_email_body(self, payload: Dict) -> str:
        """Extracts email body from Gmail payload"""
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        return base64.urlsafe_b64decode(data).decode("utf-8")
        else:
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8")
        return ""


from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
from typing import List, Dict, Optional


@dataclass
class Article:
    title: str
    content: str
    source: str
    url: Optional[str]
    date: datetime
    topic: str
    hash: str = ""

    def __post_init__(self):
        # Generate content hash to help identify similar articles
        self.hash = hashlib.md5(
            f"{self.title}{self.content[:200]}".encode()
        ).hexdigest()


@dataclass
class NewsletterContent:
    summary: str
    key_facts: List[str]
    articles: List[Article]
    date: datetime


class NewsletterProcessor:
    def __init__(self):
        self.openai_client = AsyncOpenAI()

    def _parse_email_date(self, date_str: str) -> datetime:
        """Parse email date string handling various formats including UTC with timezone offset"""
        try:
            # Remove the (UTC) suffix if present while keeping the timezone offset
            date_str = date_str.replace(" (UTC)", "")
            # Now parse with timezone offset
            return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
        except ValueError as e:
            try:
                # Try without timezone if that fails
                return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S")
            except ValueError:
                # Fallback to current date if parsing fails
                logger.warning(
                    f"Could not parse date: {date_str}. Error: {str(e)}. Using current datetime."
                )
                return datetime.now()

    @error_handler
    async def process_emails(self, emails: List[Dict]) -> List[Article]:
        """Process emails into structured articles"""
        articles = []

        for email in emails:
            try:
                # Extract articles from email using OpenAI
                extracted_data = await self._extract_articles_from_email(email)

                # Convert to Article objects
                for article_data in extracted_data.get("articles", []):
                    article = Article(
                        title=article_data["title"],
                        content=article_data["content"],
                        source=email["sender"],
                        url=article_data.get("url"),
                        date=self._parse_email_date(email["date"]),
                        topic=article_data["topic"],
                    )
                    articles.append(article)

                # Save processed email to processed directory
                email_copy = email.copy()
                email_copy["extracted_articles"] = extracted_data.get("articles", [])
                save_individual_email(email_copy, processed=True)

            except Exception as e:
                logger.error(f"Error processing email: {str(e)}")
                continue

        return articles

    async def _extract_articles_from_email(self, email: Dict) -> Dict:
        """Extract structured articles from email content"""
        prompt = f"""
        Extract articles from this newsletter email. For each article, identify:
        - Title
        - Main content
        - Topic category
        - Any URLs mentioned
        
        Format the output as JSON:
        {{
            "articles": [
                {{
                    "title": "Article title",
                    "content": "Main content",
                    "topic": "Topic category",
                    "url": "URL if present"
                }}
            ]
        }}
        
        Email content:
        {email['body']}
        """

        try:
            completion = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Extract structured article data from newsletter emails.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            return json.loads(completion.choices[0].message.content)
        except Exception as e:
            logger.error(f"Error extracting articles: {str(e)}")
            return {"articles": []}

    def group_similar_articles(self, articles: List[Article]) -> List[List[Article]]:
        """Group similar articles together based on content similarity"""
        from difflib import SequenceMatcher

        def similarity_score(a: Article, b: Article) -> float:
            # Calculate similarity based on title and content
            title_sim = SequenceMatcher(None, a.title, b.title).ratio()
            content_sim = SequenceMatcher(
                None, a.content[:200], b.content[:200]
            ).ratio()
            return (title_sim * 0.6) + (content_sim * 0.4)

        groups = []
        used_articles = set()

        for article in articles:
            if article.hash in used_articles:
                continue

            group = [article]
            used_articles.add(article.hash)

            for other in articles:
                if other.hash in used_articles:
                    continue

                if similarity_score(article, other) > 0.6:  # Threshold for similarity
                    group.append(other)
                    used_articles.add(other.hash)

            groups.append(group)

        return groups

    async def generate_daily_summary(
        self, articles: List[Article]
    ) -> NewsletterContent:
        """Generate daily summary and key facts from articles"""
        # Filter for last day's articles
        yesterday = datetime.now() - timedelta(days=1)
        recent_articles = [a for a in articles if a.date > yesterday]

        if not recent_articles:
            return NewsletterContent(
                summary="No new articles for today.",
                key_facts=[],
                articles=[],
                date=datetime.now(),
            )

        # Prepare content for summary generation
        articles_text = "\n\n".join(
            f"Title: {a.title}\nContent: {a.content}" for a in recent_articles
        )

        prompt = f"""
        Analyze these AI news articles and generate:
        1. A high-level summary of the day's AI news
        2. Key facts and developments as bullet points
        
        Format the output as JSON:
        {{
            "summary": "Overall summary of the day's news",
            "key_facts": [
                "Key fact 1",
                "Key fact 2",
                ...
            ]
        }}
        
        Articles:
        {articles_text}
        """

        try:
            completion = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Generate concise summaries of AI news.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )

            result = json.loads(completion.choices[0].message.content)

            return NewsletterContent(
                summary=result["summary"],
                key_facts=result["key_facts"],
                articles=recent_articles,
                date=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return None


async def main():
    """Process all unprocessed emails in the backlog"""
    try:
        # Initialize clients
        gmail_client = GmailClient()
        processor = NewsletterProcessor()

        # Read and process all unprocessed emails
        logger.info("Starting to process email backlog...")
        emails = await gmail_client.read_emails(process_all=True)

        if not emails:
            logger.info("No unprocessed emails found")
            return

        logger.info(f"Found {len(emails)} unprocessed emails")

        # Save raw emails
        for email in emails:
            save_individual_email(email, processed=False)

        # Process emails and generate newsletter
        articles = await processor.process_emails(emails)
        if not articles:
            logger.error("Failed to process emails into articles")
            return

        # Generate newsletter content
        newsletter_content = await processor.generate_daily_summary(articles)
        if newsletter_content is None:
            logger.error("Failed to generate newsletter summary")
            return

        # Send newsletter
        recipient = os.getenv("NEWSLETTER_RECIPIENT")
        if await send_newsletter(
            gmail_client.service, "AI Newsletter Update", newsletter_content, recipient
        ):
            logger.info("Newsletter sent successfully")
        else:
            logger.error("Failed to send newsletter")

    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
