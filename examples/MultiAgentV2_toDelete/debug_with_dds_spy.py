#!/usr/bin/env python3
"""
Comprehensive debug script with DDS monitoring and full logging
"""
import asyncio
import subprocess
import sys
import os
import time
import signal
from typing import Optional

sys.path.append('../..')
from genesis_lib.monitored_interface import MonitoredInterface

# Set up comprehensive logging
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug_full.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class ComprehensiveDebugger:
    def __init__(self):
        self.dds_spy_process: Optional[subprocess.Popen] = None
        self.interface: Optional[MonitoredInterface] = None
        
    def start_dds_spy(self):
        """Start DDS spy to monitor all DDS traffic"""
        nddshome = os.getenv('NDDSHOME')
        if not nddshome:
            logger.warning("NDDSHOME not set - cannot start DDS spy")
            return
            
        spy_path = os.path.join(nddshome, 'bin', 'rtiddsspy')
        if not os.path.exists(spy_path):
            logger.warning(f"DDS spy not found at {spy_path}")
            return
            
        try:
            logger.info("🔍 Starting DDS Spy to monitor all traffic...")
            self.dds_spy_process = subprocess.Popen(
                [spy_path, '-printSample'],
                stdout=open('dds_spy_output.log', 'w'),
                stderr=subprocess.STDOUT,
                text=True
            )
            logger.info(f"✅ DDS Spy started (PID: {self.dds_spy_process.pid})")
            logger.info("📄 DDS traffic will be logged to dds_spy_output.log")
        except Exception as e:
            logger.error(f"❌ Failed to start DDS spy: {e}")
    
    def stop_dds_spy(self):
        """Stop DDS spy"""
        if self.dds_spy_process:
            logger.info("🛑 Stopping DDS Spy...")
            self.dds_spy_process.terminate()
            try:
                self.dds_spy_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.dds_spy_process.kill()
            logger.info("✅ DDS Spy stopped")
    
    async def debug_agent_communication(self):
        """Debug the complete agent-to-agent communication flow"""
        logger.info("🧪 Starting Comprehensive Agent Communication Debug")
        logger.info("=" * 70)
        
        # Start DDS monitoring
        self.start_dds_spy()
        await asyncio.sleep(2)  # Let spy start
        
        try:
            # Create interface with full logging
            logger.info("🔧 Creating MonitoredInterface...")
            self.interface = MonitoredInterface('DebugInterface', 'DebugService')
            
            # Phase 1: Agent Discovery
            logger.info("=" * 50)
            logger.info("PHASE 1: AGENT DISCOVERY")
            logger.info("=" * 50)
            
            discovery_timeout = 20.0
            start_time = time.time()
            
            while time.time() - start_time < discovery_timeout:
                agent_count = len(self.interface.available_agents)
                logger.info(f"🔍 Discovery check: {agent_count} agents found")
                
                if agent_count >= 2:  # PersonalAssistant + WeatherAgent
                    break
                    
                await asyncio.sleep(2)
            
            final_count = len(self.interface.available_agents)
            logger.info(f"📊 Final discovery result: {final_count} agents")
            
            if final_count < 2:
                logger.error("❌ Insufficient agents discovered!")
                return False
            
            # Log all discovered agents
            for agent_id, agent_info in self.interface.available_agents.items():
                logger.info(f"🤖 Agent: {agent_info.get('prefered_name', 'Unknown')}")
                logger.info(f"   ID: {agent_id}")
                logger.info(f"   Service: {agent_info.get('service_name', 'Unknown')}")
                logger.info(f"   Full info: {agent_info}")
            
            # Phase 2: Connection to PersonalAssistant
            logger.info("=" * 50)
            logger.info("PHASE 2: CONNECT TO PERSONALASSISTANT")
            logger.info("=" * 50)
            
            personal_assistant_service = None
            for agent_id, agent_info in self.interface.available_agents.items():
                if 'personal' in agent_info.get('prefered_name', '').lower():
                    personal_assistant_service = agent_info.get('service_name')
                    logger.info(f"🎯 Found PersonalAssistant service: {personal_assistant_service}")
                    break
            
            if not personal_assistant_service:
                logger.error("❌ PersonalAssistant not found!")
                return False
            
            logger.info(f"🔗 Connecting to PersonalAssistant service: {personal_assistant_service}")
            success = await self.interface.connect_to_agent(personal_assistant_service)
            
            if not success:
                logger.error("❌ Failed to connect to PersonalAssistant")
                return False
            
            logger.info("✅ Connected to PersonalAssistant")
            
            # Phase 3: Wait for Agent Tool Setup
            logger.info("=" * 50)
            logger.info("PHASE 3: WAIT FOR AGENT TOOL SETUP")
            logger.info("=" * 50)
            
            logger.info("⏳ Waiting for PersonalAssistant to process discovered agents into tools...")
            await asyncio.sleep(15)  # Give plenty of time for agent tool setup
            
            # Phase 4: Send Weather Request
            logger.info("=" * 50)
            logger.info("PHASE 4: SEND WEATHER REQUEST")
            logger.info("=" * 50)
            
            weather_query = "What is the current weather in London, England? I need detailed weather information."
            logger.info(f"📤 Sending weather query: {weather_query}")
            logger.info("🔍 This should trigger PersonalAssistant → WeatherAgent delegation")
            
            # Send request with extended timeout
            response = await self.interface.send_request({
                "message": weather_query,
                "conversation_id": f"debug_test_{int(time.time())}"
            }, timeout_seconds=60.0)
            
            # Phase 5: Analyze Response
            logger.info("=" * 50)
            logger.info("PHASE 5: ANALYZE RESPONSE")
            logger.info("=" * 50)
            
            if not response:
                logger.error("❌ No response received")
                return False
            
            logger.info(f"📥 Response status: {response.get('status', 'Unknown')}")
            
            message = response.get('message', '')
            logger.info(f"📝 Response length: {len(message)} characters")
            logger.info(f"📄 Full response: {message}")
            
            # Analyze for weather content
            weather_indicators = [
                'temperature', 'degrees', 'celsius', 'fahrenheit',
                'weather', 'london', 'humidity', 'wind', 'pressure',
                'sunny', 'cloudy', 'rain', 'storm', 'forecast',
                'conditions', 'climate'
            ]
            
            found_indicators = [word for word in weather_indicators 
                              if word.lower() in message.lower()]
            
            logger.info(f"🌤️ Weather indicators found: {found_indicators}")
            
            # Determine success
            has_weather_content = len(found_indicators) >= 3
            has_substantial_response = len(message) > 50
            
            if has_weather_content and has_substantial_response:
                logger.info("✅ SUCCESS: Agent-to-agent delegation appears to be working!")
                return True
            else:
                logger.warning("⚠️ FAILURE: No evidence of agent-to-agent delegation")
                logger.warning("Response suggests PersonalAssistant did not call WeatherAgent")
                return False
                
        except Exception as e:
            logger.error(f"💥 Debug failed with exception: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        
        finally:
            # Cleanup
            if self.interface:
                await self.interface.close()
            self.stop_dds_spy()
    
    async def analyze_dds_logs(self):
        """Analyze the DDS spy logs for capability announcements"""
        logger.info("📊 Analyzing DDS spy logs...")
        
        try:
            if os.path.exists('dds_spy_output.log'):
                with open('dds_spy_output.log', 'r') as f:
                    content = f.read()
                    
                # Look for capability announcements
                if 'weather' in content.lower():
                    logger.info("🌤️ Weather-related DDS traffic detected")
                else:
                    logger.warning("⚠️ No weather-related DDS traffic found")
                
                if 'capabilities' in content.lower():
                    logger.info("📢 Capability announcements detected in DDS traffic")
                else:
                    logger.warning("⚠️ No capability announcements found in DDS traffic")
                
                logger.info(f"📄 DDS log file size: {len(content)} characters")
                if len(content) > 0:
                    logger.info("✅ DDS traffic was captured")
                else:
                    logger.warning("⚠️ No DDS traffic captured")
            else:
                logger.warning("❌ DDS spy log file not found")
                
        except Exception as e:
            logger.error(f"❌ Error analyzing DDS logs: {e}")

async def main():
    """Main debug function"""
    debugger = ComprehensiveDebugger()
    
    # Set up signal handler for cleanup
    def signal_handler(signum, frame):
        logger.info(f"\n🛑 Received signal {signum} - cleaning up...")
        debugger.stop_dds_spy()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        success = await debugger.debug_agent_communication()
        
        # Give DDS spy time to capture final traffic
        await asyncio.sleep(3)
        
        # Analyze what we captured
        await debugger.analyze_dds_logs()
        
        if success:
            logger.info("🎉 Debug session completed successfully")
            logger.info("✅ Agent-to-agent communication is working")
        else:
            logger.error("❌ Debug session revealed communication issues")
            logger.error("💡 Check the logs for detailed analysis")
        
        return 0 if success else 1
        
    except Exception as e:
        logger.error(f"💥 Main debug failed: {e}")
        return 1

if __name__ == "__main__":
    print("🧪 Starting Comprehensive Agent Communication Debug")
    print("📄 Logs will be written to:")
    print("   - debug_full.log (application logs)")
    print("   - dds_spy_output.log (DDS traffic)")
    print()
    
    sys.exit(asyncio.run(main())) 