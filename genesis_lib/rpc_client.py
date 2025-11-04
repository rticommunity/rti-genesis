"""
Backward compatibility wrapper - use genesis_lib.requester instead

This module provides backward compatibility for code using the old
GenesisRPCClient class name. New code should use GenesisRequester from
the requester module directly.

Copyright (c) 2025, RTI & Jason Upchurch
"""

from genesis_lib.requester import GenesisRequester

# Backward compatibility alias
GenesisRPCClient = GenesisRequester

__all__ = ['GenesisRequester', 'GenesisRPCClient']
