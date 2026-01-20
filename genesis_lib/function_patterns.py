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
Function Patterns - Pattern-Based Result Classification for Genesis

This module provides the pattern registry used to classify function results and exceptions
into structured success/error outcomes with optional recovery hints. It is used by
`genesis_lib.genesis_app.GenesisApp` to analyze results returned from function execution.

=================================================================================================
ARCHITECTURE OVERVIEW - Components
=================================================================================================

1) SuccessPattern / FailurePattern (Data Models)
   - Declarative descriptions of what “success” and “failure” look like
   - Support regex, type checks, value ranges, and exception types

2) FunctionPatternRegistry (Runtime Classifier)
   - Registers patterns per function ID
   - `check_result(function_id, result_or_exception)` → (is_success, error_code, recovery_hint)

3) pattern_registry (Global Instance)
   - Shared registry instance imported by `GenesisApp`
   - Enables centralized, consistent classification across the system

=================================================================================================
CURRENT RUNTIME USAGE - Where It’s Used Today
=================================================================================================

- `genesis_lib.genesis_app.GenesisApp`:
  • Stores `self.pattern_registry = pattern_registry`
  • Calls `check_result(...)` after function execution to classify success/failure
  • On failure, returns structured fields: error_code, message, recovery_hint

Call Chain (simplified):
```
execute_function(...) → result/exception
  → self.pattern_registry.check_result(function_id, result_or_exception)
  → structured response (status, error_code, recovery_hint)
```

=================================================================================================
WHY THIS MATTERS - Role vs Decorators and Schema Generation
=================================================================================================

- Decorators (`@genesis_function`, `@genesis_tool`) capture provider‑agnostic metadata
  and infer/define schemas for function/tool invocation and validation.
- Schema generators (`schema_generators.py`) convert that universal metadata into
  provider‑specific tool schemas (OpenAI, Anthropic, local).
- Function patterns (THIS MODULE) classify outcomes AFTER execution, independent of
  how schemas were created or which provider was used.

Separation of concerns:
- Decorators/schema: how to call a function/tool (input/shape, validation, provider formats)
- Patterns/registry: how to interpret the result (success/failure classification, recovery)

This split keeps classification logic centralized and provider‑agnostic, while allowing
providers to evolve their schema formats without touching runtime error/result semantics.

=================================================================================================
STATUS & TODO
=================================================================================================

Implemented:
- Type/regex/value‑range/exception‑based pattern checks
- Global registry with common example patterns (calculator, letter counter)

TODO (future enhancements):
- Add composable policies (e.g., AND/OR of patterns, thresholds)
- Enrich failure metadata (severity, category) and analytics hooks
- Support structured result paths (e.g., JSONPointer selectors)
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