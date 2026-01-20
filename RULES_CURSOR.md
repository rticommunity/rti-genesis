# Genesis Framework Development Rules for Cursor AI

## Critical Architectural Principles

### 1. Error Handling: Never Silent Failures

**RULE: `except Exception: pass` is 100% FORBIDDEN**

Silent exception swallowing is horrendously bad coding. It masks bugs and makes systems impossible to debug.

**NEVER do this:**
```python
try:
    some_operation()
except Exception:
    pass  # ❌ FORBIDDEN
```

**ALWAYS do this:**
```python
try:
    some_operation()
except SpecificException as e:
    logger.error(f"Operation failed: {e}")
    logger.error(traceback.format_exc())
    # Handle the error appropriately
```

**Guidelines:**
1. Catch specific exceptions when possible (`ValueError`, `KeyError`, `dds.Error`, etc.)
2. ALWAYS log exceptions with full traceback
3. If you must catch `Exception`, log it comprehensively
4. Never hide errors - they indicate bugs that must be fixed
5. Use INFO level for business logic errors (insufficient funds, level requirements)
6. Use DEBUG only for step-by-step tracing
7. Use ERROR for unexpected failures

### 2. DDS Communication: Event-Driven, Not Polling

**RULE: All DDS communication MUST use asynchronous callbacks, NOT polling**

DDS is designed as an event-driven middleware. Polling violates the architecture.

**NEVER do this:**
```python
async def handle_requests(self):
    while True:
        requests = self.replier.receive_requests(max_wait=dds.Duration(1))  # ❌ FORBIDDEN POLLING
        for request in requests:
            process(request)
        await asyncio.sleep(0.1)
```

**ALWAYS do this:**
```python
class RequestListener(dds.DynamicData.DataReaderListener):
    def __init__(self, outer):
        super().__init__()
        self._outer = outer
        
    def on_data_available(self, reader):
        """Asynchronous callback triggered by DDS when data arrives"""
        try:
            samples = self._outer.replier.take_requests()
            for request, info in samples:
                # Schedule async processing in the event loop
                asyncio.run_coroutine_threadsafe(
                    self._outer.process_request(request, info),
                    self._outer.loop
                )
        except Exception as e:
            logger.error(f"Error in listener: {e}")
            logger.error(traceback.format_exc())

# Attach listener to DataReader
self.replier.request_datareader.set_listener(listener, dds.StatusMask.DATA_AVAILABLE)
```

### 3. Configuration as Code

All configuration must be in code (Lua for Roblox, Python for Genesis framework), NOT in external files like YAML or JSON. This ensures a single source of truth and compile-time validation.

### 4. Defensive Programming

All external calls (network bridges, signals, data operations) must be wrapped in pcall blocks (Roblox) or try-except blocks (Python) with comprehensive error logging.

### 5. Explicit Error Propagation

When an error occurs, it must be:
1. Logged immediately
2. Propagated to the caller (via return value, exception, or error reply)
3. Made visible to operators/developers

## Testing Philosophy

- Test as often as possible when writing new code
- Run tests as often as possible
- Specifications must explicitly define exact return formats
- Use official Python SDKs/APIs instead of direct HTTP requests when available

## Tools and Dependencies

- Use `mise` CLI (https://mise.jdx.dev/) for dependency management, NOT aftman
- Use ProfileStore for data storage (Roblox projects)

## Remember

Silent failures are bugs that must be eliminated through defensive programming practices. Every error is an opportunity to improve system reliability.


---
*Copyright (c) 2025, RTI & Jason Upchurch*
