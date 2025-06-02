#!/usr/bin/env python3
"""
Personal Assistant - General AI Agent

A friendly, helpful general-purpose AI assistant for everyday tasks.
This agent focuses on personal productivity, daily planning, and providing
warm, empathetic assistance to users.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import logging
import sys
import os
from typing import List, Dict, Any, Optional

# Add the Genesis library path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
from config.agent_configs import get_agent_config
from config.system_settings import get_agent_defaults

logger = logging.getLogger(__name__)

class PersonalAssistant(OpenAIGenesisAgent):
    """
    Personal Assistant - A friendly, helpful general-purpose AI agent.
    
    This agent specializes in:
    - Personal productivity and task management
    - Daily planning and scheduling
    - Information gathering and research
    - Warm, empathetic communication
    - Coordinating with specialized agents for comprehensive assistance
    """
    
    def __init__(self, domain_id: int = 0):
        """
        Initialize the Personal Assistant.
        
        Args:
            domain_id: DDS domain ID for communication
        """
        # Get configuration
        config = get_agent_config("personal_assistant")
        defaults = get_agent_defaults()
        
        # Create enhanced system prompt
        system_prompt = self._create_system_prompt(config)
        
        # Initialize the OpenAI Genesis Agent
        super().__init__(
            agent_name=config["name"],
            base_service_name=config["service_name"],
            model_name=defaults["model_name"],
            classifier_model_name=defaults["classifier_model_name"],
            description=config["description"],
            domain_id=domain_id,
            enable_agent_communication=True,  # Enable agent-as-tool pattern
            enable_tracing=defaults.get("enable_tracing", False)
        )
        
        # Set the custom system prompt
        self.system_prompt = system_prompt
        
        # Store display name for reference
        self.prefered_name = config["display_name"]
        
        self.config = config
        logger.info(f"PersonalAssistant initialized: {self.prefered_name}")
    
    def _create_system_prompt(self, config: Dict[str, Any]) -> str:
        """
        Create the system prompt for the Personal Assistant.
        
        Args:
            config: Agent configuration dictionary
            
        Returns:
            Comprehensive system prompt
        """
        prompt = f"""You are {config['display_name']}, {config['description']}.

PERSONALITY & COMMUNICATION STYLE:
- Tone: {config['personality']['tone']} and {config['personality']['approach']}
- Style: {config['personality']['style']} 
- Traits: {', '.join(config['personality']['traits'])}
- Always be warm, empathetic, and encouraging
- Use a conversational, friendly tone
- Show genuine interest in helping the user

CORE CAPABILITIES:
{chr(10).join(f"- {cap}" for cap in config['capabilities'])}

SPECIALIZATIONS:
{chr(10).join(f"- {spec}" for spec in config['specializations'])}

DYNAMIC TOOL ACCESS:
You may have access to various functions and specialized agents that can help you provide comprehensive assistance. These tools are discovered automatically by the Genesis framework:

- Functions: Mathematical computations, text processing, data analysis, and other computational services
- Specialized Agents: Domain experts that can provide specialized knowledge and assistance

Important: You should ONLY reference tools that are actually available to you via function calls. Do not mention specific services or agents unless they appear in your available tools list.

RESPONSE GUIDELINES:
1. Always greet users warmly and show enthusiasm for helping
2. Listen carefully to understand their needs completely
3. Use available tools when they can help solve the user's request
4. When using tools, explain why you're using them and what value they provide
5. If no relevant tools are available, provide the best assistance you can with your knowledge
6. Be honest about your limitations when specialized tools aren't available
7. Focus on being helpful, warm, and empathetic in all interactions

EXAMPLE BEHAVIORS:
- For mathematical questions: Use calculation tools if available
- For specialized domains: Use relevant expert agents if available  
- For general conversation: Provide thoughtful, caring responses
- For complex requests: Break them down and use multiple tools if needed

Remember: You're a caring, thoughtful assistant who uses whatever tools are available to provide the best possible help, but you never assume specific tools exist unless they're actually accessible to you."""
        
        return prompt

# Main entry point for running the agent independently
async def main():
    """Main entry point for the Personal Assistant."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("🤖 Starting Personal Assistant Agent...")
    
    # Create the assistant
    assistant = PersonalAssistant()
    
    try:
        logger.info("✅ Personal Assistant started successfully!")
        logger.info(f"   Display Name: {assistant.prefered_name}")
        logger.info(f"   Specializations: {', '.join(assistant.config['specializations'])}")
        logger.info(f"   Service: {assistant.base_service_name}")
        logger.info("   Starting agent RPC service and DDS listeners...")
        logger.info("Press Ctrl+C to stop the service")
        
        # CRITICAL FIX: Start the agent's RPC service and DDS listeners
        # This is what actually makes the agent discoverable and able to process requests
        await assistant.run()
            
    except KeyboardInterrupt:
        logger.info("🛑 Shutdown requested by user")
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        return 1
    finally:
        await assistant.close()
        logger.info("👋 Personal Assistant shutdown complete")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main())) 