"""Gmail newsletter extractor."""

import base64
import json
import os
import re
from datetime import UTC, datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from ai_daily.config import config
from ai_daily.db.models import Source
from ai_daily.etl.extractors.base import BaseExtractor
from ai_daily.etl.types import RawContent


class GmailExtractor(BaseExtractor):
    """Extract newsletter content from Gmail."""

    def __init__(self):
        self.service = self._authenticate()
        self._processed_ids: set[str] = set()

    @property
    def supported_types(self) -> list[str]:
        return ["newsletter"]

    def _authenticate(self):
        """Authenticate with Gmail API using OAuth 2.0."""
        creds = None
        token_path = config.gmail.token_path

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), config.gmail.scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_config(
                    {
                        "web": {
                            "client_id": config.gmail.client_id,
                            "project_id": config.gmail.project_id,
                            "auth_uri": os.getenv("GOOGLE_AUTH_URI"),
                            "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
                            "auth_provider_x509_cert_url": os.getenv(
                                "GOOGLE_AUTH_PROVIDER_X509_CERT_URL"
                            ),
                            "client_secret": config.gmail.client_secret,
                            "redirect_uris": [f"http://localhost:{config.gmail.oauth_port}/"],
                        }
                    },
                    config.gmail.scopes,
                )
                creds = flow.run_local_server(port=config.gmail.oauth_port)

            with open(token_path, "w") as token:
                token.write(creds.to_json())

        return build("gmail", "v1", credentials=creds)

    def _load_whitelist(self, source: Source) -> set[str]:
        """Sender whitelist: the config file (editable from the dashboard) wins.

        A whitelist stored on the source row is only used as a fallback for
        databases seeded before the file became the single source of truth.
        """
        config_path = config.resolve_config_file()
        if config_path.exists():
            with open(config_path) as f:
                data = json.load(f)
            if "whitelist" in data:
                return set(data["whitelist"])

        if source.config and "whitelist" in source.config:
            return set(source.config["whitelist"])

        return set()

    def _parse_email_date(self, date_str: str) -> datetime | None:
        """Parse email date string."""
        date_str = date_str.replace(" (UTC)", "")
        try:
            return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
        except ValueError:
            try:
                return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S").replace(tzinfo=UTC)
            except ValueError:
                return None

    def _extract_email_body(self, payload: dict) -> str:
        """Extract email body from Gmail payload."""
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

    def _extract_sender_email(self, sender: str) -> str:
        """Extract email address from sender string."""
        match = re.search(r"<(.+?)>", sender)
        return match.group(1) if match else sender.strip()

    async def extract(self, source: Source) -> list[RawContent]:
        """Extract newsletters from Gmail."""
        whitelist = self._load_whitelist(source)
        days_back = source.config.get("days_back", 2) if source.config else 2

        date_threshold = (datetime.now(UTC) - timedelta(days=days_back)).strftime("%Y/%m/%d")
        search_query = f"after:{date_threshold}"

        results = self.service.users().messages().list(userId="me", q=search_query).execute()
        messages = results.get("messages", [])

        if not messages:
            return []

        raw_contents = []

        for message in messages:
            msg_id = message["id"]

            if msg_id in self._processed_ids:
                continue

            msg = (
                self.service.users().messages().get(userId="me", id=msg_id, format="full").execute()
            )
            payload = msg["payload"]
            headers = {h["name"]: h["value"] for h in payload.get("headers", [])}

            sender = headers.get("From", "")
            sender_email = self._extract_sender_email(sender)
            if sender_email not in whitelist:
                continue

            body = self._extract_email_body(payload)
            if not body:
                continue

            published_at = self._parse_email_date(headers.get("Date", ""))

            raw_content = RawContent(
                external_id=msg_id,
                title=headers.get("Subject", ""),
                content=body,
                author=sender,
                published_at=published_at,
                source_name=sender_email,
                metadata={
                    "gmail_id": msg_id,
                    "snippet": msg.get("snippet", ""),
                },
            )

            raw_contents.append(raw_content)
            self._processed_ids.add(msg_id)

        return raw_contents

    def get_external_id(self, item: RawContent) -> str:
        """Use Gmail message ID as external ID."""
        return item.external_id
