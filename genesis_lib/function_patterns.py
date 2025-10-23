# Copyright (c) 2025, RTI & Jason Upchurch

"""
Function success and failure patterns for the GENESIS distributed system.

NOTE: This module is not currently in use in the codebase. It is kept for potential future use
when a more robust pattern-based error handling system is needed. The current implementation
handles errors directly in:
- GenericFunctionClient for function discovery and calling
- OpenAIGenesisAgent for agent-specific error handling
- utils/function_utils.py for function utilities

The module provides useful abstractions for:
- Pattern-based success/failure detection
- Structured error handling with recovery hints
- Type-based and regex-based pattern matching
- Centralized pattern registry
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import re

@dataclass
class SuccessPattern:
    """Pattern for identifying successful function execution"""
    pattern_type: str  # "regex", "value_range", "type_check", etc.
    pattern: Any  # The actual pattern to match
    description: str  # Human-readable description of what success looks like

@dataclass
class FailurePattern:
    """Pattern for identifying function failures"""
    pattern_type: str  # "regex", "exception", "value_range", etc.
    pattern: Any  # The actual pattern to match
    error_code: str  # Unique error code
    description: str  # Human-readable description of the failure
    recovery_hint: Optional[str] = None  # Optional hint for recovery

class FunctionPatternRegistry:
    """Registry for function success and failure patterns"""
    
    def __init__(self):
        self.success_patterns: Dict[str, List[SuccessPattern]] = {}
        self.failure_patterns: Dict[str, List[FailurePattern]] = {}
    
    def register_patterns(self,
                         function_id: str,
                         success_patterns: Optional[List[SuccessPattern]] = None,
                         failure_patterns: Optional[List[FailurePattern]] = None):
        """
        Register success and failure patterns for a function.
        
        Args:
            function_id: Unique identifier for the function
            success_patterns: List of patterns indicating successful execution
            failure_patterns: List of patterns indicating failures
        """
        if success_patterns:
            self.success_patterns[function_id] = success_patterns
        if failure_patterns:
            self.failure_patterns[function_id] = failure_patterns
    
    def check_result(self, function_id: str, result: Any) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Check if a function result matches success or failure patterns.
        
        Args:
            function_id: ID of the function to check
            result: Result to check against patterns
            
        Returns:
            Tuple of (is_success, error_code, recovery_hint)
        """
        # Check failure patterns first (they take precedence)
        if function_id in self.failure_patterns:
            for pattern in self.failure_patterns[function_id]:
                if self._matches_pattern(result, pattern):
                    return False, pattern.error_code, pattern.recovery_hint
        
        # Check success patterns
        if function_id in self.success_patterns:
            all_patterns_match = True
            for pattern in self.success_patterns[function_id]:
                if not self._matches_pattern(result, pattern):
                    all_patterns_match = False
                    break
            if all_patterns_match:
                return True, None, None
            return False, None, None
        
        # Default to success if no patterns match
        return True, None, None
    
    def _matches_pattern(self, result: Any, pattern: SuccessPattern | FailurePattern) -> bool:
        """Check if a result matches a pattern"""
        if pattern.pattern_type == "regex":
            if isinstance(result, str):
                return bool(re.search(pattern.pattern, result))
            return False
        
        elif pattern.pattern_type == "value_range":
            if isinstance(result, (int, float)):
                min_val, max_val = pattern.pattern
                return min_val <= result <= max_val
            return False
        
        elif pattern.pattern_type == "type_check":
            return isinstance(result, pattern.pattern)
        
        elif pattern.pattern_type == "exception":
            if isinstance(pattern.pattern, type):
                return isinstance(result, pattern.pattern)
            return isinstance(result, Exception) and isinstance(result, type(pattern.pattern))
        
        return False

# Example patterns for common functions
CALCULATOR_PATTERNS = {
    "add": {
        "success": [
            SuccessPattern(
                pattern_type="type_check",
                pattern=(int, float),
                description="Result should be a number"
            ),
        ],
        "failure": [
            FailurePattern(
                pattern_type="exception",
                pattern=TypeError,
                error_code="CALC_TYPE_ERROR",
                description="Invalid argument types",
                recovery_hint="Ensure both arguments are numbers"
            ),
            FailurePattern(
                pattern_type="regex",
                pattern=r"overflow|too large",
                error_code="CALC_OVERFLOW",
                description="Number too large",
                recovery_hint="Use smaller numbers"
            )
        ]
    },
    "divide": {
        "success": [
            SuccessPattern(
                pattern_type="type_check",
                pattern=(int, float),
                description="Result should be a number"
            )
        ],
        "failure": [
            FailurePattern(
                pattern_type="exception",
                pattern=ZeroDivisionError,
                error_code="CALC_DIV_ZERO",
                description="Division by zero",
                recovery_hint="Ensure denominator is not zero"
            )
        ]
    }
}

LETTER_COUNTER_PATTERNS = {
    "count_letter": {
        "success": [
            SuccessPattern(
                pattern_type="type_check",
                pattern=int,
                description="Result should be a non-negative integer"
            ),
            SuccessPattern(
                pattern_type="value_range",
                pattern=(0, float('inf')),
                description="Count should be non-negative"
            )
        ],
        "failure": [
            FailurePattern(
                pattern_type="exception",
                pattern=ValueError,
                error_code="LETTER_INVALID",
                description="Invalid letter parameter",
                recovery_hint="Ensure letter parameter is a single character"
            )
        ]
    },
    "count_multiple_letters": {
        "success": [
            SuccessPattern(
                pattern_type="type_check",
                pattern=dict,
                description="Result should be a dictionary of counts"
            )
        ],
        "failure": [
            FailurePattern(
                pattern_type="exception",
                pattern=ValueError,
                error_code="LETTERS_INVALID",
                description="Invalid letters parameter",
                recovery_hint="Ensure all letters are single characters"
            )
        ]
    }
}

# Create global pattern registry
pattern_registry = FunctionPatternRegistry()

# Register common patterns
def register_common_patterns():
    """Register patterns for common functions"""
    for func_name, patterns in CALCULATOR_PATTERNS.items():
        pattern_registry.register_patterns(
            func_name,
            success_patterns=patterns.get("success"),
            failure_patterns=patterns.get("failure")
        )
    
    for func_name, patterns in LETTER_COUNTER_PATTERNS.items():
        pattern_registry.register_patterns(
            func_name,
            success_patterns=patterns.get("success"),
            failure_patterns=patterns.get("failure")
        )

# Register patterns on module import
register_common_patterns() 