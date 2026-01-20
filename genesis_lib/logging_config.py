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
    "genesis_lib.function_requester",
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