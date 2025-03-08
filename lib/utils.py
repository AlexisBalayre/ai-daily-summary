import os
import json
import base64
import re
from typing import Optional, Dict, List
from datetime import datetime
from dataclasses import dataclass
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parsedate_to_datetime
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from functools import wraps
import asyncio


# Set up logging with rotating file handler
def setup_logging():

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
    EMAIL_TEMPLATES_DIR: Path = Path("email_templates")
    GITHUB_HOT_REPOS_EMAIL_TEMPLATE: Path = (
        EMAIL_TEMPLATES_DIR / "github_hot_repos_email_template.html"
    )
    AI_DAILY_NEWS_EMAIL_TEMPLATE: Path = (
        EMAIL_TEMPLATES_DIR / "ai_daily_news_email_template.html"
    )

    def __post_init__(self):
        # Create necessary directories
        self.DATA_DIR.mkdir(exist_ok=True)
        self.RAW_EMAILS_DIR.mkdir(parents=True, exist_ok=True)
        self.PROCESSED_EMAILS_DIR.mkdir(parents=True, exist_ok=True)


config = Config()
logger = setup_logging()  # Initialize logger


def load_template(template_name: str) -> str:
    """Load an email template from file"""
    if template_name == "github_hot_repos":
        template_file = config.GITHUB_HOT_REPOS_EMAIL_TEMPLATE
    elif template_name == "ai_daily_news":
        template_file = config.AI_DAILY_NEWS_EMAIL_TEMPLATE
    else:
        raise FileNotFoundError("Email template file not found.")
    return template_file.read_text()


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


def send_ai_daily_newsletter(service, subject, content, recipients) -> bool:
    try:
        template = load_template("ai_daily_news")
        html_content = template.replace(
            "{{date}}", datetime.now().strftime("%B %d, %Y")
        )
        html_content = html_content.replace("{{summary}}", content.summary)
        html_content = html_content.replace("{{year}}", str(datetime.now().year))
        html_content = html_content.replace(
            "{{key_facts}}", "".join(f"<li> {fact}</li>" for fact in content.key_facts)
        )

        categories = {
            "AI Research and Advances": [],
            "AI Products, Tools, and Repositories": [],
            "Data Science Techniques and Tips": [],
            "Industry News and Trends": [],
        }

        for article in content.articles:
            topic_lower = article.topic.lower()
            if any(
                word in topic_lower
                for word in ["research", "study", "advance", "breakthrough"]
            ):
                categories["AI Research and Advances"].append(article)
            elif any(
                word in topic_lower
                for word in ["tool", "product", "repository", "framework"]
            ):
                categories["AI Products, Tools, and Repositories"].append(article)
            elif any(
                word in topic_lower
                for word in ["tip", "technique", "guide", "tutorial"]
            ):
                categories["Data Science Techniques and Tips"].append(article)
            else:
                categories["Industry News and Trends"].append(article)

        articles_html = ""
        flag = False
        for category, articles in categories.items():
            if articles:
                if flag:
                    articles_html += f"<br/><h3>{category}</h3>"
                else:
                    articles_html += f"<h3>{category}</h3>"
                flag = True
                for article in articles:
                    articles_html += (
                        f"<h4>{article.title}</h4>"
                        f"<p>{article.content}</p>"
                        f'<p>Source: {article.source} | <a href="{article.url}">Read more</a></p>'
                    )

        html_content = html_content.replace("{{articles}}", articles_html)

        # Split and clean the recipient addresses.
        recipients_list = [r.strip() for r in recipients.split(",") if r.strip()]

        for recipient in recipients_list:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["To"] = recipient  # Each recipient sees only their own email.
            message["From"] = "me"

            part = MIMEText(html_content, "html")
            message.attach(part)

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True
    except Exception as e:
        logging.error(f"Failed to send newsletter: {e}")
        return False


def send_github_hot_repositories_newsletter(
    service, subject, trending_repositories, explore_repositories, recipients
) -> bool:
    try:
        template = load_template("github_hot_repos")
        html_content = template.replace(
            "{{date}}", datetime.now().strftime("%B %d, %Y")
        )
        html_content = html_content.replace("{{year}}", str(datetime.now().year))

        trending_html = ""
        for repo in trending_repositories:
            trending_html += (
                f'<div class="repository">'
                f'<div class="repository-header">'
                f'<a class="repository-title repository-link" href="{repo.url}">{repo.author}/{repo.name}</a>'
                f"</div>"
                f'<div class="repository-stats">'
                f'<span class="stat">⭐ {repo.stars}</span>'
                f'<span class="stat">🍴 {repo.forks}</span>'
                f"</div>"
                f'<span class="language-tag">{repo.language}</span>'
                f'<p class="description">{repo.description}</p>'
                f"</div>"
            )

        explore_html = ""
        for repo in explore_repositories:
            explore_html += (
                f'<div class="repository">'
                f'<div class="repository-header">'
                f'<a class="repository-title repository-link" href="{repo.url}">{repo.author}/{repo.name}</a>'
                f"</div>"
                f'<div class="repository-stats">'
                f'<span class="stat">⭐ {repo.stars}</span>'
                f"</div>"
                f'<span class="language-tag">{repo.language}</span>'
                f'<p class="description">{repo.description}</p>'
                f"</div>"
            )

        html_content = html_content.replace("{{trending_repositories}}", trending_html)
        html_content = html_content.replace("{{explore_repositories}}", explore_html)

        # Split and clean the recipient addresses.
        recipients_list = [r.strip() for r in recipients.split(",") if r.strip()]

        for recipient in recipients_list:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["To"] = recipient  # Each recipient sees only their own email.
            message["From"] = "me"

            part = MIMEText(html_content, "html")
            message.attach(part)

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True
    except Exception as e:
        logging.error(f"Failed to send newsletter: {e}")
        return False
