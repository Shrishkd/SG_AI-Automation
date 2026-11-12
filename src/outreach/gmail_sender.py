"""
Gmail API wrapper for sending outreach emails and tracking replies.
"""

import base64
import os
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from rich.console import Console

load_dotenv()

console = Console()

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

TOKEN_PATH = "gmail_token.json"


class GmailSender:
    """Handles all Gmail API operations for outreach campaigns."""

    def __init__(self) -> None:
        self.credentials_path: str = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        self.sender_email: str = os.getenv("GMAIL_SENDER_EMAIL", "")
        self.service: Any = None
        self._creds: Credentials | None = None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self) -> None:
        """Run OAuth 2.0 flow for Gmail API access.

        Loads an existing token from *gmail_token.json* when available,
        refreshes it if expired, or launches the interactive consent flow
        for first-time auth.
        """
        creds: Credentials | None = None

        if os.path.exists(TOKEN_PATH):
            try:
                creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
            except Exception as exc:
                console.log(f"[yellow]Could not load existing token:[/] {exc}")

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                console.log("[cyan]Refreshing expired Gmail token…[/]")
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Google credentials file not found at '{self.credentials_path}'. "
                        "Download it from the GCP console and set GOOGLE_CREDENTIALS_PATH."
                    )
                console.log("[cyan]Starting Gmail OAuth consent flow…[/]")
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)

            # Persist for next run
            with open(TOKEN_PATH, "w") as f:
                f.write(creds.to_json())
            console.log(f"[green]Gmail token saved to {TOKEN_PATH}[/]")

        self._creds = creds
        self.service = build("gmail", "v1", credentials=creds)
        console.log("[bold green]✓[/] Gmail API authenticated")

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
    ) -> dict[str, str]:
        """Send an email (or reply within an existing thread).

        Returns
        -------
        dict
            ``{"message_id": …, "thread_id": …, "sent_at": …}``
        """
        self._ensure_service()

        message = self._build_mime(to, subject, body, thread_id)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        payload: dict[str, Any] = {"raw": raw}
        if thread_id:
            payload["threadId"] = thread_id

        try:
            result = (
                self.service.users()
                .messages()
                .send(userId="me", body=payload)
                .execute()
            )
            console.log(f"[green]✓ Email sent to {to}[/]  messageId={result['id']}")
            return {
                "message_id": result["id"],
                "thread_id": result["threadId"],
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }

        except HttpError as exc:
            console.log(f"[bold red]Gmail send error:[/] {exc}")
            raise

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
    ) -> dict[str, str]:
        """Create a Gmail draft instead of sending immediately.

        Returns
        -------
        dict
            ``{"draft_id": …, "message_id": …, "thread_id": …}``
        """
        self._ensure_service()

        message = self._build_mime(to, subject, body, thread_id)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        draft_body: dict[str, Any] = {"message": {"raw": raw}}
        if thread_id:
            draft_body["message"]["threadId"] = thread_id

        try:
            result = (
                self.service.users()
                .drafts()
                .create(userId="me", body=draft_body)
                .execute()
            )
            console.log(f"[green]✓ Draft created for {to}[/]  draftId={result['id']}")
            return {
                "draft_id": result["id"],
                "message_id": result["message"]["id"],
                "thread_id": result["message"]["threadId"],
            }

        except HttpError as exc:
            console.log(f"[bold red]Gmail draft error:[/] {exc}")
            raise

    # ------------------------------------------------------------------
    # Reading / Replies
    # ------------------------------------------------------------------

    def get_replies(self, thread_id: str) -> list[dict[str, Any]]:
        """Fetch all messages in a thread and return them as dicts.

        Each dict contains: ``message_id``, ``from_email``, ``subject``,
        ``body``, ``received_at``, ``is_reply``.
        """
        self._ensure_service()

        try:
            thread = (
                self.service.users()
                .threads()
                .get(userId="me", id=thread_id, format="full")
                .execute()
            )
        except HttpError as exc:
            console.log(f"[red]Failed to fetch thread {thread_id}:[/] {exc}")
            return []

        messages: list[dict[str, Any]] = []
        raw_msgs = thread.get("messages", [])

        for idx, msg in enumerate(raw_msgs):
            headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}
            body_text = self._extract_body(msg["payload"])
            internal_ts = int(msg.get("internalDate", 0)) / 1000
            received_at = datetime.fromtimestamp(internal_ts, tz=timezone.utc).isoformat()

            messages.append(
                {
                    "message_id": msg["id"],
                    "from_email": headers.get("from", ""),
                    "subject": headers.get("subject", ""),
                    "body": body_text,
                    "received_at": received_at,
                    "is_reply": idx > 0,  # first message is the original
                }
            )

        return messages

    def check_for_new_replies(self, sent_threads: list[str]) -> list[dict[str, Any]]:
        """Check multiple threads for new replies (messages not from us).

        Returns a flat list of reply dicts across all threads.
        """
        all_replies: list[dict[str, Any]] = []
        for tid in sent_threads:
            thread_msgs = self.get_replies(tid)
            for msg in thread_msgs:
                if msg["is_reply"] and self.sender_email not in msg["from_email"]:
                    all_replies.append(msg)
        return all_replies

    def get_sent_emails(self, max_results: int = 100) -> list[dict[str, Any]]:
        """List recently-sent emails from the authenticated account.

        Returns list of dicts with ``message_id``, ``to``, ``subject``,
        ``sent_at``, ``thread_id``.
        """
        self._ensure_service()

        try:
            result = (
                self.service.users()
                .messages()
                .list(userId="me", labelIds=["SENT"], maxResults=max_results)
                .execute()
            )
        except HttpError as exc:
            console.log(f"[red]Failed to list sent emails:[/] {exc}")
            return []

        sent: list[dict[str, Any]] = []
        for entry in result.get("messages", []):
            try:
                msg = (
                    self.service.users()
                    .messages()
                    .get(userId="me", id=entry["id"], format="metadata",
                         metadataHeaders=["To", "Subject"])
                    .execute()
                )
                headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
                internal_ts = int(msg.get("internalDate", 0)) / 1000
                sent.append(
                    {
                        "message_id": msg["id"],
                        "to": headers.get("to", ""),
                        "subject": headers.get("subject", ""),
                        "sent_at": datetime.fromtimestamp(internal_ts, tz=timezone.utc).isoformat(),
                        "thread_id": msg.get("threadId", ""),
                    }
                )
            except HttpError:
                continue

        return sent

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_service(self) -> None:
        if self.service is None:
            raise RuntimeError("Gmail not authenticated. Call authenticate() first.")

    def _build_mime(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
    ) -> MIMEMultipart:
        """Build a MIME message suitable for the Gmail API."""
        msg = MIMEMultipart("alternative")
        msg["To"] = to
        msg["From"] = self.sender_email
        msg["Subject"] = subject

        if thread_id:
            msg["In-Reply-To"] = thread_id
            msg["References"] = thread_id

        # Attach plain-text body; add an HTML part so clients render line-breaks.
        msg.attach(MIMEText(body, "plain"))
        html_body = body.replace("\n", "<br>\n")
        msg.attach(MIMEText(html_body, "html"))

        return msg

    @staticmethod
    def _extract_body(payload: dict) -> str:
        """Recursively extract the text/plain body from a Gmail message payload."""
        if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

        for part in payload.get("parts", []):
            text = GmailSender._extract_body(part)
            if text:
                return text

        # Fallback: try body.data directly
        data = payload.get("body", {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

        return ""

