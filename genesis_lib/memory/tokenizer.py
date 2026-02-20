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
Tokenizer module — Pluggable token counting for persistent memory.

Two built-in strategies:
- WordEstimateTokenizer: len(text.split()) * 1.3 (no dependencies, default)
- TiktokenTokenizer: wraps tiktoken if available (optional dependency)
"""

from abc import ABC, abstractmethod
import math


class TokenizerBase(ABC):
    """Abstract token counter."""

    @abstractmethod
    def count(self, text: str) -> int:
        """Return the estimated token count for the given text."""


class WordEstimateTokenizer(TokenizerBase):
    """Token estimator based on word count * 1.3 ratio."""

    def __init__(self, ratio: float = 1.3):
        self.ratio = ratio

    def count(self, text: str) -> int:
        if not text:
            return 0
        return math.ceil(len(text.split()) * self.ratio)


class TiktokenTokenizer(TokenizerBase):
    """Token counter using the tiktoken library (optional dependency)."""

    def __init__(self, model: str = "gpt-4"):
        try:
            import tiktoken
            self._enc = tiktoken.encoding_for_model(model)
        except ImportError:
            raise ImportError(
                "tiktoken is required for TiktokenTokenizer. "
                "Install with: pip install tiktoken"
            )

    def count(self, text: str) -> int:
        if not text:
            return 0
        return len(self._enc.encode(text))


def create_tokenizer(config: dict = None) -> TokenizerBase:
    """Factory function to create a tokenizer from config.

    Args:
        config: Dict with 'type' key ('word_estimate' or 'tiktoken')
                and optional 'model' for tiktoken.

    Returns:
        A TokenizerBase instance.
    """
    if config is None:
        config = {}
    tok_type = config.get("type", "word_estimate")

    if tok_type == "word_estimate":
        return WordEstimateTokenizer(ratio=config.get("ratio", 1.3))
    elif tok_type == "tiktoken":
        return TiktokenTokenizer(model=config.get("model", "gpt-4"))
    else:
        raise ValueError(f"Unknown tokenizer type: {tok_type}")
