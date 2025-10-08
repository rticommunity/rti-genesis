#!/usr/bin/env python3
"""
DronesRadar Agent for GraphInterface Demo
This agent discovers drones and makes their positions available through @genesis_tool autodiscovery.
"""

import asyncio
import rti.connextdds as dds
import json
import os
import sys

# Add Genesis-LIB to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
from genesis_lib.decorators import genesis_tool

class DronesRadar(OpenAIGenesisAgent):
    def __init__(self):
        # Generate unique service instance tag
        import time
        service_tag = f"DR_{int(time.time() * 1000) % 1000000}"
        
        super().__init__(
            model_name="gpt-4o",
            classifier_model_name="gpt-4o-mini",
            agent_name="DronesRadarAgent",
            base_service_name="OpenAIAgent",
            service_instance_tag=service_tag,  # Unique tag for this instance
            description="Specialized agent with @genesis_tool autodiscovery - it discovers drones and makes their positions available if asked.",
            enable_agent_communication=True,
            enable_tracing=True
        )

        # Initialize DDS for drone position monitoring (temporarily disabled; using mock data)
        try:
            self.participant = None
            self.reader = None
            print("[DronesRadar] DDS disabled for now; using mock drone positions")
        except Exception as e:
            print(f"[DronesRadar] DDS init (disabled) error: {e}")
            self.participant = None
            self.reader = None

            # Note: Not overriding process_agent_request - using the default OpenAIGenesisAgent implementation
        # This should work the same way as the weather agent

    def get_agent_capabilities(self):
        """Define drone-specific capabilities for agent discovery"""
        return {
            "agent_type": "specialized",
            "specializations": ["drone", "surveillance", "positioning", "tracking"],
            "capabilities": [
                "drone_position_monitoring", "real_time_tracking", "location_data",
                "surveillance_support", "position_analysis", "drone_management"
            ],
            "classification_tags": [
                "drone", "position", "location", "tracking", "surveillance",
                "monitoring", "real-time", "coordinates", "altitude", "speed"
            ],
            "model_info": {
                "type": "drone_specialist",
                "llm_model": "gpt-4o",
                "data_source": "DDS EntityLocation Topic",
                "real_api": True,
                "auto_discovery": True
            },
            "default_capable": False,  # Specialized agent
            "performance_metrics": {
                "avg_response_time": 1.0,
                "accuracy_score": 98.0,
                "availability": 99.9,
                "data_freshness": "real_time"
            }
        }

    @genesis_tool(description="Return the position of all known drones (mocked)")
    async def get_current_positions(self):
        """
        Return the position of all known drones.

        Args:
            None
        """
        # Return static mock positions while DDS is disabled
        mock = [
            {
                "id": "drone1",
                "Position": {
                    "Latitude_deg": 37.7749,
                    "Longitude_deg": -122.4194,
                    "Altitude_ft": 350.0,
                    "Speed_mps": 12.0
                },
                "Orientation": {
                    "Heading_deg": 90.0,
                    "Pitch_deg": 2.0,
                    "Roll_deg": 1.0
                },
                "EntityType": "Drone",
                "Speed": 12.0
            },
            {
                "id": "drone2",
                "Position": {
                    "Latitude_deg": 37.7755,
                    "Longitude_deg": -122.4180,
                    "Altitude_ft": 420.0,
                    "Speed_mps": 15.0
                },
                "Orientation": {
                    "Heading_deg": 135.0,
                    "Pitch_deg": 1.0,
                    "Roll_deg": 0.5
                },
                "EntityType": "Drone",
                "Speed": 15.0
            }
        ]
        return json.dumps(mock)

    def cleanup(self):
        """Clean up DDS resources"""
        if self.participant:
            try:
                self.participant.close()
                print("[DronesRadar] DDS resources cleaned up")
            except Exception as e:
                print(f"[DronesRadar] Error during cleanup: {e}")

async def main():
    """Main function to run the DronesRadar agent"""
    print("[DronesRadar] Starting DronesRadar agent...")
    
    radar = DronesRadar()
    
    try:
        print("[DronesRadar] Agent started successfully")
        print("[DronesRadar] Waiting for agent communication...")
        await radar.run()
    except KeyboardInterrupt:
        print("\n[DronesRadar] Shutting down...")
    except Exception as e:
        print(f"[DronesRadar] Error: {e}")
    finally:
        radar.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
