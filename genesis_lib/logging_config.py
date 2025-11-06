# Copyright (c) 2025, RTI & Jason Upchurch

import logging

# Define all known logger names used within the genesis_lib
# This list should be maintained as new loggers are added to the library.
GENESIS_LIB_LOGGERS = [
    "genesis_lib.agent",
    "genesis_lib.interface",
    "genesis_lib.monitored_agent",
    "genesis_lib.monitored_interface",
    "genesis_lib.openai_genesis_agent",
    "genesis_lib.function_classifier",
    "genesis_lib.function_discovery",
    "genesis_lib.generic_function_client",
    "genesis_lib.requester",
    "genesis_lib.replier",
    "genesis_lib.genesis_app",
    # Add other genesis_lib logger names here as they are created
]

def set_genesis_library_log_level(level: int) -> None:
    """
    Sets the logging level for all predefined genesis_lib loggers.

    Args:
        level: The logging level (e.g., logging.DEBUG, logging.INFO).
    """
    for logger_name in GENESIS_LIB_LOGGERS:
        logging.getLogger(logger_name).setLevel(level)
    # Also set the level for the root of the genesis_lib package itself,
    # in case some modules use logging.getLogger(__name__) directly under genesis_lib
    # and are not in the explicit list.
    logging.getLogger("genesis_lib").setLevel(level)

def get_genesis_library_loggers() -> list[str]:
    """Returns a copy of the list of known genesis_lib logger names."""
    return list(GENESIS_LIB_LOGGERS) 