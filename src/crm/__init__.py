"""
CRM Package
===========
Google Sheets CRM integration and lead lifecycle pipeline management.
"""

from .pipeline import LeadStatus, PipelineManager, STATUS_ACTIONS, VALID_TRANSITIONS
from .sheets_manager import HEADER_ROW, SheetsManager

__all__ = [
    "SheetsManager",
    "HEADER_ROW",
    "PipelineManager",
    "LeadStatus",
    "VALID_TRANSITIONS",
    "STATUS_ACTIONS",
]
