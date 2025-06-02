#!/usr/bin/env python3
"""
Agent Discovery and Selection System

This module provides automatic discovery of available general agents
and interactive selection capabilities for the CLI interface.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from genesis_lib.monitored_interface import MonitoredInterface
from config.agent_configs import get_all_general_assistants
from config.system_settings import get_interface_defaults

logger = logging.getLogger(__name__)

class AgentStatus(Enum):
    """Agent availability status."""
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"

@dataclass
class DiscoveredAgent:
    """Information about a discovered agent."""
    agent_id: str
    name: str
    display_name: str
    service_name: str
    description: str
    capabilities: List[str]
    specializations: List[str]
    status: AgentStatus
    last_seen: float
    response_time: Optional[float] = None

class AgentSelector:
    """
    Agent discovery and selection system.
    
    This class handles:
    1. Automatic discovery of available general agents
    2. Health checking and availability status
    3. Interactive agent selection for the CLI
    4. Real-time status monitoring
    """
    
    def __init__(self, interface_name: str = "MultiAgentCLI"):
        """
        Initialize the agent selector.
        
        Args:
            interface_name: Name for the monitoring interface
        """
        self.interface_name = interface_name
        self.interface = None
        self.discovered_agents: Dict[str, DiscoveredAgent] = {}
        self.general_assistant_configs = get_all_general_assistants()
        self.defaults = get_interface_defaults()
        self._discovery_active = False
        
        logger.info(f"AgentSelector initialized for interface: {interface_name}")
    
    async def start_discovery(self) -> None:
        """
        Start the agent discovery process.
        
        This method:
        1. Initializes the monitored interface
        2. Begins searching for available general agents
        3. Monitors agent status continuously
        """
        logger.info("Starting agent discovery...")
        
        try:
            # Create monitored interface for discovery
            # The MonitoredInterface automatically handles agent discovery
            self.interface = MonitoredInterface(
                interface_name=self.interface_name,
                service_name="AgentDiscoveryService"
            )
            
            logger.info("✅ MonitoredInterface created - discovery will happen automatically")
            
            self._discovery_active = True
            
            # Start discovery process - wait for agents to be discovered
            await self._discover_agents()
            
            logger.info(f"Agent discovery started. Found {len(self.discovered_agents)} agents.")
            
        except Exception as e:
            logger.error(f"Failed to start agent discovery: {e}")
            raise
    
    async def _discover_agents(self) -> None:
        """
        Discover available agents using the monitored interface.
        
        This method waits for the MonitoredInterface to discover agents
        and processes those that match our general assistant configurations.
        """
        logger.info("Waiting for agent discovery...")
        
        try:
            # Wait for first agent discovery event (like the working interface does)
            logger.info("Waiting for any agent(s) to become available (up to 30s)...")
            await asyncio.wait_for(self.interface._agent_found_event.wait(), timeout=30.0)
            logger.info("First agent(s) found. Waiting a moment for others to appear...")
            
            # Allow time for all agents to announce themselves
            await asyncio.sleep(2)
            
        except asyncio.TimeoutError:
            logger.warning("Timeout: No agent discovery signal received within 30 seconds.")
            # Don't fail - continue to check what we have
        
        # Check what agents were discovered
        if self.interface and hasattr(self.interface, 'available_agents'):
            discovered = self.interface.available_agents
            logger.info(f"Found {len(discovered)} agents in interface.available_agents")
            
            # Debug: Log all discovered agents
            for agent_id, agent_info in discovered.items():
                agent_name = agent_info.get('prefered_name', agent_info.get('name', 'Unknown'))
                service_name = agent_info.get('service_name', 'Unknown')
                logger.info(f"  📋 Discovered: {agent_name} ({service_name}) - ID: {agent_id}")
            
            # Process discovered agents
            for agent_id, agent_info in discovered.items():
                await self._process_discovered_agent(agent_id, agent_info)
        else:
            logger.warning("No available_agents attribute or interface not initialized")
        
        # Wait a bit more for additional discoveries
        additional_wait = 3.0  # Shorter wait
        logger.info(f"Waiting additional {additional_wait} seconds for more discoveries...")
        await asyncio.sleep(additional_wait)
        
        # Check again for any new discoveries
        if self.interface and hasattr(self.interface, 'available_agents'):
            discovered = self.interface.available_agents
            logger.info(f"After additional wait, found {len(discovered)} total agents")
            
            # Process any new agents
            for agent_id, agent_info in discovered.items():
                if agent_id not in self.discovered_agents:
                    await self._process_discovered_agent(agent_id, agent_info)
        
        logger.info(f"Initial discovery complete. Found {len(self.discovered_agents)} general assistants.")
        
        # Debug: Log which agents we actually processed as general assistants
        if self.discovered_agents:
            logger.info("General assistants discovered:")
            for agent_id, agent in self.discovered_agents.items():
                logger.info(f"  ✅ {agent.display_name} ({agent.service_name}) - ID: {agent_id}")
        else:
            logger.warning("❌ No general assistants were discovered!")
            logger.info("Expected to find agents with these configurations:")
            for config_name, config in self.general_assistant_configs.items():
                logger.info(f"  🎯 {config_name}: name='{config['name']}', service='{config['service_name']}'")
                
        # For debugging, also check what topic names are being used
        logger.info("Checking agent configuration vs discovered agents:")
        for config_name, config in self.general_assistant_configs.items():
            logger.info(f"  Looking for: name='{config['name']}', service='{config['service_name']}'")
            
        for agent_id, agent_info in discovered.items():
            agent_name = agent_info.get('prefered_name', agent_info.get('name', 'Unknown'))
            service_name = agent_info.get('service_name', 'Unknown')
            logger.info(f"  Found: name='{agent_name}', service='{service_name}'")
    
    async def _process_discovered_agent(self, agent_id: str, agent_info: Dict[str, Any]) -> None:
        """
        Process a newly discovered agent.
        
        Args:
            agent_id: Unique identifier for the agent
            agent_info: Information about the discovered agent
        """
        agent_name = agent_info.get('prefered_name', agent_info.get('name', 'Unknown'))
        service_name = agent_info.get('service_name', 'Unknown')
        
        # Check if this is a general assistant we're interested in
        if self._is_general_assistant(agent_name, service_name):
            discovered_agent = DiscoveredAgent(
                agent_id=agent_id,
                name=agent_name,
                display_name=self._get_display_name(agent_name),
                service_name=service_name,
                description=self._get_description(agent_name),
                capabilities=self._get_capabilities(agent_name),
                specializations=self._get_specializations(agent_name),
                status=AgentStatus.AVAILABLE,
                last_seen=time.time()
            )
            
            self.discovered_agents[agent_id] = discovered_agent
            logger.info(f"Discovered general assistant: {discovered_agent.display_name} ({agent_id})")
    
    def _is_general_assistant(self, agent_name: str, service_name: str) -> bool:
        """
        Check if the discovered agent is a general assistant.
        
        Args:
            agent_name: Name of the agent
            service_name: Service name of the agent
            
        Returns:
            True if this is a general assistant we should track
        """
        # Check against our configured general assistants
        for config_name, config in self.general_assistant_configs.items():
            if (config["name"] == agent_name or 
                config["service_name"] == service_name or
                agent_name.lower() in config_name.lower()):
                return True
        return False
    
    def _get_display_name(self, agent_name: str) -> str:
        """Get the display name for an agent."""
        for config in self.general_assistant_configs.values():
            if config["name"] == agent_name:
                return config["display_name"]
        return agent_name
    
    def _get_description(self, agent_name: str) -> str:
        """Get the description for an agent."""
        for config in self.general_assistant_configs.values():
            if config["name"] == agent_name:
                return config["description"]
        return "General AI assistant"
    
    def _get_capabilities(self, agent_name: str) -> List[str]:
        """Get the capabilities for an agent."""
        for config in self.general_assistant_configs.values():
            if config["name"] == agent_name:
                return config["capabilities"]
        return []
    
    def _get_specializations(self, agent_name: str) -> List[str]:
        """Get the specializations for an agent."""
        for config in self.general_assistant_configs.values():
            if config["name"] == agent_name:
                return config["specializations"]
        return []
    
    async def refresh_discovery(self) -> None:
        """Refresh the agent discovery to find new agents."""
        if not self._discovery_active:
            return
        
        logger.debug("Refreshing agent discovery...")
        
        # Get current discoveries
        if self.interface and hasattr(self.interface, 'available_agents'):
            discovered = self.interface.available_agents
            
            # Process any new agents
            for agent_id, agent_info in discovered.items():
                if agent_id not in self.discovered_agents:
                    await self._process_discovered_agent(agent_id, agent_info)
            
            # Update status of existing agents
            current_time = time.time()
            for agent_id, agent in self.discovered_agents.items():
                if agent_id in discovered:
                    agent.last_seen = current_time
                    agent.status = AgentStatus.AVAILABLE
                else:
                    # Mark as offline if not seen recently
                    if current_time - agent.last_seen > 30:  # 30 seconds timeout
                        agent.status = AgentStatus.OFFLINE
    
    async def health_check_agent(self, agent_id: str) -> bool:
        """
        Perform a health check on a specific agent.
        
        Args:
            agent_id: ID of the agent to check
            
        Returns:
            True if agent is healthy and responsive
        """
        if agent_id not in self.discovered_agents:
            return False
        
        agent = self.discovered_agents[agent_id]
        
        try:
            # Send a simple ping request to test responsiveness
            start_time = time.time()
            
            # For now, we'll simulate a health check
            # In a real implementation, this would send a test message
            await asyncio.sleep(0.1)  # Simulate network delay
            
            response_time = time.time() - start_time
            agent.response_time = response_time
            agent.status = AgentStatus.AVAILABLE
            agent.last_seen = time.time()
            
            logger.debug(f"Health check passed for {agent.display_name}: {response_time:.3f}s")
            return True
            
        except Exception as e:
            logger.warning(f"Health check failed for {agent.display_name}: {e}")
            agent.status = AgentStatus.OFFLINE
            return False
    
    def get_available_agents(self) -> List[DiscoveredAgent]:
        """
        Get list of available general agents.
        
        Returns:
            List of discovered agents that are currently available
        """
        return [
            agent for agent in self.discovered_agents.values()
            if agent.status == AgentStatus.AVAILABLE
        ]
    
    def get_agent_by_id(self, agent_id: str) -> Optional[DiscoveredAgent]:
        """
        Get a specific agent by ID.
        
        Args:
            agent_id: ID of the agent
            
        Returns:
            DiscoveredAgent if found, None otherwise
        """
        return self.discovered_agents.get(agent_id)
    
    def get_agent_by_name(self, name: str) -> Optional[DiscoveredAgent]:
        """
        Get an agent by name (case-insensitive).
        
        Args:
            name: Name of the agent to find
            
        Returns:
            DiscoveredAgent if found, None otherwise
        """
        name_lower = name.lower()
        for agent in self.discovered_agents.values():
            if (agent.name.lower() == name_lower or 
                agent.display_name.lower() == name_lower):
                return agent
        return None
    
    def format_agent_list(self, include_offline: bool = False) -> str:
        """
        Format the discovered agents as a readable list.
        
        Args:
            include_offline: Whether to include offline agents
            
        Returns:
            Formatted string with agent information
        """
        agents = list(self.discovered_agents.values())
        if not include_offline:
            agents = [a for a in agents if a.status != AgentStatus.OFFLINE]
        
        if not agents:
            return "No agents discovered yet. Please wait for discovery to complete..."
        
        lines = []
        lines.append(f"📋 Discovered Agents ({len(agents)} total):")
        lines.append("-" * 50)
        
        for i, agent in enumerate(agents, 1):
            status_emoji = {
                AgentStatus.AVAILABLE: "🟢",
                AgentStatus.BUSY: "🟡", 
                AgentStatus.OFFLINE: "🔴",
                AgentStatus.UNKNOWN: "⚪"
            }[agent.status]
            
            response_info = ""
            if agent.response_time is not None:
                response_info = f" ({agent.response_time:.3f}s)"
            
            lines.append(f"{i:2d}. {status_emoji} {agent.display_name}{response_info}")
            lines.append(f"     {agent.description}")
            lines.append(f"     Specializations: {', '.join(agent.specializations)}")
            lines.append("")
        
        return "\n".join(lines)
    
    async def close(self) -> None:
        """Clean up resources."""
        logger.info("Closing agent selector...")
        
        self._discovery_active = False
        
        if self.interface:
            await self.interface.close()
            self.interface = None
        
        self.discovered_agents.clear()
        logger.info("Agent selector closed.")

# Test/Demo Functions
async def demo_agent_discovery():
    """
    Demo function to test agent discovery.
    This can be used to validate the discovery system without running agents.
    """
    print("🔍 Starting Agent Discovery Demo...")
    
    selector = AgentSelector("DemoInterface")
    
    try:
        await selector.start_discovery()
        
        # Wait for some discovery time
        print("⏳ Waiting for agent discovery...")
        await asyncio.sleep(5)
        
        await selector.refresh_discovery()
        
        # Display results
        print("\n" + selector.format_agent_list())
        
        # Test health checks
        available_agents = selector.get_available_agents()
        if available_agents:
            print(f"\n🏥 Testing health check on {available_agents[0].display_name}...")
            healthy = await selector.health_check_agent(available_agents[0].agent_id)
            print(f"Health check result: {'✅ HEALTHY' if healthy else '❌ UNHEALTHY'}")
        
    finally:
        await selector.close()
    
    print("✅ Agent discovery demo completed!")

if __name__ == "__main__":
    # Run the demo if this file is executed directly
    asyncio.run(demo_agent_discovery()) 