# Copyright (c) 2025, RTI & Jason Upchurch

"""
Backward compatibility wrapper - use genesis_lib.replier instead

This module provides backward compatibility for code using the old
GenesisRPCService class name. New code should use GenesisReplier from
the replier module directly.
"""

from genesis_lib.replier import GenesisReplier

# Backward compatibility alias
GenesisRPCService = GenesisReplier

__all__ = ['GenesisReplier', 'GenesisRPCService']
