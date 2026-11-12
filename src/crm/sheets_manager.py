"""
Google Sheets CRM Manager — manages influencer data in Google Sheets.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# ── Column layout for the main "Influencers" sheet ──────────────────────
HEADER_ROW = [
    "Name",
    "Username",
    "Profile URL",
    "Niche",
    "Followers",
    "Engagement Rate",
    "Email",
    "AI Score",
    "AI Summary",
    "Status",
    "Email Sent Date",
    "Follow-up Count",
    "Last Reply Date",
    "Last Activity",
    "Notes",
]

ACTIVITY_LOG_HEADER = ["Timestamp", "Username", "Action", "Details"]

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsManager:
    """Manages Google Sheets as a lightweight CRM for influencer outreach."""

    def __init__(self, credentials_path: str, sheet_id: str) -> None:
        self.credentials_path = credentials_path
        self.sheet_id = sheet_id
        self.service = None
        self._col_index: dict[str, int] = {
            name: idx for idx, name in enumerate(HEADER_ROW)
        }

    # ── Authentication ──────────────────────────────────────────────────

    def authenticate(self) -> None:
        """Run OAuth 2.0 flow (or reload saved token) and build the Sheets service."""
        creds: Optional[Credentials] = None
        token_path = Path("token.json")

        if token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            except Exception:
                logger.warning("Could not load token.json — will re-authenticate.")

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    logger.warning("Token refresh failed — re-authenticating.")
                    creds = None

            if not creds:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)

            token_path.write_text(creds.to_json())
            logger.info("Credentials saved to token.json")

        self.service = build("sheets", "v4", credentials=creds)
        logger.info("Google Sheets service authenticated successfully.")

    # ── Helpers ──────────────────────────────────────────────────────────

    def _sheets(self):
        """Return the spreadsheets resource, ensuring we're authenticated."""
        if self.service is None:
            self.authenticate()
        return self.service.spreadsheets()

    def _get_all_values(self, range_name: str) -> list[list[str]]:
        """Read all values from a range."""
        try:
            result = (
                self._sheets()
                .values()
                .get(spreadsheetId=self.sheet_id, range=range_name)
                .execute()
            )
            return result.get("values", [])
        except HttpError as exc:
            logger.error("Failed to read range %s: %s", range_name, exc)
            return []

    def _append_row(self, range_name: str, row: list) -> bool:
        """Append a single row to the given range."""
        try:
            self._sheets().values().append(
                spreadsheetId=self.sheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]},
            ).execute()
            return True
        except HttpError as exc:
            logger.error("Failed to append row to %s: %s", range_name, exc)
            return False

    def _get_sheet_id_by_title(self, title: str) -> Optional[int]:
        """Return the numeric sheetId for a tab by its title, or None."""
        try:
            meta = self._sheets().get(spreadsheetId=self.sheet_id).execute()
            for sheet in meta.get("sheets", []):
                if sheet["properties"]["title"] == title:
                    return sheet["properties"]["sheetId"]
        except HttpError as exc:
            logger.error("Failed to fetch sheet metadata: %s", exc)
        return None

    # ── Sheet Setup ─────────────────────────────────────────────────────

    def setup_sheet(self) -> None:
        """Create header rows on both tabs if the sheet is empty.

        - Sheet1 (first tab): Influencer data with ``HEADER_ROW`` columns.
        - Activity Log (second tab): Append-only log with ``ACTIVITY_LOG_HEADER``.
        """
        # ── Main sheet (Sheet1) ──
        existing = self._get_all_values("Sheet1!A1:O1")
        if not existing:
            try:
                self._sheets().values().update(
                    spreadsheetId=self.sheet_id,
                    range="Sheet1!A1",
                    valueInputOption="RAW",
                    body={"values": [HEADER_ROW]},
                ).execute()
                logger.info("Header row created on Sheet1.")
            except HttpError as exc:
                logger.error("Failed to write header row: %s", exc)

        # ── Activity Log tab ──
        if self._get_sheet_id_by_title("Activity Log") is None:
            try:
                self._sheets().batchUpdate(
                    spreadsheetId=self.sheet_id,
                    body={
                        "requests": [
                            {
                                "addSheet": {
                                    "properties": {"title": "Activity Log"}
                                }
                            }
                        ]
                    },
                ).execute()
                logger.info("Created 'Activity Log' tab.")
            except HttpError as exc:
                logger.error("Failed to create Activity Log tab: %s", exc)

        activity_existing = self._get_all_values("Activity Log!A1:D1")
        if not activity_existing:
            try:
                self._sheets().values().update(
                    spreadsheetId=self.sheet_id,
                    range="Activity Log!A1",
                    valueInputOption="RAW",
                    body={"values": [ACTIVITY_LOG_HEADER]},
                ).execute()
                logger.info("Header row created on Activity Log.")
            except HttpError as exc:
                logger.error("Failed to write Activity Log header: %s", exc)

    # ── CRUD Operations ─────────────────────────────────────────────────

    def add_influencer(self, data: dict) -> bool:
        """Append an influencer row.  Returns False if the username already exists."""
        username = data.get("username", "").strip()
        if not username:
            logger.warning("add_influencer called without a username.")
            return False

        if self.find_influencer(username) is not None:
            logger.info("Duplicate username '%s' — skipping.", username)
            return False

        row = [str(data.get(h, "")) for h in
               [col.lower().replace(" ", "_") for col in HEADER_ROW]]
        # Alternatively map explicitly for safety:
        row = [
            str(data.get("name", "")),
            str(data.get("username", "")),
            str(data.get("profile_url", "")),
            str(data.get("niche", "")),
            str(data.get("followers", "")),
            str(data.get("engagement_rate", "")),
            str(data.get("email", "")),
            str(data.get("ai_score", "")),
            str(data.get("ai_summary", "")),
            str(data.get("status", "New Lead")),
            str(data.get("email_sent_date", "")),
            str(data.get("follow_up_count", "0")),
            str(data.get("last_reply_date", "")),
            str(data.get("last_activity", "")),
            str(data.get("notes", "")),
        ]

        success = self._append_row("Sheet1!A:O", row)
        if success:
            logger.info("Added influencer @%s.", username)
        return success

    def update_status(self, username: str, new_status: str, notes: str = "") -> None:
        """Update the Status column for *username* and log the change."""
        self.update_field(username, "Status", new_status)
        if notes:
            self.update_field(username, "Notes", notes)
        self.update_field(username, "Last Activity", datetime.now().isoformat(timespec="seconds"))
        self.log_activity(username, "Status Change", f"→ {new_status}" + (f" | {notes}" if notes else ""))

    def get_influencers_by_status(self, status: str) -> list[dict]:
        """Return all influencer rows whose Status matches *status*."""
        return [row for row in self.get_all_influencers() if row.get("Status") == status]

    def get_all_influencers(self) -> list[dict]:
        """Return every data row as a list of dicts keyed by header name."""
        rows = self._get_all_values("Sheet1!A:O")
        if len(rows) < 2:
            return []
        header = rows[0]
        results: list[dict] = []
        for row in rows[1:]:
            # Pad short rows so zip works
            padded = row + [""] * (len(header) - len(row))
            results.append(dict(zip(header, padded)))
        return results

    def find_influencer(self, username: str) -> Optional[dict]:
        """Find a single influencer by username (case-insensitive)."""
        username_lower = username.strip().lower()
        for inf in self.get_all_influencers():
            if inf.get("Username", "").strip().lower() == username_lower:
                return inf
        return None

    def update_field(self, username: str, field: str, value: str) -> None:
        """Update a single field (column) for the given username."""
        if field not in self._col_index:
            logger.error("Unknown field '%s'. Valid fields: %s", field, list(self._col_index.keys()))
            return

        rows = self._get_all_values("Sheet1!A:O")
        if len(rows) < 2:
            logger.warning("Sheet has no data rows.")
            return

        username_col = self._col_index["Username"]
        target_col = self._col_index[field]
        username_lower = username.strip().lower()

        for row_idx, row in enumerate(rows[1:], start=2):  # 1-indexed, skip header
            padded = row + [""] * (len(HEADER_ROW) - len(row))
            if padded[username_col].strip().lower() == username_lower:
                cell = f"Sheet1!{chr(65 + target_col)}{row_idx}"
                try:
                    self._sheets().values().update(
                        spreadsheetId=self.sheet_id,
                        range=cell,
                        valueInputOption="USER_ENTERED",
                        body={"values": [[value]]},
                    ).execute()
                    logger.info("Updated %s for @%s to '%s'.", field, username, value)
                except HttpError as exc:
                    logger.error("Failed to update %s for @%s: %s", field, username, exc)
                return

        logger.warning("Username '%s' not found for update_field.", username)

    # ── Activity Log ────────────────────────────────────────────────────

    def log_activity(self, username: str, action: str, details: str) -> None:
        """Append an entry to the Activity Log tab."""
        timestamp = datetime.now().isoformat(timespec="seconds")
        self._append_row("Activity Log!A:D", [timestamp, username, action, details])
        logger.debug("Logged activity: %s | %s | %s", username, action, details)

    # ── Conditional Formatting ──────────────────────────────────────────

    def apply_formatting(self) -> None:
        """Apply conditional-formatting rules to the main sheet.

        Colours by Status column value:
        - Green  → "Interested" / "Collaboration Confirmed"
        - Red    → "Not Interested"
        - Yellow → "Follow-up Due"
        - Blue   → "Replied"
        - Gray   → header row (row 1)
        """
        sheet_id = self._get_sheet_id_by_title("Sheet1")
        if sheet_id is None:
            # Fall back — the first sheet might not be titled "Sheet1"
            try:
                meta = self._sheets().get(spreadsheetId=self.sheet_id).execute()
                sheet_id = meta["sheets"][0]["properties"]["sheetId"]
            except (HttpError, KeyError, IndexError) as exc:
                logger.error("Cannot determine sheetId for formatting: %s", exc)
                return

        status_col = self._col_index["Status"]  # 0-based
        num_cols = len(HEADER_ROW)

        def _text_rule(text: str, rgb: dict) -> dict:
            return {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [
                            {
                                "sheetId": sheet_id,
                                "startRowIndex": 1,  # skip header
                                "startColumnIndex": 0,
                                "endColumnIndex": num_cols,
                            }
                        ],
                        "booleanRule": {
                            "condition": {
                                "type": "CUSTOM_FORMULA",
                                "values": [
                                    {
                                        "userEnteredValue": f'=${ chr(65 + status_col)}2="{text}"'
                                    }
                                ],
                            },
                            "format": {"backgroundColor": rgb},
                        },
                    },
                    "index": 0,
                }
            }

        green = {"red": 0.85, "green": 0.93, "blue": 0.83}
        red = {"red": 0.96, "green": 0.80, "blue": 0.80}
        yellow = {"red": 1.0, "green": 0.95, "blue": 0.75}
        blue = {"red": 0.81, "green": 0.89, "blue": 0.95}
        gray = {"red": 0.90, "green": 0.90, "blue": 0.90}

        requests_body: list[dict] = [
            _text_rule("Interested", green),
            _text_rule("Collaboration Confirmed", green),
            _text_rule("Not Interested", red),
            _text_rule("Follow-up Due", yellow),
            _text_rule("Replied", blue),
            # Gray header row (row 1)
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": num_cols,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": gray,
                            "textFormat": {"bold": True},
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            },
        ]

        try:
            self._sheets().batchUpdate(
                spreadsheetId=self.sheet_id,
                body={"requests": requests_body},
            ).execute()
            logger.info("Conditional formatting applied successfully.")
        except HttpError as exc:
            logger.error("Failed to apply formatting: %s", exc)
