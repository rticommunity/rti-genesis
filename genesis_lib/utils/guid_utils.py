"""
GUID utilities for Genesis.

Provides helpers to convert and validate GUID/instance_handle strings used in
ContentFilteredTopic parameters and logging.
"""

from typing import Any


def format_guid(handle: Any) -> str:
    """
    Convert an RTI instance_handle/GUID to a canonical string form.
    """
    try:
        return str(handle)
    except Exception:
        return ""


def validate_guid(guid: str) -> bool:
    """
    Basic validation for GUID strings. Accept non-empty ASCII strings up to 128 chars.
    """
    if not isinstance(guid, str):
        return False
    if len(guid) == 0 or len(guid) > 128:
        return False
    return True


