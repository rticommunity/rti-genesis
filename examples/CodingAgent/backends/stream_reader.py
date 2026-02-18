"""
Stream reader — reads and parses events from a coding harness subprocess.

Extracted as a standalone module so it can be tested without DDS imports.
"""

import asyncio
import logging
from typing import List, Optional, Tuple

from .base import CodingBackend
from .events import CodingEvent

logger = logging.getLogger(__name__)


async def read_events(
    proc, backend: CodingBackend, timeout: float
) -> Tuple[List[CodingEvent], str, Optional[str], bool]:
    """Read streaming events from a subprocess.

    Returns (events, result_text, session_id, timed_out).
    """
    events: List[CodingEvent] = []
    result_text = ""
    session_id: Optional[str] = None
    timed_out = False

    async def _stream():
        nonlocal result_text, session_id
        async for raw_line in proc.stdout:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            logger.debug("stdout: %s", line[:500])
            try:
                event = backend.parse_line(line)
            except Exception:
                logger.debug("parse_line raised on: %s", line[:200])
                continue
            if event is None:
                logger.debug("parse_line returned None for: %s", line[:200])
                continue

            events.append(event)
            logger.debug("event: kind=%s text=%s", event.kind, event.text[:200] if event.text else "")

            if event.kind == "init" and event.session_id:
                session_id = event.session_id
            elif event.kind == "text":
                result_text += event.text
            elif event.kind == "done" and event.text:
                result_text = event.text  # override

    try:
        await asyncio.wait_for(_stream(), timeout=timeout)
    except asyncio.TimeoutError:
        timed_out = True
        result_text = f"Request timed out after {timeout}s"

    logger.debug(
        "read_events complete: %d events, %d chars text, session=%s, timed_out=%s",
        len(events), len(result_text), session_id, timed_out,
    )
    return events, result_text, session_id, timed_out
