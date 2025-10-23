"""
Genesis Agent Classification System - Intelligent Request Routing

This module provides the core intelligence for agent-to-agent communication within
the Genesis framework. It implements semantic LLM-based classification to analyze
incoming requests and determine which agent is best suited to handle them based on
capabilities, specializations, and contextual understanding.

ARCHITECTURAL OVERVIEW:
======================

The AgentClassifier serves as the intelligent routing layer for the Genesis distributed
agent system. It bridges the gap between natural language requests and specialized
agent capabilities through semantic understanding rather than simple keyword matching.

Key responsibilities include:
- Semantic analysis of user requests using LLM classification
- Agent capability matching based on specializations and skills
- Intelligent routing decisions with explanation generation
- Fallback handling when no suitable agent is found
- Integration with the Genesis agent discovery system

DESIGN PRINCIPLES:
=================

1. **Semantic Understanding**: Uses LLM-based classification rather than keyword
   matching to understand request intent and context.

2. **Capability-Based Routing**: Routes requests based on agent specializations
   and capabilities rather than agent names or types.

3. **Intelligent Fallback**: Provides graceful degradation when no specialist
   agent is available, falling back to general-purpose agents.

4. **Explanation Generation**: Provides human-readable explanations for routing
   decisions to aid in debugging and transparency.

5. **Provider Agnostic**: Works with any LLM provider through the LLMFactory
   system, supporting OpenAI, Anthropic, and custom models.

USAGE PATTERNS:
==============

1. **Automatic Classification**: Integrated into GenesisAgent for automatic
   request routing based on discovered agent capabilities.

2. **Manual Classification**: Direct usage for custom routing logic and
   agent selection scenarios.

3. **Capability Discovery**: Used in conjunction with agent discovery to
   build routing tables based on available agent specializations.

4. **Multi-Agent Orchestration**: Enables complex workflows by routing
   different parts of requests to specialized agents.

INTEGRATION WITH GENESIS FRAMEWORK:
===================================

The AgentClassifier integrates seamlessly with the Genesis framework:

- **Agent Discovery**: Uses discovered agent metadata for classification
- **Capability System**: Leverages agent capability definitions for routing
- **LLM Factory**: Supports any LLM provider through the factory pattern
- **Memory System**: Can incorporate conversation history for context
- **Monitoring**: Provides routing explanations for system observability

ERROR HANDLING AND RESILIENCE:
==============================

- Graceful degradation when LLM classification fails
- Fallback to default capable agents when no specialist is found
- Comprehensive error logging for debugging routing issues
- Timeout handling for LLM classification requests
- Validation of agent capability metadata

Copyright (c) 2025, RTI & Jason Upchurch
"""

import logging
import asyncio
import re
from typing import Dict, Any, List, Optional, Tuple

# Get logger
logger = logging.getLogger(__name__)

# =============================================================================
# AGENT CLASSIFIER CLASS - SEMANTIC REQUEST ROUTING
# =============================================================================

class AgentClassifier:
    """
    Intelligent request routing system for Genesis agent-to-agent communication.
    
    The AgentClassifier provides semantic LLM-based classification to analyze
    incoming requests and determine which agent is best suited to handle them.
    It bridges the gap between natural language requests and specialized agent
    capabilities through intelligent understanding rather than simple keyword matching.
    
    ARCHITECTURAL ROLE:
    ===================
    
    The AgentClassifier serves as the intelligent routing layer in the Genesis
    distributed agent system. It analyzes request intent, matches capabilities,
    and provides routing decisions with explanations for transparency.
    
    KEY FEATURES:
    =============
    
    - **Semantic Understanding**: Uses LLM classification to understand request intent
    - **Capability Matching**: Routes based on agent specializations and skills
    - **Intelligent Fallback**: Graceful degradation when no specialist is available
    - **Explanation Generation**: Provides human-readable routing explanations
    - **Provider Agnostic**: Works with any LLM provider through LLMFactory
    
    USAGE EXAMPLE:
    ==============
    
    ```python
    # Initialize classifier with OpenAI
    classifier = AgentClassifier(provider="openai", model="gpt-4")
    
    # Classify a request against available agents
    best_agent = await classifier.classify_request(
        request="What's the weather like today?",
        available_agents=discovered_agents
    )
    
    # Get explanation for routing decision
    explanation = classifier.get_classification_explanation(
        request, best_agent, discovered_agents
    )
    ```
    
    INTEGRATION:
    ===========
    
    The AgentClassifier integrates seamlessly with GenesisAgent for automatic
    request routing and can be used standalone for custom routing scenarios.
    """
    
    def __init__(self, provider: str = "openai", model: str = "gpt-5-mini", custom_llm=None):
        """
        Initialize the agent classifier.
        
        Args:
            provider: LLM provider name (e.g., "openai", "anthropic"). Default: "openai"
            model: Model name for classification (e.g., "gpt-5-mini", "claude-haiku-4-5-20251001"). Default: "gpt-5-mini"
            custom_llm: Optional pre-configured LLM instance. If provided, provider and model are ignored.
        """
        self.agent_registry = {}  # agent_id -> capability info
        self.provider = provider
        self.model = model
        
        # Use custom LLM if provided, otherwise create via LLMFactory
        if custom_llm:
            self.classification_llm = custom_llm
            logger.info(f"AgentClassifier initialized with custom LLM instance")
        else:
            try:
                from .llm_factory import LLMFactory
                self.classification_llm = LLMFactory.create_llm(
                    purpose="classifier",
                    provider=provider,
                    model=model,
                    system_prompt="You are an intelligent request router for a multi-agent system."
                )
                if self.classification_llm:
                    logger.info(f"AgentClassifier initialized with {provider} provider using model {model}")
                else:
                    logger.warning(f"Failed to create classifier LLM - classification will be disabled")
            except Exception as e:
                logger.error(f"Error creating classifier LLM: {e}")
                self.classification_llm = None
        
        logger.info(f"AgentClassifier ready - LLM classification: {'enabled' if self.classification_llm else 'DISABLED'}")
    
    # =============================================================================
    # AGENT REGISTRY MANAGEMENT - DISCOVERY INTEGRATION
    # =============================================================================
    
    def update_agent_registry(self, discovered_agents: Dict[str, Dict[str, Any]]):
        """
        Update the internal agent registry with discovered agents.
        
        This method maintains the classifier's view of available agents and their
        capabilities. It should be called whenever the agent discovery system
        finds new agents or updates existing agent information.
        
        Args:
            discovered_agents: Dictionary mapping agent_id to agent metadata
                             containing capabilities, specializations, etc.
        
        Note:
            The registry is updated by copying the provided dictionary to ensure
            the classifier has the latest agent information for classification.
        """
        self.agent_registry = discovered_agents.copy()
        logger.debug(f"Updated agent registry with {len(self.agent_registry)} agents")
    
    # =============================================================================
    # SEMANTIC CLASSIFICATION METHODS - LLM-BASED ROUTING
    # =============================================================================
    
    async def classify_request(self, request: str, available_agents: Dict[str, Dict[str, Any]]) -> Optional[str]:
        """
        Determine which agent is best suited to handle a request using semantic LLM classification.
        
        This method implements pure semantic understanding through LLM-based classification.
        It analyzes the request intent and matches it against agent capabilities and
        specializations to determine the most appropriate agent for the task.
        
        CLASSIFICATION PROCESS:
        ======================
        
        1. **Request Analysis**: The LLM analyzes the request to understand intent and context
        2. **Agent Evaluation**: Each available agent's capabilities are presented to the LLM
        3. **Semantic Matching**: The LLM determines which agent best matches the request
        4. **Fallback Handling**: If no specialist is found, falls back to default capable agents
        
        Args:
            request: The request message to classify (natural language)
            available_agents: Dictionary mapping agent_id to agent metadata containing:
                            - name: Agent display name
                            - specializations: List of domain expertise areas
                            - capabilities: List of specific capabilities/skills
                            - description: Agent description
                            - default_capable: Boolean indicating general capability
        
        Returns:
            Agent ID of the best suited agent, or None if no suitable agent found
            
        Example:
            ```python
            # Classify a weather request
            best_agent = await classifier.classify_request(
                request="What's the weather like in New York?",
                available_agents={
                    "weather_agent": {
                        "name": "WeatherBot",
                        "specializations": ["weather", "meteorology"],
                        "capabilities": ["weather_forecasting", "climate_data"],
                        "default_capable": False
                    },
                    "general_agent": {
                        "name": "GeneralAssistant", 
                        "specializations": [],
                        "capabilities": ["general_assistance"],
                        "default_capable": True
                    }
                }
            )
            # Returns: "weather_agent"
            ```
        
        Note:
            This method uses pure LLM classification without any rule-based fallbacks.
            If the LLM is unavailable, the method will return None rather than
            attempting keyword-based matching.
        """
        if not available_agents:
            logger.debug("No available agents for classification")
            return None
        
        logger.info(f"Classifying request using PURE LLM: '{request[:100]}...' against {len(available_agents)} agents")
        
        # Update registry
        self.update_agent_registry(available_agents)
        
        # ONLY use LLM-based semantic classification
        if self.classification_llm:
            semantic_match = await self._llm_classify(request, available_agents)
            if semantic_match:
                logger.info(f"LLM classification selected: {semantic_match}")
                return semantic_match
            else:
                logger.info("LLM classification found no suitable agent")
        else:
            logger.warning("No LLM available for classification - agent routing disabled")
            
        # Only fallback to default capable agent if LLM found nothing
        default_match = self._find_default_capable_agent(available_agents)
        if default_match:
            logger.info(f"Using default capable agent as fallback: {default_match}")
            return default_match
        
        logger.warning("No suitable agent found for request classification")
        return None
    
    # =============================================================================
    # INTERNAL LLM CLASSIFICATION METHODS - PROVIDER-SPECIFIC LOGIC
    # =============================================================================
    
    async def _llm_classify(self, request: str, available_agents: Dict[str, Dict[str, Any]]) -> Optional[str]:
        """
        Use LLM for semantic classification with provider-agnostic interface.
        
        This method implements the core LLM-based classification logic. It formats
        the request and agent information into a structured prompt, calls the LLM,
        and parses the response to extract the best matching agent ID.
        
        CLASSIFICATION PROMPT STRUCTURE:
        ===============================
        
        The method creates a structured prompt that includes:
        1. **Request Context**: The user's request for analysis
        2. **Agent Information**: Detailed capabilities and specializations for each agent
        3. **Classification Instructions**: Clear guidance for the LLM on how to select
        4. **Response Format**: Specific format for the LLM's response
        
        Args:
            request: The request message to classify
            available_agents: Dictionary of available agents with their metadata
            
        Returns:
            Agent ID of the best match, or None if classification fails
            
        Note:
            This method handles LLM response parsing and error recovery. If the
            LLM response cannot be parsed or doesn't contain a valid agent ID,
            the method returns None to trigger fallback behavior.
        """
        if not self.classification_llm:
            logger.debug("Classification LLM not available")
            return None
        
        try:
            # Prepare agent information for the LLM
            agent_descriptions = []
            for agent_id, agent_info in available_agents.items():
                name = agent_info.get('name', agent_id)
                specializations = agent_info.get('specializations', [])
                capabilities = agent_info.get('capabilities', [])
                description = agent_info.get('description', '')
                
                agent_desc = f"Agent: {name} (ID: {agent_id})"
                if specializations:
                    agent_desc += f"\n  Specializations: {', '.join(specializations)}"
                if capabilities:
                    agent_desc += f"\n  Capabilities: {', '.join(capabilities)}"
                if description:
                    agent_desc += f"\n  Description: {description}"
                
                agent_descriptions.append(agent_desc)
            
            # Create the prompt for LLM classification
            prompt = f"""You are an intelligent request router for a multi-agent system. Your job is to analyze a user request and determine which agent is best suited to handle it.

USER REQUEST: "{request}"

AVAILABLE AGENTS:
{chr(10).join(agent_descriptions)}

Please analyze the request and select the SINGLE best agent to handle it. Consider:
1. The agent's specializations and how well they match the request domain
2. The agent's specific capabilities and whether they can fulfill the request
3. The semantic meaning and intent of the request

Respond with ONLY the agent ID (the text after "ID: ") of the best match. If no agent is particularly well-suited, respond with the ID of the most general-purpose agent.

Best Agent ID:"""

            # Call LLM via the generic ChatAgent interface
            logger.debug(f"Sending LLM classification request for: '{request[:50]}...'")
            
            # Use the generic generate_response method
            # The LLM should have a system prompt already set, but we include context in the user message
            llm_response, status = await self.classification_llm.generate_response(
                message=prompt,
                conversation_id="agent_classification"  # Use a fixed conversation ID for classification
            )
            
            if status != 0:
                logger.error(f"LLM classification failed with status {status}")
                return None
            
            logger.debug(f"LLM classification response: '{llm_response}'")
            
            # Clean up the response and extract agent ID
            llm_response = llm_response.strip()
            
            # Look for the agent ID in the response
            for agent_id in available_agents.keys():
                if agent_id in llm_response:
                    logger.info(f"LLM selected agent: {agent_id}")
                    return agent_id
            
            # If no exact match, try to extract agent ID from common patterns
            words = llm_response.lower().replace('-', '_').split()
            for word in words:
                if word in available_agents:
                    logger.info(f"LLM selected agent (extracted): {word}")
                    return word
            
            logger.warning(f"Could not parse agent ID from LLM response: '{llm_response}'")
            return None
            
        except Exception as e:
            logger.error(f"Error in LLM classification: {e}")
            logger.exception("Full traceback:")
            return None
    
    # =============================================================================
    # FALLBACK AND UTILITY METHODS - ROBUST CLASSIFICATION
    # =============================================================================
    
    def _find_default_capable_agent(self, available_agents: Dict[str, Dict[str, Any]]) -> Optional[str]:
        """
        Find a default capable agent as fallback when no specialist is available.
        
        This method provides graceful degradation when LLM classification fails
        or when no specialized agent is found for the request. It searches for
        agents marked as 'default_capable' that can handle general requests.
        
        Args:
            available_agents: Dictionary of available agents with their metadata
            
        Returns:
            Agent ID of a default capable agent, or None if none found
        """
        for agent_id, agent_info in available_agents.items():
            if agent_info.get('default_capable', False):
                logger.debug(f"Found default capable agent: {agent_id}")
                return agent_id
        
        return None
    
    # =============================================================================
    # EXPLANATION AND DEBUGGING METHODS - TRANSPARENCY
    # =============================================================================
    
    def get_classification_explanation(self, request: str, chosen_agent_id: str, 
                                    available_agents: Dict[str, Dict[str, Any]]) -> str:
        """
        Provide a human-readable explanation of why a particular agent was chosen.
        
        This method analyzes the classification decision and generates a clear
        explanation of the reasoning behind the agent selection. It examines
        capability matches, specialization alignment, and other factors that
        influenced the routing decision.
        
        EXPLANATION ANALYSIS:
        ====================
        
        The method analyzes several factors to generate explanations:
        1. **Capability Matches**: Direct matches between request and agent capabilities
        2. **Specialization Alignment**: Domain expertise that matches the request
        3. **Classification Tags**: Keywords and tags that influenced the decision
        4. **Default Capability**: Whether the agent was chosen as a general fallback
        
        Args:
            request: The original request that was classified
            chosen_agent_id: The agent ID that was selected by the classifier
            available_agents: Dictionary of all available agents with their metadata
            
        Returns:
            Human-readable explanation string describing the routing decision
            
        Example:
            ```python
            explanation = classifier.get_classification_explanation(
                request="What's the weather like?",
                chosen_agent_id="weather_agent",
                available_agents=discovered_agents
            )
            # Returns: "Selected WeatherBot because it specializes in: ['weather', 'meteorology']"
            ```
        
        Note:
            This method provides transparency into the classification process,
            which is valuable for debugging routing issues and understanding
            how the system makes routing decisions.
        """
        if chosen_agent_id not in available_agents:
            return f"Agent {chosen_agent_id} not found in available agents"
        
        agent_info = available_agents[chosen_agent_id]
        agent_name = agent_info.get('name', chosen_agent_id)
        
        # Analyze why this agent was chosen
        explanations = []
        
        # Check for exact capability matches
        request_lower = request.lower()
        capabilities = agent_info.get('capabilities', [])
        matched_capabilities = [cap for cap in capabilities 
                              if isinstance(cap, str) and cap.lower() in request_lower]
        if matched_capabilities:
            explanations.append(f"has matching capabilities: {matched_capabilities}")
        
        # Check for specialization matches
        specializations = agent_info.get('specializations', [])
        matched_specializations = [spec for spec in specializations 
                                 if isinstance(spec, str) and spec.lower() in request_lower]
        if matched_specializations:
            explanations.append(f"specializes in: {matched_specializations}")
        
        # Check for classification tag matches
        classification_tags = agent_info.get('classification_tags', [])
        request_words = set(re.findall(r'\w+', request_lower))
        matched_tags = [tag for tag in classification_tags 
                       if isinstance(tag, str) and tag.lower() in request_words]
        if matched_tags:
            explanations.append(f"has relevant tags: {matched_tags}")
        
        # Check if it's a default capable agent
        if agent_info.get('default_capable', False) and not explanations:
            explanations.append("is capable of handling general requests")
        
        if explanations:
            return f"Selected {agent_name} because it {' and '.join(explanations)}"
        else:
            return f"Selected {agent_name} as the best available option"

# NOTE: SimpleAgentClassifier removed to eliminate all rule-based matching.
# Only pure LLM-based classification is now supported via AgentClassifier. 