"""
LLM Factory - Provider-Agnostic LLM Instance Creation

This module provides the LLMFactory class, which handles intelligent auto-detection
and instantiation of LLM providers based on available API keys and user preferences.
It serves as the central factory for creating ChatAgent instances across different
LLM providers in the Genesis framework.

=================================================================================================
ARCHITECTURE OVERVIEW - Understanding the LLM Factory Pattern
=================================================================================================

The LLM Factory implements a provider-agnostic pattern that allows Genesis agents
to work with multiple LLM providers without code changes. This is essential for:

1. **Provider Flexibility**: Switch between Anthropic, OpenAI, Google, local models
2. **Cost Optimization**: Use cheaper models for classification, expensive ones for complex tasks
3. **Reliability**: Automatic fallback if primary provider is unavailable
4. **Development**: Test with different providers without changing agent code

=================================================================================================
HOW IT WORKS - Smart Provider Selection
=================================================================================================

The factory uses a priority-based selection system:

1. **Auto-Detection Mode** (default):
   - Checks environment variables for API keys
   - Selects first available provider in priority order
   - Uses purpose-based model selection (classifier/default/advanced)

2. **Explicit Provider Mode**:
   - Specify exact provider and model
   - Override environment-based selection
   - Useful for testing or specific requirements

3. **Purpose-Based Model Selection**:
   - "classifier": Fast, cheap models for function classification
   - "default": Balanced models for general conversation
   - "advanced": Most capable models for complex reasoning

=================================================================================================
PROVIDER REGISTRY - Adding New LLM Providers
=================================================================================================

The LLM_PROVIDERS list defines all available providers with their configurations:

```python
{
    "name": "anthropic",                    # Provider identifier
    "env_var": "ANTHROPIC_API_KEY",         # Environment variable for API key
    "class": AnthropicChatAgent,            # ChatAgent implementation class
    "models": {                             # Purpose-based model mapping
        "classifier": "claude-haiku-4-5-20251001",  # Fast, cheap
        "default": "claude-3-5-sonnet-20241022",    # Balanced
        "advanced": "claude-opus-4-20250514"         # Most capable
    }
}
```

To add a new provider:
1. Implement a ChatAgent class (see openai_genesis_agent.py for reference)
2. Add provider configuration to LLM_PROVIDERS
3. Update imports to include the new ChatAgent class
4. Test with existing agent code (no changes needed!)

=================================================================================================
USAGE PATTERNS - Common Integration Scenarios
=================================================================================================

1. **Genesis Agent Integration** (Automatic):
   ```python
   # GenesisAgent automatically uses LLMFactory
   agent = OpenAIGenesisAgent(agent_name="MyAgent")
   # Factory creates appropriate LLM based on available API keys
   ```

2. **Standalone LLM Usage** (Manual):
   ```python
   # Auto-detect best available provider
   llm = LLMFactory.create_llm(purpose="classifier")
   
   # Use specific provider
   llm = LLMFactory.create_llm(provider="anthropic", purpose="advanced")
   
   # Override model selection
   llm = LLMFactory.create_llm(
       provider="openai", 
       model="gpt-4o-mini",
       system_prompt="You are a helpful assistant"
   )
   ```

3. **Provider Discovery** (Runtime):
   ```python
   # Check what providers are available
   available = LLMFactory.get_available_providers()
   # Returns: ["anthropic", "openai"] (if API keys are set)
   
   # Get model options for a provider
   models = LLMFactory.get_provider_models("anthropic")
   # Returns: {"classifier": "claude-haiku-4-5-20251001", ...}
   ```

=================================================================================================
ENVIRONMENT SETUP - Required API Keys
=================================================================================================

The factory automatically detects providers based on environment variables:

```bash
# For Anthropic Claude
export ANTHROPIC_API_KEY="your-anthropic-key"

# For OpenAI GPT
export OPENAI_API_KEY="your-openai-key"

# For Google Gemini (when implemented)
export GOOGLE_API_KEY="your-google-key"

# For local models (when implemented)
export OLLAMA_HOST="http://localhost:11434"
```

The factory will use the first provider it finds with a valid API key.

=================================================================================================
INTEGRATION WITH GENESIS AGENTS - Seamless Provider Switching
=================================================================================================

Genesis agents automatically benefit from the factory's provider flexibility:

1. **Development**: Use local models or cheaper APIs
2. **Testing**: Switch providers to test compatibility
3. **Production**: Use enterprise-grade providers
4. **Fallback**: Automatic failover if primary provider fails

No agent code changes required - just set different environment variables!

=================================================================================================
ERROR HANDLING - Graceful Degradation
=================================================================================================

The factory implements comprehensive error handling:

1. **Missing API Keys**: Logs warning, returns None
2. **Invalid Providers**: Logs warning, continues to next provider
3. **API Failures**: Logs error, returns None
4. **No Providers**: Logs warning with helpful setup instructions

This ensures agents can start even if some providers are unavailable.

=================================================================================================

Copyright (c) 2025, RTI & Jason Upchurch
"""

import os
import logging
from typing import Optional, Dict, Any
from .llm import ChatAgent, AnthropicChatAgent, OpenAIChatAgent

logger = logging.getLogger(__name__)

# =============================================================================
# PROVIDER REGISTRY AND CONFIGURATION
# =============================================================================
# Central registry defining all available LLM providers with their configurations,
# API keys, models, and implementation classes.
# =============================================================================

# Provider registry with priority order and default configs
LLM_PROVIDERS = [
    {
        "name": "anthropic",
        "env_var": "ANTHROPIC_API_KEY",
        "class": AnthropicChatAgent,
        "models": {
            "classifier": "claude-haiku-4-5-20251001",  # Fast, cheap for classification
            "default": "claude-3-5-sonnet-20241022",    # Balanced for general use
            "advanced": "claude-opus-4-20250514"        # Most capable for complex tasks
        }
    },
    {
        "name": "openai",
        "env_var": "OPENAI_API_KEY",
        "class": OpenAIChatAgent,
        "models": {
            "classifier": "gpt-4o-mini",
            "default": "gpt-4o",
            "advanced": "o1"
        }
    },
    # Easy to add more providers:
    # {
    #     "name": "gemini",
    #     "env_var": "GEMINI_API_KEY",
    #     "class": GeminiChatAgent,
    #     "models": {
    #         "classifier": "gemini-1.5-flash",
    #         "default": "gemini-1.5-pro",
    #         "advanced": "gemini-2.0-exp"
    #     }
    # },
    # {
    #     "name": "local",
    #     "env_var": "OLLAMA_HOST",
    #     "class": OllamaChatAgent,
    #     "models": {
    #         "classifier": "llama3.2:1b",
    #         "default": "llama3.2:3b",
    #         "advanced": "llama3.3:70b"
    #     }
    # }
]


# =============================================================================
# LLM FACTORY CLASS - INTELLIGENT PROVIDER SELECTION
# =============================================================================
# The LLMFactory class provides intelligent auto-detection and instantiation
# of LLM providers based on available API keys and user preferences.
# =============================================================================

class LLMFactory:
    """
    Factory for creating LLM instances with intelligent provider selection.
    
    The LLMFactory is the central component for creating ChatAgent instances across
    different LLM providers in the Genesis framework. It provides:
    
    1. **Auto-Detection**: Automatically selects the best available provider
    2. **Provider Flexibility**: Switch between Anthropic, OpenAI, Google, local models
    3. **Purpose-Based Selection**: Optimize model choice for specific use cases
    4. **Error Handling**: Graceful degradation when providers are unavailable
    
    The factory uses a priority-based selection system that checks environment
    variables for API keys and selects the first available provider. This allows
    Genesis agents to work seamlessly across different LLM providers without
    code changes.
    
    Examples:
        # Auto-detect best available provider for classification
        llm = LLMFactory.create_llm(purpose="classifier")
        
        # Use specific provider for advanced reasoning
        llm = LLMFactory.create_llm(provider="anthropic", purpose="advanced")
        
        # Override model selection
        llm = LLMFactory.create_llm(
            provider="openai", 
            model="gpt-4o-mini",
            system_prompt="You are a helpful assistant"
        )
    """
    
    # =============================================================================
    # MAIN FACTORY METHODS - CORE LLM CREATION
    # =============================================================================
    # Primary methods for creating LLM instances with intelligent provider selection
    # =============================================================================
    
    @staticmethod
    def create_llm(
        purpose: str = "default",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs
    ) -> Optional[ChatAgent]:
        """
        Create an LLM instance with intelligent provider selection.
        
        This is the main entry point for creating ChatAgent instances. The factory
        automatically handles provider detection, model selection, and error handling.
        
        Args:
            purpose: Use case for model selection:
                - "classifier": Fast, cheap models for function classification
                - "default": Balanced models for general conversation  
                - "advanced": Most capable models for complex reasoning
            provider: Specific provider name ("anthropic", "openai", etc.) or None for auto-detect
            model: Specific model name or None for purpose-based default
            api_key: API key or None to use environment variable
            **kwargs: Additional arguments for the LLM constructor:
                - system_prompt: System instructions for the LLM
                - max_history: Maximum conversation history to maintain
                - temperature: Response randomness (0.0-2.0)
                - max_tokens: Maximum response length
                
        Returns:
            ChatAgent instance or None if no providers are available
            
        Raises:
            No exceptions raised - returns None on failure with logged warnings
            
        Examples:
            # Auto-detect best available provider for classification
            llm = LLMFactory.create_llm(purpose="classifier")
            
            # Use specific provider for advanced reasoning
            llm = LLMFactory.create_llm(provider="anthropic", purpose="advanced")
            
            # Override model selection with custom configuration
            llm = LLMFactory.create_llm(
                provider="openai", 
                model="gpt-4o-mini",
                system_prompt="You are a helpful assistant",
                max_history=20,
                temperature=0.7
            )
            
            # Check if LLM was created successfully
            if llm is None:
                print("No LLM providers available. Check API keys.")
            else:
                response = await llm.chat("Hello!")
        """
        if provider:
            # Use specific provider
            return LLMFactory._create_from_provider(provider, purpose, model, api_key, **kwargs)
        else:
            # Auto-detect first available provider
            return LLMFactory._auto_detect_and_create(purpose, model, **kwargs)
    
    # =============================================================================
    # INTERNAL FACTORY METHODS - PROVIDER-SPECIFIC CREATION
    # =============================================================================
    # Internal methods that handle provider-specific LLM instantiation and configuration
    # =============================================================================
    
    @staticmethod
    def _create_from_provider(
        provider: str,
        purpose: str,
        model: Optional[str],
        api_key: Optional[str],
        **kwargs
    ) -> Optional[ChatAgent]:
        """Create LLM from specific provider."""
        for provider_config in LLM_PROVIDERS:
            if provider_config["name"] == provider:
                if provider_config["class"] is None:
                    logger.warning(f"Provider '{provider}' not yet implemented")
                    return None
                
                # Get API key from parameter or environment
                key = api_key or os.getenv(provider_config["env_var"])
                if not key:
                    logger.warning(
                        f"No API key for provider '{provider}'. "
                        f"Set {provider_config['env_var']} environment variable"
                    )
                    return None
                
                # Get model name (explicit > purpose-based > default)
                model_name = model or provider_config["models"].get(purpose, provider_config["models"]["default"])
                
                # Create instance
                try:
                    logger.info(f"Creating {provider} LLM ({model_name}) for {purpose}")
                    return provider_config["class"](
                        model_name=model_name,
                        api_key=key,
                        **kwargs
                    )
                except Exception as e:
                    logger.error(f"Failed to create {provider} LLM: {e}")
                    return None
        
        logger.warning(f"Unknown provider: {provider}")
        return None
    
    @staticmethod
    def _auto_detect_and_create(purpose: str, model: Optional[str], **kwargs) -> Optional[ChatAgent]:
        """Auto-detect first available provider and create LLM."""
        logger.debug(f"Auto-detecting LLM provider for purpose: {purpose}")
        
        for provider_config in LLM_PROVIDERS:
            if provider_config["class"] is None:
                continue  # Skip unimplemented providers
            
            api_key = os.getenv(provider_config["env_var"])
            if api_key:
                logger.info(f"Auto-detected provider: {provider_config['name']}")
                return LLMFactory._create_from_provider(
                    provider_config["name"],
                    purpose,
                    model,
                    api_key,
                    **kwargs
                )
        
        # No providers available
        available_vars = [p["env_var"] for p in LLM_PROVIDERS if p["class"] is not None]
        logger.warning(
            f"No LLM providers available for {purpose}. "
            f"Set one of: {', '.join(available_vars)}"
        )
        return None
    
    # =============================================================================
    # DISCOVERY AND INSPECTION METHODS - PROVIDER INFORMATION
    # =============================================================================
    # Methods for discovering available providers and their configurations
    # =============================================================================
    
    @staticmethod
    def get_available_providers() -> list:
        """
        Get list of available (implemented) providers.
        
        This method returns all providers that have been implemented and are
        available for use. It does not check for API keys - use this to
        discover what providers are supported.
        
        Returns:
            List of provider names that are implemented and available
            
        Examples:
            # Check what providers are available
            providers = LLMFactory.get_available_providers()
            print(f"Available providers: {providers}")
            # Output: ["anthropic", "openai"]
            
            # Use in conditional logic
            if "anthropic" in LLMFactory.get_available_providers():
                llm = LLMFactory.create_llm(provider="anthropic")
        """
        return [p["name"] for p in LLM_PROVIDERS if p["class"] is not None]
    
    @staticmethod
    def get_provider_models(provider: str) -> Optional[Dict[str, str]]:
        """
        Get model configurations for a specific provider.
        
        This method returns the purpose-based model mappings for a given provider,
        allowing you to see what models are available for different use cases.
        
        Args:
            provider: Provider name (e.g., "anthropic", "openai")
            
        Returns:
            Dictionary of purpose -> model name mappings, or None if provider not found
            
        Examples:
            # Get Anthropic model options
            models = LLMFactory.get_provider_models("anthropic")
            print(models)
            # Output: {
            #     "classifier": "claude-haiku-4-5-20251001",
            #     "default": "claude-3-5-sonnet-20241022", 
            #     "advanced": "claude-opus-4-20250514"
            # }
            
            # Use in model selection logic
            if models:
                classifier_model = models["classifier"]
                llm = LLMFactory.create_llm(
                    provider="anthropic",
                    model=classifier_model
                )
        """
        for provider_config in LLM_PROVIDERS:
            if provider_config["name"] == provider:
                return provider_config["models"].copy()
        return None

