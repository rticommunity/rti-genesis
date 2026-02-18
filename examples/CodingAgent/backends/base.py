"""
CodingBackend — Abstract base class for coding harness backends.

Each backend knows how to build a subprocess command, sanitize the
environment, and parse one stdout line into a CodingEvent.
"""

import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import List, Optional

from .events import CodingEvent


class CodingBackend(ABC):
    """Subprocess bridge to a coding harness CLI."""

    def __init__(self):
        self._auth_mode: str = "subscription"  # default

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier: 'claude' or 'codex'."""

    @property
    @abstractmethod
    def cli_binary(self) -> str:
        """Name of the CLI binary on PATH."""

    @property
    @abstractmethod
    def api_key_env_vars(self) -> List[str]:
        """Env var names that trigger API billing when present."""

    @abstractmethod
    def build_command(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        cwd: Optional[str] = None,
    ) -> List[str]:
        """Construct the subprocess argv."""

    @abstractmethod
    def build_env(self) -> dict:
        """Return env dict, stripping billing keys when in subscription mode."""

    @abstractmethod
    def parse_line(self, line: str) -> Optional[CodingEvent]:
        """Parse one stdout JSON line into a normalized event (or None to skip)."""

    # ------------------------------------------------------------------
    # Concrete helpers
    # ------------------------------------------------------------------

    def set_auth_mode(self, mode: str) -> None:
        """Set the auth mode ('subscription' or 'api_key')."""
        self._auth_mode = mode

    def check_cli_installed(self) -> bool:
        """Return True if the CLI binary is on PATH."""
        return shutil.which(self.cli_binary) is not None

    def probe_command(self) -> List[str]:
        """Return a lightweight probe command for auth detection."""
        return self.build_command(prompt="ping")
