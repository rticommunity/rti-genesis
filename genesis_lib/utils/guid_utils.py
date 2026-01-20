#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
#                                                                                    #
# RTI grants Licensee a license to use, modify, compile, and create derivative       #
# works of the Software. Licensee has the right to distribute object form only       #
# for use with RTI products. The Software is provided "as is", with no warranty      #
# of any type, including any warranty for fitness for any purpose. RTI is under no   #
# obligation to maintain or support the Software. RTI shall not be liable for any    #
# incidental or consequential damages arising out of the use or inability to use     #
# the software.                                                                      #
# ####################################################################################

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


