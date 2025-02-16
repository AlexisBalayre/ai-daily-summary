import os
import json
import base64
import re
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import asyncio

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .utils import logger, error_handler, config


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
        date_2_days_ago = (datetime.utcnow() - timedelta(days=2)).strftime("%Y/%m/%d")

        # Fetch email IDs from the last 2 days
        search_query = f"after:{date_2_days_ago}"
        search_results = (
            self.service.users().messages().list(userId="me", q=search_query).execute()
        )
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
