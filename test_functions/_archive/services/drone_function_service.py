#!/usr/bin/env python3
"""
Drone Function Service for Genesis
This service provides functions for controlling drones and can be discovered by Genesis agents.
"""

import os
import sys
import logging
import json
import asyncio
import time
import uuid
from typing import Dict, Any, List, Optional
import traceback # Added for detailed error logging

# Add Genesis-LIB to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Genesis-LIB'))

from genesis_lib.monitored_service import MonitoredService
import rti.connextdds as dds

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, # Lowered level to DEBUG for more verbose tracing
    format='%(asctime)s - %(name)s - %(levelname)s - %(threadName)s - %(message)s', # Added thread name
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('drone_function_service.log')
    ]
)
logger = logging.getLogger('DroneFunctionService')


class EntityLocationListener(dds.DynamicData.DataReaderListener):
    def __init__(self):
        super().__init__()
        self.drone_positions = {}
        
    def on_data_available(self, reader):
        try:
            samples = reader.take()
            for data, info in samples:
                if data is None or info.state.instance_state != dds.InstanceState.ALIVE:
                    continue
                
                try:
                    # Extract drone ID and format it
                    drone_id = data.get_string("id")
                    formatted_drone_id = f"drone{drone_id}" if drone_id.isdigit() else drone_id
                    
                    # Get position data
                    position = data.get_value("Position")
                    orientation = data.get_value("Orientation")
                    
                    # Create drone data dictionary
                    drone_data = {
                        "id": formatted_drone_id,
                        "Position": {
                            "Latitude_deg": position.get_float64("Latitude_deg"),
                            "Longitude_deg": position.get_float64("Longitude_deg"),
                            "Altitude_ft": position.get_float64("Altitude_ft"),
                            "Speed_mps": data.get_float64("Speed")
                        },
                        "Orientation": {
                            "Heading_deg": orientation.get_float64("Heading_deg"),
                            "Pitch_deg": orientation.get_float64("Pitch_deg"),
                            "Roll_deg": orientation.get_float64("Roll_deg")
                        },
                        "EntityType": str(data.get_value("EntityType"))
                    }
                    
                    # Store in drone positions
                    self.drone_positions[formatted_drone_id] = drone_data
                    
                except Exception as e:
                    logger.error(f"Error processing drone data: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in DDS callback: {e}")


class DroneFunctionService(MonitoredService):
    """Service that provides drone control functions for Genesis"""
    
    def __init__(self):
        """Initialize the drone function service"""
        logger.info("===== SERVICE INIT START ====")
        
        # Initialize the enhanced base class with service name and capabilities
        super().__init__(
            service_name="DroneFunctionService",
            capabilities=["DroneFunctionService", "drone", "control"]
        )
        logger.debug("MonitoredService initialized")
        
        # Initialize DDS publisher for drone commands
        try:
            self.participant = dds.DomainParticipant(0)
            logger.debug(f"DDS Participant created: {self.participant.instance_handle}")
            self.type_provider = dds.QosProvider("./droneswarm.xml")
            logger.debug("DDS QoS Provider loaded from ./droneswarm.xml")
            self.type = self.type_provider.type("DroneOperation")
            logger.debug(f"DDS Type 'DroneOperation' loaded: {self.type.name}")
            self.topic = dds.DynamicData.Topic(
                self.participant,
                "DroneSwarmTopic",
                self.type
            )
            logger.debug(f"DDS Topic 'DroneSwarmTopic' created")
            self.publisher = dds.Publisher(self.participant)
            logger.debug(f"DDS Publisher created")
            self.writer = dds.DynamicData.DataWriter(self.publisher, self.topic)
            logger.debug(f"DDS DataWriter created for DroneSwarmTopic")

            qos_providerR = dds.QosProvider("./entitytypemap.xml")
            self.position_participant = qos_providerR.create_participant_from_config(
                "EntityLocationDomainParticipantLibrary::EntityLocationDomainParticipant")
            self.position_reader =  dds.DynamicData.DataReader(self.position_participant .find_datareader("EntityLocationSubscriber::EntityLocationTopicReader"))
            self.position_listener = EntityLocationListener()
            self.position_reader.set_listener(self.position_listener, dds.StatusMask.DATA_AVAILABLE)

        except Exception as e:
            logger.error(f"===== DDS INITIALIZATION FAILED: {e} ====")
            logger.error(traceback.format_exc())
            raise
        
        # Register functions
        self._register_functions()
        
        logger.info("===== SERVICE INIT COMPLETE ====")
    
    def _register_functions(self):
        """Register all drone functions with the function registry"""
        logger.info("===== REGISTERING FUNCTIONS START ====")
        
        # Register get_positions function
        try:
            func_id_get_pos = self.register_enhanced_function(
                self.get_positions,
                "Get current positions of all drones as a list",
                {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False
                },
                operation_type="query",
                common_patterns={}
            )
            logger.debug(f"Registered 'get_positions' with ID: {func_id_get_pos}")
        except Exception as e:
            logger.error(f"Failed to register 'get_positions': {e}")
            logger.error(traceback.format_exc())

        # Register take_off function
        try:
            func_id_take_off = self.register_enhanced_function(
                self.take_off,
                "Create a plan for a drone to take off to a specific altitude",
                {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "integer",
                            "description": "Target drone ID (0 for all drones, or a specific ID like 1, 2, ...)"
                        },
                        "altitude": {
                            "type": "number",
                            "description": "Altitude in meters (20-1,000)"
                        }
                    },
                    "required": ["target", "altitude"],
                    "additionalProperties": False
                },
                operation_type="planning",
                common_patterns={
                    "target": {"type": "integer", "minimum": 0},
                    "altitude": {"type": "number", "minimum": 20, "maximum": 1000}
                }
            )
            logger.debug(f"Registered 'take_off' with ID: {func_id_take_off}")
        except Exception as e:
            logger.error(f"Failed to register 'take_off': {e}")
            logger.error(traceback.format_exc())

        # Register land function
        try:
            func_id_land = self.register_enhanced_function(
                self.land,
                "Create a plan for a drone to land",
                {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "integer",
                            "description": "Target drone ID (0 for all drones, or a specific ID like 1, 2, ...)"
                        }
                    },
                    "required": ["target"],
                    "additionalProperties": False
                },
                operation_type="planning",
                common_patterns={
                    "target": {"type": "integer", "minimum": 0}
                }
            )
            logger.debug(f"Registered 'land' with ID: {func_id_land}")
        except Exception as e:
            logger.error(f"Failed to register 'land': {e}")
            logger.error(traceback.format_exc())

        # Register set_heading function
        try:
            func_id_set_heading = self.register_enhanced_function(
                self.set_heading,
                "Create a plan to set the heading of a drone",
                {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "integer",
                            "description": "Target drone ID (0 for all drones, or a specific ID like 1, 2, ...)"
                        },
                        "heading": {
                            "type": "number",
                            "description": "Heading in degrees (0-359)"
                        }
                    },
                    "required": ["target", "heading"],
                    "additionalProperties": False
                },
                operation_type="planning",
                common_patterns={
                    "target": {"type": "integer", "minimum": 0},
                    "heading": {"type": "number", "minimum": 0, "maximum": 359}
                }
            )
            logger.debug(f"Registered 'set_heading' with ID: {func_id_set_heading}")
        except Exception as e:
            logger.error(f"Failed to register 'set_heading': {e}")
            logger.error(traceback.format_exc())

        # Register move function
        try:
            func_id_move = self.register_enhanced_function(
                self.move,
                "Create a plan to move a drone to a new position",
                {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "integer",
                            "description": "Target drone ID (0 for all drones, or a specific ID like 1, 2, ...)"
                        },
                        "speed": {
                            "type": "number",
                            "description": "Speed in meters per second (20-500)"
                        },
                        "altitude": {
                            "type": "number",
                            "description": "Altitude in meters (optional)"
                        },
                        "distance": {
                            "type": "number",
                            "description": "Distance to move in meters (optional)"
                        }
                    },
                    "required": ["target", "speed"],
                    "additionalProperties": False
                },
                operation_type="planning",
                common_patterns={
                    "target": {"type": "integer", "minimum": 0},
                    "speed": {"type": "number", "minimum": 20, "maximum": 500},
                    "altitude": {"type": "number", "minimum": 0},
                    "distance": {"type": "number", "minimum": 0}
                }
            )
            logger.debug(f"Registered 'move' with ID: {func_id_move}")
        except Exception as e:
            logger.error(f"Failed to register 'move': {e}")
            logger.error(traceback.format_exc())

        # Register batch_actions function
        try:
            func_id_batch = self.register_enhanced_function(
                self.batch_actions,
                "Create and VALIDATE a plan for multiple drone actions",
                {
                    "type": "object",
                    "properties": {
                        "actions": {
                            "type": "array",
                            "description": "List of actions to perform on the drones",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "action": {
                                        "type": "string",
                                        "description": "The action to perform (e.g., 'take_off', 'land', 'move', 'set_heading')",
                                        "enum": ["take_off", "land", "move", "set_heading"]
                                    },
                                    "parameters": {
                                        "type": "object",
                                        "description": "Parameters for the action"
                                    }
                                },
                                "required": ["action", "parameters"],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": ["actions"],
                    "additionalProperties": False
                },
                operation_type="planning",
                common_patterns={
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {"type": "string", "enum": ["take_off", "land", "move", "set_heading"]},
                                "parameters": {"type": "object"}
                            },
                            "required": ["action", "parameters"]
                        }
                    }
                }
            )
            logger.debug(f"Registered 'batch_actions' with ID: {func_id_batch}")
        except Exception as e:
            logger.error(f"Failed to register 'batch_actions': {e}")
            logger.error(traceback.format_exc())

        # Register execute_plan function
        try:
            func_id_execute = self.register_enhanced_function(
                self.execute_plan,
                "Execute a previously created plan by sending DDS commands",
                {
                    "type": "object",
                    "properties": {
                        "plan": {
                            "type": "array",
                            "description": "The plan to execute",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "action": {
                                        "type": "string",
                                        "description": "The action to perform",
                                        "enum": ["take_off", "land", "move", "set_heading"]
                                    },
                                    "parameters": {
                                        "type": "object",
                                        "description": "Parameters for the action"
                                    }
                                },
                                "required": ["action", "parameters"]
                            }
                        }
                    },
                    "required": ["plan"],
                    "additionalProperties": False
                },
                operation_type="control",
                common_patterns={}
            )
            logger.debug(f"Registered 'execute_plan' with ID: {func_id_execute}")
        except Exception as e:
            logger.error(f"Failed to register 'execute_plan': {e}")
            logger.error(traceback.format_exc())
        
        logger.info("===== REGISTERING FUNCTIONS COMPLETE ====")
    
    async def get_positions(self, request_info=None) -> List[Dict[str, Any]]:
        """Get current positions of all drones as a list"""
        call_uuid = uuid.uuid4()
        logger.info(f"[Call ID: {call_uuid}] ENTERING 'get_positions'")
        
        # Get the dictionary of drone positions from the listener
        positions_dict = self.position_listener.drone_positions
        
        # Convert the dictionary values into a list
        positions_list = list(positions_dict.values())
        
        logger.info(f"[Call ID: {call_uuid}] RETURNING from 'get_positions' (List format): {json.dumps(positions_list)}")
        return positions_list
    
    def publish_command(self, command_code: int, target: int, parameters: dict):
        """Publish a command to the DDS system"""
        call_uuid = uuid.uuid4()
        logger.info(f"[Call ID: {call_uuid}] ENTERING 'publish_command' - Code: {command_code}, Target: {target}, Params: {parameters}")
        try:
            sample = dds.DynamicData(self.type)
            sample['command_code'] = command_code
            sample['target_number'] = target
            sample['parameters'] = [{'name': key, 'value': str(value)} for key, value in parameters.items()]
            logger.info(f"[Call ID: {call_uuid}] Publishing DDS command sample: {sample.to_string()}") # Use to_string for better logging
            self.writer.write(sample)
            logger.info(f"[Call ID: {call_uuid}] DDS write successful for 'publish_command'")
        except Exception as e:
            logger.error(f"[Call ID: {call_uuid}] ERROR during DDS write in 'publish_command': {e}")
            logger.error(traceback.format_exc())
            # Decide if you want to re-raise or just log
        logger.info(f"[Call ID: {call_uuid}] EXITING 'publish_command'")
            
    
    async def take_off(self, target: int, altitude: float, request_info=None) -> Dict[str, Any]:
        """Create a plan for a drone to take off to a specific altitude"""
        call_uuid = uuid.uuid4()
        logger.info(f"[Call ID: {call_uuid}] ENTERING 'take_off' - Target: {target}, Altitude: {altitude}")
        result = {
            "plan": [{
                "action": "take_off",
                "parameters": {
                    "target": target,
                    "altitude": altitude
                }
            }]
        }
        logger.info(f"[Call ID: {call_uuid}] RETURNING from 'take_off': {json.dumps(result)}")
        return result
    
    async def land(self, target: int, request_info=None) -> Dict[str, Any]:
        """Create a plan for a drone to land"""
        call_uuid = uuid.uuid4()
        logger.info(f"[Call ID: {call_uuid}] ENTERING 'land' - Target: {target}")
        result = {
            "plan": [{
                "action": "land",
                "parameters": {
                    "target": target
                }
            }]
        }
        logger.info(f"[Call ID: {call_uuid}] RETURNING from 'land': {json.dumps(result)}")
        return result
    
    async def set_heading(self, target: int, heading: float, request_info=None) -> Dict[str, Any]:
        """Create a plan to set the heading of a drone"""
        call_uuid = uuid.uuid4()
        logger.info(f"[Call ID: {call_uuid}] ENTERING 'set_heading' - Target: {target}, Heading: {heading}")
        result = {
            "plan": [{
                "action": "set_heading",
                "parameters": {
                    "target": target,
                    "heading": heading
                }
            }]
        }
        logger.info(f"[Call ID: {call_uuid}] RETURNING from 'set_heading': {json.dumps(result)}")
        return result
    
    async def move(self, target: int, speed: float, altitude: Optional[float] = None, distance: Optional[float] = None, request_info=None) -> Dict[str, Any]:
        """Create a plan to move a drone to a new position"""
        call_uuid = uuid.uuid4()
        logger.info(f"[Call ID: {call_uuid}] ENTERING 'move' - Target: {target}, Speed: {speed}, Alt: {altitude}, Dist: {distance}")
        params = {
            "target": target,
            "speed": speed
        }
        if altitude is not None:
            params["altitude"] = altitude
        if distance is not None:
            params["distance"] = distance
        result = {
            "plan": [{
                "action": "move",
                "parameters": params
            }]
        }
        logger.info(f"[Call ID: {call_uuid}] RETURNING from 'move': {json.dumps(result)}")
        return result
    
    async def batch_actions(self, actions: List[Dict[str, Any]], request_info=None) -> Dict[str, Any]:
        """Create and VALIDATE a plan for multiple drone actions"""
        call_uuid = uuid.uuid4()
        logger.info(f"[Call ID: {call_uuid}] ENTERING 'batch_actions' - Received actions for validation: {json.dumps(actions)}")
        
        validated_plan = []
        validation_errors = []

        if not isinstance(actions, list):
            logger.error(f"[Call ID: {call_uuid}] Invalid input: 'actions' is not a list.")
            return {"error": "Input 'actions' must be a list."} # Return error structure

        for i, action_item in enumerate(actions):
            if not isinstance(action_item, dict):
                logger.warning(f"[Call ID: {call_uuid}] Skipping invalid action item (not a dict) at index {i}: {action_item}")
                validation_errors.append(f"Item {i}: Not a dictionary.")
                continue

            action_type = action_item.get("action")
            parameters = action_item.get("parameters")

            if not action_type or not isinstance(action_type, str):
                logger.warning(f"[Call ID: {call_uuid}] Skipping action item {i} due to missing/invalid 'action' key: {action_item}")
                validation_errors.append(f"Item {i}: Missing or invalid 'action' key.")
                continue
            
            if not parameters or not isinstance(parameters, dict):
                logger.warning(f"[Call ID: {call_uuid}] Action item {i} ('{action_type}') missing/invalid 'parameters' dict. Adding empty one. Original: {action_item}")
                parameters = {}
                action_item["parameters"] = parameters # Ensure it's added back

            # --- Parameter Validation & Defaulting --- 
            # Ensure 'target' exists, default to 0 (all drones) if missing
            if "target" not in parameters:
                logger.warning(f"[Call ID: {call_uuid}] Action '{action_type}' (item {i}) missing 'target'. Defaulting to 0 (all drones). Params: {parameters}")
                parameters["target"] = 0
            elif not isinstance(parameters["target"], int):
                 # Attempt to convert if string, otherwise default
                try:
                    parameters["target"] = int(parameters["target"])
                    logger.warning(f"[Call ID: {call_uuid}] Action '{action_type}' (item {i}) had non-int 'target'. Converted to int. Params: {parameters}")
                except (ValueError, TypeError):
                    logger.error(f"[Call ID: {call_uuid}] Action '{action_type}' (item {i}) has invalid 'target' type: {parameters['target']}. Defaulting to 0.")
                    parameters["target"] = 0

            # Add specific validation/defaults for other actions if needed
            if action_type == "take_off":
                if "altitude" not in parameters:
                    logger.warning(f"[Call ID: {call_uuid}] Action 'take_off' (item {i}) missing 'altitude'. Defaulting to 100. Params: {parameters}")
                    parameters["altitude"] = 100
            elif action_type == "move":
                 if "speed" not in parameters:
                     logger.warning(f"[Call ID: {call_uuid}] Action 'move' (item {i}) missing 'speed'. Defaulting to 20. Params: {parameters}")
                     parameters["speed"] = 20
                 # Add checks/defaults for distance, altitude if required by your logic
            elif action_type == "set_heading":
                if "heading" not in parameters:
                     logger.error(f"[Call ID: {call_uuid}] Action 'set_heading' (item {i}) missing required 'heading'. This action step will likely fail execution.")
                     validation_errors.append(f"Item {i} ('set_heading'): Missing required 'heading' parameter.")
                     # Decide whether to skip this step or let execution handle it
            
            # Add the validated/defaulted action item to the plan
            validated_plan.append({"action": action_type, "parameters": parameters})
            logger.debug(f"[Call ID: {call_uuid}] Added validated action item {i}: {validated_plan[-1]}")

        # --- Prepare Result --- 
        result = {"plan": validated_plan}
        if validation_errors:
            result["warnings"] = validation_errors # Include warnings/errors if any occurred
            logger.warning(f"[Call ID: {call_uuid}] Returning plan with validation warnings: {validation_errors}")

        logger.info(f"[Call ID: {call_uuid}] RETURNING validated plan from 'batch_actions': {json.dumps(result)}")
        return result
    
    async def execute_plan(self, plan: List[Dict[str, Any]], request_info=None) -> Dict[str, Any]:
        """Execute a plan by sending DDS commands, waiting for heading changes if necessary."""
        call_uuid = uuid.uuid4()
        logger.info(f"[Call ID: {call_uuid}] ENTERING 'execute_plan' - Received plan: {json.dumps(plan)}")
        results = []
        start_time = time.monotonic()
        heading_wait_timeout = 100.0 # Max seconds to wait for heading change
        heading_tolerance_deg = 1.5 # Degrees tolerance for heading match

        try:
            for i, action in enumerate(plan):
                action_type = action.get("action")
                parameters = action.get("parameters", {})
                target = parameters.get("target", 0) # Get target for current action
                logger.debug(f"[Call ID: {call_uuid}] Processing plan step {i+1}: Action='{action_type}', Target={target}, Params={parameters}")
                
                # Map action types to command codes
                command_codes = {
                    "take_off": 1,
                    "land": 2,
                    "move": 3,
                    "set_heading": 4
                }
                
                if action_type in command_codes:
                    # Publish the command for the current action
                    self.publish_command(command_codes[action_type], target, parameters)
                    results.append({"action": action_type, "target": target, "status": "published"})
                    logger.debug(f"[Call ID: {call_uuid}] Step {i+1} ('{action_type}' for target {target}) published.")

                    # --- Wait Logic for Heading Change --- 
                    # If this was a set_heading for a SPECIFIC drone (target != 0)
                    # AND there is a next step which is a move for the SAME drone
                    if action_type == "set_heading" and target != 0 and (i + 1) < len(plan):
                        next_action = plan[i+1]
                        next_action_type = next_action.get("action")
                        next_parameters = next_action.get("parameters", {})
                        next_target = next_parameters.get("target", 0)
                        
                        if next_action_type == "move" and next_target == target:
                            target_heading = parameters.get("heading")
                            if target_heading is not None:
                                logger.info(f"[Call ID: {call_uuid}] Waiting for drone {target} to reach heading {target_heading:.1f}° (±{heading_tolerance_deg}° tolerance) before next move step.")
                                wait_start_time = time.monotonic()
                                heading_reached = False
                                loop_count = 0
                                while time.monotonic() - wait_start_time < heading_wait_timeout:
                                    loop_count += 1
                                    current_time = time.monotonic()
                                    elapsed_time = current_time - wait_start_time
                                    logger.debug(f"[Call ID: {call_uuid} Wait Loop {loop_count}] Elapsed: {elapsed_time:.2f}s / {heading_wait_timeout}s")
                                    
                                    current_state = self.position_listener.drone_positions.get(f"drone{target}")
                                    logger.debug(f"[Call ID: {call_uuid} Wait Loop {loop_count}] Fetched state for drone{target}: {'Found' if current_state else 'Not Found'}")

                                    if current_state and "Orientation" in current_state:
                                        current_heading = current_state["Orientation"].get("Heading_deg")
                                        logger.debug(f"[Call ID: {call_uuid} Wait Loop {loop_count}] Current heading from state: {current_heading}")
                                        if current_heading is not None:
                                            heading_diff = abs(current_heading - target_heading)
                                            # Handle wrap-around (e.g., 359 vs 1 degree)
                                            if heading_diff > 180:
                                                heading_diff = 360 - heading_diff
                                            
                                            logger.debug(f"[Call ID: {call_uuid} Wait Loop {loop_count}] Target: {target_heading:.1f}, Current: {current_heading:.1f}, Diff: {heading_diff:.1f}, Tolerance: {heading_tolerance_deg}")
                                            if heading_diff <= heading_tolerance_deg:
                                                heading_reached = True
                                                logger.info(f"[Call ID: {call_uuid}] Drone {target} reached target heading {target_heading:.1f}° (Current: {current_heading:.1f}°). Proceeding.")
                                                results[-1]["status"] = "heading_confirmed"
                                                break # Exit wait loop
                                            # else: # No need for explicit else, just continues loop if not reached
                                            #     logger.debug(f"[Call ID: {call_uuid}] Waiting... Drone {target} current heading: {current_heading:.1f}°, Target: {target_heading:.1f}°")
                                        else:
                                             logger.debug(f"[Call ID: {call_uuid} Wait Loop {loop_count}] Heading_deg is None in current state.")
                                    else:
                                        logger.debug(f"[Call ID: {call_uuid} Wait Loop {loop_count}] State found, but no 'Orientation' key or drone state not found yet.")

                                    # Short sleep before checking again
                                    logger.debug(f"[Call ID: {call_uuid} Wait Loop {loop_count}] Sleeping for 0.2s")
                                    await asyncio.sleep(0.2)
                                    logger.debug(f"[Call ID: {call_uuid} Wait Loop {loop_count}] Awoke from sleep")
                                # --- End of while loop ---
                                
                                # Check if timeout occurred (only if heading wasn't reached)
                                if not heading_reached:
                                     # Log timeout regardless of whether the loop condition naturally exited
                                     # or was broken early (though break only happens on success)
                                     final_elapsed = time.monotonic() - wait_start_time
                                     logger.warning(f"[Call ID: {call_uuid}] Timeout or loop end ({final_elapsed:.2f}s >= {heading_wait_timeout}s) waiting for drone {target} to reach heading {target_heading:.1f}°. Proceeding with move anyway.")
                                     results[-1]["status"] = "heading_timeout"
                            else:
                                logger.warning(f"[Call ID: {call_uuid}] 'set_heading' action for drone {target} was missing 'heading' parameter in plan. Cannot wait.")
                else:
                    logger.warning(f"[Call ID: {call_uuid}] Step {i+1}: Unknown action type '{action_type}'. Skipping.")
                    results.append({"action": action_type, "target": target, "status": "error", "message": "Unknown action type"})
            
            final_result = {"results": results}
            exec_time = time.monotonic() - start_time
            logger.info(f"[Call ID: {call_uuid}] RETURNING from 'execute_plan' (Duration: {exec_time:.4f}s): {json.dumps(final_result)}")
            return final_result
        except Exception as e:
            logger.error(f"[Call ID: {call_uuid}] ERROR during 'execute_plan': {e}")
            logger.error(traceback.format_exc())
            # Return partial results or an error status
            return {"error": str(e), "partial_results": results}

    def close(self):
        """Clean up resources"""
        logger.info("===== SERVICE SHUTDOWN START ====")
        if hasattr(self, 'participant') and self.participant:
            try:
                self.participant.close()
                logger.info("DDS Participant closed.")
            except Exception as e:
                logger.error(f"Error closing DDS Participant: {e}")
        super().close()
        logger.info("MonitoredService closed.")
        logger.info("===== SERVICE SHUTDOWN COMPLETE ====")

async def main():
    """Main entry point"""
    service = None
    try:
        logger.info("===== STARTING DroneFunctionService ====")
        service = DroneFunctionService()
        logger.info("Service instance created. Starting run loop.")
        await service.run() # This likely blocks until shutdown
        logger.info("Service run loop finished.")
    except KeyboardInterrupt:
        logger.info("Service interrupted by user (KeyboardInterrupt)")
    except Exception as e:
        logger.error(f"===== FATAL ERROR in main: {e} ====")
        logger.error(traceback.format_exc())
    finally:
        logger.info("===== INITIATING FINAL CLEANUP ====")
        if service:
            service.close()
        logger.info("===== DroneFunctionService EXITING ====")

if __name__ == "__main__":
    asyncio.run(main()) 