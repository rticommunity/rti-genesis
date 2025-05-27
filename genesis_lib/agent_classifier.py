"""
Agent Classification System

This module provides intelligent request routing for agent-to-agent communication.
It analyzes incoming requests and determines which agent is best suited to handle
them based on capabilities, specializations, and classification tags.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import logging
import asyncio
import os
from typing import Dict, Any, List, Optional, Tuple
import re
import json

# Get logger
logger = logging.getLogger(__name__)

# Optional OpenAI import for LLM classification
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    logger.warning("OpenAI library not available. LLM classification will be disabled.")

class AgentClassifier:
    """
    Classify requests to determine which agent(s) should handle them.
    
    Uses multiple classification strategies:
    1. Exact capability matching
    2. Specialization domain matching
    3. Keyword/tag matching
    4. LLM-based semantic matching (using GPT-4o-mini)
    5. Default capable agent fallback
    """
    
    def __init__(self, classification_llm=None, openai_api_key=None, model_name="gpt-4o-mini"):
        """
        Initialize the agent classifier.
        
        Args:
            classification_llm: Optional LLM instance for semantic classification
            openai_api_key: OpenAI API key (if None, will try environment variable)
            model_name: OpenAI model to use for classification
        """
        self.classification_llm = classification_llm
        self.agent_registry = {}  # agent_id -> capability info
        
        # Set up OpenAI client for LLM classification
        self.openai_client = None
        self.model_name = model_name
        
        if HAS_OPENAI:
            api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
            if api_key:
                try:
                    self.openai_client = openai.OpenAI(api_key=api_key)
                    logger.info(f"OpenAI client initialized for pure LLM classification using {model_name}")
                except Exception as e:
                    logger.warning(f"Failed to initialize OpenAI client: {e}")
            else:
                logger.warning("No OpenAI API key found. Agent classification will be disabled.")
        else:
            logger.warning("OpenAI library not available. Agent classification will be disabled.")
        
        logger.info(f"AgentClassifier initialized with PURE LLM classification: {'enabled' if self.openai_client else 'DISABLED'}")
    
    def update_agent_registry(self, discovered_agents: Dict[str, Dict[str, Any]]):
        """Update the internal agent registry with discovered agents"""
        self.agent_registry = discovered_agents.copy()
        logger.debug(f"Updated agent registry with {len(self.agent_registry)} agents")
    
    async def classify_request(self, request: str, available_agents: Dict[str, Dict[str, Any]]) -> Optional[str]:
        """
        Determine which agent is best suited to handle a request using PURE LLM classification.
        
        This method uses ONLY semantic LLM-based classification. No rule-based matching,
        no keyword matching, no pattern matching. Pure semantic understanding.
        
        Args:
            request: The request message to classify
            available_agents: Dictionary of available agents with their capability info
            
        Returns:
            Agent ID of the best suited agent, or None if no suitable agent found
        """
        if not available_agents:
            logger.debug("No available agents for classification")
            return None
        
        logger.info(f"Classifying request using PURE LLM: '{request[:100]}...' against {len(available_agents)} agents")
        
        # Update registry
        self.update_agent_registry(available_agents)
        
        # ONLY use LLM-based semantic classification
        if self.classification_llm or self.openai_client:
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
    

    
    async def _llm_classify(self, request: str, available_agents: Dict[str, Dict[str, Any]]) -> Optional[str]:
        """Use LLM for semantic classification (using GPT-4o-mini)"""
        if not self.openai_client:
            logger.debug("OpenAI client not available for LLM classification")
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

            # Call OpenAI API
            logger.debug(f"Sending LLM classification request for: '{request[:50]}...'")
            
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a precise agent routing system. Respond only with the requested agent ID."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature for consistent routing decisions
                max_tokens=50     # We only need the agent ID
            )
            
            # Extract the agent ID from the response
            llm_response = response.choices[0].message.content.strip()
            logger.debug(f"LLM classification response: '{llm_response}'")
            
            # Clean up the response (remove any extra text)
            # Look for the agent ID in the response
            for agent_id in available_agents.keys():
                if agent_id in llm_response:
                    logger.info(f"LLM selected agent: {agent_id}")
                    return agent_id
            
            # If no exact match, try to extract agent ID from common patterns
            # Look for patterns like "agent_id" or just the ID itself
            words = llm_response.lower().replace('-', '_').split()
            for word in words:
                if word in available_agents:
                    logger.info(f"LLM selected agent (extracted): {word}")
                    return word
            
            logger.warning(f"Could not parse agent ID from LLM response: '{llm_response}'")
            return None
            
        except Exception as e:
            logger.error(f"Error in LLM classification: {e}")
            return None
    
    def _find_default_capable_agent(self, available_agents: Dict[str, Dict[str, Any]]) -> Optional[str]:
        """Find a default capable agent as fallback"""
        for agent_id, agent_info in available_agents.items():
            if agent_info.get('default_capable', False):
                logger.debug(f"Found default capable agent: {agent_id}")
                return agent_id
        
        return None
    
    def get_classification_explanation(self, request: str, chosen_agent_id: str, 
                                    available_agents: Dict[str, Dict[str, Any]]) -> str:
        """
        Provide an explanation of why a particular agent was chosen.
        
        Args:
            request: The original request
            chosen_agent_id: The agent that was selected
            available_agents: All available agents
            
        Returns:
            Human-readable explanation string
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