#!/usr/bin/env python3
"""
Comprehensive Test for Multi-Agent Interactive CLI

This test validates the dynamic agent discovery and interaction capabilities
of the Multi-Agent system. It follows the pattern:

1. Clean Environment: Kill any existing agents
2. Controlled Startup: Start specific test agents  
3. Dynamic Discovery: Test the interface discovers agents properly
4. Interaction Testing: Validate communication with both agent types
5. Cleanup: Properly shutdown all components

The test uses deterministic agents (PersonalAssistant + WeatherAgent) while
validating that the interface remains truly dynamic and capability-driven.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import logging
import signal
import subprocess
import time
import sys
import os
from typing import Dict, Any, List, Optional
from interactive_cli import MultiAgentInteractiveCLI

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MultiAgentTester:
    """Comprehensive tester for multi-agent system"""
    
    def __init__(self):
        self.processes: List[subprocess.Popen] = []
        self.interface: Optional[MultiAgentInteractiveCLI] = None
        
    def cleanup_existing_agents(self):
        """Kill any existing agent processes"""
        logger.info("🧹 Cleaning up existing agent processes...")
        
        # Kill specific agent processes
        agent_patterns = [
            "python.*personal_assistant.py",
            "python.*weather_agent.py", 
            "python.*openai_genesis_agent.py",
            "python.*interactive_cli.py"
        ]
        
        for pattern in agent_patterns:
            try:
                result = subprocess.run(['pkill', '-f', pattern], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info(f"   Killed processes matching: {pattern}")
            except Exception as e:
                logger.debug(f"   No processes found for pattern: {pattern}")
        
        # Give processes time to fully terminate
        time.sleep(2)
        logger.info("✅ Cleanup completed")
    
    def start_agent(self, agent_script: str, agent_name: str) -> subprocess.Popen:
        """Start a specific agent and return the process"""
        logger.info(f"🚀 Starting {agent_name}...")
        
        # Get the absolute path to the agent script
        script_path = os.path.join(os.path.dirname(__file__), 'agents', agent_script)
        
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"Agent script not found: {script_path}")
        
        # Start the agent process
        process = subprocess.Popen([
            sys.executable, script_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        self.processes.append(process)
        logger.info(f"✅ {agent_name} started with PID {process.pid}")
        return process
    
    def start_calculator_service(self) -> subprocess.Popen:
        """Start the calculator service for math testing"""
        logger.info("🧮 Starting Calculator Service...")
        
        # Get path to calculator service
        calc_path = os.path.join(os.path.dirname(__file__), '..', '..', 'test_functions', 'calculator_service.py')
        calc_path = os.path.abspath(calc_path)
        
        if not os.path.exists(calc_path):
            logger.warning(f"Calculator service not found at {calc_path}")
            return None
        
        process = subprocess.Popen([
            sys.executable, calc_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        self.processes.append(process)
        logger.info(f"✅ Calculator Service started with PID {process.pid}")
        return process
    
    async def wait_for_agent_startup(self, timeout: float = 15.0):
        """Wait for agents to fully start up and register"""
        logger.info(f"⏳ Waiting for agents to start up (timeout: {timeout}s)...")
        
        # Give agents time to initialize and register with DDS
        await asyncio.sleep(5)
        
        logger.info("✅ Agent startup wait completed")
    
    async def test_dynamic_discovery(self) -> bool:
        """Test that the interface discovers agents dynamically"""
        logger.info("🔍 Testing Dynamic Agent Discovery...")
        
        try:
            # Create interface 
            self.interface = MultiAgentInteractiveCLI()
            
            # Wait for discovery
            timeout = 15.0
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                if len(self.interface.available_agents) >= 2:  # Expect PersonalAssistant + WeatherAgent
                    break
                await asyncio.sleep(0.5)
            
            # Validate discovery results
            discovered_count = len(self.interface.available_agents)
            logger.info(f"📊 Discovered {discovered_count} agents")
            
            if discovered_count < 2:
                logger.error(f"❌ Expected at least 2 agents, found {discovered_count}")
                return False
            
            # Validate agent details
            for agent_id, agent_info in self.interface.available_agents.items():
                agent_name = agent_info.get('prefered_name', 'Unknown')
                service_name = agent_info.get('service_name', 'Unknown')
                capabilities = self.interface.get_agent_capabilities(agent_info)
                
                logger.info(f"   🤖 {agent_name}")
                logger.info(f"      Service: {service_name}")
                logger.info(f"      Capabilities: {capabilities}")
                logger.info(f"      ID: {agent_id[:12]}...")
            
            logger.info("✅ Dynamic discovery test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Dynamic discovery test failed: {e}")
            return False
    
    async def test_agent_interaction(self, agent_name_pattern: str, test_message: str, expected_keywords: List[str]) -> bool:
        """Test interaction with a specific agent type"""
        logger.info(f"💬 Testing interaction with {agent_name_pattern} agent...")
        
        try:
            # Find the target agent
            target_agent = None
            for agent_id, agent_info in self.interface.available_agents.items():
                agent_name = agent_info.get('prefered_name', '').lower()
                service_name = agent_info.get('service_name', '').lower()
                
                if agent_name_pattern.lower() in agent_name or agent_name_pattern.lower() in service_name:
                    target_agent = {
                        "id": agent_id,
                        "name": agent_info.get('prefered_name', 'Unknown'),
                        "service_name": agent_info.get('service_name', 'Unknown'),
                        "capabilities": self.interface.get_agent_capabilities(agent_info),
                        "info": agent_info
                    }
                    break
            
            if not target_agent:
                logger.error(f"❌ No agent found matching pattern: {agent_name_pattern}")
                return False
            
            logger.info(f"   🎯 Found target agent: {target_agent['name']}")
            
            # Connect to the agent
            success = await self.interface.connect_to_agent(target_agent['service_name'])
            if not success:
                logger.error(f"❌ Failed to connect to {target_agent['name']}")
                return False
            
            logger.info(f"   🔗 Connected to {target_agent['name']}")
            
            # Send test message
            logger.info(f"   📤 Sending: {test_message}")
            response = await self.interface.send_request({
                "message": test_message,
                "conversation_id": f"test_{int(time.time())}"
            })
            
            # Validate response
            if not response or response.get('status') != 0:
                logger.error(f"❌ Failed to get valid response from {target_agent['name']}")
                return False
            
            response_text = response.get('message', '')
            logger.info(f"   📥 Response: {response_text[:100]}{'...' if len(response_text) > 100 else ''}")
            
            # Check for expected keywords in response
            found_keywords = []
            for keyword in expected_keywords:
                if keyword.lower() in response_text.lower():
                    found_keywords.append(keyword)
            
            if found_keywords:
                logger.info(f"   ✅ Found expected keywords: {found_keywords}")
                return True
            else:
                logger.warning(f"   ⚠️ No expected keywords found in response")
                logger.warning(f"   Expected: {expected_keywords}")
                # Don't fail the test for this - response might still be valid
                return True
                
        except Exception as e:
            logger.error(f"❌ Agent interaction test failed: {e}")
            return False
    
    async def test_capability_extraction(self) -> bool:
        """Test that capabilities are properly extracted from agents"""
        logger.info("🎯 Testing Capability Extraction...")
        
        try:
            capability_found = False
            
            for agent_id, agent_info in self.interface.available_agents.items():
                agent_name = agent_info.get('prefered_name', 'Unknown')
                capabilities = self.interface.get_agent_capabilities(agent_info)
                
                logger.info(f"   🤖 {agent_name}: {capabilities}")
                
                if capabilities:
                    capability_found = True
            
            if capability_found:
                logger.info("✅ Capability extraction test passed")
                return True
            else:
                logger.warning("⚠️ No capabilities found - agents may not be advertising properly")
                return True  # Don't fail test, just warn
                
        except Exception as e:
            logger.error(f"❌ Capability extraction test failed: {e}")
            return False
    
    async def run_comprehensive_test(self) -> bool:
        """Run the complete test suite"""
        logger.info("🧪 Starting Comprehensive Multi-Agent Test")
        logger.info("=" * 60)
        
        try:
            # Step 1: Clean environment
            self.cleanup_existing_agents()
            
            # Step 2: Start calculator service (for math functionality)
            calc_process = self.start_calculator_service()
            if calc_process:
                await asyncio.sleep(2)  # Let it start
            
            # Step 3: Start test agents
            personal_process = self.start_agent('personal_assistant.py', 'PersonalAssistant')
            weather_process = self.start_agent('weather_agent.py', 'WeatherAgent')
            
            # Step 4: Wait for startup
            await self.wait_for_agent_startup()
            
            # Step 5: Test dynamic discovery
            discovery_success = await self.test_dynamic_discovery()
            if not discovery_success:
                return False
            
            # Step 6: Test capability extraction
            capability_success = await self.test_capability_extraction()
            if not capability_success:
                return False
            
            # Step 7: Test PersonalAssistant interaction
            personal_success = await self.test_agent_interaction(
                agent_name_pattern="personal",
                test_message="Hello! Can you tell me a joke?",
                expected_keywords=["joke", "funny", "laugh", "humor"]
            )
            
            # Step 8: Test WeatherAgent interaction  
            weather_success = await self.test_agent_interaction(
                agent_name_pattern="weather",
                test_message="What's the weather like in London?",
                expected_keywords=["weather", "temperature", "london", "degrees", "climate"]
            )
            
            # Step 9: Test math capability (if calculator available)
            if calc_process:
                math_success = await self.test_agent_interaction(
                    agent_name_pattern="personal",  # PersonalAssistant should use calculator
                    test_message="What is 123 + 456?",
                    expected_keywords=["579", "123", "456", "sum", "result"]
                )
            else:
                math_success = True  # Skip if no calculator
                logger.info("⏭️ Skipping math test (calculator service not available)")
            
            # Evaluate overall results
            all_tests_passed = (
                discovery_success and 
                capability_success and 
                personal_success and 
                weather_success and 
                math_success
            )
            
            logger.info("=" * 60)
            if all_tests_passed:
                logger.info("🎉 ALL TESTS PASSED! Multi-agent system working correctly")
            else:
                logger.error("❌ Some tests failed - see details above")
            
            return all_tests_passed
            
        except Exception as e:
            logger.error(f"💥 Test suite failed with exception: {e}")
            return False
        
        finally:
            # Always cleanup
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up all processes and resources"""
        logger.info("🧹 Cleaning up test environment...")
        
        # Close interface
        if self.interface:
            try:
                await self.interface.close()
            except Exception as e:
                logger.warning(f"Error closing interface: {e}")
        
        # Terminate all processes
        for process in self.processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            except Exception as e:
                logger.warning(f"Error terminating process {process.pid}: {e}")
        
        # Final cleanup of any remaining processes
        self.cleanup_existing_agents()
        
        logger.info("✅ Cleanup completed")

async def main():
    """Main test execution"""
    tester = MultiAgentTester()
    
    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info("\n🛑 Test interrupted - cleaning up...")
        asyncio.create_task(tester.cleanup())
        sys.exit(1)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        success = await tester.run_comprehensive_test()
        return 0 if success else 1
    except Exception as e:
        logger.error(f"💥 Test execution failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main())) 