# User-Defined Agent Capabilities Guide

This guide demonstrates how to define custom agent capabilities in the Genesis framework, providing consistency across implementations and rich metadata for agent discovery.

## ⚠️ IMPORTANT: This is Completely Optional!

**You do NOT need to define capabilities for your agents to work!**

- **If you define capabilities**: Your custom definitions are used
- **If you don't define capabilities**: Automatic intelligent generation (model-based → heuristic)
- **All existing agents continue to work unchanged** - no breaking changes
- **Backward compatible**: Current examples work exactly as before

## Overview

The Genesis framework supports multiple ways to define agent capabilities (all optional):

1. **Programmatic Definition** - Using `define_capabilities()` method
2. **Method Override** - Overriding `get_agent_capabilities()`
3. **Class-Level Definition** - Using `CAPABILITIES` class attribute
4. **Dynamic Management** - Using convenience methods for runtime updates

## Inheritance Chain Access

All capability definition methods are available through the inheritance chain:

```
GenesisAgent (base class)
    ↓ inherits
MonitoredAgent (monitoring wrapper)
    ↓ inherits  
OpenAIGenesisAgent (provider implementation)
```

**Users can call capability methods directly on `OpenAIGenesisAgent` instances** - no additional implementation needed in `MonitoredAgent` or provider classes.

## Priority Order

The system checks for user-defined capabilities in this order:
1. User-defined capabilities (highest priority)
2. Model-based generation (if available)
3. Heuristic approach (fallback)

## Automatic Behavior (Default)

**If you don't define any capabilities, the system automatically:**

1. **Analyzes your agent** using the model (if available)
2. **Generates rich metadata** based on:
   - Your `@genesis_tool` methods and their descriptions
   - Your agent's class name and attributes
   - Your agent's specializations and capabilities
   - Performance characteristics and interaction patterns
3. **Falls back to heuristic generation** if model is unavailable
4. **Provides sensible defaults** for all required fields

**This means your existing agents work perfectly without any changes!**

## Method 1: Programmatic Definition

Use the `define_capabilities()` method for structured, comprehensive capability definition:

```python
from genesis_lib.genesis_agent import GenesisAgent
from genesis_lib.decorators import genesis_tool

class WeatherAgent(GenesisAgent):
    def __init__(self):
        super().__init__("WeatherAgent", "WeatherService")
        
        # Define comprehensive capabilities
        self.define_capabilities(
            agent_type="specialist",
            specializations=["weather", "meteorology", "climate"],
            capabilities=[
                "current_weather_queries",
                "weather_forecasting", 
                "climate_analysis",
                "weather_pattern_recognition"
            ],
            classification_tags=["weather", "forecast", "climate", "meteorology"],
            performance_metrics={
                "estimated_response_time": "fast",
                "complexity_handling": "moderate",
                "domain_expertise": "specialized",
                "accuracy": "high"
            },
            interaction_patterns=[
                "location_based_queries",
                "forecast_requests", 
                "weather_data_analysis"
            ],
            strengths=[
                "Accurate weather data retrieval",
                "Multi-day forecasting capabilities",
                "Pattern analysis and trend detection"
            ],
            limitations=[
                "Requires location input for most queries",
                "Limited to weather and climate domains",
                "Dependent on external weather data sources"
            ],
            default_capable=False  # Specialized agent
        )
    
    @genesis_tool(description="Get current weather", operation_type="weather_query")
    async def get_weather(self, location: str) -> dict:
        # Implementation here
        pass
```

## Method 2: Method Override

Override `get_agent_capabilities()` for custom logic or dynamic capabilities:

```python
class FinanceAgent(GenesisAgent):
    def __init__(self):
        super().__init__("FinanceAgent", "FinanceService")
        self.market_data_available = True
    
    def get_agent_capabilities(self) -> dict:
        """Override to provide custom capabilities with dynamic logic."""
        base_capabilities = {
            'agent_type': 'specialist',
            'specializations': ['finance', 'investment', 'trading'],
            'capabilities': ['stock_analysis', 'portfolio_optimization'],
            'classification_tags': ['finance', 'investment', 'stocks'],
            'default_capable': False
        }
        
        # Add dynamic capabilities based on state
        if self.market_data_available:
            base_capabilities['capabilities'].extend([
                'real_time_market_data',
                'live_trading_analysis'
            ])
            base_capabilities['performance_metrics'] = {
                'estimated_response_time': 'fast',
                'data_freshness': 'real_time'
            }
        else:
            base_capabilities['capabilities'].append('historical_analysis_only')
            base_capabilities['limitations'] = [
                'Limited to historical data',
                'No real-time market access'
            ]
        
        return base_capabilities
```

## Method 3: Class-Level Definition

Use the `CAPABILITIES` class attribute for static, reusable capability definitions:

```python
class MathAgent(GenesisAgent):
    # Class-level capabilities definition
    CAPABILITIES = {
        'agent_type': 'specialist',
        'specializations': ['mathematics', 'statistics', 'calculus'],
        'capabilities': [
            'mathematical_calculations',
            'statistical_analysis',
            'equation_solving',
            'graph_plotting'
        ],
        'classification_tags': ['math', 'statistics', 'calculus', 'algebra'],
        'default_capable': False,
        'performance_metrics': {
            'estimated_response_time': 'fast',
            'complexity_handling': 'complex',
            'domain_expertise': 'expert'
        },
        'interaction_patterns': [
            'mathematical_problem_solving',
            'statistical_analysis'
        ],
        'strengths': [
            'Accurate mathematical calculations',
            'Statistical analysis expertise',
            'Complex equation solving'
        ],
        'limitations': [
            'Mathematical domain only',
            'Requires clear problem statements'
        ]
    }
    
    def __init__(self):
        super().__init__("MathAgent", "MathService")
        # Capabilities automatically loaded from CAPABILITIES
```

## Method 4: Dynamic Capability Management

Use convenience methods for runtime capability updates:

```python
class DynamicAgent(GenesisAgent):
    def __init__(self):
        super().__init__("DynamicAgent", "DynamicService")
        
        # Start with basic capabilities
        self.define_capabilities(
            agent_type="general",
            specializations=["general"],
            capabilities=["general_assistance"],
            default_capable=True
        )
    
    def add_weather_capabilities(self):
        """Dynamically add weather capabilities."""
        self.add_specialization("weather")
        self.add_capability("weather_forecasting")
        self.add_capability("current_weather")
        self.set_performance_metric("weather_accuracy", "high")
    
    def add_math_capabilities(self):
        """Dynamically add math capabilities."""
        self.add_specialization("mathematics")
        self.add_capability("calculations")
        self.add_capability("statistical_analysis")
        self.set_performance_metric("math_precision", "expert")
    
    def enable_advanced_features(self):
        """Enable advanced features based on configuration."""
        if self.config.get('advanced_mode', False):
            self.add_capability("advanced_analysis")
            self.set_performance_metric("analysis_depth", "expert")
```

## Capability Schema

All capability definitions should include these fields:

### Required Fields
- `agent_type`: String - "general", "specialist", "tool_agent", etc.
- `specializations`: List[str] - Domain expertise areas
- `capabilities`: List[str] - Specific capabilities the agent can perform
- `classification_tags`: List[str] - Tags for categorization and discovery
- `default_capable`: Boolean - Whether agent can handle general requests

### Optional Fields
- `model_info`: Dict - Information about underlying models
- `performance_metrics`: Dict - Performance characteristics
- `interaction_patterns`: List[str] - How the agent typically interacts
- `strengths`: List[str] - Key strengths
- `limitations`: List[str] - Known limitations

## Best Practices

### 1. Be Specific and Accurate
```python
# Good: Specific and descriptive
capabilities=[
    "real_time_weather_forecasting",
    "multi_location_weather_comparison",
    "climate_trend_analysis"
]

# Avoid: Too generic
capabilities=["weather", "forecast"]
```

### 2. Use Consistent Terminology
```python
# Good: Consistent domain terminology
specializations=["meteorology", "climatology", "atmospheric_science"]
classification_tags=["weather", "forecast", "climate", "meteorology"]

# Avoid: Mixed terminology
specializations=["weather", "meteorology", "climate_stuff"]
```

### 3. Provide Rich Metadata
```python
# Good: Comprehensive metadata
self.define_capabilities(
    agent_type="specialist",
    specializations=["finance", "investment"],
    capabilities=["portfolio_optimization", "risk_assessment"],
    performance_metrics={
        "estimated_response_time": "fast",
        "complexity_handling": "complex",
        "domain_expertise": "expert"
    },
    strengths=["Real-time market data", "Advanced algorithms"],
    limitations=["Not financial advice", "Requires current data"]
)
```

### 4. Consider Discovery and Routing
```python
# Good: Tags that help with discovery
classification_tags=[
    "weather", "forecast", "temperature", "humidity", 
    "meteorology", "climate", "atmospheric"
]

# Good: Clear interaction patterns
interaction_patterns=[
    "location_based_queries",
    "forecast_requests",
    "weather_data_analysis"
]
```

## Examples by Domain

### Weather Agent
```python
self.define_capabilities(
    agent_type="specialist",
    specializations=["weather", "meteorology", "climate"],
    capabilities=[
        "current_weather_queries",
        "weather_forecasting",
        "climate_analysis",
        "weather_pattern_recognition"
    ],
    classification_tags=["weather", "forecast", "climate", "meteorology"],
    performance_metrics={
        "estimated_response_time": "fast",
        "complexity_handling": "moderate",
        "domain_expertise": "specialized"
    },
    default_capable=False
)
```

### Finance Agent
```python
self.define_capabilities(
    agent_type="specialist",
    specializations=["finance", "investment", "trading", "economics"],
    capabilities=[
        "stock_analysis",
        "portfolio_optimization",
        "market_trend_analysis",
        "risk_assessment"
    ],
    classification_tags=["finance", "investment", "trading", "stocks"],
    performance_metrics={
        "estimated_response_time": "medium",
        "complexity_handling": "complex",
        "domain_expertise": "expert"
    },
    default_capable=False
)
```

### General Assistant
```python
self.define_capabilities(
    agent_type="general",
    specializations=["general_assistance"],
    capabilities=[
        "conversation",
        "information_retrieval",
        "task_assistance",
        "problem_solving"
    ],
    classification_tags=["general", "assistant", "conversation"],
    performance_metrics={
        "estimated_response_time": "medium",
        "complexity_handling": "moderate",
        "domain_expertise": "general"
    },
    default_capable=True
)
```

## Validation and Error Handling

The system automatically validates user-defined capabilities:

- **Required fields**: Ensures all required fields are present
- **Type validation**: Ensures lists are lists, dicts are dicts, etc.
- **Default values**: Provides sensible defaults for missing fields
- **Model info**: Automatically adds model information if available
- **Error handling**: Graceful fallback to auto-generation if validation fails

## Integration with Auto-Generation

User-defined capabilities take priority over auto-generation:

1. **User-defined** (if provided) → Used directly
2. **Model-based** (if available) → Used as fallback
3. **Heuristic** → Final fallback

This ensures consistency while maintaining the benefits of intelligent auto-generation for agents that don't define custom capabilities.

## Conclusion

The user-definable capability system provides:

- **Consistency** across agent implementations
- **Rich metadata** for better discovery and routing
- **Flexibility** with multiple definition approaches
- **Validation** to ensure proper formatting
- **Priority** over auto-generation for custom control

Choose the approach that best fits your agent's needs, from simple class-level definitions to complex dynamic capability management.
