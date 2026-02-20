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
Genesis Memory Package

Re-exports the original MemoryAdapter, SimpleMemoryAdapter, and MemoryRouter
from base.py (formerly memory.py), plus new persistent memory components.
"""

# Re-export everything from the original memory module (backwards compatibility)
from .base import MemoryAdapter, SimpleMemoryAdapter, MemoryRouter

from .storage_backend import StorageBackend
from .sqlite_backend import SQLiteBackend
from .tokenizer import TokenizerBase, WordEstimateTokenizer, TiktokenTokenizer, create_tokenizer

__all__ = [
    # Original exports (backwards compatibility)
    "MemoryAdapter",
    "SimpleMemoryAdapter",
    "MemoryRouter",
    # New persistent memory exports
    "StorageBackend",
    "SQLiteBackend",
    "TokenizerBase",
    "WordEstimateTokenizer",
    "TiktokenTokenizer",
    "create_tokenizer",
]

# SQLAlchemy backend is an optional dependency
try:
    from .sqlalchemy_backend import SQLAlchemyBackend
    __all__.append("SQLAlchemyBackend")
except ImportError:
    pass

# PersistentMemoryAdapter depends on the above
try:
    from .persistent_adapter import PersistentMemoryAdapter
    __all__.append("PersistentMemoryAdapter")
except ImportError:
    pass
