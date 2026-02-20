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
Config module — JSON config file loading + environment variable support.

Provides:
- load_config(path) — reads JSON, validates, returns dict
- load_config_from_env() — reads GENESIS_MEMORY_CONFIG env var
- DEFAULT_CONFIG — sensible defaults for all settings
"""

import json
import os

DEFAULT_CONFIG = {
    "storage": {
        "backend": "sqlite",
        "path": "genesis_memory.db",
    },
    "compaction": {
        "soft_threshold_ratio": 0.6,
        "hard_threshold_ratio": 0.85,
        "model_context_window": 200000,
        "recent_window_size": 20,
        "chunk_size": 15,
    },
    "retrieval": {
        "default_policy": "windowed",
        "default_k": 50,
    },
    "tokenizer": {
        "type": "word_estimate",
    },
}


def load_config(path: str) -> dict:
    """Load a memory config from a JSON file.

    Args:
        path: Path to the JSON config file.

    Returns:
        Merged config dict (file values override defaults).

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    with open(path, "r") as f:
        user_config = json.load(f)

    return _merge_config(DEFAULT_CONFIG, user_config)


def load_config_from_env() -> dict:
    """Load memory config from the GENESIS_MEMORY_CONFIG environment variable.

    Returns:
        Merged config dict.

    Raises:
        EnvironmentError: If GENESIS_MEMORY_CONFIG is not set.
        FileNotFoundError: If the referenced file does not exist.
    """
    config_path = os.environ.get("GENESIS_MEMORY_CONFIG")
    if not config_path:
        raise EnvironmentError(
            "GENESIS_MEMORY_CONFIG environment variable is not set. "
            "Set it to the path of your memory config JSON file."
        )
    return load_config(config_path)


def _merge_config(defaults: dict, overrides: dict) -> dict:
    """Deep-merge overrides into defaults."""
    result = defaults.copy()
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_config(result[key], value)
        else:
            result[key] = value
    return result
