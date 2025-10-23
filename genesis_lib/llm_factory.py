"""
LLM Factory - Provider-agnostic LLM instance creation

Handles auto-detection and instantiation of LLM providers based on
available API keys and user preferences.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import os
import logging
from typing import Optional, Dict, Any
from .llm import ChatAgent, AnthropicChatAgent

logger = logging.getLogger(__name__)

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
        "class": None,  # TODO: Implement OpenAIChatAgent wrapper
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


class LLMFactory:
    """Factory for creating LLM instances with smart provider selection."""
    
    @staticmethod
    def create_llm(
        purpose: str = "default",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs
    ) -> Optional[ChatAgent]:
        """
        Create an LLM instance with smart provider selection.
        
        Args:
            purpose: Use case for model selection ("classifier", "default", "advanced")
            provider: Specific provider name ("anthropic", "openai", etc.) or None for auto-detect
            model: Specific model name or None for purpose-based default
            api_key: API key or None to use environment variable
            **kwargs: Additional arguments for the LLM constructor (e.g., system_prompt, max_history)
            
        Returns:
            ChatAgent instance or None if no providers are available
            
        Examples:
            # Auto-detect with purpose
            llm = LLMFactory.create_llm(purpose="classifier")
            
            # Specific provider
            llm = LLMFactory.create_llm(provider="anthropic", purpose="advanced")
            
            # Specific model
            llm = LLMFactory.create_llm(provider="anthropic", model="claude-opus-4-20250514")
            
            # With custom config
            llm = LLMFactory.create_llm(
                purpose="classifier",
                system_prompt="You are a helpful assistant",
                max_history=20
            )
        """
        if provider:
            # Use specific provider
            return LLMFactory._create_from_provider(provider, purpose, model, api_key, **kwargs)
        else:
            # Auto-detect first available provider
            return LLMFactory._auto_detect_and_create(purpose, model, **kwargs)
    
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
    
    @staticmethod
    def get_available_providers() -> list:
        """
        Get list of available (implemented) providers.
        
        Returns:
            List of provider names that are implemented
        """
        return [p["name"] for p in LLM_PROVIDERS if p["class"] is not None]
    
    @staticmethod
    def get_provider_models(provider: str) -> Optional[Dict[str, str]]:
        """
        Get model configurations for a specific provider.
        
        Args:
            provider: Provider name
            
        Returns:
            Dictionary of purpose -> model name mappings, or None if provider not found
        """
        for provider_config in LLM_PROVIDERS:
            if provider_config["name"] == provider:
                return provider_config["models"].copy()
        return None

