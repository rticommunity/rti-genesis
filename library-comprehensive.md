# Genesis Library Comprehensive Documentation

This document contains all user Python and XML files in the Genesis library.

## genesis_monitor.py

**Author:** Jason

```python
#!/usr/bin/env python3
"""
Enhanced GENESIS Monitoring Application V2.6

This application monitors the enhanced monitoring topics (ComponentLifecycleEvent,
ChainEvent, and LivelinessUpdate) using the new event categorization system to provide 
a unified view of the GENESIS distributed system state.
"""

import argparse
import logging
import sys
import time
import os
import json
from datetime import datetime
import threading
import curses
from enum import Enum
import rti.connextdds as dds
import re
from genesis_lib.utils import get_datamodel_path

# Color pairs for different event types
EVENT_COLOR_PAIRS = {
    # Discovery Events
    "NODE_DISCOVERY": 1,     # White on Blue
    "EDGE_DISCOVERY": 2,     # Black on Cyan
    "STATE_CHANGE": 3,       # Black on Green
    
    # Chain Events
    "CALL_START": 4,         # White on Blue
    "CALL_COMPLETE": 5,      # Black on Green
    "CALL_ERROR": 6,         # White on Red
    "LLM_CALL_START": 7,     # White on Magenta
    "LLM_CALL_COMPLETE": 8,  # Black on Cyan
    "CLASSIFICATION_RESULT": 9, # White on Yellow
    
    # States (for STATE_CHANGE events)
    "JOINING": 10,           # White on Blue
    "DISCOVERING": 11,       # Black on Cyan
    "READY": 12,            # Black on Green
    "BUSY": 13,             # Black on Yellow
    "DEGRADED": 14,         # White on Red
    "OFFLINE": 15,          # White on default
    
    "UNKNOWN": 0            # Default color
}

class ComponentLifecycleListener(dds.DynamicData.NoOpDataReaderListener):
    """Custom listener for ComponentLifecycleEvent topic."""
    
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.logger = logging.getLogger("ComponentLifecycleListener")
        self.logger.setLevel(logging.DEBUG)
    
    def on_data_available(self, reader):
        """Handle received data."""
        try:
            samples = reader.take()
            print(f"Got {len(samples)} samples", file=sys.stderr)
            
            for data, info in samples:
                if data is None or info.state.instance_state != dds.InstanceState.ALIVE:
                    continue
                
                print(f"\nRAW DDS DATA:", file=sys.stderr)
                print(f"Capabilities: {data['capabilities']}", file=sys.stderr)
                print(f"Reason: {data['reason']}", file=sys.stderr)
                
                print(f"\nProcessing sample: {data}", file=sys.stderr)
                
                # Map component types and states
                component_types = ["INTERFACE", "PRIMARY_AGENT", "SPECIALIZED_AGENT", "FUNCTION"]
                states = ["JOINING", "DISCOVERING", "READY", "BUSY", "DEGRADED", "OFFLINE"]
                event_categories = ["NODE_DISCOVERY", "EDGE_DISCOVERY", "STATE_CHANGE", "AGENT_INIT", "AGENT_READY", "AGENT_SHUTDOWN", "DDS_ENDPOINT"]
                
                # Convert enum values to integers for indexing
                component_type_idx = int(data["component_type"])
                previous_state_idx = int(data["previous_state"])
                new_state_idx = int(data["new_state"])
                event_category_idx = int(data["event_category"])
                
                # Safely get event category
                event_category = event_categories[event_category_idx] if 0 <= event_category_idx < len(event_categories) else "UNKNOWN"
                
                # Build data dictionary with new format fields
                data_dict = {
                    "event_category": event_category,
                    "component_id": data["component_id"],
                    "component_type": component_types[component_type_idx],
                    "previous_state": states[previous_state_idx],
                    "new_state": states[new_state_idx],
                    "timestamp": data["timestamp"],
                    "source_id": str(data["source_id"]) if data["source_id"] else "",
                    "target_id": str(data["target_id"]) if data["target_id"] else "",
                    "connection_type": str(data["connection_type"]) if data["connection_type"] else "",
                    "chain_id": data["chain_id"],
                    "call_id": data["call_id"],
                    "capabilities": data["capabilities"],
                    "reason": data["reason"]
                }
                
                if self.callback:
                    self.callback(data_dict)
                    
        except Exception as e:
            print(f"Error in ComponentLifecycleListener: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)

class ChainEventListener(dds.DynamicData.NoOpDataReaderListener):
    """Custom listener for ChainEvent topic."""
    
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.logger = logging.getLogger("ChainEventListener")
        self.logger.setLevel(logging.DEBUG)
    
    def on_data_available(self, reader):
        """Handle received data."""
        try:
            samples = reader.take()
            print(f"\nChainEventListener: Got {len(samples)} samples", file=sys.stderr)
            
            for data, info in samples:
                if data is None or info.state.instance_state != dds.InstanceState.ALIVE:
                    continue
                
                data_dict = {
                    "event_type": data["event_type"],
                    "chain_id": data["chain_id"],
                    "source_id": data["source_id"],
                    "target_id": data["target_id"],
                    "function_id": data["function_id"],
                    "timestamp": data["timestamp"],
                    "status": data["status"],
                    "call_id": data["call_id"]
                }
                
                if self.callback:
                    self.callback(data_dict)
                    
        except Exception as e:
            print(f"Error in ChainEventListener: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)

class MonitoringAppV2_6:
    """
    Terminal-based monitoring application for GENESIS V2.6.
    Displays monitoring events using the new event categorization system.
    """
    def __init__(self, domain_id=0, max_entries=1000):
        """Initialize the monitoring application."""
        self.domain_id = domain_id
        self.max_entries = max_entries
        self.entries = []
        self.entries_lock = threading.Lock()
        
        # Display control
        self.paused = False
        self.quit_flag = False
        self.show_details = False
        self.scroll_position = 0
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename='genesis_monitor_v2.6.log'
        )
        self.logger = logging.getLogger("MonitoringAppV2.6")
        
        # Create DDS entities
        print(f"\nInitializing DDS on domain {domain_id}", file=sys.stderr)
        self.participant = dds.DomainParticipant(domain_id)
        self.subscriber = dds.Subscriber(self.participant)
        
        # Get type provider
        print("Loading types from datamodel.xml", file=sys.stderr)
        provider = dds.QosProvider(get_datamodel_path())
        
        # Set up ComponentLifecycleEvent subscriber
        print("Creating ComponentLifecycleEvent topic", file=sys.stderr)
        self.lifecycle_type = provider.type("genesis_lib", "ComponentLifecycleEvent")
        self.lifecycle_topic = dds.DynamicData.Topic(
            self.participant,
            "ComponentLifecycleEvent",
            self.lifecycle_type
        )
        
        # Set up ChainEvent subscriber
        print("Creating ChainEvent topic", file=sys.stderr)
        self.chain_type = provider.type("genesis_lib", "ChainEvent")
        self.chain_topic = dds.DynamicData.Topic(
            self.participant,
            "ChainEvent",
            self.chain_type
        )
        
        # Configure reader QoS
        reader_qos = dds.QosProvider.default.datareader_qos
        reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        reader_qos.history.kind = dds.HistoryKind.KEEP_LAST
        reader_qos.history.depth = 1000
        
        # Create readers with listeners
        self.lifecycle_listener = ComponentLifecycleListener(self._lifecycle_callback)
        self.lifecycle_reader = dds.DynamicData.DataReader(
            subscriber=self.subscriber,
            topic=self.lifecycle_topic,
            qos=reader_qos,
            listener=self.lifecycle_listener,
            mask=dds.StatusMask.DATA_AVAILABLE
        )
        
        self.chain_listener = ChainEventListener(self._chain_callback)
        self.chain_reader = dds.DynamicData.DataReader(
            subscriber=self.subscriber,
            topic=self.chain_topic,
            qos=reader_qos,
            listener=self.chain_listener,
            mask=dds.StatusMask.DATA_AVAILABLE
        )
    
    def _lifecycle_callback(self, data):
        """Handle received lifecycle events."""
        with self.entries_lock:
            entry = {
                "type": "lifecycle",
                "data": data,
                "timestamp": data["timestamp"]
            }
            self._add_entry(entry)
    
    def _chain_callback(self, data):
        """Handle received chain events."""
        with self.entries_lock:
            entry = {
                "type": "chain",
                "data": data,
                "timestamp": data["timestamp"]
            }
            self._add_entry(entry)
    
    def _add_entry(self, entry):
        """Add an entry to the list and maintain max size."""
        self.entries.append(entry)
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]
    
    def run_curses(self, stdscr):
        """Run the monitoring application with curses interface."""
        # Initialize curses
        curses.curs_set(0)
        curses.use_default_colors()
        stdscr.keypad(True)
        
        # Initialize color pairs
        self._init_color_pairs()
        
        # Get screen dimensions
        max_y, max_x = stdscr.getmaxyx()
        
        # Create windows
        header_win = curses.newwin(3, max_x, 0, 0)
        main_win = curses.newwin(max_y - 5, max_x, 3, 0)
        status_win = curses.newwin(2, max_x, max_y - 2, 0)
        
        # Enable scrolling in main window
        main_win.scrollok(True)
        
        # Main loop
        refresh_interval = 0.1
        last_refresh = 0
        
        while not self.quit_flag:
            current_time = time.time()
            
            if not self.paused or current_time - last_refresh >= 1.0:
                self._update_header(header_win, max_x)
                self._update_main_window(main_win, max_y, max_x)
                self._update_status(status_win, max_x)
                last_refresh = current_time
            
            key = self._handle_input(stdscr)
            if key == ord('q'):
                self.quit_flag = True
            elif key == ord('p'):
                self.paused = not self.paused
            elif key == ord('c'):
                with self.entries_lock:
                    self.entries = []
            elif key == ord('d'):
                self.show_details = not self.show_details
            
            time.sleep(refresh_interval)
    
    def _init_color_pairs(self):
        """Initialize color pairs for different event types."""
        # Discovery Events
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)    # NODE_DISCOVERY
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)    # EDGE_DISCOVERY
        curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_GREEN)   # STATE_CHANGE
        
        # Chain Events
        curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLUE)    # CALL_START
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_GREEN)   # CALL_COMPLETE
        curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_RED)     # CALL_ERROR
        curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_MAGENTA) # LLM_CALL_START
        curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_CYAN)    # LLM_CALL_COMPLETE
        curses.init_pair(9, curses.COLOR_WHITE, curses.COLOR_YELLOW)  # CLASSIFICATION_RESULT
        
        # States
        curses.init_pair(10, curses.COLOR_WHITE, curses.COLOR_BLUE)   # JOINING
        curses.init_pair(11, curses.COLOR_BLACK, curses.COLOR_CYAN)   # DISCOVERING
        curses.init_pair(12, curses.COLOR_BLACK, curses.COLOR_GREEN)  # READY
        curses.init_pair(13, curses.COLOR_BLACK, curses.COLOR_YELLOW) # BUSY
        curses.init_pair(14, curses.COLOR_WHITE, curses.COLOR_RED)    # DEGRADED
        curses.init_pair(15, curses.COLOR_WHITE, -1)                  # OFFLINE
    
    def _format_event_line(self, data, event_type, max_x):
        """Format an event line based on its type."""
        timestamp = datetime.fromtimestamp(data["timestamp"] / 1000).strftime("%H:%M:%S.%f")[:-3]
        
        if event_type == "lifecycle":
            category = data["data"]["event_category"]
            if category == "NODE_DISCOVERY":
                # Try to extract function name from capabilities
                capabilities = {}
                try:
                    capabilities = json.loads(data['data']['capabilities'])
                except:
                    pass
                
                # Get display name from capabilities
                display_name = None
                if isinstance(capabilities, dict):
                    display_name = capabilities.get("function_name")
                
                component_info = f"{data['data']['component_id']}"
                if display_name:
                    component_info = f"{display_name} ({component_info})"
                
                event_line = f"[{timestamp}] [NODE.DISCOVERY] Component: {component_info} ({data['data']['component_type']})"
                color = EVENT_COLOR_PAIRS["NODE_DISCOVERY"]
            elif category == "EDGE_DISCOVERY":
                # Try to extract function name from capabilities for edges
                capabilities = {}
                try:
                    capabilities = json.loads(data['data']['capabilities'])
                except:
                    pass
                
                # Get function name from capabilities if available
                function_name = ""
                if isinstance(capabilities, dict):
                    function_name = capabilities.get("function_name", "")
                    if function_name:
                        function_name = f" [{function_name}]"
                
                event_line = f"[{timestamp}] [EDGE.DISCOVERY] {data['data']['connection_type']}: {data['data']['source_id']} -> {data['data']['target_id']}{function_name}"
                color = EVENT_COLOR_PAIRS["EDGE_DISCOVERY"]
            elif category == "STATE_CHANGE":
                event_line = f"[{timestamp}] [STATE.CHANGE] {data['data']['component_id']}: {data['data']['previous_state']} -> {data['data']['new_state']}"
                color = EVENT_COLOR_PAIRS[data['data']['new_state']]
            elif category == "AGENT_INIT":
                event_line = f"[{timestamp}] [AGENT.INIT] {data['data']['component_id']}: {data['data']['reason']}"
                color = EVENT_COLOR_PAIRS["JOINING"]
            elif category == "AGENT_READY":
                event_line = f"[{timestamp}] [AGENT.READY] {data['data']['component_id']}: {data['data']['reason']}"
                color = EVENT_COLOR_PAIRS["READY"]
            elif category == "AGENT_SHUTDOWN":
                event_line = f"[{timestamp}] [AGENT.SHUTDOWN] {data['data']['component_id']}: {data['data']['reason']}"
                color = EVENT_COLOR_PAIRS["OFFLINE"]
            elif category == "DDS_ENDPOINT":
                event_line = f"[{timestamp}] [DDS.ENDPOINT] {data['data']['component_id']}: {data['data']['reason']}"
                color = EVENT_COLOR_PAIRS["DISCOVERING"]
            else:
                event_line = f"[{timestamp}] [{category}] {data['data']['component_id']}: {data['data']['reason']}"
                color = EVENT_COLOR_PAIRS["UNKNOWN"]
        else:  # chain event
            event_type = data["data"]["event_type"]
            chain_id = data["data"]["chain_id"][:8]
            source = data["data"]["source_id"]
            target = data["data"]["target_id"]
            function_id = data["data"]["function_id"]
            
            if "LLM" in event_type:
                prefix = "[LLM.BASE]" if "classifier" not in function_id.lower() else "[LLM.CLASSIFIER]"
            else:
                prefix = "[CHAIN]"
            
            event_line = f"[{timestamp}] {prefix} [{event_type}] Chain {chain_id}: {source} -> {target}"
            if function_id:
                event_line += f" [{function_id}]"
            
            color = EVENT_COLOR_PAIRS.get(event_type, EVENT_COLOR_PAIRS["UNKNOWN"])
        
        if len(event_line) > max_x - 2:
            event_line = event_line[:max_x - 5] + "..."
        
        return event_line, color
    
    def _count_lines_lifecycle(self, data, show_details):
        """Count how many lines a lifecycle event will take."""
        lines = 1  # Main event line
        
        if show_details:
            # Add lines for each detail
            if data["event_category"] == "NODE_DISCOVERY":
                lines += 1  # Component Type
                try:
                    capabilities = json.loads(data['capabilities'])
                    if isinstance(capabilities, dict):
                        if "function_name" in capabilities:
                            lines += 1
                        if "description" in capabilities:
                            lines += 1
                except:
                    pass
            elif data["event_category"] == "EDGE_DISCOVERY":
                lines += 1  # Connection Type
                lines += 1  # Source
                lines += 1  # Target
                try:
                    capabilities = json.loads(data['capabilities'])
                    if isinstance(capabilities, dict) and "function_name" in capabilities:
                        lines += 1
                except:
                    pass
            elif data["event_category"] == "STATE_CHANGE":
                lines += 1  # Previous State
                lines += 1  # New State
            
            # Common details
            if data["chain_id"]:
                lines += 1
            if data["call_id"]:
                lines += 1
            if data.get("reason"):
                lines += 1
        
        return lines
    
    def _count_lines_chain(self, data, show_details):
        """Count how many lines a chain event will take."""
        lines = 1  # Main event line
        
        if show_details:
            if data.get("function_id"):
                lines += 1
            if data.get("source_id"):
                lines += 1
            if data.get("target_id"):
                lines += 1
            if data.get("status") is not None:
                lines += 1
            if data.get("chain_id"):
                lines += 1
            if data.get("call_id"):
                lines += 1
        
        return lines
    
    def _update_main_window(self, win, max_y, max_x):
        """Update the main display window."""
        win.clear()
        
        with self.entries_lock:
            # Calculate total lines needed for all entries
            total_lines = 0
            line_counts = []  # Store number of lines each entry will take
            
            # First pass - count lines
            for entry in sorted(self.entries, key=lambda x: x["timestamp"]):
                if entry["type"] == "lifecycle":
                    lines = self._count_lines_lifecycle(entry["data"], self.show_details)
                else:  # chain
                    lines = self._count_lines_chain(entry["data"], self.show_details)
                line_counts.append(lines)
                total_lines += lines
            
            # Calculate valid scroll range
            max_scroll = max(0, total_lines - (max_y - 5))
            self.scroll_position = min(max_scroll, self.scroll_position)
            self.scroll_position = max(0, self.scroll_position)
            
            # Find starting entry and offset
            current_line = 0
            start_entry = 0
            start_line_offset = 0
            
            sorted_entries = sorted(self.entries, key=lambda x: x["timestamp"])
            
            # Find which entry to start displaying from
            for i, count in enumerate(line_counts):
                if current_line + count > self.scroll_position:
                    start_entry = i
                    start_line_offset = self.scroll_position - current_line
                    break
                current_line += count
            
            # Display entries
            display_line = 0
            for i in range(start_entry, len(sorted_entries)):
                if display_line >= max_y - 5:
                    break
                
                entry = sorted_entries[i]
                event_line, color = self._format_event_line(entry, entry["type"], max_x)
                
                try:
                    # Skip lines for the first entry if there's an offset
                    if i == start_entry and start_line_offset > 0:
                        if display_line - start_line_offset >= 0:
                            win.addstr(display_line - start_line_offset, 0, event_line, curses.color_pair(color))
                    else:
                        win.addstr(display_line, 0, event_line, curses.color_pair(color))
                    display_line += 1
                    
                    if self.show_details:
                        if entry["type"] == "lifecycle":
                            details = self._get_lifecycle_details(entry["data"])
                        else:
                            details = self._get_chain_details(entry["data"])
                        
                        for detail in details:
                            if display_line >= max_y - 5:
                                break
                            if i == start_entry and start_line_offset > 0:
                                if display_line - start_line_offset >= 0:
                                    win.addstr(display_line - start_line_offset, 2, detail[:max_x-3])
                            else:
                                win.addstr(display_line, 2, detail[:max_x-3])
                            display_line += 1
                except curses.error:
                    pass
        
        win.refresh()
    
    def _get_lifecycle_details(self, data):
        """Get formatted details for a lifecycle event."""
        details = []
        
        # Add category-specific details
        if data["event_category"] == "NODE_DISCOVERY":
            details.append(f"Component Type: {data['component_type']}")
            
            # Try to extract function name from capabilities
            try:
                capabilities = json.loads(data['capabilities'])
                if isinstance(capabilities, dict) and "function_name" in capabilities:
                    details.append(f"Function Name: {capabilities['function_name']}")
                if "description" in capabilities:
                    details.append(f"Description: {capabilities['description']}")
            except:
                pass
                
        elif data["event_category"] == "EDGE_DISCOVERY":
            details.append(f"Connection Type: {data['connection_type']}")
            details.append(f"Source: {data['source_id']}")
            details.append(f"Target: {data['target_id']}")
            
            # Try to extract function name from capabilities for edges
            try:
                capabilities = json.loads(data['capabilities'])
                if isinstance(capabilities, dict) and "function_name" in capabilities:
                    details.append(f"Function: {capabilities['function_name']}")
            except:
                pass
                
        elif data["event_category"] == "STATE_CHANGE":
            details.append(f"Previous State: {data['previous_state']}")
            details.append(f"New State: {data['new_state']}")
        
        # Add common details if they exist
        if data["chain_id"]:
            details.append(f"Chain ID: {data['chain_id']}")
        if data["call_id"]:
            details.append(f"Call ID: {data['call_id']}")
        if data.get("reason"):
            details.append(f"Reason: {data['reason']}")
        
        return details
    
    def _get_chain_details(self, data):
        """Get formatted details for a chain event."""
        details = []
        
        # Add chain-specific details
        if data.get("function_id"):
            details.append(f"Function: {data['function_id']}")
        if data.get("source_id"):
            details.append(f"Source: {data['source_id']}")
        if data.get("target_id"):
            details.append(f"Target: {data['target_id']}")
        if data.get("status"):
            details.append(f"Status: {data['status']}")
        if data.get("chain_id"):
            details.append(f"Chain ID: {data['chain_id']}")
        if data.get("call_id"):
            details.append(f"Call ID: {data['call_id']}")
        
        return details
    
    def _update_header(self, win, max_x):
        """Update the header window."""
        win.clear()
        title = " GENESIS Monitor V2.6 "
        domain = f" Domain: {self.domain_id} "
        status = "PAUSED" if self.paused else "RUNNING"
        
        win.addstr(0, 0, title, curses.A_BOLD)
        win.addstr(0, max_x - len(domain), domain, curses.A_BOLD)
        win.addstr(1, 0, f" Status: {status} | Press [q]uit | [p]ause | [c]lear | [d]etails")
        win.refresh()
    
    def _update_status(self, win, max_x):
        """Update the status window."""
        win.clear()
        
        with self.entries_lock:
            total_events = len(self.entries)
            lifecycle_events = sum(1 for e in self.entries if e["type"] == "lifecycle")
            chain_events = sum(1 for e in self.entries if e["type"] == "chain")
        
        status_line = f" Events: {total_events} | Lifecycle: {lifecycle_events} | Chain: {chain_events}"
        if len(status_line) < max_x:
            status_line += " | Press 'd' to toggle details"
        
        win.addstr(0, 0, status_line)
        win.refresh()
    
    def _handle_input(self, stdscr):
        """Handle keyboard input."""
        stdscr.timeout(100)
        try:
            key = stdscr.getch()
            if key == curses.KEY_UP:
                self.scroll_position = max(0, self.scroll_position - 1)
            elif key == curses.KEY_DOWN:
                self.scroll_position += 1
            elif key == curses.KEY_PPAGE:  # Page Up
                self.scroll_position = max(0, self.scroll_position - 10)
            elif key == curses.KEY_NPAGE:  # Page Down
                self.scroll_position += 10
            return key
        except:
            return -1
    
    def run(self):
        """Run the monitoring application."""
        try:
            curses.wrapper(self.run_curses)
        except KeyboardInterrupt:
            print("\nShutting down...")
        except Exception as e:
            print(f"Exception occurred: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
        finally:
            self.logger.info("Shutting down monitoring application")
            if hasattr(self, 'lifecycle_reader'):
                self.lifecycle_reader.close()
            if hasattr(self, 'chain_reader'):
                self.chain_reader.close()
            if hasattr(self, 'participant'):
                self.participant.close()

def main():
    """Main entry point for the monitoring application."""
    parser = argparse.ArgumentParser(description="GENESIS Monitoring Application V2.6")
    parser.add_argument("--domain", type=int, default=0, help="DDS domain ID")
    parser.add_argument("--max-entries", type=int, default=1000,
                       help="Maximum number of entries to keep in memory")
    args = parser.parse_args()
    
    app = MonitoringAppV2_6(
        domain_id=args.domain,
        max_entries=args.max_entries
    )
    app.run()

if __name__ == "__main__":
    main() 
```

## test_rti_dds.py

**Author:** Jason

```python
import time
import rti.connextdds as dds
from rti.types.builtin import String

def test_rti_dds():
    # Create a DomainParticipant
    participant = dds.DomainParticipant(domain_id=0)
    
    # Create a Topic
    topic = dds.Topic(participant, "TestTopic", String)
    
    # Create a Publisher and DataWriter
    publisher = dds.Publisher(participant)
    writer = dds.DataWriter(publisher, topic)
    
    # Create a Subscriber and DataReader
    subscriber = dds.Subscriber(participant)
    reader = dds.DataReader(subscriber, topic)
    
    # Write a sample
    sample = String("Hello, RTI DDS!")
    print(f"Writing sample: {sample}")
    writer.write(sample)
    
    # Wait for the sample to be received
    time.sleep(1)
    
    # Read the sample
    samples = reader.take()
    for sample in samples:
        if sample.info.valid:
            print(f"Received sample: {sample.data}")
    
    # Cleanup
    participant.close()

if __name__ == "__main__":
    print("Starting RTI DDS test...")
    try:
        test_rti_dds()
        print("Test completed successfully!")
    except Exception as e:
        print(f"Test failed with error: {e}") 
```

## setup.py

**Author:** Jason

```python
from setuptools import setup, find_packages

setup(
    name="genesis-lib",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "flask",
        "flask-socketio",
        "tabulate",
        "anthropic",
        "openai",
    ],
    extras_require={
        'dds': ['rti-connextdds'],  # Optional DDS support
    },
    entry_points={
        'console_scripts': [
            'genesis-monitor=genesis_lib.monitoring.console:main',
            'genesis-web-monitor=genesis_lib.monitoring.web:main',
        ],
    },
)

```

## agent.py

**Author:** Jason

```python
#!/usr/bin/env python3

import asyncio
import logging
from genesis_lib.agent import GenesisAgent
from genesis_lib.function_discovery import FunctionRegistry
from genesis_lib.datamodel import FunctionRequest, FunctionReply

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("simple_agent")

class SimpleAgent(GenesisAgent):
    def __init__(self):
        super().__init__("SimpleAgent", "SimpleService")
        logger.info("SimpleAgent initialized")
    
    async def process_request(self, request: FunctionRequest) -> FunctionReply:
        """
        Process incoming requests. This is a simple echo implementation.
        """
        logger.info(f"Processing request: {request}")
        return FunctionReply(
            success=True,
            result=request.parameters.get("message", ""),
            error_message=""
        )

async def main():
    try:
        # Initialize function registry
        registry = FunctionRegistry()
        
        # Create and start agent
        agent = SimpleAgent()
        logger.info("Agent started successfully")
        
        # Keep the agent running
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"Error in agent: {str(e)}")
        raise
    finally:
        if 'agent' in locals():
            await agent.close()

if __name__ == "__main__":
    asyncio.run(main()) 
```

## my_app.py

**Author:** Jason

```python
#!/usr/bin/env python3
"""
My Genesis Application
"""

import logging
from genesis_lib.monitored_agent import MonitoredAgent
from genesis_lib.interface import GenesisInterface
from genesis_lib.genesis_app import GenesisApp
from genesis_lib.function_client import GenericFunctionClient
from genesis_lib import genesis_monitoring

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class MyAgent(MonitoredAgent):
    """My custom agent."""
    
    def __init__(self, agent_name="MyAgent"):
        """Initialize the agent."""
        super().__init__(agent_name, "Test")  # Use Test service interface
        logger.info(f"Initialized {agent_name} with Test service")
    
    def _process_request(self, request):
        """Process the request and return a reply."""
        logger.info(f"Received request: {request}")
        
        # Create a simple reply
        reply = {
            "message": f"Hello from {self.agent_name}!",
            "status": 0  # 0 indicates success
        }
        
        logger.info(f"Sending reply: {reply}")
        return reply

def main():
    """Main function."""
    # Configure DDS logging
    logger, log_publisher, handler = genesis_monitoring.configure_dds_logging(
        logger_name="MyApp",
        source_name="MyAgent",
        log_level=logging.INFO
    )
    
    # Add DDS handler to root logger so all loggers get it
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    
    try:
        # Create an agent
        agent = MyAgent()
        
        # Run the agent
        agent.run()
    finally:
        # Clean up DDS logging
        log_publisher.close()

if __name__ == "__main__":
    main()

```

## agent1.py

**Author:** Jason

```python
import logging
import os
from genesis_lib.agent import GenesisAgent, AnthropicChatAgent
import time
from typing import Any, Dict

# Configure logging for both app and library with detailed format
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG level for maximum detail
    format='%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Get logger for this file
logger = logging.getLogger(__name__)

class TracingAnthropicChatAgent(GenesisAgent, AnthropicChatAgent):
    """Custom implementation that combines GenesisAgent and AnthropicChatAgent directly"""
    def __init__(self, system_prompt: str):
        logger.info("Initializing TracingAnthropicChatAgent")
        # Initialize both parent classes
        GenesisAgent.__init__(self, agent_name="Claude", service_name="ChatGPT")
        AnthropicChatAgent.__init__(self, system_prompt=system_prompt)
        logger.info("Agent initialization complete")
        
    def run(self):
        """Override run to add tracing"""
        logger.info("Agent starting up - PID: %d", os.getpid())
        logger.debug("Agent DDS Domain ID from env: %s", os.getenv('ROS_DOMAIN_ID', 'Not Set'))
        logger.debug("Agent service name: %s", self.service_name)
        
        try:
            logger.info("Announcing agent presence")
            self.app.announce_self()
            
            # Now that we're initialized, we can log the participant info
            if hasattr(self.app, 'participant'):
                logger.debug("Agent DDS participant initialized")
                logger.debug("Agent DDS domain ID: %d", self.app.participant.domain_id)
                # Log any other participant info we might need later
            else:
                logger.warning("Agent participant not initialized")
            
            logger.info("Starting agent main loop")
            while True:
                time.sleep(0.1)  # Small sleep to prevent busy loop
                
        except Exception as e:
            logger.error("Error in agent run loop: %s", str(e), exc_info=True)
        finally:
            logger.info("Agent shutting down")
            
    def process_request(self, request: Any) -> Dict[str, Any]:
        """Process chat request using Claude"""
        message = request["message"]
        response, status = self.generate_response(message, "default")
        return {
            "message": response,
            "status": status
        }

def main():
    """Main function with enhanced tracing"""
    logger.info("Agent main() starting")
    try:
        agent = TracingAnthropicChatAgent(
            system_prompt="You are a helpful AI assistant."
        )
        logger.info("Created agent instance successfully")
        agent.run()
    except Exception as e:
        logger.error("Fatal error in main: %s", str(e), exc_info=True)
    finally:
        logger.info("Agent main() ending")

if __name__ == "__main__":
    main()

```

## interface_cli.py

**Author:** Jason

```python
#!/usr/bin/env python3

import asyncio
import logging
import argparse
from genesis_lib.interface import GenesisInterface
from genesis_lib.datamodel import FunctionRequest, FunctionReply

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("interface_cli")


SERVICE_NAME = "SimpleInterface"

class SimpleInterface(GenesisInterface):
    def __init__(self):
        super().__init__("SimpleInterface", SERVICE_NAME)
        logger.info("SimpleInterface initialized")
    
    async def send_message(self, message: str) -> str:
        """
        Send a message to the agent and get the response
        """
        request = FunctionRequest(
            function_name="process_request",
            parameters={"message": message}
        )
        
        try:
            reply = await self.send_request(request)
            if isinstance(reply, FunctionReply) and reply.success:
                return reply.result
            else:
                return f"Error: {reply.error_message if reply else 'Unknown error'}"
        except Exception as e:
            return f"Error sending request: {str(e)}"

async def main():
    parser = argparse.ArgumentParser(description='Simple Genesis Interface CLI')
    parser.add_argument('--message', '-m', type=str, help='Message to send to the agent')
    args = parser.parse_args()
    
    try:
        # Create interface
        interface = SimpleInterface()
        
        # Wait for agent to be available
        if not await interface.wait_for_agent():
            logger.error("Failed to discover agent")
            return 1
        
        if args.message:
            # Send message and get response
            response = await interface.send_message(args.message)
            print(f"Response: {response}")
        else:
            # Interactive mode
            print("Entering interactive mode (type 'exit' to quit)")
            while True:
                message = input("> ")
                if message.lower() == 'exit':
                    break
                response = await interface.send_message(message)
                print(f"Response: {response}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error in interface: {str(e)}")
        return 1
    finally:
        if 'interface' in locals():
            await interface.close()

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code) 
```

## spy_transient.xml

**Author:** Jason

```xml
<!-- spy_transient.xml -->
<dds>
  <qos_library name="SpyLib">
    <qos_profile name="TransientReliable" is_default_qos="true">
      <datareader_qos>
        <durability>
          <kind>TRANSIENT_LOCAL_DURABILITY_QOS</kind>
        </durability>
        <reliability>
          <kind>RELIABLE_RELIABILITY_QOS</kind>
        </reliability>
        <history>
          <kind>KEEP_LAST_HISTORY_QOS</kind>
          <depth>32</depth> <!-- enough for your 1-shot announce -->
        </history>
      </datareader_qos>
    </qos_profile>
  </qos_library>
</dds>
```

## test_functions/calculator_client.py

**Author:** Jason

```python
#!/usr/bin/env python3

import logging
import asyncio
import json
from typing import Dict, Any
from genesis_lib.generic_function_client import GenericFunctionClient

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("calculator_client")

class CalculatorClient:
    """
    Calculator client for testing purposes.
    This client has knowledge of calculator functions for testing,
    but uses the generic client under the hood.
    """
    
    def __init__(self):
        """Initialize the calculator client"""
        logger.info("Initializing CalculatorClient")
        
        # Use the generic client under the hood
        self.generic_client = GenericFunctionClient()
        
        # Cache for discovered function IDs
        self.function_ids = {}
    
    async def _ensure_initialized(self):
        """Ensure the client is initialized and functions are discovered"""
        if not self.function_ids:
            await self.generic_client.discover_functions()
            
            # Cache function IDs for calculator operations
            functions = self.generic_client.list_available_functions()
            for func in functions:
                name = func["name"]
                self.function_ids[name] = func["function_id"]
            
            logger.info(f"Discovered calculator functions: {list(self.function_ids.keys())}")
    
    async def add(self, x: float, y: float) -> Dict[str, Any]:
        """
        Add two numbers
        
        Args:
            x: First number to add
            y: Second number to add
            
        Returns:
            Dictionary containing input parameters and result
        """
        await self._ensure_initialized()
        
        if "add" not in self.function_ids:
            raise RuntimeError("Add function not available")
        
        logger.debug(f"CLIENT: Calling add with x={x}, y={y}")
        return await self.generic_client.call_function(self.function_ids["add"], x=x, y=y)
    
    async def subtract(self, x: float, y: float) -> Dict[str, Any]:
        """
        Subtract two numbers
        
        Args:
            x: Number to subtract from
            y: Number to subtract
            
        Returns:
            Dictionary containing input parameters and result
        """
        await self._ensure_initialized()
        
        if "subtract" not in self.function_ids:
            raise RuntimeError("Subtract function not available")
        
        logger.debug(f"CLIENT: Calling subtract with x={x}, y={y}")
        return await self.generic_client.call_function(self.function_ids["subtract"], x=x, y=y)
    
    async def multiply(self, x: float, y: float) -> Dict[str, Any]:
        """
        Multiply two numbers
        
        Args:
            x: First number to multiply
            y: Second number to multiply
            
        Returns:
            Dictionary containing input parameters and result
        """
        await self._ensure_initialized()
        
        if "multiply" not in self.function_ids:
            raise RuntimeError("Multiply function not available")
        
        logger.debug(f"CLIENT: Calling multiply with x={x}, y={y}")
        return await self.generic_client.call_function(self.function_ids["multiply"], x=x, y=y)
    
    async def divide(self, x: float, y: float) -> Dict[str, Any]:
        """
        Divide two numbers
        
        Args:
            x: Number to divide
            y: Number to divide by
            
        Returns:
            Dictionary containing input parameters and result
        """
        await self._ensure_initialized()
        
        if "divide" not in self.function_ids:
            raise RuntimeError("Divide function not available")
        
        if y == 0:
            raise ValueError("Cannot divide by zero")
        
        logger.debug(f"CLIENT: Calling divide with x={x}, y={y}")
        return await self.generic_client.call_function(self.function_ids["divide"], x=x, y=y)
    
    def close(self):
        """Close the client and release resources"""
        logger.info("Closing calculator client")
        self.generic_client.close()

async def run_calculator_test():
    """Run a test of the calculator functions"""
    client = CalculatorClient()
    
    try:
        # Test add
        try:
            result = await client.add(10, 5)
            print(f"\nFunction 'add({{'x': 10, 'y': 5}})' returned: {result}")
            print("✅ Test passed.")
            logger.info("Test passed")
        except Exception as e:
            print(f"❌ Error in add test: {str(e)}")
            logger.error(f"add test failed: {str(e)}", exc_info=True)
        
        # Test subtract
        try:
            result = await client.subtract(10, 5)
            print(f"\nFunction 'subtract({{'x': 10, 'y': 5}})' returned: {result}")
            print("✅ Test passed.")
            logger.info("Test passed")
        except Exception as e:
            print(f"❌ Error in subtract test: {str(e)}")
            logger.error(f"subtract test failed: {str(e)}", exc_info=True)
        
        # Test multiply
        try:
            result = await client.multiply(10, 5)
            print(f"\nFunction 'multiply({{'x': 10, 'y': 5}})' returned: {result}")
            print("✅ Test passed.")
            logger.info("Test passed")
        except Exception as e:
            print(f"❌ Error in multiply test: {str(e)}")
            logger.error(f"multiply test failed: {str(e)}", exc_info=True)
        
        # Test divide
        try:
            result = await client.divide(10, 2)
            print(f"\nFunction 'divide({{'x': 10, 'y': 2}})' returned: {result}")
            print("✅ Test passed.")
            logger.info("Test passed")
        except Exception as e:
            print(f"❌ Error in divide test: {str(e)}")
            logger.error(f"divide test failed: {str(e)}", exc_info=True)
        
        # Test error cases
        print("\nTesting error cases:")
        
        # Test division by zero
        try:
            await client.divide(10, 0)
            print("❌ Division by zero should have raised an error")
            logger.error("Division by zero did not raise an error")
        except ValueError as e:
            print(f"✅ Properly handled error: {str(e)}")
            logger.info(f"Test passed - properly handled error: {str(e)}")
        
        # Test type errors
        print("\nTesting type errors:")
        
        # Test with string instead of number
        try:
            # We need to bypass the client's validation to test the service's validation
            function_id = client.function_ids.get("add")
            if function_id:
                await client.generic_client.call_function(function_id, x="abc", y=5)
                print("❌ String parameter should have raised an error")
                logger.error("String parameter did not raise an error")
            else:
                print("⚠️ Skipping type error test - add function not found")
        except Exception as e:
            print(f"✅ Properly handled type error: {str(e)}")
            logger.info(f"Test passed - properly handled type error: {str(e)}")
        
        # Test with invalid JSON
        try:
            # We need to bypass the client's validation to test the service's validation
            function_id = client.function_ids.get("multiply")
            if function_id:
                # Create a custom client to send invalid JSON
                from genesis_lib.rpc_client import GenesisRPCClient
                custom_client = GenesisRPCClient(service_name="CalculatorService")
                
                # Send a request with invalid JSON
                from genesis_lib.datamodel import FunctionCall
                request = custom_client.get_request_type()(
                    id="test_invalid_json",
                    type="function",
                    function=FunctionCall(
                        name="multiply",
                        arguments="this is not valid json"
                    )
                )
                
                request_id = custom_client.requester.send_request(request)
                replies = custom_client.requester.receive_replies(
                    max_wait=custom_client.timeout,
                    related_request_id=request_id
                )
                
                if replies and not replies[0].data.success:
                    print(f"✅ Properly handled invalid JSON: {replies[0].data.error_message}")
                    logger.info(f"Test passed - properly handled invalid JSON: {replies[0].data.error_message}")
                else:
                    print("❌ Invalid JSON should have raised an error")
                    logger.error("Invalid JSON did not raise an error")
                
                custom_client.close()
            else:
                print("⚠️ Skipping invalid JSON test - multiply function not found")
        except Exception as e:
            print(f"✅ Properly handled error: {str(e)}")
            logger.info(f"Test passed - properly handled error: {str(e)}")
            
    except Exception as e:
        logger.error(f"Unexpected error during test execution: {str(e)}", exc_info=True)
    finally:
        client.close()

def main():
    """Main entry point"""
    logger.info("CLIENT: Starting calculator client")
    try:
        asyncio.run(run_calculator_test())
    except KeyboardInterrupt:
        logger.info("CLIENT: Shutting down calculator client")
    except Exception as e:
        logger.error(f"CLIENT: Error in main: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 
```

## test_functions/text_processor_client.py

**Author:** Jason

```python
#!/usr/bin/env python3

import logging
import asyncio
from genesis_lib.rpc_client import GenesisRPCClient
from typing import Dict, Any, List
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("text_processor_client")

class TextProcessorClient(GenesisRPCClient):
    """Client for the text processor service"""
    
    def __init__(self):
        """Initialize the text processor client"""
        super().__init__(service_name="TextProcessorService")
        logger.info("Initializing TextProcessorClient")
        
        # Add text processor specific validation patterns
        self.validation_patterns.update({
            "text": {
                "min_length": 1,
                "max_length": None,  # No maximum length limit
                "pattern": None  # No pattern restriction
            },
            "case": {
                "type": "enum",
                "values": ["upper", "lower", "title"]
            },
            "operation": {
                "type": "enum",
                "values": ["repeat", "pad"]
            },
            "count": {
                "type": "number",
                "minimum": 0,
                "maximum": 1000
            }
        })
    
    async def wait_for_service(self):
        """Wait for the service to be discovered and log available functions"""
        logger.info("Waiting for TextProcessorService to be discovered...")
        await super().wait_for_service()
        
        # Log discovered functions
        logger.info("Service discovered! Checking available functions...")
        try:
            # Try to call each expected function with minimal valid parameters
            expected_functions = {
                "transform_case": {"text": "test", "case": "upper"},
                "analyze_text": {"text": "test"},
                "generate_text": {"text": "test", "operation": "repeat", "count": 1},
                "count_words": {"text": "test"}
            }
            
            for func, params in expected_functions.items():
                try:
                    logger.info(f"Checking function: {func}")
                    # Try a quick call with minimal parameters
                    await self.call_function(func, **params)
                    logger.info(f"✓ Function {func} is available")
                except Exception as e:
                    logger.warning(f"✗ Function {func} is NOT available: {str(e)}")
        except Exception as e:
            logger.error(f"Error checking functions: {str(e)}")
        
        logger.info("Service discovered successfully!")
    
    def validate_enum_value(self, value: str, pattern_type: str) -> None:
        """
        Validate that a value is one of the allowed enum values
        
        Args:
            value: Value to validate
            pattern_type: Type of pattern to use (e.g., 'case', 'operation')
            
        Raises:
            ValueError: If validation fails
        """
        if pattern_type not in self.validation_patterns:
            raise ValueError(f"Unknown pattern type: {pattern_type}")
            
        pattern = self.validation_patterns[pattern_type]
        if pattern.get("type") != "enum":
            raise ValueError(f"Pattern type {pattern_type} is not an enum")
            
        if value not in pattern["values"]:
            raise ValueError(f"Value must be one of: {', '.join(pattern['values'])}")
    
    async def transform_case(self, text: str, case: str) -> Dict[str, Any]:
        """
        Transform text to specified case
        
        Args:
            text: Text to transform
            case: Target case (upper, lower, or title)
            
        Returns:
            Dictionary containing input parameters and transformed result
            
        Raises:
            ValueError: If text is empty or case is not supported
        """
        logger.debug(f"CLIENT: Calling transform_case with text='{text}', case='{case}'")
        
        # Validate inputs
        self.validate_text(text)
        self.validate_enum_value(case, pattern_type="case")
        
        return await self.call_function_with_validation("transform_case", text=text, case=case)
    
    async def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analyze text and return detailed statistics
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary containing input parameters and various statistics including:
            - total_length: Total number of characters
            - alpha_count: Number of alphabetic characters
            - digit_count: Number of numeric digits
            - space_count: Number of whitespace characters
            - punctuation_count: Number of punctuation marks
            - word_count: Number of words
            - line_count: Number of lines
            - uppercase_count: Number of uppercase letters
            - lowercase_count: Number of lowercase letters
            
        Raises:
            ValueError: If text is empty
        """
        logger.debug(f"CLIENT: Calling analyze_text with text='{text}'")
        
        # Validate input
        self.validate_text(text)
        
        return await self.call_function_with_validation("analyze_text", text=text)
    
    async def generate_text(self, text: str, operation: str, count: int) -> Dict[str, Any]:
        """
        Generate text based on input text and specified operation
        
        Args:
            text: Base text for generation
            operation: Operation to perform (repeat or pad)
            count: Number of repetitions or padding length (0-1000)
            
        Returns:
            Dictionary containing:
            - text: Original input text
            - operation: Operation performed
            - count: Count parameter used
            - result: Generated text
            - result_length: Length of generated text
            
        Raises:
            ValueError: If text is empty, operation is invalid, or count is out of range
        """
        logger.debug(f"CLIENT: Calling generate_text with text='{text}', operation='{operation}', count={count}")
        
        # Validate inputs
        self.validate_text(text)
        self.validate_enum_value(operation, pattern_type="operation")
        self.validate_numeric(count, pattern_type="count")
        
        return await self.call_function_with_validation("generate_text", text=text, operation=operation, count=count)

async def run_text_processor_test():
    """Run a test of the text processor functions"""
    client = TextProcessorClient()
    
    try:
        # Wait for service discovery
        logger.info("Starting service discovery...")
        await client.wait_for_service()
        
        test_text = "Hello, World! 123"
        
        # Test transform_case
        try:
            logger.info("Testing transform_case function...")
            result = await client.transform_case(test_text, "upper")
            print(f"\nFunction 'transform_case({{'text': '{test_text}', 'case': 'upper'}})' returned: {result}")
            print("✅ Test passed.")
            logger.info("Test passed")
        except Exception as e:
            print(f"❌ Error in transform_case test: {str(e)}")
            logger.error(f"transform_case test failed: {str(e)}", exc_info=True)
        
        # Test analyze_text
        try:
            logger.info("Testing analyze_text function...")
            result = await client.analyze_text(test_text)
            print(f"\nFunction 'analyze_text({{'text': '{test_text}'}})' returned: {result}")
            print("✅ Test passed.")
            logger.info("Test passed")
        except Exception as e:
            print(f"❌ Error in analyze_text test: {str(e)}")
            logger.error(f"analyze_text test failed: {str(e)}", exc_info=True)
        
        # Test generate_text
        try:
            logger.info("Testing generate_text function...")
            result = await client.generate_text(test_text, "repeat", 2)
            print(f"\nFunction 'generate_text({{'text': '{test_text}', 'operation': 'repeat', 'count': 2}})' returned: {result}")
            print("✅ Test passed.")
            logger.info("Test passed")
        except Exception as e:
            print(f"❌ Error in generate_text test: {str(e)}")
            logger.error(f"generate_text test failed: {str(e)}", exc_info=True)
        
        # Test error cases
        print("\nTesting error cases:")
        
        # Test empty text
        try:
            logger.info("Testing empty text error case...")
            await client.transform_case("", "upper")
            print("❌ Empty text should have raised an error")
            logger.error("Empty text did not raise an error")
        except ValueError as e:
            print(f"✅ Properly handled error: {str(e)}")
            logger.info(f"Test passed - properly handled error: {str(e)}")
        
        # Test invalid case
        try:
            logger.info("Testing invalid case error case...")
            await client.transform_case(test_text, "invalid_case")
            print("❌ Invalid case should have raised an error")
            logger.error("Invalid case did not raise an error")
        except ValueError as e:
            print(f"✅ Properly handled error: {str(e)}")
            logger.info(f"Test passed - properly handled error: {str(e)}")
        
        # Test invalid operation
        try:
            logger.info("Testing invalid operation error case...")
            await client.generate_text(test_text, "invalid_operation", 1)
            print("❌ Invalid operation should have raised an error")
            logger.error("Invalid operation did not raise an error")
        except ValueError as e:
            print(f"✅ Properly handled error: {str(e)}")
            logger.info(f"Test passed - properly handled error: {str(e)}")
        
        # Test count out of range
        try:
            logger.info("Testing count out of range error case...")
            await client.generate_text(test_text, "repeat", 1001)
            print("❌ Count > 1000 should have raised an error")
            logger.error("Count > 1000 did not raise an error")
        except ValueError as e:
            print(f"✅ Properly handled error: {str(e)}")
            logger.info(f"Test passed - properly handled error: {str(e)}")
        
        # Test unknown function
        try:
            logger.info("Testing unknown function error case...")
            await client.call_function("unknown_function", text="test")
            print("❌ Unknown function should have raised an error")
            logger.error("Unknown function did not raise an error")
        except RuntimeError as e:
            print(f"✅ Properly handled error: {str(e)}")
            logger.info(f"Test passed - properly handled error: {str(e)}")
            
    except Exception as e:
        logger.error(f"Unexpected error during test execution: {str(e)}", exc_info=True)
    finally:
        client.close()

def main():
    """Main entry point"""
    logger.info("CLIENT: Starting text processor client")
    try:
        asyncio.run(run_text_processor_test())
    except KeyboardInterrupt:
        logger.info("CLIENT: Shutting down text processor client")
    except Exception as e:
        logger.error(f"CLIENT: Error in main: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 
```

## test_functions/text_processor_service.py

**Author:** Jason

```python
#!/usr/bin/env python3

import logging
import asyncio
from typing import Dict, Any, List
import json
from pydantic import BaseModel, Field
from genesis_lib.enhanced_service_base import EnhancedServiceBase
from genesis_lib.decorators import genesis_function

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("text_processor_service")

# Pydantic models for function arguments
class TextArgs(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000, description="Text to process")

class TransformCaseArgs(TextArgs):
    case: str = Field(..., enum=["upper", "lower", "title"], description="Case to transform text to")

class GenerateTextArgs(TextArgs):
    operation: str = Field(..., enum=["repeat", "reverse"], description="Operation to perform on text")
    count: int = Field(..., ge=1, le=100, description="Number of times to perform operation")

class TextProcessorService(EnhancedServiceBase):
    """Implementation of the text processor service using Genesis RPC framework"""
    
    def __init__(self):
        """Initialize the text processor service"""
        super().__init__(service_name="TextProcessorService", capabilities=["text_processor", "text_manipulation"])
        logger.info("TextProcessorService initialized")
        # Everything is now auto-registered; just advertise
        self._advertise_functions()
        logger.info("Functions advertised")

    async def cleanup(self):
        """Clean up resources before shutdown"""
        logger.info("Cleaning up TextProcessorService resources...")
        await super().cleanup()
        logger.info("TextProcessorService cleanup complete")

    def close(self):
        """Clean up resources"""
        logger.info("Closing TextProcessorService...")
        super().close()
        logger.info("TextProcessorService closed")

    @genesis_function(description="Count the number of words in a text",
                     model=TextArgs,
                     operation_type="analysis")
    async def count_words(self, text: str, request_info=None) -> Dict[str, Any]:
        """Count the number of words in a text."""
        logger.info(f"Received count_words request: text='{text}'")
        self.publish_function_call_event("count_words", {"text": text}, request_info)
        
        # Split text into words and count
        words = text.split()
        word_count = len(words)
        
        result = {
            "text": text,
            "word_count": word_count,
            "words": words
        }
        
        self.publish_function_result_event("count_words", result, request_info)
        logger.info(f"Count words result: {result}")
        return result

    @genesis_function(description="Transform text to specified case",
                     model=TransformCaseArgs,
                     operation_type="transformation")
    async def transform_case(self, text: str, case: str, request_info=None) -> Dict[str, Any]:
        """Transform text to specified case."""
        logger.info(f"Received transform_case request: text='{text}', case={case}")
        self.publish_function_call_event("transform_case", {"text": text, "case": case}, request_info)
        
        # Transform text based on case
        if case == "upper":
            transformed = text.upper()
        elif case == "lower":
            transformed = text.lower()
        elif case == "title":
            transformed = text.title()
        else:
            raise ValueError(f"Invalid case: {case}")
        
        result = {
            "original_text": text,
            "transformed_text": transformed,
            "case": case
        }
        
        self.publish_function_result_event("transform_case", result, request_info)
        logger.info(f"Transform case result: {result}")
        return result

    @genesis_function(description="Analyze text for various metrics",
                     model=TextArgs,
                     operation_type="analysis")
    async def analyze_text(self, text: str, request_info=None) -> Dict[str, Any]:
        """Analyze text for various metrics."""
        logger.info(f"Received analyze_text request: text='{text}'")
        self.publish_function_call_event("analyze_text", {"text": text}, request_info)
        
        # Basic text analysis
        words = text.split()
        sentences = text.split('.')
        characters = len(text)
        word_count = len(words)
        sentence_count = len([s for s in sentences if s.strip()])
        
        result = {
            "text": text,
            "character_count": characters,
            "word_count": word_count,
            "sentence_count": sentence_count,
            "average_word_length": sum(len(word) for word in words) / word_count if word_count > 0 else 0
        }
        
        self.publish_function_result_event("analyze_text", result, request_info)
        logger.info(f"Analyze text result: {result}")
        return result

    @genesis_function(description="Generate text based on operation and count",
                     model=GenerateTextArgs,
                     operation_type="generation")
    async def generate_text(self, text: str, operation: str, count: int, request_info=None) -> Dict[str, Any]:
        """Generate text based on operation and count."""
        logger.info(f"Received generate_text request: text='{text}', operation={operation}, count={count}")
        self.publish_function_call_event("generate_text", {"text": text, "operation": operation, "count": count}, request_info)
        
        # Generate text based on operation
        if operation == "repeat":
            generated = (text + " ") * count
        elif operation == "reverse":
            generated = text[::-1] * count
        else:
            raise ValueError(f"Invalid operation: {operation}")
        
        result = {
            "original_text": text,
            "generated_text": generated.strip(),
            "operation": operation,
            "count": count
        }
        
        self.publish_function_result_event("generate_text", result, request_info)
        logger.info(f"Generate text result: {result}")
        return result

def main():
    """Main entry point for the text processor service."""
    logger.info("Starting text processor service")
    try:
        service = TextProcessorService()
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("Shutting down text processor service")
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)
    finally:
        # Ensure cleanup is called
        if 'service' in locals():
            asyncio.run(service.cleanup())

if __name__ == "__main__":
    main() 
```

## test_functions/drone_function_service.py

**Author:** Jason

```python
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

from genesis_lib.enhanced_service_base import EnhancedServiceBase
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


class DroneFunctionService(EnhancedServiceBase):
    """Service that provides drone control functions for Genesis"""
    
    def __init__(self):
        """Initialize the drone function service"""
        logger.info("===== SERVICE INIT START ====")
        
        # Initialize the enhanced base class with service name and capabilities
        super().__init__(
            service_name="DroneFunctionService",
            capabilities=["DroneFunctionService", "drone", "control"]
        )
        logger.debug("EnhancedServiceBase initialized")
        
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
        logger.info("EnhancedServiceBase closed.")
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
```

## test_functions/letter_counter_service.py

**Author:** Jason

```python
#!/usr/bin/env python3

import logging
import asyncio
import json
from typing import Dict, Any, List
import re
from genesis_lib.enhanced_service_base import EnhancedServiceBase
import rti.connextdds as dds
from genesis_lib.utils import get_datamodel_path

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("letter_counter_service")

class LetterCounterService(EnhancedServiceBase):
    """Implementation of the letter counter service using Genesis RPC framework"""
    
    def __init__(self):
        """Initialize the letter counter service"""
        # Initialize the enhanced base class with service name and capabilities
        super().__init__(
            service_name="LetterCounterService",
            capabilities=["letter_counter", "text_analysis"]
        )
        
        # Get types from XML for monitoring
        config_path = get_datamodel_path()
        self.type_provider = dds.QosProvider(config_path)
        self.component_lifecycle_type = self.type_provider.type("genesis_lib", "ComponentLifecycleEvent")
        
        # Get common schemas
        text_schema = self.get_common_schema("text")
        letter_schema = self.get_common_schema("letter")
        
        # Register letter counter functions with OpenAI-style schemas
        self.register_enhanced_function(
            self.count_letter,
            "Count occurrences of a letter in text",
            {
                "type": "object",
                "properties": {
                    "text": text_schema.copy(),
                    "letter": letter_schema.copy()
                },
                "required": ["text", "letter"],
                "additionalProperties": False
            },
            operation_type="analysis",
            common_patterns={
                "text": {"type": "text", "min_length": 1},
                "letter": {"type": "letter"}
            }
        )
        
        self.register_enhanced_function(
            self.count_multiple_letters,
            "Count occurrences of multiple letters in text",
            {
                "type": "object",
                "properties": {
                    "text": text_schema.copy(),
                    "letters": {
                        "type": "array",
                        "items": letter_schema.copy(),
                        "minItems": 1,
                        "maxItems": 26,
                        "description": "Letters to count"
                    }
                },
                "required": ["text", "letters"],
                "additionalProperties": False
            },
            operation_type="analysis",
            common_patterns={
                "text": {"type": "text", "min_length": 1}
            }
        )
        
        self.register_enhanced_function(
            self.get_letter_frequency,
            "Get frequency distribution of letters in text",
            {
                "type": "object",
                "properties": {
                    "text": text_schema.copy()
                },
                "required": ["text"],
                "additionalProperties": False
            },
            operation_type="analysis",
            common_patterns={
                "text": {"type": "text", "min_length": 1}
            }
        )
        
        # Advertise functions
        self._advertise_functions()
    
    def count_letter(self, text: str, letter: str, request_info=None) -> Dict[str, Any]:
        """
        Count occurrences of a letter in text
        
        Args:
            text: Text to analyze
            letter: Letter to count
            request_info: Request information containing client ID
            
        Returns:
            Dictionary containing input parameters and count
            
        Raises:
            ValueError: If text is empty or letter is not a single alphabetic character
        """
        try:
            # Publish function call event
            self.publish_function_call_event(
                "count_letter",
                {"text": text, "letter": letter},
                request_info
            )
            
            logger.debug(f"SERVICE: count_letter called with text='{text}', letter='{letter}'")
            
            # Validate inputs
            self.validate_text_input(text, min_length=1)
            self.validate_text_input(letter, min_length=1, max_length=1, pattern="^[a-zA-Z]$")
            
            # Count occurrences (case insensitive)
            count = text.lower().count(letter.lower())
            
            # Log the result
            logger.info(f"==== LETTER COUNTER SERVICE: count_letter('{text}', '{letter}') = {count} ====")
            
            # Publish function result event
            self.publish_function_result_event(
                "count_letter",
                {"result": count},
                request_info
            )
            
            return self.format_response({"text": text, "letter": letter}, count)
        except Exception as e:
            # Publish function error event
            self.publish_function_error_event(
                "count_letter",
                e,
                request_info
            )
            raise
    
    def count_multiple_letters(self, text: str, letters: List[str], request_info=None) -> Dict[str, Any]:
        """
        Count occurrences of multiple letters in text
        
        Args:
            text: Text to analyze
            letters: List of letters to count
            request_info: Request information containing client ID
            
        Returns:
            Dictionary containing input parameters and counts
            
        Raises:
            ValueError: If text is empty or any letter is invalid
        """
        try:
            # Publish function call event
            self.publish_function_call_event(
                "count_multiple_letters",
                {"text": text, "letters": letters},
                request_info
            )
            
            logger.debug(f"SERVICE: count_multiple_letters called with text='{text}', letters={letters}")
            
            # Validate inputs
            self.validate_text_input(text, min_length=1)
            if not letters:
                raise ValueError("Letters list cannot be empty")
            if len(letters) > 26:
                raise ValueError("Cannot count more than 26 letters")
            
            # Validate each letter
            for letter in letters:
                self.validate_text_input(letter, min_length=1, max_length=1, pattern="^[a-zA-Z]$")
            
            # Count occurrences (case insensitive)
            counts = {}
            text_lower = text.lower()
            for letter in letters:
                counts[letter] = text_lower.count(letter.lower())
            
            # Publish function result event
            self.publish_function_result_event(
                "count_multiple_letters",
                {"result": counts},
                request_info
            )
            
            return self.format_response({"text": text, "letters": letters}, counts)
        except Exception as e:
            # Publish function error event
            self.publish_function_error_event(
                "count_multiple_letters",
                e,
                request_info
            )
            raise
    
    def get_letter_frequency(self, text: str, request_info=None) -> Dict[str, Any]:
        """
        Get frequency distribution of letters in text
        
        Args:
            text: Text to analyze
            request_info: Request information containing client ID
            
        Returns:
            Dictionary containing input parameters, total count, and frequency distribution
            
        Raises:
            ValueError: If text is empty
        """
        try:
            # Publish function call event
            self.publish_function_call_event(
                "get_letter_frequency",
                {"text": text},
                request_info
            )
            
            logger.debug(f"SERVICE: get_letter_frequency called with text='{text}'")
            
            # Validate input
            self.validate_text_input(text, min_length=1)
            
            # Count letter frequencies (case insensitive)
            text_lower = text.lower()
            letter_count = {}
            total_letters = 0
            
            for char in text_lower:
                if char.isalpha():
                    letter_count[char] = letter_count.get(char, 0) + 1
                    total_letters += 1
            
            # Calculate percentages
            frequencies = {}
            for letter, count in letter_count.items():
                frequencies[letter] = {
                    "count": count,
                    "percentage": round((count / total_letters) * 100, 1) if total_letters > 0 else 0
                }
            
            # Publish function result event
            self.publish_function_result_event(
                "get_letter_frequency",
                {"result": frequencies},
                request_info
            )
            
            return self.format_response({"text": text}, {"total_letters": total_letters, "frequencies": frequencies})
        except Exception as e:
            # Publish function error event
            self.publish_function_error_event(
                "get_letter_frequency",
                e,
                request_info
            )
            raise

def main():
    """Main entry point"""
    logger.info("SERVICE: Starting letter counter service")
    try:
        # Create and run the letter counter service
        service = LetterCounterService()
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("SERVICE: Shutting down letter counter service")
    except Exception as e:
        logger.error(f"SERVICE: Error in main: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 
```

## test_functions/test_text_processor_close.py

**Author:** Jason

```python
#!/usr/bin/env python3

import logging
import asyncio
from text_processor_service import TextProcessorService

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("text_processor_test")

async def test_service_lifecycle():
    """Test the service lifecycle including proper cleanup"""
    logger.info("Starting service lifecycle test...")
    
    # Create and start the service
    service = TextProcessorService()
    
    try:
        # Start the service in a background task
        service_task = asyncio.create_task(service.run())
        
        # Wait a bit to let the service initialize
        await asyncio.sleep(2)
        
        # Test that the service is running by checking if functions are advertised
        assert len(service.functions) > 0, "Service should have registered functions"
        logger.info(f"Service has {len(service.functions)} registered functions")
        
        # Explicitly close the service
        logger.info("Testing explicit service close...")
        service.close()
        
        # Wait for the service task to complete
        await service_task
        
        logger.info("Service lifecycle test completed successfully")
        
    except Exception as e:
        logger.error(f"Error during service lifecycle test: {str(e)}", exc_info=True)
        raise
    finally:
        # Ensure service is closed even if test fails
        if 'service' in locals():
            service.close()

def main():
    """Main entry point"""
    logger.info("Starting text processor service lifecycle test")
    try:
        asyncio.run(test_service_lifecycle())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)
    finally:
        logger.info("Test completed")

if __name__ == "__main__":
    main() 
```

## test_functions/test_all_services.py

**Author:** Jason

```python
#!/usr/bin/env python3

import asyncio
import logging
import json
import time
import sys
import os
import random
from typing import Dict, Any, List

# Import the generic function client from genesis_lib
from genesis_lib.generic_function_client import GenericFunctionClient

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Set default level to WARNING to reduce verbosity
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_all_services")
logger.setLevel(logging.INFO)  # Keep INFO level for test progress and results

class AllServicesTest:
    """Test class for testing all Genesis services together"""
    
    def __init__(self):
        """Initialize the test class"""
        logger.info("Initializing test for all services")
        self.client = GenericFunctionClient()
        self.test_results = []
    
    async def discover_functions(self):
        """Discover all available functions"""
        logger.info("Discovering functions...")
        await self.client.discover_functions(timeout_seconds=15)
        functions = self.client.list_available_functions()
        
        # Group functions by service
        services = {}
        for func in functions:
            service_name = func.get("service_name", "UnknownService")
            if service_name not in services:
                services[service_name] = []
            services[service_name].append(func)
        
        # Print discovered functions by service
        logger.info(f"Discovered {len(functions)} functions across {len(services)} services")
        for service_name, funcs in services.items():
            logger.info(f"Service: {service_name} - {len(funcs)} functions")
            for func in funcs:
                logger.info(f"  - {func['name']}: {func['description']}")
        
        return functions
    
    async def test_calculator_service(self):
        """Test the calculator service"""
        logger.info("===== Testing Calculator Service =====")
        
        # Test add function
        try:
            logger.info("Testing add function...")
            result = await self.client.call_function_by_name("add", x=10, y=5)
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "CalculatorService",
                "function": "add",
                "args": {"x": 10, "y": 5},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing add function: {str(e)}")
            self.test_results.append({
                "service": "CalculatorService",
                "function": "add",
                "args": {"x": 10, "y": 5},
                "error": str(e),
                "success": False
            })
        
        # Test subtract function
        try:
            logger.info("Testing subtract function...")
            result = await self.client.call_function_by_name("subtract", x=10, y=5)
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "CalculatorService",
                "function": "subtract",
                "args": {"x": 10, "y": 5},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing subtract function: {str(e)}")
            self.test_results.append({
                "service": "CalculatorService",
                "function": "subtract",
                "args": {"x": 10, "y": 5},
                "error": str(e),
                "success": False
            })
        
        # Test multiply function
        try:
            logger.info("Testing multiply function...")
            result = await self.client.call_function_by_name("multiply", x=10, y=5)
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "CalculatorService",
                "function": "multiply",
                "args": {"x": 10, "y": 5},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing multiply function: {str(e)}")
            self.test_results.append({
                "service": "CalculatorService",
                "function": "multiply",
                "args": {"x": 10, "y": 5},
                "error": str(e),
                "success": False
            })
        
        # Test divide function
        try:
            logger.info("Testing divide function...")
            result = await self.client.call_function_by_name("divide", x=10, y=5)
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "CalculatorService",
                "function": "divide",
                "args": {"x": 10, "y": 5},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing divide function: {str(e)}")
            self.test_results.append({
                "service": "CalculatorService",
                "function": "divide",
                "args": {"x": 10, "y": 5},
                "error": str(e),
                "success": False
            })
    
    async def test_calculator_performance(self):
        """Test calculator service performance and accuracy with rapid requests"""
        logger.info("===== Testing Calculator Service Performance =====")
        
        operations = ["add", "subtract", "multiply", "divide"]
        total_tests = 100
        successful_tests = 0
        total_time = 0
        
        logger.info(f"Running {total_tests} rapid calculator operations...")
        
        for i in range(total_tests):
            # Generate random numbers (avoiding 0 for division)
            x = random.uniform(1, 100)
            y = random.uniform(1, 100)
            
            # Select random operation
            operation = random.choice(operations)
            
            # Calculate expected result locally
            if operation == "add":
                expected = x + y
            elif operation == "subtract":
                expected = x - y
            elif operation == "multiply":
                expected = x * y
            else:  # divide
                expected = x / y
            
            try:
                start_time = time.time()
                result_dict = await self.client.call_function_by_name(operation, x=x, y=y)
                end_time = time.time()
                
                # Calculate request time
                request_time = end_time - start_time
                total_time += request_time
                
                # Extract the numeric result from the dictionary response
                if isinstance(result_dict, dict):
                    result = result_dict.get('result', None)
                    if result is None:
                        logger.error(f"Test {i+1}: No 'result' field in response: {result_dict}")
                        continue
                else:
                    result = result_dict  # In case the service returns the number directly
                
                # Verify result (using small epsilon for floating point comparison)
                if abs(float(result) - expected) < 1e-10:
                    successful_tests += 1
                else:
                    logger.error(f"Test {i+1}: Result mismatch for {operation}({x}, {y})")
                    logger.error(f"Expected: {expected}, Got: {result}")
                    logger.error(f"Full response: {result_dict}")
                
                # Log progress every 10 tests
                if (i + 1) % 10 == 0:
                    logger.info(f"Completed {i+1}/{total_tests} tests. Current success rate: {(successful_tests/(i+1))*100:.2f}%")
                
                # Minimal delay to prevent overwhelming the service
                await asyncio.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Error in test {i+1}: {str(e)}")
                logger.error(f"Operation: {operation}, x={x}, y={y}")
                self.test_results.append({
                    "service": "CalculatorService",
                    "function": operation,
                    "args": {"x": x, "y": y},
                    "error": str(e),
                    "success": False
                })
        
        # Log performance metrics
        avg_time = total_time / total_tests
        success_rate = (successful_tests / total_tests) * 100
        
        logger.info("===== Performance Test Results =====")
        logger.info(f"Total tests: {total_tests}")
        logger.info(f"Successful tests: {successful_tests}")
        logger.info(f"Success rate: {success_rate:.2f}%")
        logger.info(f"Total time: {total_time:.2f} seconds")
        logger.info(f"Average request time: {avg_time:.4f} seconds")
        
        self.test_results.append({
            "service": "CalculatorService",
            "function": "performance_test",
            "metrics": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "success_rate": success_rate,
                "total_time": total_time,
                "average_request_time": avg_time
            },
            "success": successful_tests == total_tests
        })
    
    async def test_letter_counter_service(self):
        """Test the letter counter service"""
        logger.info("===== Testing Letter Counter Service =====")
        
        # Test count_letter function
        try:
            logger.info("Testing count_letter function...")
            result = await self.client.call_function_by_name("count_letter", text="lollapalooza", letter="l")
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "LetterCounterService",
                "function": "count_letter",
                "args": {"text": "lollapalooza", "letter": "l"},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing count_letter function: {str(e)}")
            self.test_results.append({
                "service": "LetterCounterService",
                "function": "count_letter",
                "args": {"text": "lollapalooza", "letter": "l"},
                "error": str(e),
                "success": False
            })
        
        # Test count_multiple_letters function
        try:
            logger.info("Testing count_multiple_letters function...")
            result = await self.client.call_function_by_name("count_multiple_letters", text="mississippi", letters=["m", "i", "s", "p"])
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "LetterCounterService",
                "function": "count_multiple_letters",
                "args": {"text": "mississippi", "letters": ["m", "i", "s", "p"]},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing count_multiple_letters function: {str(e)}")
            self.test_results.append({
                "service": "LetterCounterService",
                "function": "count_multiple_letters",
                "args": {"text": "mississippi", "letters": ["m", "i", "s", "p"]},
                "error": str(e),
                "success": False
            })
        
        # Test get_letter_frequency function
        try:
            logger.info("Testing get_letter_frequency function...")
            result = await self.client.call_function_by_name("get_letter_frequency", text="mississippi")
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "LetterCounterService",
                "function": "get_letter_frequency",
                "args": {"text": "mississippi"},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing get_letter_frequency function: {str(e)}")
            self.test_results.append({
                "service": "LetterCounterService",
                "function": "get_letter_frequency",
                "args": {"text": "mississippi"},
                "error": str(e),
                "success": False
            })
    
    async def test_text_processor_service(self):
        """Test the text processor service"""
        logger.info("===== Testing Text Processor Service =====")
        
        # Test transform_case function
        try:
            logger.info("Testing transform_case function...")
            result = await self.client.call_function_by_name("transform_case", text="Hello World", case="upper")
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "TextProcessorService",
                "function": "transform_case",
                "args": {"text": "Hello World", "case": "upper"},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing transform_case function: {str(e)}")
            self.test_results.append({
                "service": "TextProcessorService",
                "function": "transform_case",
                "args": {"text": "Hello World", "case": "upper"},
                "error": str(e),
                "success": False
            })
        
        # Test analyze_text function
        try:
            logger.info("Testing analyze_text function...")
            result = await self.client.call_function_by_name("analyze_text", text="The quick brown fox jumps over the lazy dog.")
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "TextProcessorService",
                "function": "analyze_text",
                "args": {"text": "The quick brown fox jumps over the lazy dog."},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing analyze_text function: {str(e)}")
            self.test_results.append({
                "service": "TextProcessorService",
                "function": "analyze_text",
                "args": {"text": "The quick brown fox jumps over the lazy dog."},
                "error": str(e),
                "success": False
            })
        
        # Test generate_text function
        try:
            logger.info("Testing generate_text function...")
            result = await self.client.call_function_by_name("generate_text", text="Hello", operation="repeat", count=3)
            logger.info(f"Result: {result}")
            self.test_results.append({
                "service": "TextProcessorService",
                "function": "generate_text",
                "args": {"text": "Hello", "operation": "repeat", "count": 3},
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"Error testing generate_text function: {str(e)}")
            self.test_results.append({
                "service": "TextProcessorService",
                "function": "generate_text",
                "args": {"text": "Hello", "operation": "repeat", "count": 3},
                "error": str(e),
                "success": False
            })
    
    def print_results(self):
        """Print the test results"""
        logger.info("===== Test Results =====")
        
        # Group results by service
        services = {}
        for result in self.test_results:
            service_name = result.get("service", "UnknownService")
            if service_name not in services:
                services[service_name] = {"total": 0, "success": 0, "failure": 0}
            
            services[service_name]["total"] += 1
            if result.get("success", False):
                services[service_name]["success"] += 1
            else:
                services[service_name]["failure"] += 1
        
        # Print results by service
        total_tests = len(self.test_results)
        total_success = sum(1 for result in self.test_results if result.get("success", False))
        total_failure = total_tests - total_success
        
        logger.info(f"Total tests: {total_tests}")
        logger.info(f"Successful tests: {total_success}")
        logger.info(f"Failed tests: {total_failure}")
        logger.info(f"Success rate: {total_success / total_tests * 100:.2f}%")
        
        for service_name, stats in services.items():
            logger.info(f"Service: {service_name}")
            logger.info(f"  Total tests: {stats['total']}")
            logger.info(f"  Successful tests: {stats['success']}")
            logger.info(f"  Failed tests: {stats['failure']}")
            logger.info(f"  Success rate: {stats['success'] / stats['total'] * 100:.2f}%")
        
        # Print failed tests
        if total_failure > 0:
            logger.info("Failed tests:")
            for result in self.test_results:
                if not result.get("success", False):
                    logger.info(f"  Service: {result.get('service', 'UnknownService')}")
                    logger.info(f"  Function: {result.get('function', 'UnknownFunction')}")
                    logger.info(f"  Args: {result.get('args', {})}")
                    logger.info(f"  Error: {result.get('error', 'Unknown error')}")
                    logger.info("")
    
    async def run_all_tests(self):
        """Run all tests"""
        logger.info("Running all tests...")
        
        # Discover functions
        await self.discover_functions()
        
        # Add call_function_by_name method to the client
        self.client.call_function_by_name = self._call_function_by_name
        
        # Run tests for each service
        await self.test_calculator_service()
        await self.test_calculator_performance()
        await self.test_letter_counter_service()
        await self.test_text_processor_service()
        
        # Print results
        self.print_results()
    
    async def _call_function_by_name(self, function_name, **kwargs):
        """
        Call a function by name.
        
        Args:
            function_name: Name of the function to call
            **kwargs: Arguments to pass to the function
            
        Returns:
            Function result
        """
        # Find the function ID by name
        function_id = None
        for func in self.client.list_available_functions():
            if func["name"] == function_name:
                function_id = func["function_id"]
                break
        
        if not function_id:
            raise ValueError(f"Function not found: {function_name}")
        
        # Call the function
        return await self.client.call_function(function_id, **kwargs)
    
    def close(self):
        """Clean up resources"""
        logger.info("Cleaning up resources...")
        self.client.close()

async def main():
    """Main entry point"""
    logger.info("Starting test for all services")
    test = None
    try:
        # Create and run the test
        test = AllServicesTest()
        await test.run_all_tests()
        
        # Check if any tests failed
        if test.test_results and any(not result.get('success', False) for result in test.test_results):
            logger.error("Some tests failed - see above for details")
            return 1
            
        return 0
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        return 1
    finally:
        # Clean up
        if test:
            test.close()

if __name__ == "__main__":
    # Run the main function
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 
```

## test_functions/test_function_schemas.py

**Author:** Jason

```python
#!/usr/bin/env python3

import logging
import asyncio
import json
from typing import Dict, Any, List
from test_functions.generic_function_client import GenericFunctionClient

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("schema_test")

# Expected schemas for calculator functions
EXPECTED_CALCULATOR_SCHEMAS = {
    "add": {
        "type": "object",
        "properties": {
            "x": {
                "type": "number",
                "description": "First number"
            },
            "y": {
                "type": "number",
                "description": "Second number"
            }
        },
        "required": ["x", "y"]
    },
    "subtract": {
        "type": "object",
        "properties": {
            "x": {
                "type": "number",
                "description": "First number"
            },
            "y": {
                "type": "number",
                "description": "Second number"
            }
        },
        "required": ["x", "y"]
    },
    "multiply": {
        "type": "object",
        "properties": {
            "x": {
                "type": "number",
                "description": "First number"
            },
            "y": {
                "type": "number",
                "description": "Second number"
            }
        },
        "required": ["x", "y"]
    },
    "divide": {
        "type": "object",
        "properties": {
            "x": {
                "type": "number",
                "description": "First number"
            },
            "y": {
                "type": "number",
                "description": "Second number"
            }
        },
        "required": ["x", "y"]
    }
}

# Expected schemas for letter counter functions
EXPECTED_LETTER_COUNTER_SCHEMAS = {
    "count_letter": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text input"
            },
            "letter": {
                "type": "string",
                "description": "Single letter input"
            }
        },
        "required": ["text", "letter"]
    },
    "count_multiple_letters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text input"
            },
            "letters": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "List of letters to count"
            }
        },
        "required": ["text", "letters"]
    },
    "get_letter_frequency": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text input"
            }
        },
        "required": ["text"]
    }
}

# Expected schemas for text processor functions
EXPECTED_TEXT_PROCESSOR_SCHEMAS = {
    "transform_case": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text input"
            },
            "case": {
                "type": "string",
                "description": "Target case transformation to apply",
                "enum": ["upper", "lower", "title"]
            }
        },
        "required": ["text", "case"]
    },
    "analyze_text": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text input"
            }
        },
        "required": ["text"]
    },
    "generate_text": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text input"
            },
            "operation": {
                "type": "string",
                "description": "Operation to perform on the text",
                "enum": ["repeat", "pad"]
            },
            "count": {
                "type": "integer",
                "description": "For 'repeat': number of times to repeat the text. For 'pad': length of padding on each side",
                "minimum": 0,
                "maximum": 1000
            }
        },
        "required": ["text", "operation", "count"]
    }
}

async def verify_function_schemas():
    """
    Verify that the discovered function schemas match our expectations.
    """
    client = GenericFunctionClient()
    
    try:
        # Discover available functions with a longer timeout
        print("Waiting for function discovery (10 seconds)...")
        await client.discover_functions(timeout_seconds=10)
        
        # List available functions
        functions = client.list_available_functions()
        print("\nDiscovered Functions:")
        for func in functions:
            print(f"  - {func['function_id']}: {func['name']} - {func['description']}")
        
        # Verify calculator schemas
        print("\nVerifying Calculator Schemas:")
        calculator_functions = [f for f in functions if f['name'] in EXPECTED_CALCULATOR_SCHEMAS]
        
        if not calculator_functions:
            print("❌ No calculator functions discovered")
        else:
            for func in calculator_functions:
                name = func['name']
                discovered_schema = func['schema']
                expected_schema = EXPECTED_CALCULATOR_SCHEMAS.get(name)
                
                if not expected_schema:
                    print(f"❌ No expected schema for calculator function: {name}")
                    continue
                    
                # Compare schemas
                schema_match = compare_schemas(discovered_schema, expected_schema)
                if schema_match:
                    print(f"✅ Schema for {name} matches expected schema")
                else:
                    print(f"❌ Schema mismatch for {name}")
                    print(f"Expected: {json.dumps(expected_schema, indent=2)}")
                    print(f"Discovered: {json.dumps(discovered_schema, indent=2)}")
        
        # Verify letter counter schemas
        print("\nVerifying Letter Counter Schemas:")
        letter_counter_functions = [f for f in functions if f['name'] in EXPECTED_LETTER_COUNTER_SCHEMAS]
        
        if not letter_counter_functions:
            print("❌ No letter counter functions discovered")
        else:
            for func in letter_counter_functions:
                name = func['name']
                discovered_schema = func['schema']
                expected_schema = EXPECTED_LETTER_COUNTER_SCHEMAS.get(name)
                
                if not expected_schema:
                    print(f"❌ No expected schema for letter counter function: {name}")
                    continue
                    
                # Compare schemas
                schema_match = compare_schemas(discovered_schema, expected_schema)
                if schema_match:
                    print(f"✅ Schema for {name} matches expected schema")
                else:
                    print(f"❌ Schema mismatch for {name}")
                    print(f"Expected: {json.dumps(expected_schema, indent=2)}")
                    print(f"Discovered: {json.dumps(discovered_schema, indent=2)}")
        
        # Verify text processor schemas
        print("\nVerifying Text Processor Schemas:")
        text_processor_functions = [f for f in functions if f['name'] in EXPECTED_TEXT_PROCESSOR_SCHEMAS]
        
        if not text_processor_functions:
            print("❌ No text processor functions discovered")
        else:
            for func in text_processor_functions:
                name = func['name']
                discovered_schema = func['schema']
                expected_schema = EXPECTED_TEXT_PROCESSOR_SCHEMAS.get(name)
                
                if not expected_schema:
                    print(f"❌ No expected schema for text processor function: {name}")
                    continue
                    
                # Compare schemas
                schema_match = compare_schemas(discovered_schema, expected_schema)
                if schema_match:
                    print(f"✅ Schema for {name} matches expected schema")
                else:
                    print(f"❌ Schema mismatch for {name}")
                    print(f"Expected: {json.dumps(expected_schema, indent=2)}")
                    print(f"Discovered: {json.dumps(discovered_schema, indent=2)}")
        
    except Exception as e:
        logger.error(f"Error during schema verification: {str(e)}", exc_info=True)
    finally:
        client.close()

def compare_schemas(schema1: Dict[str, Any], schema2: Dict[str, Any]) -> bool:
    """
    Compare two schemas to see if they match.
    This is a simplified comparison that checks:
    1. Same type
    2. Same properties
    3. Same required fields
    
    Args:
        schema1: First schema to compare
        schema2: Second schema to compare
        
    Returns:
        True if schemas match, False otherwise
    """
    # Check type
    if schema1.get('type') != schema2.get('type'):
        return False
    
    # Check properties
    props1 = schema1.get('properties', {})
    props2 = schema2.get('properties', {})
    
    if set(props1.keys()) != set(props2.keys()):
        return False
    
    # Check property types
    for prop_name in props1:
        if props1[prop_name].get('type') != props2[prop_name].get('type'):
            return False
    
    # Check required fields
    req1 = set(schema1.get('required', []))
    req2 = set(schema2.get('required', []))
    
    if req1 != req2:
        return False
    
    return True

def main():
    """Main entry point"""
    logger.info("Starting schema verification test")
    try:
        asyncio.run(verify_function_schemas())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 
```

## test_functions/calculator_service.py

**Author:** Jason

```python
#!/usr/bin/env python3
import logging, asyncio, sys
from typing import Dict, Any
from datetime import datetime
from genesis_lib.decorators import genesis_function
from genesis_lib.enhanced_service_base import EnhancedServiceBase

# --------------------------------------------------------------------------- #
# Exceptions                                                                  #
# --------------------------------------------------------------------------- #
class CalculatorError(Exception):
    """Base exception for calculator service errors."""
    pass

class InvalidInputError(CalculatorError):
    """Raised when input values are invalid."""
    pass

class DivisionByZeroError(CalculatorError):
    """Raised when attempting to divide by zero."""
    pass

# --------------------------------------------------------------------------- #
# Service                                                                     #
# --------------------------------------------------------------------------- #
logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    force=True)  # Force reconfiguration of the root logger
logger = logging.getLogger("calculator_service")
logger.setLevel(logging.DEBUG)  # Explicitly set logger level

class CalculatorService(EnhancedServiceBase):
    """Implementation of the calculator service using the decorator pattern.
    
    This service provides basic arithmetic operations with input validation
    and standardized response formatting. It extends EnhancedServiceBase to
    leverage built-in function registration, monitoring, and discovery.
    """

    def __init__(self):
        logger.info("===== DDS TRACE: CalculatorService initializing... =====")
        super().__init__("CalculatorService", capabilities=["calculator", "math"])
        logger.info("===== DDS TRACE: CalculatorService EnhancedServiceBase initialized. =====")
        logger.info("===== DDS TRACE: Calling _advertise_functions... =====")
        self._advertise_functions()
        logger.info("===== DDS TRACE: _advertise_functions called. =====")
        logger.info("CalculatorService initialized")

    @genesis_function()
    async def add(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Add two numbers together.
        
        Args:
            x: First number to add (example: 5.0)
            y: Second number to add (example: 3.0)
            request_info: Optional request metadata
            
        Returns:
            Dict containing the result of the addition
            
        Examples:
            >>> await add(5, 3)
            {'result': 8}
            
        Raises:
            InvalidInputError: If either number is outside the valid range [-1,000,000, 1,000,000]
        """
        logger.info(f"Received add request: x={x}, y={y}")
        self.publish_function_call_event("add", {"x": x, "y": y}, request_info)
        
        try:
            result = x + y
            self.publish_function_result_event("add", {"result": result}, request_info)
            logger.info(f"Add result: {result}")
            return {"result": result}
        except Exception as e:
            logger.error(f"Error in add operation: {str(e)}")
            raise InvalidInputError(f"Failed to add numbers: {str(e)}")

    @genesis_function()
    async def subtract(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Subtract the second number from the first.
        
        Args:
            x: The number to subtract from (example: 5.0)
            y: The number to subtract (example: 3.0)
            request_info: Optional request metadata
            
        Returns:
            Dict containing the result of the subtraction
            
        Examples:
            >>> await subtract(5, 3)
            {'result': 2}
            
        Raises:
            InvalidInputError: If either number is outside the valid range [-1,000,000, 1,000,000]
        """
        logger.info(f"Received subtract request: x={x}, y={y}")
        self.publish_function_call_event("subtract", {"x": x, "y": y}, request_info)
        
        try:
            result = x - y
            self.publish_function_result_event("subtract", {"result": result}, request_info)
            logger.info(f"Subtract result: {result}")
            return {"result": result}
        except Exception as e:
            logger.error(f"Error in subtract operation: {str(e)}")
            raise InvalidInputError(f"Failed to subtract numbers: {str(e)}")

    @genesis_function()
    async def multiply(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Multiply two numbers together.
        
        Args:
            x: First number to multiply (example: 5.0)
            y: Second number to multiply (example: 3.0)
            request_info: Optional request metadata
            
        Returns:
            Dict containing the result of the multiplication
            
        Examples:
            >>> await multiply(5, 3)
            {'result': 15}
            
        Raises:
            InvalidInputError: If either number is outside the valid range [-1,000,000, 1,000,000]
        """
        logger.info(f"Received multiply request: x={x}, y={y}")
        self.publish_function_call_event("multiply", {"x": x, "y": y}, request_info)
        
        try:
            result = x * y
            self.publish_function_result_event("multiply", {"result": result}, request_info)
            logger.info(f"Multiply result: {result}")
            return {"result": result}
        except Exception as e:
            logger.error(f"Error in multiply operation: {str(e)}")
            raise InvalidInputError(f"Failed to multiply numbers: {str(e)}")

    @genesis_function()
    async def divide(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Divide the first number by the second.
        
        Args:
            x: The number to divide (example: 6.0)
            y: The number to divide by (example: 2.0)
            request_info: Optional request metadata
            
        Returns:
            Dict containing the result of the division
            
        Examples:
            >>> await divide(6, 2)
            {'result': 3}
            
        Raises:
            InvalidInputError: If either number is outside the valid range [-1,000,000, 1,000,000]
            DivisionByZeroError: If attempting to divide by zero
        """
        logger.info(f"Received divide request: x={x}, y={y}")
        self.publish_function_call_event("divide", {"x": x, "y": y}, request_info)
        
        try:
            if y == 0:
                raise DivisionByZeroError("Cannot divide by zero")
            result = x / y
            self.publish_function_result_event("divide", {"result": result}, request_info)
            logger.info(f"Divide result: {result}")
            return {"result": result}
        except DivisionByZeroError:
            logger.error("Attempted division by zero")
            raise
        except Exception as e:
            logger.error(f"Error in divide operation: {str(e)}")
            raise InvalidInputError(f"Failed to divide numbers: {str(e)}")

# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #
def main():
    logger.info("SERVICE: Starting calculator service")
    try:
        service = CalculatorService()
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("SERVICE: Shutting down calculator service")

if __name__ == "__main__":
    main()

```

## run_scripts/test_agent.py

**Author:** Jason

```python
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
import os
import asyncio
import sys
import logging

class TestAgent(OpenAIGenesisAgent):
    def __init__(self):
        # Initialize the base class with our specific configuration
        super().__init__(
            model_name="gpt-4o",  # You can change this to your preferred model
            classifier_model_name="gpt-4o-mini",  # You can change this to your preferred model
            agent_name="TestAgent",  # Match the class name
            description="A test agent for monitoring and function tests",
            enable_tracing=True  # Enable tracing for testing
        )

async def main():
    # Configure basic logging for the script and to see genesis_lib DEBUG logs
    log_level = logging.DEBUG # Or logging.INFO for less verbosity

    # AGGRESSIVE LOGGING RESET
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]: # Iterate over a copy
        root_logger.removeHandler(handler)
        handler.close() # Ensure handlers release resources

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout # Ensure logs go to stdout to be captured by test runner
    )
    # Ensure specific genesis_lib loggers are also at DEBUG if needed,
    # basicConfig might set root, but good to be explicit for key modules.
    logging.getLogger("genesis_lib.function_discovery").setLevel(logging.DEBUG)
    logging.getLogger("genesis_app").setLevel(logging.DEBUG) # For GenesisApp close logs

    # Create and run the agent
    agent = TestAgent()
    
    try:
        # Give some time for initialization and announcement propagation
        await asyncio.sleep(2)  # Use async sleep instead of time.sleep
        
        # Get message from command line argument or use default
        message = sys.argv[1] if len(sys.argv) > 1 else "Hello, can you tell me a joke?"
        
        # Example usage
        response = await agent.process_message(message)
        print(f"Agent response: {response}")
        
    finally:
        # Clean up using parent class cleanup
        await agent.close()

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main()) 
```

## genesis_lib/config/USER_QOS_PROFILES.xml

**Author:** Jason

```xml
<?xml version="1.0"?>

<!--
 (c) 2005-2015 Copyright, Real-Time Innovations, Inc.  All rights reserved.
 RTI grants Licensee a license to use, modify, compile, and create derivative
 works of the Software.  Licensee has the right to distribute object form only
 for use with RTI products.  The Software is provided "as is", with no warranty
 of any type, including any warranty for fitness for any purpose. RTI is under
 no obligation to maintain or support the Software.  RTI shall not be liable for
 any incidental or consequential damages arising out of the use or inability to
 use the software.
 -->
<dds xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:noNamespaceSchemaLocation="http://community.rti.com/schema/6.0.0/rti_dds_qos_profiles.xsd"
     version="6.0.0">
    <!-- QoS Library containing the QoS profile used in the generated example.

        A QoS library is a named set of QoS profiles.
    -->
    <qos_library name="cft_Library">

        <!-- QoS profile used to configure reliable communication between the DataWriter
             and DataReader created in the example code.

             A QoS profile groups a set of related QoS.
        -->
        <qos_profile name="cft_Profile" is_default_qos="true">
            <!-- QoS used to configure the data writer created in the example code -->
            <datawriter_qos>
                <reliability>
                    <kind>RELIABLE_RELIABILITY_QOS</kind>
                </reliability>
                <!-- Enabled transient local durability to provide history to
                     late-joiners. -->
                <durability>
                    <kind>TRANSIENT_LOCAL_DURABILITY_QOS</kind>
                </durability>
                <!-- The last twenty samples are saved for late joiners -->
                <history>
                    <kind>KEEP_LAST_HISTORY_QOS</kind>
                    <depth>500</depth>
                </history>
                <!-- Set the publishing mode to asynchronous -->
                <publish_mode>
                    <kind>ASYNCHRONOUS_PUBLISH_MODE_QOS</kind>
                </publish_mode>
            </datawriter_qos>

            <!-- QoS used to configure the data reader created in the example code -->
            <datareader_qos>
                <reliability>
                    <kind>RELIABLE_RELIABILITY_QOS</kind>
                </reliability>
                <!-- Enabled transient local durability to get history when
                     late-joining the DDS domain. -->
                <durability>
                    <kind>TRANSIENT_LOCAL_DURABILITY_QOS</kind>
                </durability>
                <!-- The last twenty samples are saved for late joiners -->
                <history>
                    <kind>KEEP_LAST_HISTORY_QOS</kind>
                    <depth>500</depth>
                </history>
            </datareader_qos>

            <participant_qos>
                <!-- Use UDPv4 transport only to avoid shared memory issues on macOS -->
                <transport_builtin>
                    <mask>UDPv4</mask>
                </transport_builtin>
                <participant_name>
                    <name>RTI Content Filtered Topic STRINGMATCH</name>
                </participant_name>
            </participant_qos>
        </qos_profile>

    </qos_library>
</dds>
```

## run_scripts/math_test_interface.py

**Author:** Jason

```python
#!/usr/bin/env python3
import logging
import sys
import os
import time
import traceback
import asyncio
import random
import uuid
import json

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from genesis_lib.monitored_interface import MonitoredInterface

# Configure logging for this script
logger = logging.getLogger("MathTestInterface")

# Explicitly configure root logger and add a stream handler to stdout
root_logger = logging.getLogger() # Get the root logger
# Ensure there's a handler for stdout if one isn't already configured effectively
# We want to make sure this script's logs go to where the test runner expects them.
# A simple check: if no handlers, or if the existing ones don't include a StreamHandler to stdout/stderr.
# For simplicity here, let's just ensure our script's logger level and add a handler if root has none.
if not root_logger.hasHandlers(): # A more robust check might be needed depending on environment
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(stdout_handler)

root_logger.setLevel(logging.DEBUG) # Set root logger level to DEBUG
logger.setLevel(logging.INFO)       # Keep MathTestInterface script's own direct logs at INFO

class MathTestInterface:
    def __init__(self, interface_id):
        self.interface_id = interface_id
        self.interface = None
        self.conversation_id = str(uuid.uuid4())
        logger.info(f"🚀 TRACE: MathTestInterface {interface_id} starting - Conversation ID: {self.conversation_id}")

    async def run(self):
        interface = None # Ensure interface is defined in outer scope for finally block
        try:
            logger.info("🏗️ TRACE: Creating MathService interface...")
            # Create interface - now using MonitoredInterface directly
            interface = MonitoredInterface(interface_name="MathTestInterface", service_name="InterfaceAgent111")

            logger.info(f"🔍 TRACE: Waiting for agent discovery event...")
            try:
                await asyncio.wait_for(interface._agent_found_event.wait(), timeout=30.0)
            except asyncio.TimeoutError:
                logger.error(f"❌ TRACE: Timeout waiting for any agent to be discovered.")
                if interface: await interface.close()
                return 1

            # Select the first agent discovered (simple strategy for testing)
            chosen_agent = None
            if interface.available_agents:
                 # Log the list of available agents for verification
                 logger.info(f"🔎 TRACE: Available agents found: {interface.available_agents}")
                 chosen_agent = list(interface.available_agents.values())[0]
                 logger.info(f"✅ TRACE: Agent discovered. Selecting first available: {chosen_agent['prefered_name']}")
            else:
                logger.error("❌ TRACE: Agent found event triggered, but no agents in available list?!")
                if interface: await interface.close()
                return 1
                
            # Connect to the chosen agent
            logger.info(f"🔗 TRACE: Attempting to connect to service: {chosen_agent['service_name']}")
            if not await interface.connect_to_agent(chosen_agent['service_name'], timeout_seconds=10.0):
                logger.error(f"❌ TRACE: Failed to connect to agent service {chosen_agent['service_name']}")
                if interface: await interface.close()
                return 1
                
            # Store the ID of the connected agent for departure handling
            interface._connected_agent_id = chosen_agent['instance_id']
            logger.info(f"✅ TRACE: Successfully connected to agent: {chosen_agent['prefered_name']} (ID: {interface._connected_agent_id})")
            
            # Generate random math operation
            operations = ['add', 'subtract', 'multiply', 'divide']
            operation = random.choice(operations)
            x = random.randint(1, 100)
            y = random.randint(1, 100)
            
            # Create test request using the same message structure as baseline
            test_request = {
                'message': json.dumps({
                    'x': x,
                    'y': y,
                    'operation': operation,
                    'conversation_id': self.conversation_id
                }),
                'conversation_id': self.conversation_id  # Add conversation_id at the top level for session tracking
            }
            
            logger.info(f"📤 TRACE: Sending math request: {test_request}")

            # Send the request using the existing interface method
            reply = await interface.send_request(test_request)
            
            if reply:
                logger.info(f"📥 TRACE: Received reply: {reply}")
                if reply.get('status') != 0:
                    logger.warning(f"⚠️ TRACE: Reply indicated error status: {reply['status']}")
                else:
                    # Parse the response
                    response_data = json.loads(reply['message'])
                    result = float(response_data)

                    # Calculate expected result
                    expected_result = self._calculate_expected_result(x, y, operation)

                    # Compare results
                    if abs(result - expected_result) < 0.0001:  # Use small epsilon for float comparison
                        logger.info(f"✅ TRACE: Math test passed - result={result}, expected={expected_result}")
                        return 0
                    else:
                        logger.error(f"❌ TRACE: Math test failed - result={result}, expected={expected_result}")
                        return 1
            else:
                # Check if the agent departed during the request
                if interface and not interface._connected_agent_id:
                    logger.error("❌ TRACE: No reply received, and the connected agent has departed.")
                else:
                    logger.error("❌ TRACE: No reply received from agent (agent might still be connected). Check agent logs.")
                return 1

        except Exception as e:
            logger.error(f"❌ TRACE: Error in math test: {str(e)}")
            logger.error(traceback.format_exc())
            # Ensure cleanup happens even on unexpected error
            if interface:
                try:
                    await interface.close()
                except Exception as close_e:
                    logger.error(f"❌ TRACE: Error during cleanup: {close_e}")
            return 1 # Indicate failure
        finally:
            # Ensure interface is closed cleanly even if run completes successfully or errors out early
            if interface: 
                logger.info("🧹 TRACE: Cleaning up interface (finally block)")
                try:
                    await interface.close()
                except Exception as final_close_e:
                     logger.error(f"❌ TRACE: Error during final interface cleanup: {final_close_e}")

    def _calculate_expected_result(self, x, y, operation):
        if operation == 'add':
            return x + y
        elif operation == 'subtract':
            return x - y
        elif operation == 'multiply':
            return x * y
        elif operation == 'divide':
            return x / y
        return None

async def main():
    logger.info("🚀 TRACE: MathTestInterface starting")
    interface = MathTestInterface("Interface1")
    exit_code = await interface.run()
    logger.info(f"🏁 TRACE: MathTestInterface ending with exit code: {exit_code}")
    return exit_code

if __name__ == "__main__":
    sys.exit(asyncio.run(main())) 
```

## run_scripts/simpleGenesisInterfaceCLI.py

**Author:** Jason

```python
import asyncio
import logging
import sys
import argparse # Added for command-line arguments
from genesis_lib.monitored_interface import MonitoredInterface
from genesis_lib.logging_config import set_genesis_library_log_level # Import the new utility

# Logger will be configured in main() after parsing args
logger = logging.getLogger("SimpleGenesisInterfaceCLI")

INTERFACE_NAME = "SimpleCLI-111"
# AGENT_SERVICE_NAME is no longer a fixed target for initial connection filtering.
# The user will select an agent, and its specific service_name will be used.

async def main(verbose: bool = False): # Added verbose parameter
    # Configure basic logging for this script
    log_level = logging.DEBUG if verbose else logging.INFO
    # Application script configures its own root logger and its desired level
    logging.basicConfig(
        level=log_level, # This sets the default for all loggers unless overridden
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # If verbose mode is enabled for the script, also make genesis_lib verbose.
    # Otherwise, genesis_lib loggers will respect the script's root logger setting (e.g., INFO).
    # We previously changed noisy INFOs in the library to DEBUGs, so this should be cleaner.
    if verbose:
        set_genesis_library_log_level(logging.DEBUG)
        # The lines below are now handled by set_genesis_library_log_level
        # logging.getLogger("genesis_lib.monitored_interface").setLevel(logging.DEBUG)
        # logging.getLogger("genesis_lib.interface").setLevel(logging.DEBUG)
        # logging.getLogger("genesis_app").setLevel(logging.DEBUG)
    # else:
        # Optional: If you wanted genesis_lib to be *quieter* than the script by default
        # (e.g. script is INFO, but library is WARNING unless script is DEBUG)
        # you could add: set_genesis_library_log_level(logging.WARNING)
        # But for now, let them inherit the script's level or be DEBUG if script is verbose.

    logger.info(f"Initializing '{INTERFACE_NAME}' (Log Level: {logging.getLevelName(log_level)})...")
    # Initialize the MonitoredInterface. The service_name here is more of a default
    # or for how the interface itself might be identified, not for filtering agents initially.
    interface = MonitoredInterface(
        interface_name=INTERFACE_NAME,
        service_name="GenericInterfaceService" # Can be a generic name for the interface itself
    )

    target_agent_id = None
    target_agent_service_name = None
    connected_agent_name = "N/A"

    try:
        print("Waiting for any agent(s) to become available (up to 30s)...")
        try:
            await asyncio.wait_for(interface._agent_found_event.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            logger.error("Timeout: No agent discovery signal received within 30 seconds. Exiting.")
            await interface.close()
            return

        print("First agent(s) found. Waiting a moment for others to appear...")
        await asyncio.sleep(2)

        if not interface.available_agents:
            logger.error("No agents were discovered even after waiting. Exiting.")
            await interface.close()
            return

        print("Available agents:")
        agent_list = list(interface.available_agents.values())
        for i, agent_info in enumerate(agent_list):
            print(f"  {i+1}. Name: '{agent_info.get('prefered_name', 'N/A')}', ID: '{agent_info.get('instance_id')}', Service: '{agent_info.get('service_name')}'")

        if not agent_list:
            logger.error("No agents available to select. Exiting.")
            await interface.close()
            return

        selected_index = -1
        while True:
            try:
                choice = await asyncio.to_thread(input, "Select agent by number: ")
                selected_index = int(choice) - 1
                if 0 <= selected_index < len(agent_list):
                    selected_agent = agent_list[selected_index]
                    target_agent_id = selected_agent.get('instance_id')
                    target_agent_service_name = selected_agent.get('service_name')
                    connected_agent_name = selected_agent.get('prefered_name', target_agent_id)
                    break
                else:
                    print("Invalid selection. Please enter a number from the list.")
            except ValueError:
                print("Invalid input. Please enter a number.")
            except RuntimeError:
                print("Input stream closed during selection.")
                await interface.close()
                return
        
        if not target_agent_id or not target_agent_service_name:
            logger.error("Failed to select a valid agent or retrieve its details. Exiting.")
            await interface.close()
            return

        print(f"Attempting to connect to agent '{connected_agent_name}' (ID: {target_agent_id}) offering service '{target_agent_service_name}'...")
        
        connection_successful = await interface.connect_to_agent(
            service_name=target_agent_service_name,
            timeout_seconds=10.0
        )
        
        if connection_successful:
            interface._connected_agent_id = target_agent_id

        if not connection_successful:
            logger.error(f"Failed to establish RPC connection with agent '{connected_agent_name}' for service '{target_agent_service_name}'. Exiting.")
            await interface.close()
            return

        print(f"Successfully connected to agent: '{connected_agent_name}' (Service: '{target_agent_service_name}').")
        print("You can now send messages. Type 'quit' or 'exit' to stop.")

        while True:
            try:
                user_input = await asyncio.to_thread(input, f"To [{connected_agent_name}]: ")
            except RuntimeError:
                print("Input stream closed.")
                break
                
            if user_input.lower() in ['quit', 'exit']:
                print("User requested exit.")
                break

            if not user_input:
                continue

            request_data = {"message": user_input}
            logger.info(f"Sending to agent: {request_data}")
            
            response = await interface.send_request(request_data, timeout_seconds=20.0)
            
            if response:
                print(f"Agent response: {response.get('message', 'No message content in response')}")
                if response.get('status', -1) != 0:
                    logger.warning(f"Agent indicated an issue with status: {response.get('status')}")
            else:
                logger.error("No response from agent or request timed out.")
                if interface._connected_agent_id and interface._connected_agent_id not in interface.available_agents:
                     logger.error("Connection lost: The agent may have departed. Please restart the CLI.")
                     break

    except KeyboardInterrupt:
        print("\\nKeyboard interrupt received. Shutting down...")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        print(f"Closing '{INTERFACE_NAME}' and releasing resources...")
        if 'interface' in locals() and interface:
            await interface.close()
        print(f"'{INTERFACE_NAME}' has been shut down.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Simple Genesis Interface CLI.")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level) for the CLI and Genesis libraries."
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(verbose=args.verbose)) # Pass verbose flag to main
    except KeyboardInterrupt:
        logger.info("CLI terminated by user.")
    sys.exit(0)

```

## run_scripts/baseline_test_interface.py

**Author:** Jason

```python
#!/usr/bin/env python3
import logging
import sys
import os
import time
import traceback
import asyncio

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from monitored_interface_cli import TracingMonitoredChatGPTInterface

# Configure logging with detailed format
log_file = os.path.join(project_root, 'logs', 'baseline_test_interface.log')
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'))

logger = logging.getLogger("BaselineTestInterface")
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

# Also configure root logger to show output in console
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

async def main():
    logger.info("🚀 TRACE: BaselineTestInterface starting - PID: %d", os.getpid())
    interface = None
    exit_code = 1 # Default to error

    try:
        logger.info("🏗️ TRACE: Creating ChatGPT interface...")
        # Use the same interface class as the CLI for consistency
        interface = TracingMonitoredChatGPTInterface()

        logger.info("🔍 TRACE: Waiting for agent discovery...")
        # Run wait_for_agent in a thread pool since it's not async
        loop = asyncio.get_event_loop()
        if not await loop.run_in_executor(None, interface.wait_for_agent):
            logger.error("❌ TRACE: No agent found, exiting")
            sys.exit(1)

        logger.info("✅ TRACE: Agent discovered successfully")
        test_message = "Tell me a joke."
        logger.info(f"📤 TRACE: Sending test message: '{test_message}'")

        # Send the request using the existing interface method
        # Run send_request in a thread pool since it's not async
        reply = await loop.run_in_executor(None, interface.send_request, {'message': test_message})
        if reply:
            logger.info(f"📥 TRACE: Received reply: {reply}")
            if reply.get('status') != 0:
                logger.warning("⚠️ TRACE: Reply indicated error status: %d", reply['status'])
            else:
                logger.info("✅ TRACE: Test completed successfully")
                exit_code = 0
        else:
            logger.error("❌ TRACE: No reply received from agent")

    except Exception as e:
        logger.error(f"❌ TRACE: Error in baseline test: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        if interface:
            logger.info("🧹 TRACE: Cleaning up interface")
            interface.close()
        logger.info(f"🏁 TRACE: BaselineTestInterface ending with exit code: {exit_code}")
        sys.exit(exit_code)

if __name__ == "__main__":
    asyncio.run(main()) 
```

## run_scripts/simpleGenesisInterfaceStatic.py

**Author:** Jason

```python
import asyncio
import logging
import sys
import argparse
from genesis_lib.monitored_interface import MonitoredInterface
from genesis_lib.logging_config import set_genesis_library_log_level

logger = logging.getLogger("SimpleGenesisInterfaceStatic")

INTERFACE_NAME = "SimpleStaticInterface-001"
MATH_QUESTION = "What is 123 plus 456?" # Predefined question
# EXPECTED_ANSWER_SUBSTRING = "579" # We'll check for this in the shell script via logs

async def main(verbose: bool = False, question: str = MATH_QUESTION):
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout # Ensure logs go to stdout for shell script to capture
    )

    if verbose:
        set_genesis_library_log_level(logging.DEBUG)

    logger.info(f"Initializing '{INTERFACE_NAME}' (Log Level: {logging.getLevelName(log_level)})...")
    interface = MonitoredInterface(
        interface_name=INTERFACE_NAME,
        service_name="StaticInterfaceService"
    )

    target_agent_id = None
    target_agent_service_name = None
    connected_agent_name = "N/A"
    exit_code = 1 # Default to failure

    try:
        logger.info("Waiting for any agent(s) to become available (up to 30s)...")
        try:
            await asyncio.wait_for(interface._agent_found_event.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            logger.error("Timeout: No agent discovery signal received within 30 seconds. Exiting.")
            await interface.close()
            return exit_code

        logger.info("First agent(s) found. Waiting a moment for others to appear...")
        await asyncio.sleep(2) # Allow time for all agents to announce

        if not interface.available_agents:
            logger.error("No agents were discovered even after waiting. Exiting.")
            await interface.close()
            return exit_code

        logger.info("Available agents:")
        agent_list = list(interface.available_agents.values())
        for i, agent_info in enumerate(agent_list):
            logger.info(f"  {i+1}. Name: '{agent_info.get('prefered_name', 'N/A')}', ID: '{agent_info.get('instance_id')}', Service: '{agent_info.get('service_name')}'")

        if not agent_list:
            logger.error("No agents available to select. Exiting.")
            await interface.close()
            return exit_code

        # Automatically select the first agent
        selected_agent = agent_list[0]
        target_agent_id = selected_agent.get('instance_id')
        target_agent_service_name = selected_agent.get('service_name')
        connected_agent_name = selected_agent.get('prefered_name', target_agent_id)
        
        if not target_agent_id or not target_agent_service_name:
            logger.error(f"Failed to automatically select an agent or retrieve its details. Agent info: {selected_agent}. Exiting.")
            await interface.close()
            return exit_code

        logger.info(f"Attempting to connect to agent '{connected_agent_name}' (ID: {target_agent_id}) offering service '{target_agent_service_name}'...")
        
        connection_successful = await interface.connect_to_agent(
            service_name=target_agent_service_name,
            timeout_seconds=10.0
        )
        
        if connection_successful:
            # This was an internal detail for the CLI's display, not strictly necessary for connection status
            # but good for logging if the MonitoredInterface uses it.
            interface._connected_agent_id = target_agent_id 

        if not connection_successful:
            logger.error(f"Failed to establish RPC connection with agent '{connected_agent_name}' for service '{target_agent_service_name}'. Exiting.")
            await interface.close()
            return exit_code

        print(f"Successfully connected to agent: '{connected_agent_name}' (Service: '{target_agent_service_name}').")
        
        request_data = {"message": question}
        print(f"Sending to agent [{connected_agent_name}]: {request_data}")
        
        response = await interface.send_request(request_data, timeout_seconds=20.0)
        
        if response:
            print(f"Agent response: {response.get('message', 'No message content in response')}")
            if response.get('status', -1) == 0:
                # We will verify content in the shell script via grep
                print("Request successful and response received.")
                exit_code = 0 # Success
            else:
                logger.warning(f"Agent indicated an issue with status: {response.get('status')}")
        else:
            logger.error("No response from agent or request timed out.")
            if interface._connected_agent_id and interface._connected_agent_id not in interface.available_agents :
                 logger.error("Connection lost: The agent may have departed.")

    except KeyboardInterrupt:
        logger.info("\\\\nKeyboard interrupt received. Shutting down...")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        logger.info(f"Closing '{INTERFACE_NAME}' and releasing resources...")
        if 'interface' in locals() and interface:
            await interface.close()
        logger.info(f"'{INTERFACE_NAME}' has been shut down. Exiting with code {exit_code}.")
        # The return from main will be used by sys.exit
        return exit_code

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Simple Genesis Static Interface.")
    parser.add_argument(
        "--question",
        type=str,
        default=MATH_QUESTION,
        help="The question to send to the agent."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level) for the script and Genesis libraries."
    )
    args = parser.parse_args()

    # The script will now exit with 0 on success, 1 on failure, based on main's return
    # This is important for the calling shell script to determine test pass/fail.
    script_result_code = 1 # Default to failure
    try:
        script_result_code = asyncio.run(main(verbose=args.verbose, question=args.question))
    except KeyboardInterrupt:
        logger.info("Script terminated by user.")
    except Exception as e:
        logger.error(f"Unhandled exception in __main__: {e}", exc_info=True)
    finally:
        sys.exit(script_result_code) 
```

## run_scripts/test_monitoring.py

**Author:** Jason

```python
#!/usr/bin/env python3
"""
Test script for monitoring functionality.
Verifies that agent and function monitoring events are being published correctly.
"""

import argparse
import logging
import sys
import time
import os
import json
from datetime import datetime
import threading
import rti.connextdds as dds
from genesis_lib.utils import get_datamodel_path
import re
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class MonitoringTest:
    def __init__(self, domain_id=0):
        """Initialize the monitoring test."""
        self.domain_id = domain_id
        self.events = []
        self.events_lock = threading.Lock()
        self.expected_events = set()
        self.expected_events_lock = threading.Lock()
        self.test_complete = False
        self.quit_flag = False
        
        # Initialize logger
        self.logger = logging.getLogger("MonitoringTest")
        self.logger.setLevel(logging.DEBUG)
        
        # Create DDS entities
        self.logger.info(f"Initializing DDS on domain {domain_id}")
        participant_qos = dds.QosProvider.default.participant_qos
        self.participant = dds.DomainParticipant(domain_id, participant_qos)
        
        # Create subscriber with appropriate QoS
        subscriber_qos = dds.QosProvider.default.subscriber_qos
        subscriber_qos.partition.name = [""]  # Default partition
        self.subscriber = dds.Subscriber(self.participant, subscriber_qos)
        
        # Get type provider
        self.logger.info("Loading types from datamodel.xml")
        provider = dds.QosProvider(get_datamodel_path())
        
        # Set up ComponentLifecycleEvent subscriber
        self.logger.info("Creating ComponentLifecycleEvent topic")
        self.lifecycle_type = provider.type("genesis_lib", "ComponentLifecycleEvent")
        self.lifecycle_topic = dds.DynamicData.Topic(
            self.participant,
            "ComponentLifecycleEvent",
            self.lifecycle_type
        )
        
        # Set up ChainEvent subscriber
        self.logger.info("Creating ChainEvent topic")
        self.chain_type = provider.type("genesis_lib", "ChainEvent")
        self.chain_topic = dds.DynamicData.Topic(
            self.participant,
            "ChainEvent",
            self.chain_type
        )
        
        # Configure reader QoS
        reader_qos = dds.QosProvider.default.datareader_qos
        reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        reader_qos.history.kind = dds.HistoryKind.KEEP_LAST
        reader_qos.history.depth = 1000
        
        # Set up subscription matching listener
        self.subscription_listener = self._setup_subscription_listener()
        
        # Create readers with listeners
        self.lifecycle_listener = self.ComponentLifecycleListener(self)
        self.lifecycle_reader = dds.DynamicData.DataReader(
            subscriber=self.subscriber,
            topic=self.lifecycle_topic,
            qos=reader_qos,
            listener=self.lifecycle_listener,
            mask=dds.StatusMask.DATA_AVAILABLE | dds.StatusMask.SUBSCRIPTION_MATCHED
        )
        
        self.chain_listener = self.ChainEventListener(self)
        self.chain_reader = dds.DynamicData.DataReader(
            subscriber=self.subscriber,
            topic=self.chain_topic,
            qos=reader_qos,
            listener=self.chain_listener,
            mask=dds.StatusMask.DATA_AVAILABLE | dds.StatusMask.SUBSCRIPTION_MATCHED
        )
        
        # Set up expected events
        self._setup_expected_events()
        
        self.logger.info("Monitoring test initialization complete")
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self.expected_events = {
            'calculator_service_1_discovery',
            'calculator_service_1_ready',
            'calculator_service_2_discovery',
            'calculator_service_2_ready',
            'calculator_service_3_discovery',
            'calculator_service_3_ready',
            'agent_discovery',
            'agent_ready',
            'function_discovery',
            'function_call_start',
            'function_call_complete'
        }
        self.discovered_services = set()
        self.log_lines = []  # Initialize log_lines to track service discovery order
    
    def _setup_subscription_listener(self):
        """Set up subscription matching listener."""
        class SubscriptionMatchListener(dds.DynamicData.NoOpDataReaderListener):
            def __init__(self, test_instance):
                super().__init__()
                self.test_instance = test_instance

            def on_subscription_matched(self, reader, status):
                # Only log matches for ComponentLifecycleEvent topic
                if reader.topic_name == "ComponentLifecycleEvent":
                    current_count = status.current_count
                    total_count = status.total_count
                    self.test_instance.logger.info(f"Subscription match update for {reader.topic_name}:")
                    self.test_instance.logger.info(f"  Current matched publications: {current_count}")
                    self.test_instance.logger.info(f"  Total cumulative matches: {total_count}")

        return SubscriptionMatchListener(self)
    
    class ComponentLifecycleListener(dds.DynamicData.NoOpDataReaderListener):
        def __init__(self, test_instance):
            super().__init__()
            self.test_instance = test_instance
            self.logger = logging.getLogger("ComponentLifecycleListener")
            self.logger.setLevel(logging.DEBUG)
        
        def on_data_available(self, reader):
            """Handle received data."""
            try:
                samples = reader.take()
                self.logger.debug(f"Got {len(samples)} samples")
                
                for data, info in samples:
                    if data is None or info.state.instance_state != dds.InstanceState.ALIVE:
                        continue
                    
                    self.logger.debug(f"\nRAW DDS DATA:")
                    self.logger.debug(f"Capabilities: {data['capabilities']}")
                    self.logger.debug(f"Reason: {data['reason']}")
                    
                    # Map component types and states
                    component_types = ["INTERFACE", "PRIMARY_AGENT", "SPECIALIZED_AGENT", "FUNCTION"]
                    states = ["JOINING", "DISCOVERING", "READY", "BUSY", "DEGRADED", "OFFLINE"]
                    event_categories = ["NODE_DISCOVERY", "EDGE_DISCOVERY", "STATE_CHANGE", "AGENT_INIT", "AGENT_READY", "AGENT_SHUTDOWN", "DDS_ENDPOINT"]
                    
                    # Convert enum values to integers for indexing
                    component_type_idx = int(data["component_type"])
                    previous_state_idx = int(data["previous_state"])
                    new_state_idx = int(data["new_state"])
                    event_category_idx = int(data["event_category"])
                    
                    # Safely get event category
                    event_category = event_categories[event_category_idx] if 0 <= event_category_idx < len(event_categories) else "UNKNOWN"
                    
                    # Build data dictionary
                    data_dict = {
                        "event_category": event_category,
                        "component_id": data["component_id"],
                        "component_type": component_types[component_type_idx],
                        "previous_state": states[previous_state_idx],
                        "new_state": states[new_state_idx],
                        "timestamp": data["timestamp"],
                        "source_id": str(data["source_id"]) if data["source_id"] else "",
                        "target_id": str(data["target_id"]) if data["target_id"] else "",
                        "connection_type": str(data["connection_type"]) if data["connection_type"] else "",
                        "chain_id": data["chain_id"],
                        "call_id": data["call_id"],
                        "capabilities": data["capabilities"],
                        "reason": data["reason"]
                    }
                    
                    self.test_instance._lifecycle_callback(data_dict)
                    
            except Exception as e:
                self.logger.error(f"Error in ComponentLifecycleListener: {e}")
                traceback.print_exc(file=sys.stderr)
    
    class ChainEventListener(dds.DynamicData.NoOpDataReaderListener):
        def __init__(self, test_instance):
            super().__init__()
            self.test_instance = test_instance
            self.logger = logging.getLogger("ChainEventListener")
            self.logger.setLevel(logging.DEBUG)
        
        def on_data_available(self, reader):
            """Handle received data."""
            try:
                samples = reader.take()
                self.logger.debug(f"Got {len(samples)} samples")
                
                for data, info in samples:
                    if data is None or info.state.instance_state != dds.InstanceState.ALIVE:
                        continue
                    
                    data_dict = {
                        "event_type": data["event_type"],
                        "chain_id": data["chain_id"],
                        "source_id": data["source_id"],
                        "target_id": data["target_id"],
                        "function_id": data["function_id"],
                        "timestamp": data["timestamp"],
                        "status": data["status"],
                        "call_id": data["call_id"]
                    }
                    
                    self.test_instance._chain_callback(data_dict)
                    
            except Exception as e:
                self.logger.error(f"Error in ChainEventListener: {e}")
                traceback.print_exc(file=sys.stderr)
    
    def _setup_expected_events(self):
        """Set up the expected events we should see."""
        with self.expected_events_lock:
            # Agent discovery events
            self.expected_events.add("agent_discovery")
            self.expected_events.add("agent_ready")
            
            # Calculator service discovery events
            for i in range(1, 4):
                self.expected_events.add(f"calculator_service_{i}_discovery")
                self.expected_events.add(f"calculator_service_{i}_ready")
            
            # Function discovery events
            self.expected_events.add("function_discovery")
            
            # Function call events
            self.expected_events.add("function_call_start")
            self.expected_events.add("function_call_complete")
    
    def _lifecycle_callback(self, data):
        """Handle received lifecycle events."""
        try:
            with self.events_lock:
                self.events.append(("lifecycle", data))
                self._check_expected_event(data)
                
        except Exception as e:
            self.logger.error(f"Error processing lifecycle event: {e}")
    
    def _chain_callback(self, data):
        """Handle received chain events."""
        try:
            with self.events_lock:
                self.events.append(("chain", data))
                self._check_expected_event(data)
                
        except Exception as e:
            self.logger.error(f"Error processing chain event: {e}")
    
    def _check_expected_event(self, event_data):
        """Check if the event matches any expected events and remove them from the list."""
        try:
            # Extract data from the event
            capabilities = event_data.get("capabilities", {})
            reason = event_data.get("reason", "")
            
            # Convert capabilities to dict if it's a string list
            if isinstance(capabilities, list):
                capabilities = {"capabilities": capabilities}
            
            self.logger.debug(f"\nRAW DDS DATA:")
            self.logger.debug(f"Capabilities: {capabilities}")
            self.logger.debug(f"Reason: {reason}")
            
            # Check for calculator service discovery
            if "Function app" in reason and "discovered" in reason:
                service_id = reason.split()[-1]
                for i in range(1, 4):
                    event_name = f"calculator_service_{i}_discovery"
                    if event_name in self.expected_events:
                        self.logger.info(f"✅ Found calculator service {i} discovery event")
                        self.expected_events.remove(event_name)
                        break
                    
            # Check for calculator service ready state
            if "All CalculatorService functions published and ready for calls" in reason:
                for i in range(1, 4):
                    event_name = f"calculator_service_{i}_ready"
                    if event_name in self.expected_events:
                        self.logger.info(f"✅ Found calculator service {i} ready event")
                        self.expected_events.remove(event_name)
                        break
                    
            # Check for agent discovery
            if "TestAgent" in reason and "discovered" in reason:
                if "agent_discovery" in self.expected_events:
                    self.logger.info("✅ Found agent discovery event")
                    self.expected_events.remove("agent_discovery")
                
            # Check for agent ready state
            if "TestAgent" in reason and "ready for requests" in reason:
                if "agent_ready" in self.expected_events:
                    self.logger.info("✅ Found agent ready event")
                    self.expected_events.remove("agent_ready")
                
            # Check for function discovery
            if "Function 'add'" in reason and "available" in reason:
                if "function_discovery" in self.expected_events:
                    self.logger.info("✅ Found add function discovery event")
                    self.expected_events.remove("function_discovery")
                
            # Check for function call start
            if "Processing function call: add" in reason:
                if "function_call_start" in self.expected_events:
                    self.logger.info("✅ Found function call start event")
                    self.expected_events.remove("function_call_start")
                
            # Check for function call completion
            if "Completed function call: add" in reason:
                if "function_call_complete" in self.expected_events:
                    self.logger.info("✅ Found function call complete event")
                    self.expected_events.remove("function_call_complete")
                
            self.logger.debug(f"Remaining expected events: {self.expected_events}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error checking event: {str(e)}")
            return False

    def run_test(self):
        """Run the monitoring test."""
        try:
            self.logger.info("Starting monitoring test...")
            
            # Set initial timeout
            timeout = time.time() + 60  # 60 second timeout
            
            # Wait for all expected events
            while self.expected_events and time.time() < timeout:
                # Check if we've received all events
                if not self.expected_events:
                    break
                
                # Log remaining events every 5 seconds
                if int(time.time()) % 5 == 0:
                    self.logger.debug(f"Remaining expected events: {self.expected_events}")
                
                time.sleep(0.1)  # Small sleep to prevent busy waiting
            
            # Check if we got all events
            if not self.expected_events:
                self.logger.info("All expected events received successfully!")
            else:
                self.logger.error(f"❌ Test timed out waiting for events: {self.expected_events}")
                
            # Print test summary
            self._print_test_summary()
            
            return len(self.expected_events) == 0
            
        except Exception as e:
            self.logger.error(f"Error during test execution: {e}")
            traceback.print_exc()
            return False
        finally:
            self.logger.info("Cleaning up DDS resources...")
            try:
                self.close()
                self.logger.info("Cleanup completed successfully")
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")

    def _print_test_summary(self):
        """Print a summary of the test results."""
        with self.events_lock:
            total_events = len(self.events)
            lifecycle_events = sum(1 for e in self.events if e[0] == "lifecycle")
            chain_events = sum(1 for e in self.events if e[0] == "chain")
            
            self.logger.info("\nTest Summary:")
            self.logger.info("=============")
            self.logger.info(f"Total events received: {total_events}")
            self.logger.info(f"Lifecycle events: {lifecycle_events}")
            self.logger.info(f"Chain events: {chain_events}")
            self.logger.info(f"Missing events: {len(self.expected_events)}")
            self.logger.info("=============")

    def close(self):
        """Clean up resources."""
        self.logger.info("Cleaning up DDS resources...")
        try:
            # Helper function to safely close a DDS entity
            def safe_close(entity, entity_name):
                try:
                    if hasattr(self, entity) and getattr(self, entity) is not None:
                        if not getattr(self, entity).closed:
                            getattr(self, entity).close()
                except Exception as e:
                    # Log at debug level since this is expected cleanup behavior
                    self.logger.debug(f"Note: {entity_name} was already closed or had cleanup error: {e}")

            # Close readers first
            safe_close('lifecycle_reader', 'lifecycle reader')
            safe_close('chain_reader', 'chain reader')
            
            # Then close topics
            safe_close('lifecycle_topic', 'lifecycle topic')
            safe_close('chain_topic', 'chain topic')
            
            # Then subscriber
            safe_close('subscriber', 'subscriber')
            
            # Finally close participant
            safe_close('participant', 'participant')
            
            self.logger.info("Cleanup completed successfully")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            traceback.print_exc()

def main():
    """Main entry point for the monitoring test."""
    parser = argparse.ArgumentParser(description="Test monitoring functionality")
    parser.add_argument("--domain", type=int, default=0, help="DDS domain ID")
    parser.add_argument("--timeout", type=int, default=60, help="Test timeout in seconds")
    args = parser.parse_args()
    
    test = MonitoringTest(domain_id=args.domain)
    try:
        success = test.run_test()
        sys.exit(0 if success else 1)
    finally:
        test.close()

if __name__ == "__main__":
    main() 
```

## run_scripts/math_test_agent.py

**Author:** Jason

```python
#!/usr/bin/env python3
import logging
import asyncio
import sys
import traceback
import time
import uuid
import json
import rti.connextdds as dds
from genesis_lib.monitored_agent import MonitoredAgent
import signal

# Configure root logger to handle all loggers
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Set all genesis_lib loggers to DEBUG
for name in ['genesis_lib', 'genesis_lib.agent', 'genesis_lib.monitored_agent', 'genesis_lib.genesis_app']:
    logging.getLogger(name).setLevel(logging.DEBUG)

# Get our specific logger
logger = logging.getLogger("MathTestAgent")
logger.setLevel(logging.DEBUG)

# Test log message
print("🔍 TRACE: Script starting, before any initialization (print)")
logger.info("🔍 TRACE: Script starting, before any initialization (logger)")

class MathTestAgent(MonitoredAgent):
    """
    A monitored agent for testing concurrent Interface <-> Agent RPC
    using simple math operations.
    """
    print("🏗️ TRACE: Starting MathTestAgent initialization... (print)")
    logger.info("🏗️ TRACE: Starting MathTestAgent initialization... (logger)")
    def __init__(self):
        logger.info("🏗️ TRACE: Starting MathTestAgent initialization...")
        try:
            super().__init__(
                agent_name="MathTestAgent",
                base_service_name="MathTestService",
                agent_type="TEST_AGENT",
                agent_id=str(uuid.uuid4())
            )
            logger.info("✅ TRACE: MonitoredAgent base class initialized")
            self._shutdown_event = asyncio.Event()
            logger.info("✅ TRACE: MathTestAgent initialization complete")
        except Exception as e:
            logger.error(f"💥 TRACE: Error during MathTestAgent initialization: {e}")
            logger.error(f"Stack trace: {traceback.format_exc()}")

    async def process_request(self, request):
        """Process math operation requests"""
        try:
            # Get the message field from the dictionary
            message = request.get("message")
            if message is None:
                raise ValueError("Request dictionary missing 'message' key")
            
            # Parse request JSON (message itself is expected to be a JSON string)
            request_data = json.loads(message)
            
            # Extract operation and numbers from request
            operation = request_data["operation"]
            x = request_data["x"]
            y = request_data["y"]
            conversation_id = request_data["conversation_id"]
            
            # Perform operation
            result = 0
            if operation == "add":
                result = x + y
            elif operation == "multiply":
                result = x * y
            elif operation == "divide":
                if y == 0:
                    raise ValueError("Cannot divide by zero")
                result = x / y
            elif operation == "subtract":
                result = x - y
            else:
                raise ValueError(f"Unsupported operation: {operation}")
                
            # Return result
            return {
                "message": str(result),
                "status": 0,
                "conversation_id": conversation_id
            }
        except Exception as e:
            return {
                "message": f"Error processing request: {str(e)}",
                "status": 1,
                "conversation_id": ""
            }

async def main():
    """Main function"""
    try:
        # Create and run agent
        agent = MathTestAgent()
        logger.info("✅ TRACE: Agent created, starting run...")
        await agent.run()
    except KeyboardInterrupt:
        logger.info("👋 TRACE: Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"💥 TRACE: Error in main: {e}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
    finally:
        # Clean shutdown
        if 'agent' in locals():
            logger.info("🧹 TRACE: Cleaning up agent...")
            await agent.close()
            logger.info("✅ TRACE: Agent cleanup complete")

if __name__ == "__main__":
    asyncio.run(main()) 
```

## run_scripts/baseline_test_agent.py

**Author:** Jason

```python
#!/usr/bin/env python3
import logging
import asyncio
import sys
import traceback
import time
from genesis_lib.monitored_agent import MonitoredAgent

# Configure logging with detailed format
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
logger = logging.getLogger("BaselineTestAgent")

class BaselineTestAgent(MonitoredAgent):
    """
    A simple monitored agent for baseline testing of Interface <-> Agent RPC
    using the 'ChatGPT' service name and existing request/reply types.
    """
    def __init__(self):
        logger.info("🚀 TRACE: Starting BaselineTestAgent initialization...")
        try:
            super().__init__(
                agent_name="BaselineTestAgent",
                service_name="ChatGPT",  # Use the service name the interface expects
                agent_type="AGENT",      # Standard agent type
                description="Baseline agent for testing Interface RPC"
            )
            logger.info("✅ TRACE: BaselineTestAgent initialized successfully")
        except Exception as e:
            logger.error(f"💥 TRACE: Error during initialization: {e}")
            logger.error(f"Stack trace:\n{traceback.format_exc()}")
            raise

    async def _process_request(self, request) -> dict:
        """
        Handles incoming requests for the 'ChatGPT' service.
        Returns a fixed joke response.
        """
        logger.info(f"📥 TRACE: Received request: {request}")
        try:
            # Extract message and conversation_id from the DynamicData object
            message = request['message']
            conversation_id = request['conversation_id']
            logger.info(f"📝 TRACE: Processing request - message='{message}', conversation_id='{conversation_id}'")

            # Fixed joke response
            reply_message = "Why don't scientists trust atoms? Because they make up everything!"
            status = 0 # Success

            logger.info(f"📤 TRACE: Sending reply - message='{reply_message}', status={status}")
            # Return structure must match ChatGPTReply
            return {
                'message': reply_message,
                'status': status,
                'conversation_id': conversation_id # Echo back conversation ID if present
            }
        except Exception as e:
            logger.error(f"💥 TRACE: Error processing request: {e}")
            logger.error(f"Stack trace:\n{traceback.format_exc()}")
            raise

async def main():
    logger.info("🎬 TRACE: Starting main()")
    agent = None
    try:
        logger.info("🏗️ TRACE: Creating BaselineTestAgent instance")
        agent = BaselineTestAgent()
        
        logger.info("🔄 TRACE: Starting agent event loop")
        shutdown_event = asyncio.Event()
        
        # The agent's request handling runs via the Replier's listener mechanism,
        # which is set up in the base class __init__. We just need to keep the event loop running.
        logger.info("⏳ TRACE: Waiting for shutdown signal...")
        await shutdown_event.wait() # Keep running until interrupted
        
    except KeyboardInterrupt:
        logger.info("👋 TRACE: KeyboardInterrupt received, shutting down.")
    except Exception as e:
        logger.error(f"💥 TRACE: Fatal error in main: {e}")
        logger.error(f"Stack trace:\n{traceback.format_exc()}")
    finally:
        if agent:
            logger.info("🧹 TRACE: Closing agent resources...")
            await agent.close()
            logger.info("✅ TRACE: Agent closed successfully")
        logger.info("👋 TRACE: main() ending")

if __name__ == "__main__":
    logger.info("🚀 TRACE: Script starting")
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"💥 TRACE: Script error: {e}")
        logger.error(f"Stack trace:\n{traceback.format_exc()}")
    logger.info("👋 TRACE: Script ending") 
```

## run_scripts/simpleGenesisAgent.py

**Author:** Jason

```python
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
import asyncio
import logging # Added for script-level logging
import argparse # Added for command-line arguments

# Configure basic logging for this script
# logging.basicConfig(
#     level=logging.INFO, 
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
logger = logging.getLogger("SimpleGenesisAgentScript")

class SimpleGenesisAgent(OpenAIGenesisAgent):
    def __init__(self, service_instance_tag: str = None): # Added service_instance_tag
        # Initialize the base class with our specific configuration
        super().__init__(
            model_name="gpt-4o",  # You can change this to your preferred model
            classifier_model_name="gpt-4o-mini",  # You can change this to your preferred model
            agent_name="SimpleGenesisAgentForTheWin",  # Friendly name for this agent instance
            # base_service_name="MyCustomChatService", # Optional: Override default OpenAIChat
            service_instance_tag=service_instance_tag,     # Pass the tag
            description="A simple agent that listens for messages via Genesis interface and processes them.", 
            enable_tracing=True  # Enable tracing for testing
        )
        # The base class (OpenAIGenesisAgent) also has its own logging for initialization details
        logger.info(f"'{self.agent_name}' instance (tag: {service_instance_tag or 'default'}) created. RPC Service: '{self.rpc_service_name}'. Ready to connect to Genesis services.")

async def main(tag: str = None, verbose: bool = False): # Added verbose parameter
    print(f"###### AGENT MAIN STARTED - Tag: {tag}, Verbose: {verbose} ######") 
    # ---- START DIAGNOSTIC BLOCK ----
    # import logging # logging is already imported at the top of the file
    root_logger = logging.getLogger()
    print(f"###### Root logger level: {logging.getLevelName(root_logger.level)} ######")
    print(f"###### Root logger handlers: {root_logger.handlers} ######")
    script_logger = logging.getLogger("SimpleGenesisAgentScript")
    print(f"###### Script logger effective level: {logging.getLevelName(script_logger.getEffectiveLevel())} ######")
    print(f"###### Script logger handlers: {script_logger.handlers} ######")
    print(f"###### Script logger propagate: {script_logger.propagate} ######")
    # ---- END DIAGNOSTIC BLOCK (BEFORE) ----
    log_level = logging.DEBUG if verbose else logging.INFO

    # logging.basicConfig(  # This was found to be ineffective as root is already configured
    #     level=log_level, 
    #     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    # )
    # ---- REMOVE "AFTER basicConfig" DIAGNOSTICS ----
    # print(f"###### Root logger level AFTER basicConfig: {logging.getLevelName(logging.getLogger().level)} ######")
    # print(f"###### Root logger handlers AFTER basicConfig: {logging.getLogger().handlers} ######")

    # Explicitly set the root logger's level. 
    # The existing handler (<StreamHandler <stderr> (NOTSET)>) should pick this up.
    logging.getLogger().setLevel(log_level)
    print(f"###### Root logger level AFTER EXPLICIT SET: {logging.getLevelName(logging.getLogger().level)} ######") # New diagnostic

    # If verbose mode is enabled for the script, also make genesis_lib verbose.
    if verbose:
        # Explicitly set the genesis_lib logger's level.
        # The existing handler (<StreamHandler <stderr> (NOTSET)>) should pick this up.
        genesis_lib_logger = logging.getLogger("genesis_lib")
        genesis_lib_logger.setLevel(log_level)
        print(f"###### genesis_lib logger level AFTER EXPLICIT SET: {logging.getLevelName(genesis_lib_logger.level)} ######") # New diagnostic

    agent_display_name = f"SimpleGenesisAgent{f'-{tag}' if tag else ''}"
    logger.info(f"Initializing '{agent_display_name}' (Log Level: {logging.getLevelName(log_level)})...")
    # Initialize the agent
    agent = SimpleGenesisAgent(service_instance_tag=tag) # Pass tag to constructor
    
    try:
        # Give some time for initialization and announcement propagation (e.g., DDS discovery)
        logger.info("Allowing 2 seconds for agent components to initialize and announce themselves...")
        await asyncio.sleep(2)
        
        logger.info(f"Starting '{agent.agent_name}' main loop. It will now listen for messages via the Genesis interface.")
        logger.info("Press Ctrl+C to stop the agent.")
        
        # The MonitoredAgent (base of OpenAIGenesisAgent) should provide self.app (a GenesisApp instance)
        # which has a run() method to start all services, including DDS listeners.
        # This call is typically blocking and will keep the agent alive.
        # if hasattr(agent, 'app') and callable(getattr(agent.app, 'run', None)):
        #     await agent.app.run()
        # else:
        #     logger.error(f"Could not start '{agent.agent_name}' main loop: 'agent.app.run()' method not found or not callable.")
        #     logger.info("The agent will not be able to receive messages from the Genesis interface.")
            # If app.run() is not available or not blocking, the script might exit or not function as intended.
            # For a robust agent, ensure the underlying GenesisApp framework correctly provides this.

        # GenesisAgent (base class of MonitoredAgent) provides the run() method
        if hasattr(agent, 'run') and callable(getattr(agent, 'run', None)):
            await agent.run() # Corrected: Call agent.run() instead of agent.app.run()
        else:
            logger.error(f"Could not start '{agent.agent_name}' main loop: 'agent.run()' method not found or not callable.")
            logger.info("The agent will not be able to receive messages from the Genesis interface.")

    except KeyboardInterrupt:
        logger.info(f"'{agent.agent_name}' received KeyboardInterrupt. Initiating shutdown...")
    except Exception as e:
        logger.error(f"An unexpected error occurred in '{agent.agent_name}' main loop: {e}", exc_info=True)
    finally:
        logger.info(f"Closing '{agent.agent_name}' and releasing resources...")
        if 'agent' in locals() and agent: # Ensure agent was successfully initialized
            await agent.close()
        logger.info(f"'{agent.agent_name}' has been shut down.")

if __name__ == "__main__":
    # Run the async main function
    # asyncio.run(main()) # Old way

    parser = argparse.ArgumentParser(description="Run the SimpleGenesisAgent.")
    parser.add_argument(
        "--tag",
        type=str,
        default=None,
        help="An optional instance tag to make the agent's RPC service name unique (e.g., 'instance1')."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level) for the agent script and Genesis libraries."
    )
    args = parser.parse_args()

    asyncio.run(main(tag=args.tag, verbose=args.verbose)) # Pass verbose flag to main

```

## docs/github_comments.py

**Author:** 

```python
import requests
from datetime import datetime, timedelta
import os
from typing import List, Dict
import json

def get_github_comments(repo_owner: str, repo_name: str, token: str) -> List[Dict]:
    """
    Fetch comments from GitHub issues and pull requests for the last two months.
    """
    # Calculate date two months ago
    two_months_ago = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # GitHub API base URL
    base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    all_comments = []
    
    # Get issues and their comments
    issues_url = f"{base_url}/issues"
    params = {
        "state": "all",
        "since": two_months_ago,
        "per_page": 100
    }
    
    response = requests.get(issues_url, headers=headers, params=params)
    issues = response.json()
    
    for issue in issues:
        # Get comments for each issue
        comments_url = f"{base_url}/issues/{issue['number']}/comments"
        comments_response = requests.get(comments_url, headers=headers)
        comments = comments_response.json()
        
        for comment in comments:
            comment_date = datetime.strptime(comment['created_at'], "%Y-%m-%dT%H:%M:%SZ")
            if comment_date >= datetime.strptime(two_months_ago, "%Y-%m-%dT%H:%M:%SZ"):
                all_comments.append({
                    'type': 'issue_comment',
                    'issue_number': issue['number'],
                    'issue_title': issue['title'],
                    'author': comment['user']['login'],
                    'body': comment['body'],
                    'created_at': comment['created_at']
                })
    
    # Get pull requests and their comments
    prs_url = f"{base_url}/pulls"
    prs_response = requests.get(prs_url, headers=headers, params=params)
    prs = prs_response.json()
    
    for pr in prs:
        # Get comments for each PR
        comments_url = f"{base_url}/pulls/{pr['number']}/comments"
        comments_response = requests.get(comments_url, headers=headers)
        comments = comments_response.json()
        
        for comment in comments:
            comment_date = datetime.strptime(comment['created_at'], "%Y-%m-%dT%H:%M:%SZ")
            if comment_date >= datetime.strptime(two_months_ago, "%Y-%m-%dT%H:%M:%SZ"):
                all_comments.append({
                    'type': 'pr_comment',
                    'pr_number': pr['number'],
                    'pr_title': pr['title'],
                    'author': comment['user']['login'],
                    'body': comment['body'],
                    'created_at': comment['created_at']
                })
    
    return sorted(all_comments, key=lambda x: x['created_at'], reverse=True)

def generate_comment_history(comments: List[Dict], output_file: str):
    """
    Generate a markdown file with the comment history.
    """
    with open(output_file, 'w') as f:
        f.write("# GitHub Comment History (Last 2 Months)\n\n")
        
        for comment in comments:
            f.write(f"## {comment['type'].upper()} - {comment.get('issue_title', comment.get('pr_title', ''))}\n\n")
            f.write(f"**Author:** {comment['author']}\n")
            f.write(f"**Date:** {comment['created_at']}\n")
            f.write(f"**Issue/PR #:** {comment.get('issue_number', comment.get('pr_number', ''))}\n\n")
            f.write(f"{comment['body']}\n\n")
            f.write("---\n\n")

if __name__ == "__main__":
    # Get GitHub token from environment variable
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("Please set the GITHUB_TOKEN environment variable")
        exit(1)
    
    # Replace these with your repository details
    repo_owner = "RTI"  # Replace with actual owner
    repo_name = "Genesis_LIB"  # Replace with actual repo name
    
    comments = get_github_comments(repo_owner, repo_name, token)
    generate_comment_history(comments, "docs/notes/comment_history.md") 
```

## examples/HelloWorld/hello_world_agent.py

**Author:** Jason

```python
#!/usr/bin/env python3

"""
HelloWorldAgent - A simple example of a Genesis agent that uses OpenAI capabilities
to interact with a calculator service.
"""

import logging
import asyncio
import sys
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hello_world_agent")

class HelloWorldAgent(OpenAIGenesisAgent):
    """A simple agent that can use the calculator service."""
    
    def __init__(self):
        """Initialize the HelloWorldAgent."""
        super().__init__(
            model_name="gpt-4o",
            classifier_model_name="gpt-4o-mini",
            agent_name="HelloWorldAgent",
            description="A simple agent that can perform basic arithmetic operations",
            enable_tracing=True
        )
        logger.info("HelloWorldAgent initialized")

async def main():
    """Run the HelloWorldAgent with test calculations."""
    try:
        # Create and start agent
        agent = HelloWorldAgent()
        logger.info("Agent started successfully")
        
        # Give some time for initialization
        await asyncio.sleep(2)
        
        # Get message from command line argument or use default
        message = sys.argv[1] if len(sys.argv) > 1 else "What is 42 plus 24?"
        
        # Process the message
        response = await agent.process_message(message)
        print(f"Agent response: {response}")
        
    except Exception as e:
        logger.error(f"Error in agent: {str(e)}")
        raise
    finally:
        if 'agent' in locals():
            await agent.close()

if __name__ == "__main__":
    asyncio.run(main()) 
```

## examples/HelloWorld/hello_world_service.py

**Author:** Jason

```python
#!/usr/bin/env python3

"""
A simple calculator service that demonstrates basic Genesis service functionality.
Provides basic arithmetic operations: add and multiply.
"""

import logging
import asyncio
from typing import Dict, Any
from genesis_lib.enhanced_service_base import EnhancedServiceBase
from genesis_lib.decorators import genesis_function

# Configure logging to show INFO level messages
# This helps with debugging and monitoring service operations
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hello_calculator")

class HelloCalculator(EnhancedServiceBase):
    """A simple calculator service demonstrating Genesis functionality."""
    
    def __init__(self):
        """Initialize the calculator service."""
        # Initialize the base service with a name and capabilities
        # The capabilities list helps other services discover what this service can do
        super().__init__(
            "HelloCalculator",
            capabilities=["calculator", "math"]
        )
        logger.info("HelloCalculator service initialized")
        # Advertise the available functions to the Genesis network
        # This makes the functions discoverable by other services
        self._advertise_functions()
        logger.info("Functions advertised")

    # The @genesis_function decorator marks this as a callable function in the Genesis network
    # The function signature (x: float, y: float) and docstring Args section must match exactly
    # Both are used by Genesis to generate the function schema and validate calls
    # Note: Comments must be above the decorator, not in the docstring
    @genesis_function()
    async def add(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Add two numbers together.
        
        Args:
            x: First number to add
            y: Second number to add
            request_info: Optional request metadata
            
        Returns:
            Dict containing the result of the addition
            
        Examples:
            >>> await add(5, 3)
            {'result': 8}
        """
        # Log the incoming request for debugging and monitoring
        logger.info(f"Received add request: x={x}, y={y}")
        
        try:
            # Perform the addition operation
            result = x + y
            # Log the result for debugging
            logger.info(f"Add result: {result}")
            # Return the result in a standardized format
            return {"result": result}
        except Exception as e:
            # Log any errors that occur during the operation
            logger.error(f"Error in add operation: {str(e)}")
            raise

    # The @genesis_function decorator marks this as a callable function in the Genesis network
    # The function signature (x: float, y: float) and docstring Args section must match exactly
    # Both are used by Genesis to generate the function schema and validate calls
    # Note: Comments must be above the decorator, not in the docstring
    @genesis_function()
    async def multiply(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Multiply two numbers together.
        
        Args:
            x: First number to multiply
            y: Second number to multiply
            request_info: Optional request metadata
            
        Returns:
            Dict containing the result of the multiplication
            
        Examples:
            >>> await multiply(5, 3)
            {'result': 15}
        """
        # Log the incoming request for debugging and monitoring
        logger.info(f"Received multiply request: x={x}, y={y}")
        
        try:
            # Perform the multiplication operation
            result = x * y
            # Log the result for debugging
            logger.info(f"Multiply result: {result}")
            # Return the result in a standardized format
            return {"result": result}
        except Exception as e:
            # Log any errors that occur during the operation
            logger.error(f"Error in multiply operation: {str(e)}")
            raise

def main():
    """Run the calculator service."""
    # Initialize and start the service
    logger.info("Starting HelloCalculator service")
    try:
        # Create an instance of the calculator service
        service = HelloCalculator()
        # Run the service using asyncio
        asyncio.run(service.run())
    except KeyboardInterrupt:
        # Handle graceful shutdown on Ctrl+C
        logger.info("Shutting down HelloCalculator service")

if __name__ == "__main__":
    main() 
```

## examples/ExampleInterface/example_agent.py

**Author:** Jason

```python
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
import asyncio
import logging # Added for script-level logging
import argparse # Added for command-line arguments

# Configure basic logging for this script
# The initial logging.basicConfig call has been removed as it's better to
# configure logging once in the main execution block, especially when
# log levels might depend on command-line arguments.
# logging.basicConfig(
#     level=logging.INFO, 
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )

# Get a logger instance for this specific module.
# This allows for more granular control over logging if needed elsewhere.
logger = logging.getLogger("SimpleGenesisAgentScript")

class SimpleGenesisAgent(OpenAIGenesisAgent):
    """
    A simple example of an agent built using the OpenAIGenesisAgent base class.
    This agent demonstrates how to initialize and run an agent that can connect
    to the Genesis messaging infrastructure. It can be given an instance tag
    to differentiate multiple running instances.
    """
    def __init__(self, service_instance_tag: str = None): # Added service_instance_tag
        """
        Initializes the SimpleGenesisAgent.

        Args:
            service_instance_tag (str, optional): An optional tag to make the
                agent's underlying RPC service name unique. This is useful when
                running multiple instances of the same agent. Defaults to None.
        """
        # Initialize the base class (OpenAIGenesisAgent) with specific configurations.
        super().__init__(
            model_name="gpt-4o",  # Specifies the primary OpenAI model to be used.
            classifier_model_name="gpt-4o-mini",  # Specifies the OpenAI model for classification tasks.
            agent_name="SimpleGenesisAgentForTheWin",  # A friendly, descriptive name for this agent instance.
            # base_service_name="MyCustomChatService", # Optional: Uncomment to override the default OpenAIChat service name.
            service_instance_tag=service_instance_tag,     # Pass the tag to the base class for service name uniqueness.
            description="A simple agent that listens for messages via Genesis interface and processes them.", 
            enable_tracing=True  # Enable OpenTelemetry tracing for observability.
        )
        # Log that the agent instance has been created.
        # The base class OpenAIGenesisAgent also performs its own logging during initialization.
        logger.info(f"'{self.agent_name}' instance (tag: {service_instance_tag or 'default'}) created. RPC Service: '{self.rpc_service_name}'. Ready to connect to Genesis services.")

async def main(tag: str = None, verbose: bool = False): # Added verbose parameter
    """
    The main asynchronous function to set up logging, initialize, and run the SimpleGenesisAgent.

    Args:
        tag (str, optional): An instance tag for the agent, passed from command-line arguments.
                             Defaults to None.
        verbose (bool, optional): If True, sets logging to DEBUG level for this script
                                  and the `genesis_lib`. Defaults to False (INFO level).
    """
    # Determine the logging level based on the verbose flag.
    log_level = logging.DEBUG if verbose else logging.INFO

    # Configure the root logger.
    # This is the primary point of logging configuration for the application.
    # It's important to set this up before any loggers are used extensively.
    logging.basicConfig(
        level=log_level, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True # `force=True` ensures that if the root logger was already configured (e.g. by a library), this configuration will override it.
    )
    # The explicit setLevel on root logger after basicConfig is redundant if basicConfig is called with `force=True` and `level`.
    # logging.getLogger().setLevel(log_level)

    # If verbose mode is enabled, also set the `genesis_lib` logger to DEBUG.
    # This allows for more detailed output from the underlying Genesis library components.
    if verbose:
        genesis_lib_logger = logging.getLogger("genesis_lib")
        genesis_lib_logger.setLevel(logging.DEBUG) # Set to DEBUG
        # It's good practice to also ensure handlers are present if changing levels directly,
        # but basicConfig(force=True) should have set up a handler on the root logger
        # that child loggers like 'genesis_lib' will propagate to by default.
        logger.debug("Verbose logging enabled for 'genesis_lib'.")


    # Construct a display name for the agent, incorporating the tag if provided.
    agent_display_name = f"SimpleGenesisAgent{f'-{tag}' if tag else ''}"
    logger.info(f"Initializing '{agent_display_name}' (Log Level: {logging.getLevelName(log_level)})...")
    
    # Instantiate the agent.
    agent = SimpleGenesisAgent(service_instance_tag=tag) # Pass the tag to the agent's constructor.
    
    try:
        # A short delay to allow for system components (like DDS discovery) to initialize
        # and for the agent's services to be announced on the network.
        logger.info("Allowing 2 seconds for agent components to initialize and announce themselves...")
        await asyncio.sleep(2)
        
        logger.info(f"Starting '{agent.agent_name}' main loop. It will now listen for messages via the Genesis interface.")
        logger.info("Press Ctrl+C to stop the agent.")
        
        # The `GenesisAgent` class (a base for `OpenAIGenesisAgent`) provides a `run()` method.
        # This method typically starts all necessary background tasks, such as listening for
        # incoming RPC requests or messages, and blocks until the agent is shut down.
        if hasattr(agent, 'run') and callable(getattr(agent, 'run', None)):
            await agent.run() # This is the primary call to start the agent's active lifecycle.
        else:
            # This case should ideally not be reached if using the standard GenesisAgent hierarchy.
            logger.error(f"Could not start '{agent.agent_name}' main loop: 'agent.run()' method not found or not callable.")
            logger.info("The agent will not be able to receive messages from the Genesis interface.")

    except KeyboardInterrupt:
        # Handle graceful shutdown on Ctrl+C.
        logger.info(f"'{agent.agent_name}' received KeyboardInterrupt. Initiating shutdown...")
    except Exception as e:
        # Log any other unexpected exceptions that occur during the agent's runtime.
        logger.error(f"An unexpected error occurred in '{agent.agent_name}' main loop: {e}", exc_info=True)
    finally:
        # This block ensures that resources are cleaned up regardless of how the try block exits.
        logger.info(f"Closing '{agent.agent_name}' and releasing resources...")
        if 'agent' in locals() and agent: # Check if 'agent' variable exists and was initialized.
            # The `close()` method should handle shutting down services, closing connections, etc.
            await agent.close()
        logger.info(f"'{agent.agent_name}' has been shut down.")

if __name__ == "__main__":
    # This block executes when the script is run directly.
    
    # Set up an argument parser to handle command-line options.
    parser = argparse.ArgumentParser(description="Run the SimpleGenesisAgent.")
    parser.add_argument(
        "--tag",
        type=str,
        default=None,
        help="An optional instance tag to make the agent's RPC service name unique (e.g., 'instance1')."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true", # If this flag is present, args.verbose will be True.
        help="Enable verbose logging (DEBUG level) for the agent script and Genesis libraries."
    )
    args = parser.parse_args() # Parse the command-line arguments.

    # Run the main asynchronous function using asyncio.run().
    # Pass the parsed 'tag' and 'verbose' arguments to the main function.
    asyncio.run(main(tag=args.tag, verbose=args.verbose))

```

## examples/ExampleInterface/example_interface.py

**Author:** Jason

```python
import asyncio
import logging
import sys
import argparse # Added for command-line arguments
from genesis_lib.monitored_interface import MonitoredInterface
from genesis_lib.logging_config import set_genesis_library_log_level # Import the new utility

# Get a logger instance for this specific module.
# The actual configuration (level, formatters, handlers) will be done in the main() function.
logger = logging.getLogger("SimpleGenesisInterfaceCLI")

# Define a constant for the interface's own name.
# This can be used for identification in logs or discovery mechanisms if needed.
INTERFACE_NAME = "SimpleCLI-111"

# The AGENT_SERVICE_NAME is no longer a fixed target. Instead, the interface
# will discover available agents and allow the user to select one.

async def main(verbose: bool = False): # Added verbose parameter
    """
    The main asynchronous function to set up logging, initialize, and run the 
    Simple Genesis Interface Command Line Interface (CLI).

    This CLI allows a user to discover and connect to a Genesis agent, and then
    send messages to it interactively.

    Args:
        verbose (bool, optional): If True, sets logging to DEBUG level for this script
                                  and the `genesis_lib`. Defaults to False (INFO level).
    """
    # Determine the logging level based on the verbose flag.
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Configure basic logging for the application script.
    # This sets the default logging level for all loggers in the application
    # unless they are explicitly overridden.
    logging.basicConfig(
        level=log_level, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True # `force=True` ensures that if the root logger was already configured, this configuration will override it.
    )

    # If verbose mode is enabled for this script, also set the `genesis_lib` 
    # loggers to DEBUG level. This provides more detailed output from the library.
    if verbose:
        set_genesis_library_log_level(logging.DEBUG)
        logger.debug("Verbose logging enabled for 'genesis_lib'.")
    # If not verbose, `genesis_lib` loggers will typically inherit the level set by
    # the `logging.basicConfig` call (e.g., INFO).

    logger.info(f"Initializing '{INTERFACE_NAME}' (Log Level: {logging.getLevelName(log_level)})...")
    
    # Initialize the MonitoredInterface.
    # `interface_name` is a friendly name for this interface instance.
    # `service_name` here can be generic, as the specific agent service to connect to
    # will be determined by user selection from discovered agents.
    interface = MonitoredInterface(
        interface_name=INTERFACE_NAME,
        service_name="GenericInterfaceService" # A generic name for this interface service instance.
    )

    # Variables to store details of the agent the user selects to connect to.
    target_agent_id = None
    target_agent_service_name = None
    connected_agent_name = "N/A" # For display purposes once connected.

    try:
        # Initial phase: Wait for agent discovery.
        # The `_agent_found_event` is an asyncio.Event within MonitoredInterface that gets set
        # when the first agent advertisement is received.
        logger.info("Waiting for any agent(s) to become available (up to 30s)...")
        try:
            # Wait for the event to be set, with a timeout to prevent indefinite blocking.
            await asyncio.wait_for(interface._agent_found_event.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            logger.error("Timeout: No agent discovery signal received within 30 seconds. Exiting.")
            await interface.close() # Ensure resources are released.
            return

        # Once the first agent is found, allow a brief moment for other agents that might be
        # starting up simultaneously to also announce themselves.
        logger.info("First agent(s) found. Waiting a moment for others to appear...")
        await asyncio.sleep(2)

        # Check if any agents are actually available in the interface's tracking.
        if not interface.available_agents:
            logger.error("No agents were discovered even after waiting. Exiting.")
            await interface.close()
            return

        # Agent selection phase.
        logger.info("Available agents:")
        # Convert the dictionary of available agents to a list for indexed selection.
        agent_list = list(interface.available_agents.values())
        for i, agent_info in enumerate(agent_list):
            # Display information about each discovered agent to the user.
            # `prefered_name` is usually the `agent_name` set by the agent.
            # `instance_id` is a unique identifier for the agent instance.
            # `service_name` is the RPC service name the agent is offering.
            print(f"  {i+1}. Name: '{agent_info.get('prefered_name', 'N/A')}', ID: '{agent_info.get('instance_id')}', Service: '{agent_info.get('service_name')}'")

        if not agent_list: # Should be redundant due to the earlier check, but good for safety.
            logger.error("No agents available to select. Exiting.")
            await interface.close()
            return

        # Loop to get valid user input for agent selection.
        selected_index = -1
        while True:
            try:
                # Use asyncio.to_thread to run the blocking input() call in a separate thread,
                # preventing it from blocking the asyncio event loop.
                choice = await asyncio.to_thread(input, "Select agent by number: ")
                selected_index = int(choice) - 1 # Convert to 0-based index.
                if 0 <= selected_index < len(agent_list):
                    selected_agent = agent_list[selected_index]
                    target_agent_id = selected_agent.get('instance_id')
                    target_agent_service_name = selected_agent.get('service_name')
                    connected_agent_name = selected_agent.get('prefered_name', target_agent_id) # Fallback to ID if name is missing.
                    break # Valid selection, exit loop.
                else:
                    print("Invalid selection. Please enter a number from the list.")
            except ValueError:
                print("Invalid input. Please enter a number.")
            except RuntimeError:
                # This can happen if the input stream is closed (e.g., piped input ends).
                logger.warning("Input stream closed during agent selection.")
                await interface.close()
                return
        
        # Ensure that agent details were successfully retrieved after selection.
        if not target_agent_id or not target_agent_service_name:
            logger.error("Failed to select a valid agent or retrieve its details. Exiting.")
            await interface.close()
            return

        logger.info(f"Attempting to connect to agent '{connected_agent_name}' (ID: {target_agent_id}) offering service '{target_agent_service_name}'...")
        
        # Attempt to establish an RPC connection to the selected agent's service.
        connection_successful = await interface.connect_to_agent(
            service_name=target_agent_service_name, # The specific service name of the chosen agent.
            timeout_seconds=10.0 # Timeout for the connection attempt.
        )
        
        # If connection is successful, MonitoredInterface internally sets up the RPC client.
        # Storing `_connected_agent_id` might be used by the interface for context, 
        # e.g. to verify if the connected agent is still among available_agents later.
        if connection_successful:
            interface._connected_agent_id = target_agent_id # Note: direct access to a protected member.
                                                        # Consider if MonitoredInterface should expose a method or property for this.

        if not connection_successful:
            logger.error(f"Failed to establish RPC connection with agent '{connected_agent_name}' for service '{target_agent_service_name}'. Exiting.")
            await interface.close()
            return

        logger.info(f"Successfully connected to agent: '{connected_agent_name}' (Service: '{target_agent_service_name}').")
        print("You can now send messages. Type 'quit' or 'exit' to stop.")

        # Main interaction loop: get user input and send to agent.
        while True:
            try:
                user_input = await asyncio.to_thread(input, f"To [{connected_agent_name}]: ")
            except RuntimeError:
                logger.warning("Input stream closed during message input.")
                break # Exit loop if input stream is closed.
                
            if user_input.lower() in ['quit', 'exit']:
                logger.info("User requested exit.")
                break # Exit loop if user types quit/exit.

            if not user_input: # Skip empty input.
                continue

            # Prepare the request data. The structure depends on what the agent expects.
            # For OpenAIGenesisAgent, it typically expects a dictionary with a "message" key.
            request_data = {"message": user_input}
            logger.info(f"Sending to agent: {request_data}")
            
            # Send the request to the connected agent and await the response.
            response = await interface.send_request(request_data, timeout_seconds=20.0)
            
            if response:
                # Process and display the agent's response.
                # The response structure also depends on the agent; OpenAIGenesisAgent usually
                # returns a dictionary with "message" and "status".
                print(f"Agent response: {response.get('message', 'No message content in response')}")
                if response.get('status', 0) != 0: # Assuming status 0 is success.
                    logger.warning(f"Agent indicated an issue with status: {response.get('status')}")
            else:
                logger.error("No response from agent or request timed out.")
                # Check if the lack of response might be due to the agent disappearing.
                # `available_agents` is updated by the discovery mechanism.
                if interface._connected_agent_id and \
                   interface._connected_agent_id not in interface.available_agents:
                     logger.error("Connection lost: The agent may have departed. Please restart the CLI.")
                     break # Exit loop as connection is lost.

    except KeyboardInterrupt:
        # Handle graceful shutdown on Ctrl+C.
        print("\nKeyboard interrupt received. Shutting down...") # User-facing message for Ctrl+C.
    except Exception as e:
        # Log any other unexpected exceptions.
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        # This block ensures that resources are cleaned up.
        logger.info(f"Closing '{INTERFACE_NAME}' and releasing resources...")
        if 'interface' in locals() and interface: # Check if 'interface' was initialized.
            await interface.close() # Call the interface's close method.
        logger.info(f"'{INTERFACE_NAME}' has been shut down.")

if __name__ == "__main__":
    # This block executes when the script is run directly.

    # Set up an argument parser for command-line options.
    parser = argparse.ArgumentParser(description="Run the Simple Genesis Interface CLI.")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true", # If this flag is present, args.verbose will be True.
        help="Enable verbose logging (DEBUG level) for the CLI and Genesis libraries."
    )
    args = parser.parse_args() # Parse the arguments.

    try:
        # Run the main asynchronous function.
        asyncio.run(main(verbose=args.verbose)) # Pass the verbose flag.
    except KeyboardInterrupt:
        # This handles Ctrl+C if it occurs before or during asyncio.run() setup,
        # though the one inside main() is more typical for interrupting the running loop.
        logger.info("CLI terminated by user at top level.")
    # Exit the script. sys.exit(0) indicates successful termination.
    sys.exit(0)

```

## examples/ExampleInterface/example_service.py

**Author:** Jason

```python
#!/usr/bin/env python3
import logging, asyncio, sys
from typing import Dict, Any
# `datetime` was imported but not used. It can be removed if not needed for future extensions.
# from datetime import datetime 
from genesis_lib.decorators import genesis_function
from genesis_lib.enhanced_service_base import EnhancedServiceBase

# --------------------------------------------------------------------------- #
# Exceptions                                                                  #
# --------------------------------------------------------------------------- #
class CalculatorError(Exception):
    """Base exception for calculator service errors.
    This allows for catching all calculator-specific exceptions with a single except block.
    """
    pass

class InvalidInputError(CalculatorError):
    """Raised when input values are invalid (e.g., not numbers, out of expected range, etc.)."""
    pass

class DivisionByZeroError(CalculatorError):
    """Raised when an attempt is made to divide a number by zero."""
    pass

# --------------------------------------------------------------------------- #
# Service                                                                     #
# --------------------------------------------------------------------------- #

# Configure logging for the calculator service.
# `force=True` is used to ensure this configuration takes precedence if the
# root logger has already been configured by another module (though in a standalone
# service script, this is less likely to be an issue initially).
# Setting the level to DEBUG here means that all debug messages from this logger
# and its children will be processed, provided handlers also allow it.
logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    force=True)  # Force reconfiguration of the root logger

# Get a specific logger instance for this service.
# This allows for more targeted logging control if this service were part of a larger application.
logger = logging.getLogger("calculator_service")
# Explicitly set the logger level. If basicConfig already set the root logger to DEBUG,
# this specific logger would inherit it. However, explicit setting is clearer.
logger.setLevel(logging.DEBUG)

class CalculatorService(EnhancedServiceBase):
    """Implementation of a simple calculator service.
    
    This service demonstrates how to use the `EnhancedServiceBase` and the
    `@genesis_function` decorator to expose methods as part of a Genesis service.
    It provides basic arithmetic operations: add, subtract, multiply, and divide.
    Each operation includes input validation (implicitly by type hints, explicitly for division by zero)
    and uses the logger to record requests and results.
    It also demonstrates publishing function call and result events, which can be useful for monitoring.
    """

    def __init__(self):
        """Initializes the CalculatorService.
        
        Sets up the service name and capabilities using the parent class constructor.
        It then calls `_advertise_functions()` which is a method from `EnhancedServiceBase`
        that automatically registers methods decorated with `@genesis_function`.
        """
        # Call the parent class constructor to set up the service name and its capabilities.
        # "CalculatorService" is the name this service will be known by in the Genesis system.
        # "capabilities" is a list of strings that can be used for service discovery or categorization.
        super().__init__("CalculatorService", capabilities=["calculator", "math"])

        # This method (from EnhancedServiceBase) finds all methods in this class
        # decorated with `@genesis_function` and prepares them to be called via RPC.
        self._advertise_functions()
        # logger.info(f"'{self.service_name}' initialized with capabilities: {self.capabilities}.") # Commented out due to AttributeError

    @genesis_function()
    async def add(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Add two numbers together.
        
        Args:
            x (float): First number to add (example: 5.0)
            y (float): Second number to add (example: 3.0)
            request_info (optional): Optional request metadata provided by the Genesis framework.
                                     This can contain information about the caller or request context.
            
        Returns:
            Dict[str, Any]: A dictionary containing the result of the addition, typically `{'result': sum}`.
            
        Examples:
            If called via an RPC mechanism, a request like `add(x=5, y=3)` would be processed.
            The expected return would be `{'result': 8}`.
            
        Raises:
            InvalidInputError: If an error occurs during addition (though basic `+` on floats is unlikely to raise this directly
                               unless type checking/conversion fails before this point, or if more complex validation were added).
                               The current implementation catches a generic Exception and wraps it.
        """
        # Log the incoming request with its parameters.
        logger.info(f"Received add request: x={x}, y={y}, request_info: {request_info}")
        # Publish an event indicating a function call has been received.
        # This is useful for monitoring and tracing systems.
        self.publish_function_call_event("add", {"x": x, "y": y}, request_info)
        
        try:
            # Perform the addition.
            result = x + y
            # Publish an event with the result of the function call.
            self.publish_function_result_event("add", {"result": result}, request_info)
            logger.info(f"Add result: {result}")
            # Return the result in a dictionary, a common pattern for service responses.
            return {"result": result}
        except Exception as e:
            # Catch any unexpected errors during the operation.
            logger.error(f"Error in add operation: {str(e)}", exc_info=True) # Log with stack trace.
            # Re-raise as a service-specific exception for consistent error handling by clients.
            self.publish_function_error_event("add", {"error": str(e), "x": x, "y": y}, request_info)
            raise InvalidInputError(f"Failed to add numbers: {str(e)}")

    @genesis_function()
    async def subtract(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Subtract the second number from the first.
        
        Args:
            x (float): The number to subtract from (example: 5.0)
            y (float): The number to subtract (example: 3.0)
            request_info (optional): Optional request metadata.
            
        Returns:
            Dict[str, Any]: Dict containing the result of the subtraction, `{'result': difference}`.
            
        Raises:
            InvalidInputError: If an error occurs during subtraction.
        """
        logger.info(f"Received subtract request: x={x}, y={y}, request_info: {request_info}")
        self.publish_function_call_event("subtract", {"x": x, "y": y}, request_info)
        
        try:
            result = x - y
            self.publish_function_result_event("subtract", {"result": result}, request_info)
            logger.info(f"Subtract result: {result}")
            return {"result": result}
        except Exception as e:
            logger.error(f"Error in subtract operation: {str(e)}", exc_info=True)
            self.publish_function_error_event("subtract", {"error": str(e), "x": x, "y": y}, request_info)
            raise InvalidInputError(f"Failed to subtract numbers: {str(e)}")

    @genesis_function()
    async def multiply(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Multiply two numbers together.
        
        Args:
            x (float): First number to multiply (example: 5.0)
            y (float): Second number to multiply (example: 3.0)
            request_info (optional): Optional request metadata.
            
        Returns:
            Dict[str, Any]: Dict containing the result of the multiplication, `{'result': product}`.
            
        Raises:
            InvalidInputError: If an error occurs during multiplication.
        """
        logger.info(f"Received multiply request: x={x}, y={y}, request_info: {request_info}")
        self.publish_function_call_event("multiply", {"x": x, "y": y}, request_info)
        
        try:
            result = x * y
            self.publish_function_result_event("multiply", {"result": result}, request_info)
            logger.info(f"Multiply result: {result}")
            return {"result": result}
        except Exception as e:
            logger.error(f"Error in multiply operation: {str(e)}", exc_info=True)
            self.publish_function_error_event("multiply", {"error": str(e), "x": x, "y": y}, request_info)
            raise InvalidInputError(f"Failed to multiply numbers: {str(e)}")

    @genesis_function()
    async def divide(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Divide the first number by the second.
        
        Args:
            x (float): The number to divide (the dividend) (example: 6.0)
            y (float): The number to divide by (the divisor) (example: 2.0)
            request_info (optional): Optional request metadata.
            
        Returns:
            Dict[str, Any]: Dict containing the result of the division, `{'result': quotient}`.
            
        Raises:
            InvalidInputError: If an error occurs during division (other than division by zero).
            DivisionByZeroError: If attempting to divide by zero (y is 0).
        """
        logger.info(f"Received divide request: x={x}, y={y}, request_info: {request_info}")
        self.publish_function_call_event("divide", {"x": x, "y": y}, request_info)
        
        try:
            if y == 0:
                # Specific check for division by zero, raising a specific custom error.
                logger.warning("Attempted division by zero") # Log as warning, as it's a client error.
                raise DivisionByZeroError("Cannot divide by zero")
            result = x / y
            self.publish_function_result_event("divide", {"result": result}, request_info)
            logger.info(f"Divide result: {result}")
            return {"result": result}
        except DivisionByZeroError: # Catch the specific error to re-raise it.
            # This ensures that DivisionByZeroError is not caught by the generic Exception handler below
            # and wrapped in InvalidInputError.
            self.publish_function_error_event("divide", {"error": "DivisionByZeroError", "x": x, "y": y}, request_info)
            raise
        except Exception as e:
            logger.error(f"Error in divide operation: {str(e)}", exc_info=True)
            self.publish_function_error_event("divide", {"error": str(e), "x": x, "y": y}, request_info)
            raise InvalidInputError(f"Failed to divide numbers: {str(e)}")

# --------------------------------------------------------------------------- #
# Main execution block                                                        #
# --------------------------------------------------------------------------- #
def main():
    """Main function to start the CalculatorService.
    
    This function instantiates the service and runs its main loop using `asyncio.run()`.
    It includes a try-except block to catch `KeyboardInterrupt` for graceful shutdown.
    """
    logger.info("SERVICE: Starting calculator service...")
    service = None # Initialize service to None for the finally block
    try:
        # Create an instance of the service.
        service = CalculatorService()
        # Run the service. This is a blocking call that starts the service's
        # event loop and keeps it running until stopped (e.g., by KeyboardInterrupt or service.stop()).
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("SERVICE: KeyboardInterrupt received, shutting down calculator service...")
    except Exception as e:
        logger.error(f"SERVICE: An unexpected error occurred: {e}", exc_info=True)
    finally:
        # Ensures that if the service has a close or cleanup method, it could be called here.
        # For EnhancedServiceBase, cleanup is typically handled within its run/stop methods
        # or by asyncio.run() managing tasks.
        # If specific cleanup beyond what `service.run()` handles upon exit is needed,
        # it would be added here, e.g., `if service: await service.close_resources()`.
        logger.info("SERVICE: Calculator service has shut down.")

if __name__ == "__main__":
    # This ensures that main() is called only when the script is executed directly,
    # not when it's imported as a module.
    main()

```

## genesis_lib/monitored_agent.py

**Author:** Jason

```python
#!/usr/bin/env python3
"""
MonitoredAgent Base Class for Genesis Agents

This module defines the MonitoredAgent class, which extends the GenesisAgent
base class to provide standardized monitoring capabilities for agents operating
within the Genesis network. It handles the publishing of various monitoring events,
including agent lifecycle, state changes, and function call chains, using DDS topics.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import logging
import time
import uuid
import json
import os
from typing import Any, Dict, Optional, List
import rti.connextdds as dds
import rti.rpc as rpc
from genesis_lib.utils import get_datamodel_path
from .agent import GenesisAgent
from genesis_lib.generic_function_client import GenericFunctionClient
import traceback
import asyncio
from datetime import datetime
from genesis_lib.genesis_monitoring import MonitoringSubscriber

# Configure logging
logger = logging.getLogger(__name__)

# Event type mapping
EVENT_TYPE_MAP = {
    "AGENT_DISCOVERY": 0,  # FUNCTION_DISCOVERY enum value
    "AGENT_REQUEST": 1,    # FUNCTION_CALL enum value
    "AGENT_RESPONSE": 2,   # FUNCTION_RESULT enum value
    "AGENT_STATUS": 3      # FUNCTION_STATUS enum value
}

# Agent type mapping
AGENT_TYPE_MAP = {
    "AGENT": 1,            # PRIMARY_AGENT
    "SPECIALIZED_AGENT": 2, # SPECIALIZED_AGENT
    "INTERFACE": 0         # INTERFACE
}

# Event category mapping
EVENT_CATEGORY_MAP = {
    "NODE_DISCOVERY": 0,
    "EDGE_DISCOVERY": 1,
    "STATE_CHANGE": 2,
    "AGENT_INIT": 3,
    "AGENT_READY": 4
}

class MonitoredAgent(GenesisAgent):
    """
    Base class for agents with monitoring capabilities.
    Extends GenesisAgent to add standardized monitoring.
    """
    
    # Class attribute for function client (can be overridden in subclasses if needed)
    _function_client_initialized = False
    
    def __init__(self, agent_name: str, base_service_name: str, 
                 agent_type: str = "AGENT", service_instance_tag: Optional[str] = None, 
                 agent_id: str = None, description: str = None, domain_id: int = 0):
        """
        Initialize the monitored agent.
        
        Args:
            agent_name: Name of the agent
            base_service_name: The fundamental type of service (e.g., "Chat", "ImageGeneration")
            agent_type: Type of agent (AGENT, SPECIALIZED_AGENT)
            service_instance_tag: Optional tag for unique RPC service name instance
            agent_id: Optional UUID for the agent (if None, will generate one)
            description: Optional description of the agent
            domain_id: Optional DDS domain ID
        """
        logger.info(f"MonitoredAgent {agent_name} STARTING initializing with agent_id {agent_id}")
        # Initialize base class (GenesisAgent) with the new service name parameters
        super().__init__(
            agent_name=agent_name,
            base_service_name=base_service_name,
            service_instance_tag=service_instance_tag,
            agent_id=agent_id
        )
        logger.info(f"MonitoredAgent {agent_name} initialized with base class")
        # Store additional parameters as instance variables
        self.agent_type = agent_type
        self.description = description or f"A {agent_type} providing {base_service_name} service"
        self.domain_id = domain_id
        self.monitor = None
        self.subscription = None
        
        # Initialize function client and cache
        self._initialize_function_client()
        self.function_cache: Dict[str, Dict[str, Any]] = {}
        
        # Initialize agent capabilities
        self.agent_capabilities = {
            "agent_type": agent_type,
            "service": base_service_name,
            "functions": [],  # Will be populated during function discovery
            "supported_tasks": []  # To be populated by subclasses
        }
        
        # Get types from XML
        config_path = get_datamodel_path()
        self.type_provider = dds.QosProvider(config_path)
        self.request_type = self.type_provider.type("genesis_lib", "InterfaceAgentRequest")
        self.reply_type = self.type_provider.type("genesis_lib", "InterfaceAgentReply")
        
        # Set up monitoring
        self._setup_monitoring()
        
        # Create subscription match listener
        self._setup_subscription_listener()

        # Publish agent discovery event
        self.publish_component_lifecycle_event(
            category="NODE_DISCOVERY",
            message=f"Agent {agent_name} discovered",
            previous_state="OFFLINE",
            new_state="DISCOVERING",
            source_id=self.app.agent_id,
            target_id=self.app.agent_id,
            capabilities=json.dumps({
                "agent_type": agent_type,
                "service": base_service_name,
                "description": self.description,
                "agent_id": self.app.agent_id
            })
        )

        # Publish agent ready event
        self.publish_component_lifecycle_event(
            category="AGENT_READY",
            message=f"{agent_name} ready for requests",
            previous_state="DISCOVERING",
            new_state="READY",
            source_id=self.app.agent_id,
            target_id=self.app.agent_id,
            capabilities=json.dumps({
                "agent_type": agent_type,
                "service": base_service_name,
                "description": self.description,
                "agent_id": self.app.agent_id
            })
        )
        
        logger.info(f"Monitored agent {agent_name} initialized with type {agent_type}, agent_id={self.app.agent_id}, dds_guid={self.app.dds_guid}")
    
    def _initialize_function_client(self) -> None:
        """Initialize the GenericFunctionClient if not already done."""
        # Ensure participant is ready
        if not self.app or not self.app.participant:
            logger.error("Cannot initialize function client: DDS Participant not available.")
            return
        
        # Use a class-level flag to prevent multiple initializations if needed,
    def _setup_monitoring(self) -> None:
        """
        Set up monitoring resources and initialize state.
        """
        try:
            # Get monitoring type from XML
            self.monitoring_type = self.type_provider.type("genesis_lib", "MonitoringEvent")
            
            # Create monitoring topic
            self.monitoring_topic = dds.DynamicData.Topic(
                self.app.participant,
                "MonitoringEvent",
                self.monitoring_type
            )
            
            # Create monitoring publisher with QoS
            publisher_qos = dds.QosProvider.default.publisher_qos
            publisher_qos.partition.name = [""]  # Default partition
            self.monitoring_publisher = dds.Publisher(
                participant=self.app.participant,
                qos=publisher_qos
            )
            
            # Create monitoring writer with QoS
            writer_qos = dds.QosProvider.default.datawriter_qos
            writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
            writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            self.monitoring_writer = dds.DynamicData.DataWriter(
                pub=self.monitoring_publisher,
                topic=self.monitoring_topic,
                qos=writer_qos
            )

            # Set up enhanced monitoring (V2)
            # Create topics for new monitoring types
            self.component_lifecycle_type = self.type_provider.type("genesis_lib", "ComponentLifecycleEvent")
            self.chain_event_type = self.type_provider.type("genesis_lib", "ChainEvent")
            self.liveliness_type = self.type_provider.type("genesis_lib", "LivelinessUpdate")

            # Create topics
            self.component_lifecycle_topic = dds.DynamicData.Topic(
                self.app.participant,
                "ComponentLifecycleEvent",
                self.component_lifecycle_type
            )
            self.chain_event_topic = dds.DynamicData.Topic(
                self.app.participant,
                "ChainEvent",
                self.chain_event_type
            )
            self.liveliness_topic = dds.DynamicData.Topic(
                self.app.participant,
                "LivelinessUpdate",
                self.liveliness_type
            )

            # Create writers with QoS
            writer_qos = dds.QosProvider.default.datawriter_qos
            writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
            writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE

            # Create writers for each monitoring type using the same publisher
            self.component_lifecycle_writer = dds.DynamicData.DataWriter(
                pub=self.monitoring_publisher,
                topic=self.component_lifecycle_topic,
                qos=writer_qos
            )
            self.chain_event_writer = dds.DynamicData.DataWriter(
                pub=self.monitoring_publisher,
                topic=self.chain_event_topic,
                qos=writer_qos
            )
            self.liveliness_writer = dds.DynamicData.DataWriter(
                pub=self.monitoring_publisher,
                topic=self.liveliness_topic,
                qos=writer_qos
            )
            
            # Initialize state tracking
            self.current_state = "OFFLINE"
            self.last_state_change = datetime.now()
            self.state_history = []
            self.event_correlation = {}
            
            # Publish initial state
            self.publish_component_lifecycle_event(
                category="STATE_CHANGE",
                message="Initializing monitoring",
                previous_state="OFFLINE",
                new_state="INITIALIZING",
                source_id=self.app.agent_id,
                target_id=self.app.agent_id
            )
            self.current_state = "INITIALIZING"
            
            # Set up event correlation tracking
            self.event_correlation = {
                "monitoring_events": {},
                "lifecycle_events": {},
                "chain_events": {}
            }
            
            # Transition to READY state
            self.publish_component_lifecycle_event(
                category="STATE_CHANGE",
                message="Monitoring initialized successfully",
                previous_state="INITIALIZING",
                new_state="READY",
                source_id=self.app.agent_id,
                target_id=self.app.agent_id
            )
            self.current_state = "READY"
            
        except Exception as e:
            logger.error(f"Failed to initialize monitoring: {e}")
            self.current_state = "DEGRADED"
            raise
    
    def _setup_subscription_listener(self):
        """Set up a listener to track subscription matches"""
        class SubscriptionMatchListener(dds.DynamicData.NoOpDataReaderListener):
            def __init__(self, logger_instance):
                super().__init__()
                self.logger = logger_instance
                
            def on_subscription_matched(self, reader, status):
                # Only log matches for ComponentLifecycleEvent topic
                if reader and reader.topic_description and reader.topic_description.name == "ComponentLifecycleEvent":
                    self.logger.debug("ComponentLifecycleEvent subscription matched")

        # Pass the main MonitoredAgent logger to the listener
        listener = SubscriptionMatchListener(logger) 
        
        # Configure reader QoS for component lifecycle events
        reader_qos = dds.QosProvider.default.datareader_qos
        reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        
        # Add listener to component lifecycle reader
        self.component_lifecycle_reader = dds.DynamicData.DataReader(
            subscriber=self.app.subscriber,
            topic=self.component_lifecycle_topic,
            qos=reader_qos,
            listener=listener,
            mask=dds.StatusMask.SUBSCRIPTION_MATCHED
        )
    
    def publish_monitoring_event(self, 
                               event_type: str,
                               metadata: Optional[Dict[str, Any]] = None,
                               call_data: Optional[Dict[str, Any]] = None,
                               result_data: Optional[Dict[str, Any]] = None,
                               status_data: Optional[Dict[str, Any]] = None,
                               request_info: Optional[Any] = None) -> None:
        """
        Publish a monitoring event.
        
        Args:
            event_type: Type of event (AGENT_DISCOVERY, AGENT_REQUEST, etc.)
            metadata: Additional metadata about the event
            call_data: Data about the request/call (if applicable)
            result_data: Data about the response/result (if applicable)
            status_data: Data about the agent status (if applicable)
            request_info: Request information containing client ID
        """
        try:
            event = dds.DynamicData(self.monitoring_type)
            
            # Set basic fields
            event["event_id"] = str(uuid.uuid4())
            event["timestamp"] = int(time.time() * 1000)
            event["event_type"] = EVENT_TYPE_MAP[event_type]
            event["entity_type"] = AGENT_TYPE_MAP.get(self.agent_type, 1)  # Default to PRIMARY_AGENT if type not found
            event["entity_id"] = self.agent_name
            
            # Set optional fields
            if metadata:
                event["metadata"] = json.dumps(metadata)
            if call_data:
                event["call_data"] = json.dumps(call_data)
            if result_data:
                event["result_data"] = json.dumps(result_data)
            if status_data:
                event["status_data"] = json.dumps(status_data)
            
            # Write the event
            self.monitoring_writer.write(event)
            logger.debug(f"Published monitoring event: {event_type}")
            
        except Exception as e:
            logger.error(f"Error publishing monitoring event: {str(e)}")
            logger.error(traceback.format_exc())
    
    def publish_component_lifecycle_event(self, 
                                       category: str,
                                       message: str = None,
                                       previous_state: str = None,
                                       new_state: str = None,
                                       reason: str = None,
                                       capabilities: str = None,
                                       component_id: str = None,
                                       source_id: str = None,
                                       target_id: str = None,
                                       connection_type: str = None):
        """
        Publish a component lifecycle event for the agent.
        
        Args:
            category: Event category (e.g., EDGE_DISCOVERY, EDGE_READY)
            message: Optional message to include with the event
            previous_state: Previous state of the component
            new_state: New state of the component
            reason: Reason for the state change
            capabilities: JSON string of component capabilities
            component_id: ID of the component
            source_id: Source ID for edge events
            target_id: Target ID for edge events
            connection_type: Type of connection for edge events
        """
        try:
            if not hasattr(self, 'component_lifecycle_type') or not self.component_lifecycle_type:
                logger.debug(f"Component lifecycle monitoring not initialized, skipping event: {category}")
                return
            
            if not hasattr(self, 'component_lifecycle_writer') or not self.component_lifecycle_writer:
                logger.debug(f"Component lifecycle writer not initialized, skipping event: {category}")
                return

            # Map state strings to enum values
            states = {
                "JOINING": 0,
                "DISCOVERING": 1,
                "READY": 2,
                "BUSY": 3,
                "DEGRADED": 4,
                "OFFLINE": 5
            }

            # Map event categories to enum values
            event_categories = {
                "NODE_DISCOVERY": 0,
                "EDGE_DISCOVERY": 1,
                "STATE_CHANGE": 2,
                "AGENT_INIT": 3,
                "AGENT_READY": 4,
                "AGENT_SHUTDOWN": 5,
                "DDS_ENDPOINT": 6
            }

            # Create event
            event = dds.DynamicData(self.component_lifecycle_type)
            
            # Set component ID (use provided ID or agent name)
            event["component_id"] = component_id if component_id else self.agent_name
            
            # Set component type (AGENT for agent)
            event["component_type"] = 2
            
            # Set states based on category or provided states
            if previous_state and new_state:
                event["previous_state"] = states.get(previous_state, states["DISCOVERING"])
                event["new_state"] = states.get(new_state, states["DISCOVERING"])
            else:
                if category == "NODE_DISCOVERY":
                    event["previous_state"] = states["DISCOVERING"]
                    event["new_state"] = states["DISCOVERING"]
                elif category == "AGENT_INIT":
                    event["previous_state"] = states["OFFLINE"]
                    event["new_state"] = states["JOINING"]
                elif category == "AGENT_READY":
                    event["previous_state"] = states["DISCOVERING"]
                    event["new_state"] = states["READY"]
                elif category == "BUSY":
                    event["previous_state"] = states["READY"]
                    event["new_state"] = states["BUSY"]
                elif category == "READY":
                    event["previous_state"] = states["BUSY"]
                    event["new_state"] = states["READY"]
                elif category == "DEGRADED":
                    event["previous_state"] = states["BUSY"]
                    event["new_state"] = states["DEGRADED"]
                else:
                    event["previous_state"] = states["DISCOVERING"]
                    event["new_state"] = states["DISCOVERING"]
            
            # Set other fields
            event["timestamp"] = int(time.time() * 1000)
            event["reason"] = reason if reason else (message if message else "")
            event["capabilities"] = capabilities if capabilities else json.dumps(self.agent_capabilities)
            
            # Set event category
            if category in event_categories:
                event["event_category"] = event_categories[category]
            else:
                event["event_category"] = event_categories["NODE_DISCOVERY"]
            
            # Set source and target IDs, defaulting to self.app.agent_id
            event["source_id"] = source_id if source_id else self.app.agent_id
            if category == "EDGE_DISCOVERY":
                # For edge discovery, target is the function being discovered
                event["target_id"] = target_id if target_id else self.app.agent_id
                event["connection_type"] = connection_type if connection_type else "function_connection"
            else:
                # For other events, source and target are the same (self.app.agent_id)
                event["target_id"] = target_id if target_id else self.app.agent_id
                event["connection_type"] = connection_type if connection_type else ""

            self.component_lifecycle_writer.write(event)
            self.component_lifecycle_writer.flush()
        except Exception as e:
            logger.error(f"Error publishing component lifecycle event: {e}")
            logger.debug(f"Event category was: {category}")
    
    async def process_request(self, request: Any) -> Dict[str, Any]:
        """
        Process a request with monitoring.
        
        This implementation wraps the concrete process_request with monitoring events.
        Concrete implementations should override _process_request instead.
        
        Args:
            request: The request to process
            
        Returns:
            Dictionary containing the response data
        """
        # Generate chain and call IDs for tracking
        chain_id = str(uuid.uuid4())
        call_id = str(uuid.uuid4())

        try:
            # Ensure we're in READY state before processing
            if self.current_state != "READY":
                self.publish_component_lifecycle_event(
                    category="STATE_CHANGE",
                    message=f"Transitioning to READY state before processing request",
                    previous_state=self.current_state,
                    new_state="READY",
                    source_id=self.app.agent_id,
                    target_id=self.app.agent_id
                )
                self.current_state = "READY"

            # Transition to BUSY state
            self.publish_component_lifecycle_event(
                category="STATE_CHANGE",
                message=f"Processing request: {str(request)}",
                previous_state="READY",
                new_state="BUSY",
                source_id=self.app.agent_id,
                target_id=self.app.agent_id
            )
            self.current_state = "BUSY"

            # Publish legacy request received event
            self.publish_monitoring_event(
                "AGENT_REQUEST",
                call_data={"request": str(request)},
                metadata={
                    "service": self.base_service_name,
                    "chain_id": chain_id,
                    "call_id": call_id
                }
            )
            
            # Process request using concrete implementation
            result = await self._process_request(request)
            
            # Publish successful response event
            self.publish_monitoring_event(
                "AGENT_RESPONSE",
                result_data={"response": str(result)},
                metadata={
                    "service": self.base_service_name,
                    "status": "success",
                    "chain_id": chain_id,
                    "call_id": call_id
                }
            )

            # Transition back to READY state
            self.publish_component_lifecycle_event(
                category="STATE_CHANGE",
                message=f"Request processed successfully: {str(result)}",
                previous_state="BUSY",
                new_state="READY",
                source_id=self.app.agent_id,
                target_id=self.app.agent_id
            )
            self.current_state = "READY"
            
            return result
            
        except Exception as e:
            # Publish error event
            self.publish_monitoring_event(
                "AGENT_STATUS",
                status_data={"error": str(e)},
                metadata={
                    "service": self.base_service_name,
                    "status": "error",
                    "chain_id": chain_id,
                    "call_id": call_id
                }
            )

            # Transition to DEGRADED state on error
            self.publish_component_lifecycle_event(
                category="STATE_CHANGE",
                message=f"Error processing request: {str(e)}",
                previous_state=self.current_state,
                new_state="DEGRADED",
                source_id=self.app.agent_id,
                target_id=self.app.agent_id
            )
            self.current_state = "DEGRADED"
            
            # Attempt recovery by transitioning back to READY
            try:
                self.publish_component_lifecycle_event(
                    category="STATE_CHANGE",
                    message="Attempting recovery to READY state",
                    previous_state="DEGRADED",
                    new_state="READY",
                    source_id=self.app.agent_id,
                    target_id=self.app.agent_id
                )
                self.current_state = "READY"
            except Exception as recovery_error:
                logger.error(f"Failed to recover from DEGRADED state: {recovery_error}")
            
            raise
    
    def _process_request(self, request: Any) -> Dict[str, Any]:
        """
        Process the request and return reply data.
        
        This method should be overridden by concrete implementations.
        
        Args:
            request: The request to process
            
        Returns:
            Dictionary containing the response data
        """
        raise NotImplementedError("Concrete agents must implement _process_request")
    
    async def close(self) -> None:
        """
        Close monitoring resources and transition to OFFLINE state.
        """
        try:
            # Transition to OFFLINE state
            self.publish_component_lifecycle_event(
                category="STATE_CHANGE",
                message="Shutting down monitoring",
                previous_state=self.current_state,
                new_state="OFFLINE",
                source_id=self.app.agent_id,
                target_id=self.app.agent_id
            )
            
            # Detach listener first to potentially resolve waitset issues
            if hasattr(self, 'component_lifecycle_reader'):
                self.component_lifecycle_reader.set_listener(None, dds.StatusMask.NONE)
                self.component_lifecycle_reader.close() # Also close the reader itself

            # Clean up monitoring resources
            if hasattr(self, 'monitoring_writer'):
                self.monitoring_writer.close()
            if hasattr(self, 'monitoring_publisher'):
                self.monitoring_publisher.close()
            if hasattr(self, 'monitoring_topic'):
                self.monitoring_topic.close()
            if hasattr(self, 'component_lifecycle_writer'):
                self.component_lifecycle_writer.close()
            if hasattr(self, 'chain_event_writer'):
                self.chain_event_writer.close()
            if hasattr(self, 'liveliness_writer'):
                self.liveliness_writer.close()
            if hasattr(self, 'component_lifecycle_topic'):
                self.component_lifecycle_topic.close()
            if hasattr(self, 'chain_event_topic'):
                self.chain_event_topic.close()
            if hasattr(self, 'liveliness_topic'):
                self.liveliness_topic.close()
            
            # Clear state tracking
            self.current_state = "OFFLINE"
            self.last_state_change = datetime.now()
            self.state_history = []
            self.event_correlation = {}
            
            # Call parent class cleanup
            if hasattr(self, 'app'):
                await self.app.close()
            
        except Exception as e:
            logger.error(f"Error during monitoring shutdown: {e}")
            self.current_state = "DEGRADED"
            raise

    def wait_for_agent(self) -> bool:
        """
        Wait for an agent to become available.
        Now includes edge discovery events for multiple connections.
        """
        try:
            logger.debug("Starting wait_for_agent")
            # Wait for agent using base class implementation
            result = super().wait_for_agent()
            logger.debug(f"Base wait_for_agent returned: {result}")

            if result:
                # Get all discovered agents' information
                agent_infos = self.app.get_all_agent_info()
                logger.debug(f"Got agent infos: {agent_infos}")
                
                for agent_info in agent_infos:
                    if agent_info:
                        # Format the edge discovery reason string exactly as expected by the monitor
                        # This format is critical for the monitor to recognize it as an edge discovery event
                        provider_id = str(agent_info.get('instance_handle', ''))
                        client_id = str(self.app.participant.instance_handle)
                        function_id = str(uuid.uuid4())
                        
                        # Format exactly as monitor expects for edge discovery
                        reason = f"provider={provider_id} client={client_id} function={function_id} name={self.base_service_name}"
                        logger.debug(f"Publishing edge discovery event with reason: {reason}")

                        # Publish edge discovery event while in DISCOVERING state
                        self.publish_component_lifecycle_event(
                            category="EDGE_DISCOVERY",
                            message=reason,
                            capabilities=json.dumps({
                                "agent_type": self.agent_type,
                                "service": self.base_service_name,
                                "edge_type": "agent_function",
                                "provider_id": provider_id,
                                "client_id": client_id,
                                "function_id": function_id
                            }),
                            source_id=self.app.agent_id,
                            target_id=self.app.agent_id
                        )
                        logger.debug("Published edge discovery event")

                        # Add a small delay to ensure events are distinguishable
                        time.sleep(0.1)

            return result

        except Exception as e:
            logger.error(f"Error in wait_for_agent: {str(e)}")
            # Transition to degraded state on error
            self.publish_component_lifecycle_event(
                category="DEGRADED",
                message=f"Error discovering functions: {str(e)}",
                source_id=self.app.agent_id,
                target_id=self.app.agent_id
            )
            return False


    
    def _get_requester_guid(self, function_client) -> str:
        """
        Extract the DDS GUID of the requester from a function client.
        
        Args:
            function_client: An instance of a function client
            
        Returns:
            The DDS GUID of the requester, or None if not available
        """
        requester_guid = None
        
        try:
            # Try different paths to get the requester GUID
            if hasattr(function_client, 'requester') and hasattr(function_client.requester, 'request_datawriter'):
                requester_guid = str(function_client.requester.request_datawriter.instance_handle)
                logger.debug(f"===== TRACING: Got requester GUID from request_datawriter: {requester_guid} =====")
            elif hasattr(function_client, 'requester') and hasattr(function_client.requester, 'participant'):
                requester_guid = str(function_client.requester.participant.instance_handle)
                logger.debug(f"===== TRACING: Got requester GUID from participant: {requester_guid} =====")
            elif hasattr(function_client, 'participant'):
                requester_guid = str(function_client.participant.instance_handle)
                logger.debug(f"===== TRACING: Got requester GUID from client participant: {requester_guid} =====")
        except Exception as e:
            logger.error(f"===== TRACING: Error getting requester GUID: {e} =====")
            logger.error(traceback.format_exc())
            
        return requester_guid
    
    def store_function_requester_guid(self, guid: str):
        """
        Store the function requester GUID and create edges to known function providers.
        
        Args:
            guid: The DDS GUID of the function requester
        """
        logger.debug(f"===== TRACING: Storing function requester GUID: {guid} =====")
        self.function_requester_guid = guid
        
        # Create edges to all known function providers
        if hasattr(self, 'function_provider_guids'):
            for provider_guid in self.function_provider_guids:
                try:
                    # Create a unique edge key
                    edge_key = f"direct_requester_to_provider_{guid}_{provider_guid}"
                    
                    # Publish direct edge discovery event
                    self.publish_component_lifecycle_event(
                        category="EDGE_DISCOVERY",
                        message=f"Direct connection: {guid} -> {provider_guid}",
                        capabilities=json.dumps({
                            "edge_type": "direct_connection",
                            "requester_guid": guid,
                            "provider_guid": provider_guid,
                            "agent_id": self.app.agent_id,
                            "agent_name": self.agent_name,
                            "service_name": self.base_service_name
                        }),
                        source_id=guid,
                        target_id=provider_guid,
                        connection_type="CONNECTS_TO"
                    )
                    
                    logger.debug(f"===== TRACING: Published direct requester-to-provider edge: {guid} -> {provider_guid} =====")
                except Exception as e:
                    logger.error(f"===== TRACING: Error publishing direct requester-to-provider edge: {e} =====")
                    logger.error(traceback.format_exc())
    
    def store_function_provider_guid(self, guid: str):
        """
        Store a function provider GUID and create an edge if the function requester is known.
        
        Args:
            guid: The DDS GUID of the function provider
        """
        logger.debug(f"===== TRACING: Storing function provider GUID: {guid} =====")
        
        # Initialize the set if it doesn't exist
        if not hasattr(self, 'function_provider_guids'):
            self.function_provider_guids = set()
            
        # Add the provider GUID to the set
        self.function_provider_guids.add(guid)
        
        # Create an edge if the function requester is known
        if hasattr(self, 'function_requester_guid') and self.function_requester_guid:
            try:
                # Create a unique edge key
                edge_key = f"direct_requester_to_provider_{self.function_requester_guid}_{guid}"
                
                # Publish direct edge discovery event
                self.publish_component_lifecycle_event(
                    category="EDGE_DISCOVERY",
                    message=f"Direct connection: {self.function_requester_guid} -> {guid}",
                    capabilities=json.dumps({
                        "edge_type": "direct_connection",
                        "requester_guid": self.function_requester_guid,
                        "provider_guid": guid,
                        "agent_id": self.app.agent_id,
                        "agent_name": self.agent_name,
                        "service_name": self.base_service_name
                    }),
                    source_id=self.function_requester_guid,
                    target_id=guid,
                    connection_type="CONNECTS_TO"
                )
                
                logger.debug(f"===== TRACING: Published direct requester-to-provider edge: {self.function_requester_guid} -> {guid} =====")
            except Exception as e:
                logger.error(f"===== TRACING: Error publishing direct requester-to-provider edge: {e} =====")
                logger.error(traceback.format_exc())
    
    def publish_discovered_functions(self, functions: List[Dict[str, Any]]) -> None:
        """
        Publish discovered functions as monitoring events.
        
        Args:
            functions: List of discovered functions
        """
        logger.debug(f"===== TRACING: Publishing {len(functions)} discovered functions as monitoring events =====")
        
        # Get the function requester DDS GUID if available
        function_requester_guid = None
        
        # First try to get it from the stored function client
        if hasattr(self, 'function_client'):
            function_requester_guid = self._get_requester_guid(self.function_client)
            
            # Store the function requester GUID for later use
            if function_requester_guid:
                self.function_requester_guid = function_requester_guid
                logger.debug(f"===== TRACING: Stored function requester GUID: {function_requester_guid} =====")
            
        # If we still don't have it, try other methods
        if not function_requester_guid and hasattr(self, 'app') and hasattr(self.app, 'function_registry'):
            try:
                function_requester_guid = str(self.app.function_registry.participant.instance_handle)
                logger.debug(f"===== TRACING: Function requester GUID from registry: {function_requester_guid} =====")
                
                # Store the function requester GUID for later use
                self.function_requester_guid = function_requester_guid
                logger.debug(f"===== TRACING: Stored function requester GUID: {function_requester_guid} =====")
            except Exception as e:
                logger.error(f"===== TRACING: Error getting function requester GUID from registry: {e} =====")
        
        # Collect provider GUIDs from discovered functions
        provider_guids = set()
        function_provider_guid = None
        
        for func in functions:
            if 'provider_id' in func and func['provider_id']:
                provider_guid = func['provider_id']
                provider_guids.add(provider_guid)
                logger.debug(f"===== TRACING: Found provider GUID: {provider_guid} =====")
                
                # Store the provider GUID for later use
                self.store_function_provider_guid(provider_guid)
                
                # Store the first provider GUID as the main function provider GUID
                if function_provider_guid is None:
                    function_provider_guid = provider_guid
                    logger.debug(f"===== TRACING: Using {function_provider_guid} as the main function provider GUID =====")
        
        # Publish a monitoring event for each discovered function
        for func in functions:
            function_id = func.get('function_id', str(uuid.uuid4()))
            function_name = func.get('name', 'unknown')
            provider_id = func.get('provider_id', '')
            
            # Publish as a component lifecycle event
            self.publish_component_lifecycle_event(
                category="NODE_DISCOVERY",
                message=f"Function discovered: {function_name} ({function_id})",
                capabilities=json.dumps({
                    "function_id": function_id,
                    "function_name": function_name,
                    "function_description": func.get('description', ''),
                    "function_schema": func.get('schema', {}),
                    "provider_id": provider_id,
                    "provider_name": func.get('provider_name', '')
                }),
                source_id=self.app.agent_id,
                target_id=function_id,
                connection_type="FUNCTION"
            )
            
            # Also publish an edge discovery event connecting the agent to the function
            self.publish_component_lifecycle_event(
                category="EDGE_DISCOVERY",
                message=f"Agent {self.agent_name} can call function {function_name}",
                capabilities=json.dumps({
                    "edge_type": "agent_function",
                    "function_id": function_id,
                    "function_name": function_name
                }),
                source_id=self.app.agent_id,
                target_id=function_id,
                connection_type="CALLS"
            )
            
            # Also publish as a legacy monitoring event
            self.publish_monitoring_event(
                "AGENT_DISCOVERY",
                metadata={
                    "function_id": function_id,
                    "function_name": function_name,
                    "provider_id": provider_id,
                    "provider_name": func.get('provider_name', '')
                },
                status_data={
                    "status": "available",
                    "state": "discovered",
                    "description": func.get('description', ''),
                    "schema": json.dumps(func.get('schema', {}))
                }
            )
            
            logger.debug(f"===== TRACING: Published function discovery event for {function_name} ({function_id}) =====")
        
        # Publish edge discovery events connecting the function requester to each provider
        if function_requester_guid:
            for provider_guid in provider_guids:
                if provider_guid:
                    try:
                        # Create a unique edge key
                        edge_key = f"requester_to_provider_{function_requester_guid}_{provider_guid}"
                        
                        # Publish edge discovery event
                        self.publish_component_lifecycle_event(
                            category="EDGE_DISCOVERY",
                            message=f"Function requester connects to provider: {function_requester_guid} -> {provider_guid}",
                            capabilities=json.dumps({
                                "edge_type": "requester_provider",
                                "requester_guid": function_requester_guid,
                                "provider_guid": provider_guid,
                                "agent_id": self.app.agent_id,
                                "agent_name": self.agent_name
                            }),
                            source_id=function_requester_guid,
                            target_id=provider_guid,
                            connection_type="DISCOVERS"
                        )
                        
                        logger.debug(f"===== TRACING: Published requester-to-provider edge: {function_requester_guid} -> {provider_guid} =====")
                    except Exception as e:
                        logger.error(f"===== TRACING: Error publishing requester-to-provider edge: {e} =====")
                        logger.error(traceback.format_exc())
        
        # If we have both the function requester GUID and the main function provider GUID,
        # create a direct edge between them
        if function_provider_guid:
            try:
                # Create a unique edge key for the direct connection
                direct_edge_key = f"direct_requester_to_provider_{function_requester_guid}_{function_provider_guid}"
                
                # Publish direct edge discovery event
                self.publish_component_lifecycle_event(
                    category="EDGE_DISCOVERY",
                    message=f"Direct connection: {function_requester_guid} -> {function_provider_guid}",
                    capabilities=json.dumps({
                        "edge_type": "direct_connection",
                        "requester_guid": function_requester_guid,
                        "provider_guid": function_provider_guid,
                        "agent_id": self.app.agent_id,
                        "agent_name": self.agent_name,
                        "service_name": self.base_service_name
                    }),
                    source_id=function_requester_guid,
                    target_id=function_provider_guid,
                    connection_type="CONNECTS_TO"
                )
                
                logger.debug(f"===== TRACING: Published direct requester-to-provider edge: {function_requester_guid} -> {function_provider_guid} =====")
            except Exception as e:
                logger.error(f"===== TRACING: Error publishing direct requester-to-provider edge: {e} =====")
                logger.error(traceback.format_exc())
        else:
            logger.warning("===== TRACING: Could not publish requester-to-provider edge: function_requester_guid not available =====")
        
        # Log a summary of all discovered functions
        function_names = [f.get('name', 'unknown') for f in functions]
        logger.debug(f"===== TRACING: MonitoredAgent has discovered these functions: {function_names} =====")
        
        # Transition to READY state after discovering functions
        self.publish_component_lifecycle_event(
            category="READY",
            message=f"Agent {self.agent_name} discovered {len(functions)} functions and is ready",
            capabilities=json.dumps({
                "agent_type": self.agent_type,
                "service": self.base_service_name,
                "discovered_functions": len(functions),
                "function_names": function_names
            }),
            source_id=self.app.agent_id,
            target_id=self.app.agent_id
        )

    def create_requester_provider_edge(self, requester_guid: str, provider_guid: str):
        """
        Explicitly create an edge between a function requester and provider.
        
        Args:
            requester_guid: The DDS GUID of the function requester
            provider_guid: The DDS GUID of the function provider
        """
        logger.debug(f"===== TRACING: Creating explicit requester-to-provider edge: {requester_guid} -> {provider_guid} =====")
        
        try:
            # Create a unique edge key
            edge_key = f"explicit_requester_to_provider_{requester_guid}_{provider_guid}"
            
            # Publish direct edge discovery event
            self.publish_component_lifecycle_event(
                category="EDGE_DISCOVERY",
                message=f"Explicit connection: {requester_guid} -> {provider_guid}",
                capabilities=json.dumps({
                    "edge_type": "explicit_connection",
                    "requester_guid": requester_guid,
                    "provider_guid": provider_guid,
                    "agent_id": self.app.agent_id,
                    "agent_name": self.agent_name,
                    "service_name": self.base_service_name
                }),
                source_id=requester_guid,
                target_id=provider_guid,
                connection_type="CONNECTS_TO"
            )
            
            logger.debug(f"===== TRACING: Published explicit requester-to-provider edge: {requester_guid} -> {provider_guid} =====")
            return True
        except Exception as e:
            logger.error(f"===== TRACING: Error publishing explicit requester-to-provider edge: {e} =====")
            logger.error(traceback.format_exc())
            return False

    def set_agent_capabilities(self, supported_tasks: list[str] = None, additional_capabilities: dict = None):
        """
        Set or update agent capabilities in a user-friendly way.
        
        Args:
            supported_tasks: List of tasks this agent can perform
            additional_capabilities: Dictionary of additional capability metadata
        """
        if supported_tasks:
            self.agent_capabilities["supported_tasks"] = supported_tasks
            
        if additional_capabilities:
            self.agent_capabilities.update(additional_capabilities)
            
        # Publish updated capabilities
        self.publish_component_lifecycle_event(
            category="STATE_CHANGE",
            message="Agent capabilities updated",
            capabilities=json.dumps(self.agent_capabilities),
            source_id=self.app.agent_id,
            target_id=self.app.agent_id
        ) 

    def _publish_llm_call_start(self, chain_id: str, call_id: str, model_identifier: str):
        """Publish a chain event for LLM call start"""
        chain_event = dds.DynamicData(self.chain_event_type)
        chain_event["chain_id"] = chain_id
        chain_event["call_id"] = call_id
        chain_event["interface_id"] = str(self.app.participant.instance_handle)
        chain_event["primary_agent_id"] = ""
        chain_event["specialized_agent_ids"] = ""
        chain_event["function_id"] = model_identifier
        chain_event["query_id"] = str(uuid.uuid4())
        chain_event["timestamp"] = int(time.time() * 1000)
        chain_event["event_type"] = "LLM_CALL_START"
        chain_event["source_id"] = str(self.app.participant.instance_handle)
        chain_event["target_id"] = "OpenAI"
        chain_event["status"] = 0
        
        self.chain_event_writer.write(chain_event)
        self.chain_event_writer.flush()

    def _publish_llm_call_complete(self, chain_id: str, call_id: str, model_identifier: str):
        """Publish a chain event for LLM call completion"""
        chain_event = dds.DynamicData(self.chain_event_type)
        chain_event["chain_id"] = chain_id
        chain_event["call_id"] = call_id
        chain_event["interface_id"] = str(self.app.participant.instance_handle)
        chain_event["primary_agent_id"] = ""
        chain_event["specialized_agent_ids"] = ""
        chain_event["function_id"] = model_identifier
        chain_event["query_id"] = str(uuid.uuid4())
        chain_event["timestamp"] = int(time.time() * 1000)
        chain_event["event_type"] = "LLM_CALL_COMPLETE"
        chain_event["source_id"] = "OpenAI"
        chain_event["target_id"] = str(self.app.participant.instance_handle)
        chain_event["status"] = 0
        
        self.chain_event_writer.write(chain_event)
        self.chain_event_writer.flush()

    def _publish_classification_result(self, chain_id: str, call_id: str, classified_function_name: str, classified_function_id: str):
        """Publish a chain event for function classification result"""
        chain_event = dds.DynamicData(self.chain_event_type)
        chain_event["chain_id"] = chain_id
        chain_event["call_id"] = call_id
        chain_event["interface_id"] = str(self.app.participant.instance_handle)
        chain_event["primary_agent_id"] = ""
        chain_event["specialized_agent_ids"] = ""
        chain_event["function_id"] = classified_function_id
        chain_event["query_id"] = str(uuid.uuid4())
        chain_event["timestamp"] = int(time.time() * 1000)
        chain_event["event_type"] = "CLASSIFICATION_RESULT"
        chain_event["source_id"] = str(self.app.participant.instance_handle)
        chain_event["target_id"] = classified_function_name
        chain_event["status"] = 0
        
        self.chain_event_writer.write(chain_event)
        self.chain_event_writer.flush()

    def _publish_function_call_start(self, chain_id: str, call_id: str, function_name: str, function_id: str, target_provider_id: str = None):
        """Publish a chain event for function call start"""
        chain_event = dds.DynamicData(self.chain_event_type)
        chain_event["chain_id"] = chain_id
        chain_event["call_id"] = call_id
        chain_event["interface_id"] = str(self.app.participant.instance_handle)
        chain_event["primary_agent_id"] = ""
        chain_event["specialized_agent_ids"] = ""
        chain_event["function_id"] = function_id
        chain_event["query_id"] = str(uuid.uuid4())
        chain_event["timestamp"] = int(time.time() * 1000)
        chain_event["event_type"] = "FUNCTION_CALL_START"
        chain_event["source_id"] = str(self.app.participant.instance_handle)
        chain_event["target_id"] = target_provider_id if target_provider_id else function_name
        chain_event["status"] = 0
        
        self.chain_event_writer.write(chain_event)
        self.chain_event_writer.flush()

    def _publish_function_call_complete(self, chain_id: str, call_id: str, function_name: str, function_id: str, source_provider_id: str = None):
        """Publish a chain event for function call completion"""
        chain_event = dds.DynamicData(self.chain_event_type)
        chain_event["chain_id"] = chain_id
        chain_event["call_id"] = call_id
        chain_event["interface_id"] = str(self.app.participant.instance_handle)
        chain_event["primary_agent_id"] = ""
        chain_event["specialized_agent_ids"] = ""
        chain_event["function_id"] = function_id
        chain_event["query_id"] = str(uuid.uuid4())
        chain_event["timestamp"] = int(time.time() * 1000)
        chain_event["event_type"] = "FUNCTION_CALL_COMPLETE"
        chain_event["source_id"] = source_provider_id if source_provider_id else function_name
        chain_event["target_id"] = str(self.app.participant.instance_handle)
        chain_event["status"] = 0
        
        self.chain_event_writer.write(chain_event)
        self.chain_event_writer.flush() 
```

## genesis_lib/logging_config.py

**Author:** Jason

```python
import logging

# Define all known logger names used within the genesis_lib
# This list should be maintained as new loggers are added to the library.
GENESIS_LIB_LOGGERS = [
    "genesis_lib.agent",
    "genesis_lib.interface",
    "genesis_lib.monitored_agent",
    "genesis_lib.monitored_interface",
    "genesis_lib.openai_genesis_agent",
    "genesis_lib.function_classifier",
    "genesis_lib.function_discovery",
    "genesis_lib.generic_function_client",
    "genesis_lib.rpc_client",
    "genesis_lib.rpc_service",
    "genesis_lib.genesis_app",
    # Add other genesis_lib logger names here as they are created
]

def set_genesis_library_log_level(level: int) -> None:
    """
    Sets the logging level for all predefined genesis_lib loggers.

    Args:
        level: The logging level (e.g., logging.DEBUG, logging.INFO).
    """
    for logger_name in GENESIS_LIB_LOGGERS:
        logging.getLogger(logger_name).setLevel(level)
    # Also set the level for the root of the genesis_lib package itself,
    # in case some modules use logging.getLogger(__name__) directly under genesis_lib
    # and are not in the explicit list.
    logging.getLogger("genesis_lib").setLevel(level)

def get_genesis_library_loggers() -> list[str]:
    """Returns a copy of the list of known genesis_lib logger names."""
    return list(GENESIS_LIB_LOGGERS) 
```

## genesis_lib/rpc_service.py

**Author:** Jason

```python
"""
Genesis RPC Service

This module provides the core RPC service implementation for the Genesis framework,
enabling reliable function execution and communication between distributed components.
It serves as the foundation for all service-side RPC interactions in the Genesis network,
providing a robust and flexible interface for remote function handling.

Key responsibilities include:
- DDS-based RPC communication with remote clients
- Function registration and schema management
- Request handling and validation
- Error handling and response formatting
- Resource lifecycle management
- Common validation patterns for inputs

The GenesisRPCService is designed to be extended by specialized services and used by
higher-level components like EnhancedServiceBase. It handles the complexity of
DDS-based RPC communication, allowing developers to focus on implementing their
service functions without worrying about the underlying communication details.

The service supports:
- Automatic function registration with schemas
- JSON-based request/response handling
- Input validation with common patterns
- Asynchronous function execution
- Comprehensive error handling
- Resource cleanup and lifecycle management

Copyright (c) 2025, RTI & Jason Upchurch
"""

import rti.connextdds as dds
import rti.rpc
import asyncio
import logging
import json
import inspect
from typing import Dict, Any, Optional
from dataclasses import field
import jsonschema
import re

# Set up logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('GenesisRPCService')

class GenesisRPCService:
    """
    Base class for all Genesis RPC services.
    Provides function registration, request handling, and RPC communication.
    """
    def __init__(self, service_name: str = "GenesisRPCService"):
        """
        Initialize the RPC service.
        
        Args:
            service_name: Name of the service for RPC discovery
        """
        logger.info("Initializing DDS Domain Participant...")
        self.participant = dds.DomainParticipant(domain_id=0)
        
        logger.info("Creating RPC Replier...")
        self.replier = rti.rpc.Replier(
            request_type=self.get_request_type(),
            reply_type=self.get_reply_type(),
            participant=self.participant,
            service_name=service_name
        )
        
        # Dictionary to store registered functions and their schemas
        self.functions: Dict[str, Dict[str, Any]] = {}
        
        # Common schema patterns
        self.common_schemas = {
            "text": {
                "type": "string",
                "description": "Text input",
                "minLength": 1
            },
            "count": {
                "type": "integer",
                "description": "Count parameter",
                "minimum": 0,
                "maximum": 1000
            },
            "letter": {
                "type": "string",
                "description": "Single letter input",
                "minLength": 1,
                "maxLength": 1,
                "pattern": "^[a-zA-Z]$"
            },
            "number": {
                "type": "number",
                "description": "Numeric input"
            }
        }
    
    def get_request_type(self):
        """Get the request type for RPC communication. Override if needed."""
        from genesis_lib.datamodel import FunctionRequest
        return FunctionRequest
    
    def get_reply_type(self):
        """Get the reply type for RPC communication. Override if needed."""
        from genesis_lib.datamodel import FunctionReply
        return FunctionReply
    
    def register_function(self, 
                         func, 
                         description: str, 
                         parameters: Dict[str, Any],
                         operation_type: Optional[str] = None,
                         common_patterns: Optional[Dict[str, Any]] = None):
        """
        Register a function with its OpenAI-style schema
        
        Args:
            func: The function to register
            description: A description of what the function does
            parameters: JSON schema for the function parameters
            operation_type: Type of operation (e.g., "calculation", "transformation")
            common_patterns: Common validation patterns used by this function
            
        Returns:
            The registered function (allows use as a decorator)
        """
        from genesis_lib.datamodel import Tool, Function, validate_schema
        
        func_name = func.__name__
        logger.info(f"Registering function: {func_name}")
        
        # Validate the parameters schema
        try:
            validate_schema(parameters)
        except ValueError as e:
            logger.error(f"Invalid schema for function {func_name}: {str(e)}")
            raise
        
        # Create OpenAI-compliant function definition
        function = Function(
            name=func_name,
            description=description,
            parameters=json.dumps(parameters),
            strict=True
        )
        
        # Create OpenAI-compliant tool definition
        tool = Tool(type="function", function=function)
        
        # Store function and its schema
        self.functions[func_name] = {
            "tool": tool,
            "implementation": func,  # Store actual function for execution
            "operation_type": operation_type,
            "common_patterns": common_patterns
        }
        
        return func
    
    async def run(self):
        """Run the service and handle incoming requests."""
        logger.info(f"Service running with {len(self.functions)} registered functions.")
        logger.info(f"Available functions: {', '.join(self.functions.keys())}")
        logger.info("Waiting for requests...")
        
        try:
            while True:
                logger.debug("Waiting for next request...")
                requests = self.replier.receive_requests(max_wait=dds.Duration(3600))
                
                for request_sample in requests:
                    request = request_sample.data
                    request_info = request_sample.info  # Get the request info with publication handle
                    function_name = request.function.name
                    arguments_json = request.function.arguments
                    
                    logger.info(f"Received request: id={request.id}, function={function_name}, args={arguments_json}")
                    
                    reply = None
                    
                    try:
                        # Check if the function exists
                        if function_name in self.functions:
                            func = self.functions[function_name]["implementation"]
                            tool = self.functions[function_name]["tool"]
                            
                            # Parse the JSON arguments
                            try:
                                args_data = json.loads(arguments_json)
                                
                                # If strict mode is enabled, validate arguments against schema
                                if tool.function.strict:
                                    schema = json.loads(tool.function.parameters)
                                    jsonschema.validate(args_data, schema)
                                
                                # Call the function with the parsed arguments and request info
                                logger.debug(f"Calling {function_name} with args={args_data}")
                                
                                # Add request_info to the function call
                                args_data["request_info"] = request_info
                                
                                # Call the function
                                result = func(**args_data)
                                
                                # If the result is a coroutine, await it
                                if inspect.iscoroutine(result):
                                    result = await result
                                    
                                # Convert result to JSON
                                result_json = json.dumps(result)
                                logger.info(f"Function {function_name} returned: {result_json}")
                                
                                reply = self.get_reply_type()(
                                    result_json=result_json,
                                    success=True,
                                    error_message=""
                                )
                            except json.JSONDecodeError as e:
                                logger.error(f"Invalid JSON arguments: {str(e)}")
                                reply = self.get_reply_type()(
                                    result_json="null",
                                    success=False,
                                    error_message=f"Invalid JSON arguments: {str(e)}"
                                )
                            except Exception as e:
                                logger.error(f"Error executing function: {str(e)}", exc_info=True)
                                reply = self.get_reply_type()(
                                    result_json="null",
                                    success=False,
                                    error_message=f"Error executing function: {str(e)}"
                                )
                        else:
                            logger.warning(f"Unknown function requested: {function_name}")
                            reply = self.get_reply_type()(
                                result_json="null",
                                success=False,
                                error_message=f"Unknown function: {function_name}"
                            )
                    except Exception as e:
                        logger.error(f"Unexpected error processing request: {str(e)}", exc_info=True)
                        reply = self.get_reply_type()(
                            result_json="null",
                            success=False,
                            error_message=f"Internal service error: {str(e)}"
                        )
                    
                    if reply is None:
                        logger.error("No reply was created - this should never happen")
                        reply = self.get_reply_type()(
                            result_json="null",
                            success=False,
                            error_message="Internal service error: No reply created"
                        )
                        
                    logger.info(f"Sending reply: success={reply.success}")
                    self.replier.send_reply(reply, request_sample.info)

        except KeyboardInterrupt:
            logger.info("Service shutting down.")
        except Exception as e:
            logger.error(f"Unexpected error in service: {str(e)}", exc_info=True)
        finally:
            logger.info("Cleaning up service resources...")
            self.replier.close()
            self.participant.close()
            logger.info("Service cleanup complete.")

    def format_response(self, inputs: Dict[str, Any], result: Any, include_inputs: bool = True) -> Dict[str, Any]:
        """
        Format a function response with consistent structure.
        
        Args:
            inputs: Original input parameters
            result: Function result
            include_inputs: Whether to include input parameters in response
            
        Returns:
            Formatted response dictionary
        """
        response = {}
        
        # Include original inputs if requested
        if include_inputs:
            response.update(inputs)
            
        # Add result based on type
        if isinstance(result, dict):
            response.update(result)
        else:
            response["result"] = result
            
        return response

    def validate_text_input(self, text: str, min_length: int = 1, max_length: Optional[int] = None,
                          pattern: Optional[str] = None) -> None:
        """
        Validate text input against common constraints.
        
        Args:
            text: Text to validate
            min_length: Minimum length required
            max_length: Maximum length allowed (if any)
            pattern: Regex pattern to match (if any)
            
        Raises:
            ValueError: If validation fails
        """
        if not text or len(text) < min_length:
            raise ValueError(f"Text must be at least {min_length} character(s)")
            
        if max_length and len(text) > max_length:
            raise ValueError(f"Text cannot exceed {max_length} character(s)")
            
        if pattern and not re.match(pattern, text):
            raise ValueError(f"Text must match pattern: {pattern}")

    def validate_numeric_input(self, value: float, minimum: Optional[float] = None,
                             maximum: Optional[float] = None) -> None:
        """
        Validate numeric input against common constraints.
        
        Args:
            value: Number to validate
            minimum: Minimum value allowed (if any)
            maximum: Maximum value allowed (if any)
            
        Raises:
            ValueError: If validation fails
        """
        if minimum is not None and value < minimum:
            raise ValueError(f"Value must be at least {minimum}")
            
        if maximum is not None and value > maximum:
            raise ValueError(f"Value cannot exceed {maximum}")

    def get_common_schema(self, schema_type: str) -> Dict[str, Any]:
        """
        Get a common schema by type.
        
        Args:
            schema_type: Type of schema to get (e.g., 'text', 'count', 'letter', 'number')
            
        Returns:
            Schema dictionary
            
        Raises:
            ValueError: If schema type is not found
        """
        if schema_type not in self.common_schemas:
            raise ValueError(f"Unknown schema type: {schema_type}")
        return self.common_schemas[schema_type].copy()

    def close(self):
        """Clean up service resources"""
        logger.info("Cleaning up service resources...")
        if hasattr(self, 'replier'):
            self.replier.close()
        if hasattr(self, 'participant'):
            self.participant.close()
        logger.info("Service cleanup complete") 
```

## genesis_lib/generic_function_client.py

**Author:** Jason

```python
"""
Genesis Generic Function Client

This module provides a high-level client implementation for the Genesis framework that
enables dynamic discovery and invocation of functions across the distributed network.
It serves as a key integration point for agents and services to discover and utilize
functions without requiring prior knowledge of their implementation or location.

Key responsibilities include:
- Dynamic discovery of functions through the Genesis function registry
- Automatic service client lifecycle management
- Intelligent function routing based on service capabilities
- Schema validation and function metadata handling
- Seamless integration with the Genesis RPC system

The GenericFunctionClient is designed to be the primary interface for agents and
services to discover and call functions in the Genesis network. It handles all the
complexity of function discovery, service management, and RPC communication, allowing
developers to focus on building their agents and services without worrying about
the underlying communication details.

Copyright (c) 2025, RTI & Jason Upchurch
"""

#!/usr/bin/env python3

import logging
import asyncio
import json
import time
import uuid
from typing import Dict, Any, List, Optional
import rti.connextdds as dds
from genesis_lib.rpc_client import GenesisRPCClient
from genesis_lib.function_discovery import FunctionRegistry

# Configure logging
# logging.basicConfig(level=logging.WARNING,  # REMOVE THIS
#                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("generic_function_client")
# logger.setLevel(logging.INFO)  # REMOVE THIS

class GenericFunctionClient:
    """
    A truly generic function client that can discover and call any function service
    without prior knowledge of the specific functions.
    """
    
    def __init__(self, function_registry: Optional[FunctionRegistry] = None, participant: Optional[dds.DomainParticipant] = None, domain_id: int = 0):
        """
        Initialize the generic function client.
        
        Args:
            function_registry: Optional existing FunctionRegistry instance to use.
                             If None, a new one will be created.
            participant: Optional existing DDS Participant instance to use for the registry.
            domain_id: DDS domain ID to use if creating a new registry without a participant.
        """
        logger.debug("Initializing GenericFunctionClient")
        
        # Track if we created the registry
        self._created_registry = False
        if function_registry is None:
            self.function_registry = FunctionRegistry(participant=participant, domain_id=domain_id)
            self._created_registry = True
        else:
            self.function_registry = function_registry
        
        # Store discovered functions
        self.discovered_functions = {}
        
        # Store service-specific clients
        self.service_clients = {}
        
    async def discover_functions(self, timeout_seconds: int = 10) -> Dict[str, Any]:
        """
        Discover available functions in the distributed system.
        Waits until functions are discovered (signaled by registry event) or the timeout is reached.

        Args:
            timeout_seconds: How long to wait for functions to be discovered

        Returns:
            Dictionary of discovered functions
        """
        logger.debug(f"===== DDS TRACE: Waiting for function discovery event (timeout: {timeout_seconds}s)... =====")

        try:
            # Wait for the registry's discovery event or timeout
            registry_event = self.function_registry._discovery_event
            logger.debug(f"===== DDS TRACE: Waiting on event {id(registry_event)}... =====")
            await asyncio.wait_for(registry_event.wait(), timeout=timeout_seconds)
            logger.debug(f"===== DDS TRACE: Function discovery event received or already set (event: {id(registry_event)}). =====")
        except asyncio.TimeoutError:
            logger.warning(f"===== DDS TRACE: Timeout ({timeout_seconds}s) reached waiting for function discovery event. =====")
        except Exception as e:
             logger.error(f"===== DDS TRACE: Error waiting for function discovery event: {e} ====")

        # Regardless of event, grab the current state of discovered functions from the registry
        logger.debug("===== DDS TRACE: Retrieving discovered functions from registry... =====")
        self.discovered_functions = self.function_registry.discovered_functions.copy()
        logger.debug(f"===== DDS TRACE: Retrieved {len(self.discovered_functions)} functions from registry. =====")
        logger.debug("===== DDS TRACE: GenericFunctionClient internal cache content START =====")
        for func_id, func_data in self.discovered_functions.items():
            if isinstance(func_data, dict):
                cap_obj = func_data.get('capability')
                cap_type = type(cap_obj).__name__ if cap_obj else 'None'
                # Safely get service_name from dict first, then try from capability if needed
                service_name_from_dict = func_data.get('service_name', 'MISSING_IN_DICT')
                service_name_from_cap = 'N/A'
                if isinstance(cap_obj, dds.DynamicData) and 'service_name' in cap_obj:
                     try:
                         service_name_from_cap = cap_obj['service_name']
                     except Exception as e:
                         service_name_from_cap = f'ERROR_READING_CAP: {e}'
                elif cap_obj:
                    service_name_from_cap = 'WRONG_CAP_TYPE'
                
                logger.debug(f"  - ID: {func_id}, Name: {func_data.get('name')}, Provider: {func_data.get('provider_id')}, SvcName(dict): {service_name_from_dict}, CapType: {cap_type}, SvcName(cap): {service_name_from_cap}")
            else:
                logger.warning(f"  - ID: {func_id}, Unexpected data format: {type(func_data).__name__}")
        logger.debug("===== DDS TRACE: GenericFunctionClient internal cache content END =====")

        # Log the discovered functions
        if not self.discovered_functions:
            logger.warning("No functions were discovered in the registry.")
            return {}

        logger.debug(f"Discovered {len(self.discovered_functions)} functions in registry")
        for func_id, func_info in self.discovered_functions.items():
            if isinstance(func_info, dict):
                logger.debug(f"  - {func_id}: {func_info.get('name', 'unknown')} - {func_info.get('description', 'No description')}")
            else:
                logger.debug(f"  - {func_id}: {func_info}")
        
        return self.discovered_functions
    
    def get_service_client(self, service_name: str) -> GenesisRPCClient:
        """
        Get or create a client for a specific service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            RPC client for the service
        """
        if service_name not in self.service_clients:
            logger.debug(f"Creating new client for service: {service_name}")
            client = GenesisRPCClient(service_name=service_name)
            # Set a reasonable timeout (10 seconds)
            client.timeout = dds.Duration(seconds=10)
            self.service_clients[service_name] = client
        
        return self.service_clients[service_name]
    
    async def call_function(self, function_id: str, **kwargs) -> Dict[str, Any]:
        """
        Call a function by its ID with the given arguments.
        
        Args:
            function_id: ID of the function to call
            **kwargs: Arguments to pass to the function
            
        Returns:
            Function result
            
        Raises:
            ValueError: If the function is not found
            RuntimeError: If the function call fails
        """
        # Get function info directly from the registry
        registry_functions = self.function_registry.get_all_discovered_functions()
        func_info = registry_functions.get(function_id)

        if not func_info:
            # Attempt to refresh the function list from the registry if not found initially
            # This handles cases where functions might appear between the agent's last check and the call attempt.
            # However, OpenAIGenesisAgent now calls _ensure_functions_discovered (which uses list_available_functions)
            # on every request, so GenericFunctionClient's list_available_functions is already fresh.
            # The discover_functions method in GFC is more for an initial blocking discovery.
            # For call_function, if it's not in the registry's current snapshot, it's safer to error out.
            logger.error(f"Function ID {function_id} not found in FunctionRegistry's current list.")
            raise ValueError(f"Function not found: {function_id}")
        
        # Extract function name and provider ID
        if isinstance(func_info, dict):
            function_name = func_info.get('name')
            provider_id = func_info.get('provider_id')
            capability = func_info.get('capability') # Get the stored capability object
        else:
            raise RuntimeError(f"Invalid function info format for {function_id}")
        
        if not function_name:
            raise RuntimeError(f"Function name not found for {function_id}")
        
        # Determine the service name dynamically from the capability object
        service_name = None
        if capability:
            try:
                # Attempt to get service_name directly from the capability object
                # Access using dictionary syntax for dds.DynamicData
                if 'service_name' in capability:
                    service_name = capability['service_name']
                else:
                    logger.warning(f"'service_name' field missing in capability for {function_id}")
            except TypeError:
                logger.warning(f"Capability object for {function_id} is not dictionary-like or does not contain 'service_name'. Type: {type(capability)}")
            except KeyError:
                 logger.warning(f"'service_name' field not found in capability for {function_id}")
            except Exception as e:
                logger.warning(f"Error accessing service_name from capability for {function_id}: {e}")
        
        if not service_name:
            # If service_name couldn't be determined, raise an error
            logger.error(f"Could not determine service name for function {function_id} (provider: {provider_id})")
            raise RuntimeError(f"Service name not found for function {function_id}")
        
        logger.debug(f"Using discovered service name: {service_name} for function: {function_name} (provider: {provider_id})")
        
        # Get or create a client for this service
        client = self.get_service_client(service_name)
        
        # Wait for the service to be discovered
        logger.debug(f"Waiting for service {service_name} to be discovered")
        try:
            await client.wait_for_service(timeout_seconds=5)
        except TimeoutError as e:
            logger.warning(f"Service discovery timed out, but attempting call anyway: {str(e)}")
        
        # Call the function through RPC
        logger.debug(f"Calling function {function_name} via RPC")
        try:
            return await client.call_function(function_name, **kwargs)
        except Exception as e:
            raise RuntimeError(f"Error calling function {function_name}: {str(e)}")
    
    def get_function_schema(self, function_id: str) -> Dict[str, Any]:
        """
        Get the schema for a specific function.
        
        Args:
            function_id: ID of the function
            
        Returns:
            Function schema
            
        Raises:
            ValueError: If the function is not found
        """
        if function_id not in self.discovered_functions:
            raise ValueError(f"Function not found: {function_id}")
        
        return self.discovered_functions[function_id].schema
    
    def list_available_functions(self) -> List[Dict[str, Any]]:
        """
        List all available functions with their descriptions and schemas.
        Directly queries the FunctionRegistry for the most up-to-date list.
        
        Returns:
            List of function information dictionaries
        """
        result = []
        # Directly access the FunctionRegistry's list of discovered functions
        # The FunctionRegistry.get_all_discovered_functions() returns a copy of its internal dict.
        registry_functions = self.function_registry.get_all_discovered_functions()

        for func_id, func_info in registry_functions.items():
            if isinstance(func_info, dict):
                # Get the schema directly from the function info
                schema = func_info.get('schema', {})
                function_name = func_info.get('name', func_id)
                provider_id = func_info.get('provider_id')
                capability = func_info.get('capability')

                # Determine the service name dynamically
                service_name = None
                if capability:
                    try:
                        # Attempt to get service_name directly from the capability object
                        # Access using dictionary syntax for dds.DynamicData
                        if 'service_name' in capability:
                            service_name = capability['service_name']
                        else:
                            logger.warning(f"'service_name' field missing in capability for {func_id}")
                    except TypeError:
                         logger.warning(f"Capability object for {func_id} is not dictionary-like or does not contain 'service_name'. Type: {type(capability)}")
                    except KeyError:
                         logger.warning(f"'service_name' field not found in capability for {func_id}")
                    except Exception as e:
                        logger.warning(f"Error accessing service_name from capability for {func_id}: {e}")
                
                if not service_name:
                    # Fallback or default if service name cannot be determined
                    logger.warning(f"Could not determine service name for function {func_id} (provider: {provider_id}), using 'UnknownService'")
                    service_name = "UnknownService" 
                
                result.append({
                    "function_id": func_id,
                    "name": function_name,
                    "description": func_info.get('description', 'No description'),
                    "schema": schema,
                    "service_name": service_name
                })
            else:
                # Handle non-dictionary function info (unlikely but for robustness)
                result.append({
                    "function_id": func_id,
                    "name": str(func_info),
                    "description": "Unknown function format",
                    "schema": {},
                    "service_name": "UnknownService"
                })
        return result
    
    def close(self):
        """Close all client resources, including the FunctionRegistry if created by this instance"""
        logger.debug("Cleaning up GenericFunctionClient resources...")
        # Close service-specific clients
        for client in self.service_clients.values():
            client.close()
            
        # Close the FunctionRegistry if this client created it
        if self._created_registry and hasattr(self, 'function_registry') and self.function_registry:
            logger.debug("Closing FunctionRegistry created by GenericFunctionClient...")
            self.function_registry.close()
            self.function_registry = None # Clear reference
            
        logger.debug("GenericFunctionClient cleanup complete.")

async def run_generic_client_test():
    """
    Run a test of the generic function client.
    This test has zero knowledge of function schemas or calling conventions.
    It simply discovers functions and tests the first function it finds.
    """
    client = GenericFunctionClient()
    
    try:
        # Discover available functions
        await client.discover_functions()
        
        # List available functions
        functions = client.list_available_functions()
        print("\nAvailable Functions:")
        for func in functions:
            print(f"  - {func['function_id']}: {func['name']} - {func['description']}")
        
        if functions:
            # Test the first function we find
            test_func = functions[0]
            print(f"\nTesting function: {test_func['name']} - {test_func['description']}")
            
            # Get the schema to understand what parameters are needed
            schema = test_func['schema']
            print(f"Function schema: {json.dumps(schema, indent=2)}")
            
            # Extract required parameters and their types
            required_params = {}
            if 'properties' in schema:
                for param_name, param_schema in schema['properties'].items():
                    # Check if parameter is required
                    is_required = 'required' in schema and param_name in schema['required']
                    
                    if is_required:
                        # Determine a test value based on the parameter type
                        if param_schema.get('type') == 'number' or param_schema.get('type') == 'integer':
                            # Use a simple number for testing
                            required_params[param_name] = 10
                        elif param_schema.get('type') == 'string':
                            # Use a simple string for testing
                            required_params[param_name] = "test"
                        elif param_schema.get('type') == 'boolean':
                            # Use a simple boolean for testing
                            required_params[param_name] = True
                        else:
                            # Default to a string for unknown types
                            required_params[param_name] = "test"
            
            if required_params:
                print(f"Calling function with parameters: {required_params}")
                try:
                    result = await client.call_function(test_func['function_id'], **required_params)
                    print(f"Function returned: {result}")
                    print("✅ Test passed.")
                except Exception as e:
                    print(f"❌ Error calling function: {str(e)}")
            else:
                print("No required parameters found in schema, skipping test.")
        else:
            print("\nNo functions found to test.")
            
    except Exception as e:
        logger.error(f"Error in test: {str(e)}", exc_info=True)
    finally:
        client.close()

def main():
    """Main entry point"""
    logger.debug("Starting GenericFunctionClient")
    try:
        asyncio.run(run_generic_client_test())
    except KeyboardInterrupt:
        logger.debug("Client shutting down due to keyboard interrupt")
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 
```

## genesis_lib/interface.py

**Author:** Jason

```python
"""
Genesis Interface Base Class

This module provides the abstract base class `GenesisInterface` for all interfaces
within the Genesis framework. It establishes the core interface functionality,
communication patterns, and integration with the underlying DDS infrastructure
managed by `GenesisApp`.

Key responsibilities include:
- Initializing the interface's identity and DDS presence via `GenesisApp`.
- Setting up an RPC requester to send requests to agents.
- Handling agent discovery and registration monitoring.
- Providing utilities for interface lifecycle management (`connect_to_agent`, `send_request`, `close`).
- Managing callback registration for agent discovery and departure events.

This class serves as the foundation upon which specialized interfaces, like
`MonitoredInterface`, are built.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import time
import logging
import os
from abc import ABC
from typing import Any, Dict, Optional, List, Callable, Coroutine
import rti.connextdds as dds
import rti.rpc as rpc
from .genesis_app import GenesisApp
import uuid
import json
from genesis_lib.utils import get_datamodel_path
import asyncio
import traceback

# Get logger
logger = logging.getLogger(__name__)

class RegistrationListener(dds.DynamicData.NoOpDataReaderListener):
    """Listener for registration announcements"""
    def __init__(self, 
                 interface, 
                 loop: asyncio.AbstractEventLoop,
                 on_discovered: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None, 
                 on_departed: Optional[Callable[[str], Coroutine[Any, Any, None]]] = None):
        logger.debug("🔧 TRACE: RegistrationListener class init calling now")
        super().__init__()
        self.interface = interface
        self.received_announcements = {}  # Track announcements by instance_id
        self.on_agent_discovered = on_discovered
        self.on_agent_departed = on_departed
        self._loop = loop
        logger.debug("🔧 TRACE: Registration listener initialized with callbacks")
        
    def on_data_available(self, reader):
        """Handle new registration announcements and departures"""
        logger.debug("🔔 TRACE: RegistrationListener.on_data_available called (sync)")
        try:
            samples = reader.read()
            logger.debug(f"📦 TRACE: Read {len(samples)} samples from reader")
            
            for data, info in samples:
                if data is None:
                    logger.warning(f"⚠️ TRACE: Skipping sample - data is None. Instance Handle: {info.instance_handle if info else 'Unknown'}")
                    continue
                    
                instance_id = data.get_string('instance_id')
                if not instance_id:
                    logger.warning(f"⚠️ TRACE: Skipping sample - missing instance_id. Data: {data}")
                    continue

                if info.state.instance_state == dds.InstanceState.ALIVE:
                    if instance_id not in self.received_announcements:
                        service_name = data.get_string('service_name')
                        prefered_name = data.get_string('prefered_name')
                        agent_info = {
                            'message': data.get_string('message'),
                            'prefered_name': prefered_name,
                            'default_capable': data.get_int32('default_capable'),
                            'instance_id': instance_id,
                            'service_name': service_name,
                            'timestamp': time.time()
                        }
                        self.received_announcements[instance_id] = agent_info
                        logger.debug(f"✨ TRACE: Agent DISCOVERED: {prefered_name} ({service_name}) - ID: {instance_id}")
                        if self.on_agent_discovered:
                            # Schedule the async task creation onto the main loop thread
                            self._loop.call_soon_threadsafe(asyncio.create_task, self._run_discovery_callback(agent_info))
                elif info.state.instance_state in [dds.InstanceState.NOT_ALIVE_DISPOSED, dds.InstanceState.NOT_ALIVE_NO_WRITERS]:
                    if instance_id in self.received_announcements:
                        departed_info = self.received_announcements.pop(instance_id)
                        logger.debug(f"👻 TRACE: Agent DEPARTED: {departed_info.get('prefered_name', 'N/A')} - ID: {instance_id} - Reason: {info.state.instance_state}")
                        if self.on_agent_departed:
                            # Schedule the async task creation onto the main loop thread
                            self._loop.call_soon_threadsafe(asyncio.create_task, self._run_departure_callback(instance_id))
        except dds.Error as dds_e:
            logger.error(f"❌ TRACE: DDS Error in on_data_available: {dds_e}")
            logger.error(traceback.format_exc())
        except Exception as e:
            logger.error(f"❌ TRACE: Unexpected error processing registration announcement: {e}")
            logger.error(traceback.format_exc())

    def on_subscription_matched(self, reader, status):
        """Track when registration publishers are discovered"""
        logger.debug(f"🤝 TRACE: Registration subscription matched event. Current count: {status.current_count}")
        # We're not using this for discovery anymore, just logging for debugging

    # --- Helper methods to run async callbacks --- 
    async def _run_discovery_callback(self, agent_info: Dict[str, Any]):
        """Safely run the discovery callback coroutine."""
        try:
            # Check again in case the callback was unset between scheduling and running
            if self.on_agent_discovered: 
                await self.on_agent_discovered(agent_info)
        except Exception as cb_e:
            instance_id = agent_info.get('instance_id', 'UNKNOWN')
            logger.error(f"❌ TRACE: Error executing on_agent_discovered callback task for {instance_id}: {cb_e}")
            logger.error(traceback.format_exc())
            
    async def _run_departure_callback(self, instance_id: str):
        """Safely run the departure callback coroutine."""
        try:
            # Check again
            if self.on_agent_departed:
                await self.on_agent_departed(instance_id)
        except Exception as cb_e:
            logger.error(f"❌ TRACE: Error executing on_agent_departed callback task for {instance_id}: {cb_e}")
            logger.error(traceback.format_exc())
    # --- End helper methods --- 

class GenesisInterface(ABC):
    """Base class for all Genesis interfaces"""
    def __init__(self, interface_name: str, service_name: str):
        self.interface_name = interface_name
        self.service_name = service_name # This is the *interface's* service name, may differ from agent's
        self.app = GenesisApp(preferred_name=interface_name)
        self.discovered_agent_service_name: Optional[str] = None # To store discovered agent service name
        self.requester: Optional[rpc.Requester] = None # Requester will be created after discovery
        
        # Get types from XML
        config_path = get_datamodel_path()
        self.type_provider = dds.QosProvider(config_path)
        # Hardcode InterfaceAgent request/reply types
        self.request_type = self.type_provider.type("genesis_lib", "InterfaceAgentRequest")
        self.reply_type = self.type_provider.type("genesis_lib", "InterfaceAgentReply")
        
        # Store member names for later use
        self.reply_members = [member.name for member in self.reply_type.members()]
        
        # Placeholders for callbacks
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._on_agent_discovered_callback: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None
        self._on_agent_departed_callback: Optional[Callable[[str], Coroutine[Any, Any, None]]] = None
        
        # Set up registration monitoring with listener
        self._loop = asyncio.get_running_loop()
        self._setup_registration_monitoring()

    def _setup_registration_monitoring(self):
        """Set up registration monitoring with listener"""
        try:
            logger.debug("🔧 TRACE: Setting up registration monitoring...")
            
            # Configure reader QoS
            reader_qos = dds.QosProvider.default.datareader_qos
            reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
            reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            reader_qos.history.kind = dds.HistoryKind.KEEP_LAST
            reader_qos.history.depth = 500  # Match agent's writer depth
            reader_qos.liveliness.kind = dds.LivelinessKind.AUTOMATIC
            reader_qos.liveliness.lease_duration = dds.Duration(seconds=2)
            reader_qos.ownership.kind = dds.OwnershipKind.SHARED
            
            logger.debug("📋 TRACE: Configured reader QoS settings")
            
            # Create registration reader with listener
            logger.debug("🎯 TRACE: Creating registration listener...")
            self.registration_listener = RegistrationListener(
                self,
                self._loop,
                on_discovered=self._on_agent_discovered_callback, 
                on_departed=self._on_agent_departed_callback
            )
            
            logger.debug("📡 TRACE: Creating registration reader...")
            self.app.registration_reader = dds.DynamicData.DataReader(
                subscriber=self.app.subscriber,
                topic=self.app.registration_topic,
                qos=reader_qos,
                listener=self.registration_listener,
                mask=dds.StatusMask.DATA_AVAILABLE | dds.StatusMask.SUBSCRIPTION_MATCHED
            )
            
            logger.debug("✅ TRACE: Registration monitoring setup complete")
            
        except Exception as e:
            logger.error(f"❌ TRACE: Error setting up registration monitoring: {e}")
            logger.error(traceback.format_exc())
            raise

    async def connect_to_agent(self, service_name: str, timeout_seconds: float = 5.0) -> bool:
        """
        Create the RPC Requester to connect to a specific agent service.
        Waits briefly for the underlying DDS replier endpoint to be matched.
        """
        if self.requester:
             logger.warning(f"⚠️ TRACE: Requester already exists for service '{self.discovered_agent_service_name}'. Overwriting.")
             self.requester.close()

        logger.debug(f"🔗 TRACE: Attempting to connect to agent service: {service_name}")
        try:
            self.requester = rpc.Requester(
                request_type=self.request_type,
                reply_type=self.reply_type,
                participant=self.app.participant,
                service_name=service_name
            )
            self.discovered_agent_service_name = service_name

            start_time = time.time()
            while self.requester.matched_replier_count == 0:
                if time.time() - start_time > timeout_seconds:
                    logger.error(f"❌ TRACE: Timeout ({timeout_seconds}s) waiting for DDS replier match for service '{service_name}'")
                    self.requester.close()
                    self.requester = None
                    self.discovered_agent_service_name = None
                    return False
                await asyncio.sleep(0.1)
            
            logger.debug(f"✅ TRACE: RPC Requester created and DDS replier matched for service: {service_name}")
            return True
            
        except Exception as req_e:
            logger.error(f"❌ TRACE: Failed to create or match RPC Requester for service '{service_name}': {req_e}")
            logger.error(traceback.format_exc())
            self.requester = None
            self.discovered_agent_service_name = None
            return False

    async def _wait_for_rpc_match(self):
        """Helper to wait for RPC discovery"""
        if not self.requester:
             logger.warning("⚠️ TRACE: Requester not created yet, cannot wait for RPC match.")
             return
        while self.requester.matched_replier_count == 0:
            await asyncio.sleep(0.1)
        logger.debug(f"RPC match confirmed for service: {self.discovered_agent_service_name}!")

    async def send_request(self, request_data: Dict[str, Any], timeout_seconds: float = 10.0) -> Optional[Dict[str, Any]]:
        """Send request to agent and wait for reply"""
        if not self.requester:
            logger.error("❌ TRACE: Cannot send request, agent not discovered or requester not created.")
            return None
            
        try:
            # Create request
            request = dds.DynamicData(self.request_type)
            for key, value in request_data.items():
                request[key] = value
                
            # Send request and wait for reply using synchronous API in a thread
            logger.debug(f"Sending request to agent service '{self.discovered_agent_service_name}': {request_data}")
            
            def _send_request_sync(requester, req, timeout):
                # Ensure the requester is valid before using it
                if requester is None:
                    logger.error("❌ TRACE: _send_request_sync called with None requester.")
                    return None
                try:
                    request_id = requester.send_request(req)
                    # Convert float seconds to int seconds and nanoseconds
                    seconds = int(timeout)
                    nanoseconds = int((timeout - seconds) * 1e9)
                    replies = requester.receive_replies(
                        max_wait=dds.Duration(seconds=seconds, nanoseconds=nanoseconds),
                        min_count=1,
                        related_request_id=request_id
                    )
                    if replies:
                        return replies[0]  # Returns (reply, info) tuple
                    return None
                except Exception as sync_e:
                    logger.error(f"❌ TRACE: Error in _send_request_sync: {sync_e}")
                    logger.error(traceback.format_exc())
                    return None
                
            result = await asyncio.to_thread(_send_request_sync, self.requester, request, timeout_seconds)
            
            if result:
                reply, info = result
                # Convert reply to dict
                reply_dict = {}
                for member in self.reply_members:
                    reply_dict[member] = reply[member]
                    
                logger.debug(f"Received reply from agent: {reply_dict}")
                return reply_dict
            else:
                logger.error("No reply received")
                return None
            
        except dds.TimeoutError:
            logger.error(f"Timeout waiting for reply after {timeout_seconds} seconds")
            return None
        except Exception as e:
            logger.error(f"Error sending request: {e}")
            return None

    async def close(self):
        """Clean up resources"""
        if hasattr(self, 'requester') and self.requester: # Check if requester exists before closing
            self.requester.close()
        if hasattr(self, 'app'):
            await self.app.close()

    # --- New Callback Registration Methods ---
    def register_discovery_callback(self, callback: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]):
        """Register a callback to be invoked when an agent is discovered."""
        logger.debug(f"🔧 TRACE: Registering discovery callback: {callback.__name__ if callback else 'None'}")
        self._on_agent_discovered_callback = callback
        # If listener already exists, update its callback directly
        if hasattr(self, 'registration_listener') and self.registration_listener:
            self.registration_listener.on_agent_discovered = callback

    def register_departure_callback(self, callback: Callable[[str], Coroutine[Any, Any, None]]):
        """Register a callback to be invoked when an agent departs."""
        logger.debug(f"🔧 TRACE: Registering departure callback: {callback.__name__ if callback else 'None'}")
        self._on_agent_departed_callback = callback
        # If listener already exists, update its callback directly
        if hasattr(self, 'registration_listener') and self.registration_listener:
            self.registration_listener.on_agent_departed = callback
    # --- End New Callback Registration Methods --- 
```

## genesis_lib/datamodel.py

**Author:** Jason

```python
"""
Genesis Function Call Data Model

This module defines the data structures used for function calling RPC (Remote Procedure Call)
within the Genesis framework. It implements OpenAI-style function calling interfaces using
RTI's IDL (Interface Definition Language) for type-safe serialization and deserialization.

Key responsibilities include:
- Defining function call request/reply structures for RPC communication
- Implementing OpenAI-compatible function calling interfaces
- Providing schema validation for function definitions
- Supporting session management operations

Note: This is a temporary implementation that will be integrated into the main
datamodel.xml in a future update. The current separation allows for rapid iteration
on the function calling interface while maintaining compatibility with the existing
DDS infrastructure.

Copyright (c) 2025, RTI & Jason Upchurch
"""

from dataclasses import field
from typing import Union, Sequence, Optional, Dict, Any
import rti.idl as idl
from enum import IntEnum
import sys
import os
import json

@idl.struct(
    member_annotations = {
        'name': [idl.bound(255)],
        'description': [idl.bound(255)],
    }
)
class Function:
    """
    OpenAI-style function definition with name, description, and parameters.
    """
    name: str = ""  # Name of the function
    description: str = ""  # Description of what the function does
    parameters: str = ""  # JSON-encoded parameters schema
    strict: bool = True  # Whether to enforce strict type checking

@idl.struct(
    member_annotations = {
        'type': [idl.bound(255)],
    }
)
class Tool:
    """
    OpenAI-style tool definition, currently only supporting function tools.
    """
    type: str = "function"  # Type of tool (currently only "function" is supported)
    function: Function = field(default_factory=Function)  # Function definition

@idl.struct(
    member_annotations = {
        'name': [idl.bound(255)],
        'arguments': [idl.bound(255)],
    }
)
class FunctionCall:
    """
    OpenAI-style function call with name and arguments.
    """
    name: str = ""  # Name of the function to call
    arguments: str = ""  # JSON-encoded arguments for the function

@idl.struct(
    member_annotations = {
        'id': [idl.bound(255)],
        'type': [idl.bound(255)],
    }
)
class FunctionRequest:
    """
    OpenAI-style function request with unique ID and type.
    """
    id: str = ""  # Unique identifier for the function call
    type: str = "function"  # Always "function" to match OpenAI format
    function: FunctionCall = field(default_factory=FunctionCall)  # Nested function call details

@idl.struct(
    member_annotations = {
        'result_json': [],  # No bound annotation means unbounded
        'error_message': [idl.bound(255)],
    }
)
class FunctionReply:
    """
    Reply from a function execution with result and status.
    """
    result_json: str = ""  # JSON-encoded result from the function
    success: bool = False  # Whether the function executed successfully
    error_message: str = ""  # Error message if the function failed

@idl.struct
class SessionRequest:
    """Request for session management operations"""
    operation: str  # "CREATE", "JOIN", "LEAVE", "CLOSE"
    session_id: str  # UUID for the session
    client_id: str  # UUID of the client making the request
    metadata: str  # JSON string containing additional session metadata

@idl.struct
class SessionReply:
    """Reply to session management operations"""
    success: bool
    session_id: str  # UUID for the session
    error_message: str  # Empty if success is True
    metadata: str  # JSON string containing session state/metadata

@idl.struct
class SessionEvent:
    """Event published when session state changes"""
    event_type: str  # "CREATED", "JOINED", "LEFT", "CLOSED"
    session_id: str  # UUID for the session
    client_id: str  # UUID of the client involved
    timestamp: int  # Unix timestamp in milliseconds
    metadata: str  # JSON string containing event details

def validate_schema(schema: Dict[str, Any]) -> bool:
    """
    Validate that a schema follows OpenAI's function schema format.
    
    Args:
        schema: The schema to validate
        
    Returns:
        bool: True if valid, False otherwise
        
    Raises:
        ValueError: If the schema is invalid with details about why
    """
    required_fields = {"type", "properties"}
    if not isinstance(schema, dict):
        raise ValueError("Schema must be a dictionary")
    
    if not all(field in schema for field in required_fields):
        raise ValueError(f"Schema missing required fields: {required_fields - schema.keys()}")
    
    if schema["type"] != "object":
        raise ValueError('Schema "type" must be "object"')
    
    if not isinstance(schema["properties"], dict):
        raise ValueError("Schema properties must be a dictionary")
    
    for prop_name, prop in schema["properties"].items():
        if not isinstance(prop, dict):
            raise ValueError(f"Property {prop_name} must be a dictionary")
        if "type" not in prop:
            raise ValueError(f"Property {prop_name} missing required field 'type'")
        if "description" not in prop:
            raise ValueError(f"Property {prop_name} missing required field 'description'")
    
    return True 
```

## genesis_lib/llm.py

**Author:** Jason

```python
"""
LLM-related functionality for the GENESIS library
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from anthropic import Anthropic
import os

@dataclass
class Message:
    """Represents a single message in the conversation"""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

class ChatAgent(ABC):
    """Base class for chat agents"""
    def __init__(self, agent_name: str, model_name: str, system_prompt: Optional[str] = None,
                 max_history: int = 10):
        self.agent_name = agent_name
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.max_history = max_history
        self.conversations: Dict[str, List[Message]] = {}
        self.logger = logging.getLogger(__name__)
    
    def _cleanup_old_conversations(self):
        """Remove old conversations if we exceed max_history"""
        if len(self.conversations) > self.max_history:
            # Remove oldest conversation
            oldest_id = min(self.conversations.items(), key=lambda x: x[1][-1].timestamp)[0]
            del self.conversations[oldest_id]
    
    @abstractmethod
    def generate_response(self, message: str, conversation_id: str) -> tuple[str, int]:
        """Generate a response to the given message"""
        pass

class AnthropicChatAgent(ChatAgent):
    """Chat agent using Anthropic's Claude model"""
    def __init__(self, model_name: str = "claude-3-opus-20240229", api_key: Optional[str] = None,
                 system_prompt: Optional[str] = None, max_history: int = 10):
        super().__init__("Claude", model_name, system_prompt, max_history)
        # Get API key from environment if not provided
        if api_key is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key is None:
                raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
        self.client = Anthropic(api_key=api_key)
        self.logger.warning("AnthropicChatAgent initialized - this may cause rate limit issues")
    
    def generate_response(self, message: str, conversation_id: str) -> tuple[str, int]:
        """Generate a response using Claude"""
        try:
            self.logger.warning(f"AnthropicChatAgent.generate_response called with message: '{message[:30]}...' - this may cause rate limit issues")
            
            # Get or create conversation history
            if conversation_id not in self.conversations:
                self.conversations[conversation_id] = []
            
            # Add user message
            self.conversations[conversation_id].append(
                Message(role="user", content=message)
            )
            
            # Clean up empty messages from conversation history
            self.conversations[conversation_id] = [
                msg for msg in self.conversations[conversation_id]
                if msg.content.strip()  # Keep only messages with non-empty content
            ]
            
            # Generate response
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                system=self.system_prompt if self.system_prompt else "You are a helpful AI assistant.",
                messages=[
                    {"role": msg.role, "content": msg.content}
                    for msg in self.conversations[conversation_id]
                ]
            )
            
            # Get response text, handling empty responses
            response_text = response.content[0].text if response.content else ""
            
            # Add assistant response only if it's not empty
            if response_text.strip():
                self.conversations[conversation_id].append(
                    Message(role="assistant", content=response_text)
                )
            
            # Cleanup old conversations
            self._cleanup_old_conversations()
            
            return response_text, 0
            
        except Exception as e:
            self.logger.error(f"Error generating response: {e}")
            return str(e), 1 
```

## genesis_lib/function_classifier.py

**Author:** Jason

```python
#!/usr/bin/env python3

"""
Genesis Function Classifier

This module provides intelligent function classification capabilities for the Genesis framework,
enabling efficient and accurate matching between user queries and available functions. It serves
as a critical component in the function discovery and selection pipeline, using lightweight LLMs
to quickly identify relevant functions before deeper processing.

Key responsibilities include:
- Rapid classification of functions based on user queries
- Intelligent filtering of irrelevant functions
- Optimization of function selection for LLM processing
- Support for complex function metadata analysis
- Integration with the Genesis function discovery system

The FunctionClassifier enables the Genesis network to efficiently match user needs with
available capabilities, reducing the cognitive load on primary LLMs and improving
response times.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import os
import logging
import json
from typing import Dict, List, Any, Optional

# Configure logging
logger = logging.getLogger("genesis_function_classifier")

class FunctionClassifier:
    """
    Class for classifying and filtering functions based on their relevance to a user query.
    This class uses a lightweight LLM to quickly identify which functions are relevant
    to a given user query, reducing the number of functions that need to be passed to
    the main processing LLM.
    """
    
    def __init__(self, llm_client=None):
        """
        Initialize the function classifier
        
        Args:
            llm_client: The LLM client to use for classification (optional)
        """
        self.llm_client = llm_client
        logger.debug("===== TRACING: FunctionClassifier initialized =====")
    
    def _format_for_classification(self, functions: List[Dict]) -> str:
        """
        Format function metadata for efficient classification
        
        Args:
            functions: List of function metadata dictionaries
            
        Returns:
            Formatted function metadata as a string
        """
        formatted_functions = []
        
        for func in functions:
            # Extract the essential information for classification
            name = func.get("name", "")
            description = func.get("description", "")
            
            # Format the function information
            formatted_function = f"Function: {name}\nDescription: {description}\n"
            
            # Add parameter information if available
            schema = func.get("schema", {})
            if schema and "properties" in schema:
                formatted_function += "Parameters:\n"
                for param_name, param_info in schema["properties"].items():
                    param_desc = param_info.get("description", "")
                    formatted_function += f"- {param_name}: {param_desc}\n"
            
            formatted_functions.append(formatted_function)
        
        # Combine all formatted functions into a single string
        return "\n".join(formatted_functions)
    
    def _build_classification_prompt(self, query: str, formatted_functions: str) -> str:
        """
        Build a prompt for the classification LLM
        
        Args:
            query: The user query
            formatted_functions: Formatted function metadata
            
        Returns:
            Classification prompt as a string
        """
        return f"""
You are a function classifier for a distributed system. Your task is to identify which functions are relevant to the user's query.

User Query: {query}

Available Functions:
{formatted_functions}

Instructions:
1. Analyze the user query carefully.
2. Identify which functions would be helpful in answering the query.
3. Return ONLY the names of the relevant functions, one per line.
4. If no functions are relevant, return "NONE".

Relevant Functions:
"""
    
    def _parse_classification_result(self, result: str) -> List[str]:
        """
        Parse the classification result from the LLM
        
        Args:
            result: The classification result from the LLM
            
        Returns:
            List of relevant function names
        """
        # Split the result into lines and clean up
        lines = [line.strip() for line in result.strip().split("\n") if line.strip()]
        
        # Filter out any lines that are not function names
        function_names = []
        for line in lines:
            # Skip lines that are clearly not function names
            if line.lower() == "none":
                return []
            # Skip the "Relevant Functions" header that might be included in the response
            if line.lower() == "relevant functions":
                continue
            if ":" in line or line.startswith("-") or line.startswith("*"):
                # Extract the function name if it's in a list format
                parts = line.split(":", 1)
                if len(parts) > 1:
                    name = parts[0].strip("-* \t")
                    function_names.append(name)
                else:
                    name = line.strip("-* \t")
                    function_names.append(name)
            else:
                function_names.append(line)
        
        return function_names
    
    def classify_functions(self, query: str, functions: List[Dict], model_name: str = "gpt-4o") -> List[Dict]:
        """
        Classify functions based on their relevance to the user query
        
        Args:
            query: The user query
            functions: List of function metadata dictionaries
            model_name: The model to use for classification (default: "gpt-4o")
            
        Returns:
            List of relevant function metadata dictionaries
        """
        logger.debug(f"===== TRACING: Classifying functions for query: {query} =====")
        
        # If no LLM client is provided, return all functions
        if not self.llm_client:
            logger.warning("===== TRACING: No LLM client provided, returning all functions =====")
            return functions
        
        # If there are no functions, return an empty list
        if not functions:
            logger.warning("===== TRACING: No functions to classify =====")
            return []
        
        try:
            # Format the functions for classification
            formatted_functions = self._format_for_classification(functions)
            
            # Build the classification prompt
            prompt = self._build_classification_prompt(query, formatted_functions)
            
            # Call the LLM for classification
            logger.debug("===== TRACING: Calling LLM for function classification =====")
            
            # Use the OpenAI chat completions API with the specified model
            response = self.llm_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a function classifier that identifies relevant functions for user queries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            # Extract the result from the response
            result = response.choices[0].message.content
            
            # Parse the classification result
            relevant_function_names = self._parse_classification_result(result)
            
            logger.debug(f"===== TRACING: Identified {len(relevant_function_names)} relevant functions =====")
            for name in relevant_function_names:
                logger.debug(f"===== TRACING: Relevant function: {name} =====")
            
            # Filter the functions based on the classification result
            relevant_functions = []
            for func in functions:
                if func.get("name") in relevant_function_names:
                    relevant_functions.append(func)
            
            return relevant_functions
        except Exception as e:
            logger.error(f"===== TRACING: Error classifying functions: {str(e)} =====")
            # In case of error, return all functions
            return functions 
```

## genesis_lib/rpc_client.py

**Author:** Jason

```python
"""
Genesis RPC Client

This module provides the core RPC client implementation for the Genesis framework,
enabling reliable function calling and communication between distributed components.
It serves as the foundation for all client-side RPC interactions in the Genesis network,
providing a robust and flexible interface for remote function invocation.

Key responsibilities include:
- DDS-based RPC communication with remote services
- Function call validation and error handling
- Service discovery and connection management
- Input validation with configurable patterns
- Timeout and error handling
- Resource lifecycle management

The GenesisRPCClient is designed to be extended by specialized clients (e.g.,
TextProcessorClient) and used by higher-level components like GenericFunctionClient
and GenesisInterface. It handles the complexity of DDS-based RPC communication,
allowing developers to focus on building their services without worrying about
the underlying communication details.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import rti.connextdds as dds
import rti.rpc
import asyncio
import logging
import json
import time
import uuid
from typing import Any, Dict, Optional

# Set up logging
logging.basicConfig(level=logging.WARNING,  # Reduce verbosity
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('GenesisRPCClient')
logger.setLevel(logging.INFO)  # Keep INFO level for important events

class GenesisRPCClient:
    """
    Base class for all Genesis RPC clients.
    Provides function calling and RPC communication.
    """
    def __init__(self, service_name: str = "GenesisRPCService", timeout: int = 10):
        """
        Initialize the RPC client.
        
        Args:
            service_name: Name of the service to connect to
            timeout: Timeout in seconds for function calls
        """
        logger.info("Initializing DDS Domain Participant...")
        self.participant = dds.DomainParticipant(domain_id=0)
        
        logger.info(f"Creating RPC Requester for service: {service_name}...")
        self.requester = rti.rpc.Requester(
            request_type=self.get_request_type(),
            reply_type=self.get_reply_type(),
            participant=self.participant,
            service_name=service_name
        )
        
        self.timeout = dds.Duration(seconds=timeout)
        
        # Common validation patterns
        self.validation_patterns = {
            "text": {
                "min_length": 1,
                "max_length": None,
                "pattern": None
            },
            "letter": {
                "min_length": 1,
                "max_length": 1,
                "pattern": "^[a-zA-Z]$"
            },
            "count": {
                "minimum": 0,
                "maximum": 1000
            }
        }
    
    def get_request_type(self):
        """Get the request type for RPC communication. Override if needed."""
        from genesis_lib.datamodel import FunctionRequest
        return FunctionRequest
    
    def get_reply_type(self):
        """Get the reply type for RPC communication. Override if needed."""
        from genesis_lib.datamodel import FunctionReply
        return FunctionReply
    
    async def wait_for_service(self, timeout_seconds: int = 10) -> bool:
        """
        Wait for the service to be discovered.
        
        Args:
            timeout_seconds: How long to wait for service discovery
            
        Returns:
            True if service was discovered, False if timed out
            
        Raises:
            TimeoutError: If service is not discovered within timeout
        """
        logger.info("Waiting for service discovery...")
        start_time = time.time()
        while self.requester.matched_replier_count == 0:
            if time.time() - start_time > timeout_seconds:
                raise TimeoutError(f"Service discovery timed out after {timeout_seconds} seconds")
            await asyncio.sleep(0.1)
            
        logger.info(f"Service discovered! Matched replier count: {self.requester.matched_replier_count}")
        return True
    
    def validate_text(self, text: str, pattern_type: str = "text") -> None:
        """
        Validate text input using predefined patterns.
        
        Args:
            text: Text to validate
            pattern_type: Type of pattern to use (e.g., 'text', 'letter')
            
        Raises:
            ValueError: If validation fails
        """
        import re
        
        if pattern_type not in self.validation_patterns:
            raise ValueError(f"Unknown pattern type: {pattern_type}")
            
        pattern = self.validation_patterns[pattern_type]
        
        if not text:
            raise ValueError("Text cannot be empty")
            
        if pattern["min_length"] and len(text) < pattern["min_length"]:
            raise ValueError(f"Text must be at least {pattern['min_length']} character(s)")
            
        if pattern["max_length"] and len(text) > pattern["max_length"]:
            raise ValueError(f"Text cannot exceed {pattern['max_length']} character(s)")
            
        if pattern["pattern"] and not re.match(pattern["pattern"], text):
            raise ValueError(f"Text must match pattern: {pattern['pattern']}")

    def validate_numeric(self, value: float, pattern_type: str = "count") -> None:
        """
        Validate numeric input using predefined patterns.
        
        Args:
            value: Number to validate
            pattern_type: Type of pattern to use (e.g., 'count')
            
        Raises:
            ValueError: If validation fails
        """
        if pattern_type not in self.validation_patterns:
            raise ValueError(f"Unknown pattern type: {pattern_type}")
            
        pattern = self.validation_patterns[pattern_type]
        
        if pattern.get("minimum") is not None and value < pattern["minimum"]:
            raise ValueError(f"Value must be at least {pattern['minimum']}")
            
        if pattern.get("maximum") is not None and value > pattern["maximum"]:
            raise ValueError(f"Value cannot exceed {pattern['maximum']}")

    def handle_error_response(self, error_message: str) -> None:
        """
        Handle error responses with consistent error messages.
        
        Args:
            error_message: Error message from service
            
        Raises:
            ValueError: For validation errors
            RuntimeError: For other errors
        """
        # Common validation error patterns
        validation_patterns = [
            "must be at least",
            "cannot exceed",
            "must match pattern",
            "cannot be empty",
            "must be one of"
        ]
        
        # Check if this is a validation error
        if any(pattern in error_message.lower() for pattern in validation_patterns):
            raise ValueError(error_message)
        else:
            raise RuntimeError(error_message)

    async def call_function_with_validation(self, function_name: str, **kwargs) -> Dict[str, Any]:
        """
        Call a function with input validation.
        
        Args:
            function_name: Name of the function to call
            **kwargs: Function arguments
            
        Returns:
            Function result
            
        Raises:
            ValueError: For validation errors
            RuntimeError: For other errors
        """
        try:
            result = await self.call_function(function_name, **kwargs)
            return result
        except Exception as e:
            self.handle_error_response(str(e))

    async def call_function(self, function_name: str, **kwargs) -> Dict[str, Any]:
        """
        Call a remote function with the given name and arguments.
        
        Args:
            function_name: Name of the function to call
            **kwargs: Arguments to pass to the function
            
        Returns:
            Dictionary containing the function's result
            
        Raises:
            TimeoutError: If no reply is received within timeout
            RuntimeError: If the function call fails
            ValueError: If the result JSON is invalid
        """
        # Create a unique ID for this function call
        call_id = f"call_{uuid.uuid4().hex[:8]}"
        
        # Arguments are passed directly as kwargs
        arguments_json = json.dumps(kwargs)
        
        # Create the request with function call
        from genesis_lib.datamodel import FunctionCall
        request = self.get_request_type()(
            id=call_id,
            type="function",
            function=FunctionCall(
                name=function_name,
                arguments=arguments_json
            )
        )
        
        logger.info(f"Calling remote function: {function_name}")
        logger.debug(f"Call ID: {call_id}")
        logger.debug(f"Arguments: {arguments_json}")
        
        # Send the request
        request_id = self.requester.send_request(request)
        logger.debug("Request sent successfully")
        
        try:
            # Wait for and receive the reply
            logger.debug(f"Waiting for reply with timeout of {self.timeout.nanosec / 1e9} seconds")
            replies = self.requester.receive_replies(
                max_wait=self.timeout,
                related_request_id=request_id
            )
            
            if not replies:
                logger.error("No reply received within timeout period")
                raise TimeoutError(f"No reply received for function '{function_name}' within timeout period")
            
            # Process the reply
            reply = replies[0].data
            logger.debug(f"Received reply: success={reply.success}, error_message='{reply.error_message}'")
            
            if reply.success:
                # Parse the result JSON
                try:
                    result = json.loads(reply.result_json)
                    logger.info(f"Function {function_name} returned: {result}")
                    return result
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing result JSON: {str(e)}")
                    raise ValueError(f"Invalid result JSON: {str(e)}")
            else:
                logger.warning(f"Function call failed: {reply.error_message}")
                raise RuntimeError(f"Remote function call failed: {reply.error_message}")
                
        except dds.TimeoutError:
            logger.error(f"Timeout waiting for reply to '{function_name}' function call")
            raise TimeoutError(f"Timeout waiting for reply to '{function_name}' function call")
    
    def close(self):
        """Close the client resources."""
        logger.info("Cleaning up client resources...")
        self.requester.close()
        self.participant.close()
        logger.info("Client cleanup complete.") 
```

## genesis_lib/genesis_app.py

**Author:** Jason

```python
"""
Genesis Application Base Class

This module provides the foundational base class `GenesisApp` that serves as the core
integration point for all components in the Genesis framework. It establishes the
essential DDS infrastructure, function registration capabilities, and lifecycle
management that are required by both agents and interfaces.

Key responsibilities include:
- DDS participant and topic management
- Function registration and discovery infrastructure
- Agent registration and presence announcement
- Resource lifecycle management
- Error pattern handling and recovery
- Integration with the Genesis monitoring system

The GenesisApp class is designed to be extended by both `GenesisAgent` and
`GenesisInterface` classes, providing them with the necessary infrastructure
for DDS-based communication and function discovery. It handles the complexity
of DDS setup, QoS configuration, and resource management, allowing derived
classes to focus on their specific roles in the Genesis network.

Copyright (c) 2025, RTI & Jason Upchurch
"""

#!/usr/bin/env python3

import logging
import time
from typing import Dict, List, Any, Optional, Callable
import uuid
import rti.connextdds as dds
from genesis_lib.function_discovery import FunctionRegistry, FunctionInfo
from .function_patterns import SuccessPattern, FailurePattern, pattern_registry
import os
import traceback
from genesis_lib.utils import get_datamodel_path
import asyncio

# Configure logging
logger = logging.getLogger("genesis_app")

class GenesisApp:
    """
    Base class for Genesis applications that provides function registration
    and discovery capabilities.
    
    This class integrates with the FunctionRegistry to provide a clean
    interface for registering functions from Genesis applications.
    """
    
    def __init__(self, participant=None, domain_id=0, preferred_name="DefaultAgent", agent_id=None):
        """
        Initialize the Genesis application.
        
        Args:
            participant: DDS participant (if None, will create one)
            domain_id: DDS domain ID
            preferred_name: Preferred name for this application instance
            agent_id: Optional UUID for the agent (if None, will generate one)
        """
        # Generate or use provided agent ID
        self.agent_id = agent_id or str(uuid.uuid4())
        self.preferred_name = preferred_name
        
        # Initialize DDS participant
        if participant is None:
            participant_qos = dds.QosProvider.default.participant_qos
            self.participant = dds.DomainParticipant(domain_id, qos=participant_qos)
        else:
            self.participant = participant
            
        # Store DDS GUID
        self.dds_guid = str(self.participant.instance_handle)
        
        # Get types from XML
        config_path = get_datamodel_path()
        self.type_provider = dds.QosProvider(config_path)
        self.registration_type = self.type_provider.type("genesis_lib", "genesis_agent_registration_announce")
        
        # Create topics
        self.registration_topic = dds.DynamicData.Topic(
            self.participant, 
            "GenesisRegistration", 
            self.registration_type
        )
        
        # Create publisher and subscriber with QoS
        self.publisher = dds.Publisher(
            self.participant,
            qos=dds.QosProvider.default.publisher_qos
        )
        self.subscriber = dds.Subscriber(
            self.participant,
            qos=dds.QosProvider.default.subscriber_qos
        )
        
        # Create DataWriter with QoS
        writer_qos = dds.QosProvider.default.datawriter_qos
        writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        writer_qos.history.kind = dds.HistoryKind.KEEP_LAST
        writer_qos.history.depth = 500
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        writer_qos.liveliness.kind = dds.LivelinessKind.AUTOMATIC
        writer_qos.liveliness.lease_duration = dds.Duration(seconds=2)
        writer_qos.ownership.kind = dds.OwnershipKind.SHARED
        
        # Initialize function registry and pattern registry
        logger.debug("===== DDS TRACE: Initializing FunctionRegistry in GenesisApp =====")
        self.function_registry = FunctionRegistry(self.participant, domain_id)
        logger.debug(f"===== DDS TRACE: FunctionRegistry initialized with participant {self.participant.instance_handle} =====")
        self.pattern_registry = pattern_registry
        
        # Register built-in functions
        logger.debug("===== DDS TRACE: Starting built-in function registration =====")
        self._register_builtin_functions()
        logger.debug("===== DDS TRACE: Completed built-in function registration =====")
        
        logger.info(f"GenesisApp initialized with agent_id={self.agent_id}, dds_guid={self.dds_guid}")

    def get_available_functions(self) -> Dict[str, Dict[str, Any]]:
        """
        Retrieves a snapshot of all currently discovered functions available on the network.
        This information is sourced from the FunctionRegistry.

        Returns:
            A dictionary mapping function_id to its details (name, description, provider_id, etc.).
        """
        if hasattr(self, 'function_registry') and self.function_registry:
            return self.function_registry.get_all_discovered_functions()
        else:
            logger.warning("FunctionRegistry not available in GenesisApp, cannot get available functions.")
            return {}

    async def close(self):
        """Close all DDS entities and cleanup resources"""
        if hasattr(self, '_closed') and self._closed:
            logger.info(f"GenesisApp {self.agent_id} is already closed")
            return

        try:
            # Close DDS entities in reverse order of creation
            resources_to_close = ['function_registry', 'registration_topic',
                                'publisher', 'subscriber', 'participant']
            
            for resource in resources_to_close:
                if hasattr(self, resource):
                    try:
                        resource_obj = getattr(self, resource)
                        if hasattr(resource_obj, 'close') and not getattr(resource_obj, '_closed', False):
                            if asyncio.iscoroutinefunction(resource_obj.close):
                                await resource_obj.close()
                            else:
                                resource_obj.close()
                    except Exception as e:
                        # Only log as warning if the error is not about being already closed
                        if "already closed" not in str(e).lower():
                            logger.warning(f"Error closing {resource}: {str(e)}")
            
            # Mark as closed
            self._closed = True
            logger.info(f"GenesisApp {self.agent_id} closed successfully")
        except Exception as e:
            logger.error(f"Error closing GenesisApp: {str(e)}")
            logger.error(traceback.format_exc())

    # Sync version of close for backward compatibility
    def close_sync(self):
        """Synchronous version of close for backward compatibility"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.close())
        finally:
            loop.close()

    def _register_builtin_functions(self):
        """Register any built-in functions for this application"""
        logger.debug("===== DDS TRACE: _register_builtin_functions called =====")
        # Override this method in subclasses to register built-in functions
        pass

    def execute_function(self, function_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a registered function with error pattern checking.
        
        Args:
            function_id: ID of function to execute
            parameters: Function parameters
            
        Returns:
            Dictionary containing result or error information
        """
        try:
            # Execute the function
            result = super().execute_function(function_id, parameters)
            
            # Check result against patterns
            is_success, error_code, recovery_hint = self.pattern_registry.check_result(function_id, result)
            
            if is_success:
                return {
                    "status": "success",
                    "result": result
                }
            else:
                return {
                    "status": "error",
                    "error_code": error_code,
                    "message": str(result),
                    "recovery_hint": recovery_hint
                }
                
        except Exception as e:
            # Check if exception matches any failure patterns
            is_success, error_code, recovery_hint = self.pattern_registry.check_result(function_id, e)
            
            return {
                "status": "error",
                "error_code": error_code or "UNKNOWN_ERROR",
                "message": str(e),
                "recovery_hint": recovery_hint
            } 
```

## genesis_lib/monitored_interface.py

**Author:** Jason

```python
#!/usr/bin/env python3
"""
Genesis Monitored Interface

This module provides the `MonitoredInterface` class that extends `GenesisInterface`
to add comprehensive monitoring capabilities. It enhances the base interface with
event publishing, lifecycle tracking, and performance monitoring through the DDS
infrastructure.

Key responsibilities include:
- Extending GenesisInterface with standardized monitoring capabilities.
- Publishing interface lifecycle events (JOINING, DISCOVERING, READY, etc.).
- Tracking and publishing request/response events.
- Managing component lifecycle events and chain events.
- Providing enhanced monitoring through DDS topics and writers.
- Supporting both legacy and enhanced (V2) monitoring systems.

This class serves as the monitoring-enabled version of the base interface,
allowing interfaces to participate in the Genesis monitoring ecosystem.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import logging
import time
import uuid
import json
import os
from typing import Any, Dict, Optional, Callable, Coroutine
import rti.connextdds as dds
from .interface import GenesisInterface
from genesis_lib.utils import get_datamodel_path
import asyncio
import functools

# Configure logging
logger = logging.getLogger(__name__)

# Event type mapping
EVENT_TYPE_MAP = {
    "INTERFACE_DISCOVERY": 0,  # Legacy discovery event
    "INTERFACE_REQUEST": 1,    # Request event
    "INTERFACE_RESPONSE": 2,   # Response event
    "INTERFACE_STATUS": 3      # Status event
}

def monitor_method(event_type: str):
    """
    Decorator to add monitoring to interface methods.
    
    Args:
        event_type: Type of event to publish (e.g., "INTERFACE_REQUEST", "INTERFACE_RESPONSE")
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Get request data from args or kwargs
            request_data = args[0] if args else kwargs.get('request_data', {})
            
            # Publish request monitoring event
            self.publish_monitoring_event(
                event_type,
                metadata={
                    "interface_name": self.interface_name,
                    "service_name": self.service_name,
                    "provider_id": str(self.app.participant.instance_handle)
                },
                call_data=request_data if event_type == "INTERFACE_REQUEST" else None,
                result_data=request_data if event_type == "INTERFACE_RESPONSE" else None
            )
            
            # Call the original method
            result = await func(self, *args, **kwargs)
            
            # If this was a request and we got a response, publish response event
            if event_type == "INTERFACE_REQUEST" and result:
                self.publish_monitoring_event(
                    "INTERFACE_RESPONSE",
                    metadata={
                        "interface_name": self.interface_name,
                        "service_name": self.service_name,
                        "provider_id": str(self.app.participant.instance_handle)
                    },
                    result_data=result
                )
            
            return result
        return wrapper
    return decorator

class MonitoredInterface(GenesisInterface):
    """
    Base class for interfaces with monitoring capabilities.
    Extends GenesisInterface to add standardized monitoring.
    """
    
    def __init__(self, interface_name: str, service_name: str):
        """
        Initialize the monitored interface.
        
        Args:
            interface_name: Name of the interface
            service_name: Name of the service this interface connects to
        """
        super().__init__(interface_name=interface_name, service_name=service_name)
        
        # Set up monitoring
        self._setup_monitoring()
        
        # --- Callback related state ---
        self.available_agents: Dict[str, Dict[str, Any]] = {}
        self._agent_found_event = asyncio.Event()
        self._connected_agent_id: Optional[str] = None
        # --- End callback related state ---

        # Register internal handlers for discovery/departure
        # These methods are now defined within this class
        self.register_discovery_callback(self._handle_agent_discovered)
        self.register_departure_callback(self._handle_agent_departed)
        
        # Announce interface presence
        self._publish_discovery_event()
        
        logger.debug(f"Monitored interface {interface_name} initialized")
    
    def _setup_monitoring(self):
        """Set up DDS entities for monitoring"""
        # Get monitoring type from XML
        self.monitoring_type = self.type_provider.type("genesis_lib", "MonitoringEvent")
        
        # Create monitoring topic
        self.monitoring_topic = dds.DynamicData.Topic(
            self.app.participant,
            "MonitoringEvent",
            self.monitoring_type
        )
        
        # Create monitoring publisher with QoS
        publisher_qos = dds.QosProvider.default.publisher_qos
        publisher_qos.partition.name = [""]  # Default partition
        self.monitoring_publisher = dds.Publisher(
            participant=self.app.participant,
            qos=publisher_qos
        )
        
        # Create monitoring writer with QoS
        writer_qos = dds.QosProvider.default.datawriter_qos
        writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        self.monitoring_writer = dds.DynamicData.DataWriter(
            pub=self.monitoring_publisher,
            topic=self.monitoring_topic,
            qos=writer_qos
        )

        # Set up enhanced monitoring (V2)
        # Create topics for new monitoring types
        self.component_lifecycle_type = self.type_provider.type("genesis_lib", "ComponentLifecycleEvent")
        self.chain_event_type = self.type_provider.type("genesis_lib", "ChainEvent")
        self.liveliness_type = self.type_provider.type("genesis_lib", "LivelinessUpdate")

        # Create topics
        self.component_lifecycle_topic = dds.DynamicData.Topic(
            self.app.participant,
            "ComponentLifecycleEvent",
            self.component_lifecycle_type
        )
        self.chain_event_topic = dds.DynamicData.Topic(
            self.app.participant,
            "ChainEvent",
            self.chain_event_type
        )
        self.liveliness_topic = dds.DynamicData.Topic(
            self.app.participant,
            "LivelinessUpdate",
            self.liveliness_type
        )

        # Create writers with QoS
        writer_qos = dds.QosProvider.default.datawriter_qos
        writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE

        # Create writers for each monitoring type
        self.component_lifecycle_writer = dds.DynamicData.DataWriter(
            pub=self.monitoring_publisher,
            topic=self.component_lifecycle_topic,
            qos=writer_qos
        )
        self.chain_event_writer = dds.DynamicData.DataWriter(
            pub=self.monitoring_publisher,
            topic=self.chain_event_topic,
            qos=writer_qos
        )
        self.liveliness_writer = dds.DynamicData.DataWriter(
            pub=self.monitoring_publisher,
            topic=self.liveliness_topic,
            qos=writer_qos
        )
    
    def _publish_discovery_event(self):
        """Publish interface discovery event"""
        interface_id = str(self.app.participant.instance_handle)
        
        # First publish node discovery event for the interface itself
        self.publish_component_lifecycle_event(
            previous_state="DISCOVERING",
            new_state="DISCOVERING",
            reason=f"Component {interface_id} joined domain",
            capabilities=json.dumps({
                "interface_type": "INTERFACE",
                "service": self.service_name,
                "interface_id": interface_id
            }),
            event_category="NODE_DISCOVERY",
            source_id=interface_id,
            target_id="N/A"  # For node discovery of self, target is same as source
        )

        # Publish legacy monitoring event
        self.publish_monitoring_event(
            "INTERFACE_DISCOVERY",
            metadata={
                "interface_name": self.interface_name,
                "service_name": self.service_name,
                "provider_id": interface_id
            },
            status_data={"status": "available", "state": "ready"}
        )

        # Transition to discovering state
        self.publish_component_lifecycle_event(
            previous_state="JOINING",
            new_state="DISCOVERING",
            reason=f"{interface_id} JOINING -> DISCOVERING",
            capabilities=json.dumps({
                "interface_type": "INTERFACE",
                "service": self.service_name,
                "interface_id": interface_id
            }),
            event_category="STATE_CHANGE",
            source_id=interface_id,
            target_id=interface_id  # For state changes, target is self
        )

        # Transition to ready state
        self.publish_component_lifecycle_event(
            previous_state="DISCOVERING",
            new_state="READY",
            reason=f"{interface_id} DISCOVERING -> READY",
            capabilities=json.dumps({
                "interface_type": "INTERFACE",
                "service": self.service_name,
                "interface_id": interface_id
            }),
            event_category="STATE_CHANGE",
            source_id=interface_id,
            target_id=interface_id  # For state changes, target is self
        )
    
    def publish_monitoring_event(self, 
                               event_type: str,
                               metadata: Optional[Dict[str, Any]] = None,
                               call_data: Optional[Dict[str, Any]] = None,
                               result_data: Optional[Dict[str, Any]] = None,
                               status_data: Optional[Dict[str, Any]] = None,
                               request_info: Optional[Any] = None) -> None:
        """
        Publish a monitoring event.
        
        Args:
            event_type: Type of event (INTERFACE_DISCOVERY, INTERFACE_REQUEST, etc.)
            metadata: Additional metadata about the event
            call_data: Data about the request/call (if applicable)
            result_data: Data about the response/result (if applicable)
            status_data: Data about the interface status (if applicable)
            request_info: Request information containing client ID
        """
        try:
            event = dds.DynamicData(self.monitoring_type)
            
            # Set basic fields
            event["event_id"] = str(uuid.uuid4())
            event["timestamp"] = int(time.time() * 1000)
            event["event_type"] = EVENT_TYPE_MAP[event_type]
            event["entity_type"] = 0  # INTERFACE enum value
            event["entity_id"] = self.interface_name
            
            # Set optional fields
            if metadata:
                event["metadata"] = json.dumps(metadata)
            if call_data:
                event["call_data"] = json.dumps(call_data)
            if result_data:
                event["result_data"] = json.dumps(result_data)
            if status_data:
                event["status_data"] = json.dumps(status_data)
            
            # Write the event
            self.monitoring_writer.write(event)
            logger.debug(f"Published monitoring event: {event_type}")
            
        except Exception as e:
            logger.error(f"Error publishing monitoring event: {str(e)}")
    
    def publish_component_lifecycle_event(self, 
                                       previous_state: str,
                                       new_state: str,
                                       reason: str = "",
                                       capabilities: str = "",
                                       chain_id: str = "",
                                       call_id: str = "",
                                       event_category: str = None,
                                       source_id: str = "",
                                       target_id: str = "",
                                       connection_type: str = None):
        """
        Publish a component lifecycle event for the interface.
        
        Args:
            previous_state: Previous state of the interface (JOINING, DISCOVERING, READY, etc.)
            new_state: New state of the interface
            reason: Reason for the state change
            capabilities: Interface capabilities as JSON string
            chain_id: ID of the chain this event belongs to (if any)
            call_id: Call ID (if any)
            event_category: Category of the event (NODE_DISCOVERY, EDGE_DISCOVERY, STATE_CHANGE)
            source_id: Source ID of the event
            target_id: Target ID of the event
            connection_type: Type of connection for edge discovery events (optional)
        """
        try:
            # Map state strings to enum values
            states = {
                "JOINING": 0,
                "DISCOVERING": 1,
                "READY": 2,
                "BUSY": 3,
                "DEGRADED": 4,
                "OFFLINE": 5
            }
            
            # Map event categories to enum values
            event_categories = {
                "NODE_DISCOVERY": 0,
                "EDGE_DISCOVERY": 1,
                "STATE_CHANGE": 2,
                "AGENT_INIT": 3,
                "AGENT_READY": 4,
                "AGENT_SHUTDOWN": 5,
                "DDS_ENDPOINT": 6
            }
            
            # Get interface ID - this is our component ID
            interface_id = str(self.app.participant.instance_handle)
            
            # Ensure we have a source_id for all events
            if not source_id:
                source_id = interface_id
            
            event = dds.DynamicData(self.component_lifecycle_type)
            event["component_id"] = interface_id
            event["component_type"] = 0  # INTERFACE enum value
            event["previous_state"] = states[previous_state]
            event["new_state"] = states[new_state]
            event["timestamp"] = int(time.time() * 1000)
            event["reason"] = reason
            event["capabilities"] = capabilities
            event["chain_id"] = chain_id
            event["call_id"] = call_id
            
            # Handle event categorization with proper ID requirements
            if event_category:
                event["event_category"] = event_categories[event_category]  # Use direct lookup instead of .get()
                event["source_id"] = source_id
                
                if event_category == "EDGE_DISCOVERY":
                    # For edge events, ensure we have different source and target IDs
                    if not target_id or target_id == source_id:
                        logger.warning("Edge discovery event requires different source and target IDs")
                        return
                    event["target_id"] = target_id
                    event["connection_type"] = connection_type if connection_type else "agent_connection"
                elif event_category == "STATE_CHANGE":
                    # For state changes, both source and target should be the interface ID
                    event["source_id"] = interface_id
                    event["target_id"] = interface_id
                    event["connection_type"] = ""
                else:
                    # For other events, use provided target_id or leave empty
                    event["target_id"] = target_id if target_id else ""
                    event["connection_type"] = ""
            else:
                # Default to state change if no category provided
                event["event_category"] = event_categories["STATE_CHANGE"]
                event["source_id"] = interface_id
                event["target_id"] = interface_id
                event["connection_type"] = ""

            self.component_lifecycle_writer.write(event)
            self.component_lifecycle_writer.flush()
            logger.debug(f"Published component lifecycle event: {previous_state} -> {new_state}")
        except Exception as e:
            logger.error(f"Error publishing component lifecycle event: {e}")
            logger.error(f"Event category was: {event_category}")
    
    # --- Internal Callback Handlers --- 
    async def _handle_agent_discovered(self, agent_info: dict):
        """Internal callback handler for agent discovery."""
        instance_id = agent_info['instance_id']
        prefered_name = agent_info['prefered_name']
        service_name = agent_info['service_name']
        logger.debug(f"<MonitoredInterface Handler> Agent Discovered: {prefered_name} ({service_name}) - ID: {instance_id}")
        self.available_agents[instance_id] = agent_info
        # For this simple test, signal that *an* agent is found
        # A real app might have more complex logic here (e.g., find specific name)
        # Or expose the event/agents list publicly for the app to manage.
        if not self._agent_found_event.is_set():
            logger.debug("<MonitoredInterface Handler> Signaling internal agent found event.")
            self._agent_found_event.set() 

    async def _handle_agent_departed(self, instance_id: str):
        """Internal callback handler for agent departure."""
        if instance_id in self.available_agents:
            departed_agent = self.available_agents.pop(instance_id)
            prefered_name = departed_agent.get('prefered_name', 'N/A')
            logger.debug(f"<MonitoredInterface Handler> Agent Departed: {prefered_name} - ID: {instance_id}")
            # If the departed agent was the one we connected to, handle it
            if instance_id == self._connected_agent_id:
                 logger.warning(f"<MonitoredInterface Handler> Connected agent {prefered_name} departed! Need to handle reconnection or failure.")
                 self._connected_agent_id = None
                 # Consider if requester should be closed here? Or just let send_request fail?
                 # self.requester.close() # This might cause issues if called from callback context
                 # Potentially clear the event if the application logic relies on it
                 # self._agent_found_event.clear() # If we need to wait for a *new* agent
        else:
            logger.warning(f"<MonitoredInterface Handler> Received departure for unknown agent ID: {instance_id}")
    # --- End Internal Callback Handlers ---

    @monitor_method("INTERFACE_REQUEST")
    async def send_request(self, request_data: Dict[str, Any], timeout_seconds: float = 10.0) -> Optional[Dict[str, Any]]:
        """Send request to agent with monitoring"""
        # Check if we are connected before sending
        if not self.requester or not self._connected_agent_id:
            logger.error("❌ MonitoredInterface cannot send request, not connected to an agent.")
            # Check if the agent we thought we were connected to just departed
            if self._connected_agent_id and self._connected_agent_id not in self.available_agents:
                logger.warning("Connection lost as the target agent departed.")
                self._connected_agent_id = None # Ensure state reflects disconnection
            return None
        
        return await super().send_request(request_data, timeout_seconds)
    
    async def close(self):
        """Clean up resources"""
        try:
            # First transition to BUSY state for shutdown
            self.publish_component_lifecycle_event(
                previous_state="READY",
                new_state="BUSY",
                reason=f"Interface {self.interface_name} preparing for shutdown"
            )

            # Add a small delay to ensure events are distinguishable
            await asyncio.sleep(0.1)

            # Then transition to OFFLINE
            self.publish_component_lifecycle_event(
                previous_state="BUSY",
                new_state="OFFLINE",
                reason=f"Interface {self.interface_name} shutting down"
            )

            # Publish legacy offline status
            self.publish_monitoring_event(
                "INTERFACE_STATUS",
                status_data={"status": "offline"},
                metadata={"service": self.service_name}
            )
            
            # Close monitoring resources
            if hasattr(self, 'monitoring_writer'):
                self.monitoring_writer.close()
            if hasattr(self, 'monitoring_publisher'):
                self.monitoring_publisher.close()
            if hasattr(self, 'monitoring_topic'):
                self.monitoring_topic.close()
            if hasattr(self, 'component_lifecycle_writer'):
                self.component_lifecycle_writer.close()
            if hasattr(self, 'chain_event_writer'):
                self.chain_event_writer.close()
            if hasattr(self, 'liveliness_writer'):
                self.liveliness_writer.close()
            
            # Close base class resources
            await super().close()
            
        except Exception as e:
            logger.error(f"Error closing monitored interface: {str(e)}") 
```

## genesis_lib/agent.py

**Author:** Jason

```python
"""
Genesis Agent Base Class

This module provides the abstract base class `GenesisAgent` for all agents
within the Genesis framework. It establishes the core agent lifecycle,
communication patterns, and integration with the underlying DDS infrastructure
managed by `GenesisApp`.

Key responsibilities include:
- Initializing the agent's identity and DDS presence via `GenesisApp`.
- Handling agent registration on the Genesis network.
- Setting up an RPC replier to receive and process requests for the agent's service.
- Defining an abstract `process_request` method that concrete subclasses must implement
  to handle service-specific logic.
- Providing utilities for agent lifecycle management (`run`, `close`).
- Offering mechanisms for function discovery within the Genesis network.

This class serves as the foundation upon which specialized agents, like
`MonitoredAgent`, are built.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import sys
import time
import logging
import os
import json
import asyncio
import traceback
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
import rti.connextdds as dds
import rti.rpc as rpc
from .genesis_app import GenesisApp
from .llm import ChatAgent, AnthropicChatAgent
from .utils import get_datamodel_path

# Get logger
logger = logging.getLogger(__name__)

class GenesisAgent(ABC):
    """Base class for all Genesis agents"""
    registration_writer: Optional[dds.DynamicData.DataWriter] = None # Define at class level

    def __init__(self, agent_name: str, base_service_name: str, 
                 service_instance_tag: Optional[str] = None, agent_id: str = None):
        """
        Initialize the agent.
        
        Args:
            agent_name: Name of the agent (for display, identification)
            base_service_name: The fundamental type of service offered (e.g., "Chat", "ImageGeneration")
            service_instance_tag: Optional tag to make this instance's RPC service name unique (e.g., "Primary", "User1")
            agent_id: Optional UUID for the agent (if None, will generate one)
        """
        logger.info(f"GenesisAgent {agent_name} STARTING initializing with agent_id {agent_id}, base_service_name: {base_service_name}, tag: {service_instance_tag}")
        self.agent_name = agent_name
        
        self.base_service_name = base_service_name
        if service_instance_tag:
            self.rpc_service_name = f"{base_service_name}_{service_instance_tag}"
        else:
            self.rpc_service_name = base_service_name
        
        logger.info(f"Determined RPC service name: {self.rpc_service_name}")

        logger.debug("===== DDS TRACE: Creating GenesisApp in GenesisAgent =====")
        self.app = GenesisApp(preferred_name=self.agent_name, agent_id=agent_id)
        logger.debug(f"===== DDS TRACE: GenesisApp created with agent_id {self.app.agent_id} =====")
        logger.info(f"GenesisAgent {self.agent_name} initialized with app {self.app.agent_id}")


        # Get types from XML
        config_path = get_datamodel_path()
        self.type_provider = dds.QosProvider(config_path)
        # Initialize RPC types
        self.request_type = self.type_provider.type("genesis_lib", "InterfaceAgentRequest")
        self.reply_type = self.type_provider.type("genesis_lib", "InterfaceAgentReply")
        logger.info(f"GenesisAgent {self.agent_name} initialized with hardcoded InterfaceAgent RPC types")
        # Create event loop for async operations
        self.loop = asyncio.get_event_loop()
        logger.info(f"GenesisAgent {self.agent_name} initialized with loop {self.loop}")


        # Create registration writer with QoS
        writer_qos = dds.QosProvider.default.datawriter_qos
        writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        writer_qos.history.kind = dds.HistoryKind.KEEP_LAST
        writer_qos.history.depth = 500
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        writer_qos.liveliness.kind = dds.LivelinessKind.AUTOMATIC
        writer_qos.liveliness.lease_duration = dds.Duration(seconds=2)
        writer_qos.ownership.kind = dds.OwnershipKind.SHARED

        # Create registration writer
        self.registration_writer = dds.DynamicData.DataWriter(
            self.app.publisher,
            self.app.registration_topic,
            qos=writer_qos
        )
        logger.debug("✅ TRACE: Registration writer created with QoS settings")

        # Create replier with data available listener
        class RequestListener(dds.DynamicData.DataReaderListener):
            def __init__(self, agent):
                super().__init__()  # Call parent class __init__
                self.agent = agent
                
            def on_data_available(self, reader):
                # Get all available samples
                samples = self.agent.replier.take_requests()
                for request, info in samples:
                    if request is None or info.state.instance_state != dds.InstanceState.ALIVE:
                        continue
                        
                    logger.info(f"Received request: {request}")
                    
                    try:
                        # Create task to process request asynchronously
                        asyncio.run_coroutine_threadsafe(self._process_request(request, info), self.agent.loop)
                    except Exception as e:
                        logger.error(f"Error creating request processing task: {e}")
                        logger.error(traceback.format_exc())
                        
            async def _process_request(self, request, info):
                try:
                    request_dict = {}
                    if hasattr(self.agent.request_type, 'members') and callable(self.agent.request_type.members):
                        for member in self.agent.request_type.members():
                            member_name = member.name
                            try:
                                # Check member type and use appropriate getter
                                # Assuming InterfaceAgentRequest has only string members for now
                                # A more robust solution would check member.type.kind
                                if member.type.kind == dds.TypeKind.STRING_TYPE:
                                    request_dict[member_name] = request.get_string(member_name)
                                # TODO: Add handling for other types (INT32, BOOLEAN, etc.) if InterfaceAgentRequest evolves
                                else:
                                    logger.warning(f"Unsupported member type for '{member_name}' during DDS-to-dict conversion. Attempting direct assignment (may fail).")
                                    # This part is risky and likely incorrect for non-basic types if not handled properly
                                    request_dict[member_name] = request[member_name] 
                            except Exception as e:
                                logger.warning(f"Could not convert member '{member_name}' from DDS request to dict: {e}")
                    else:
                        logger.error("Cannot convert DDS request to dict: self.agent.request_type does not have a members() method. THIS IS A PROBLEM.")
                        # If we can't determine members, we can't reliably convert.
                        # Passing the raw request here would be inconsistent with agents expecting a dict.
                        # It's better to let it fail or send an error reply if conversion is impossible.
                        raise TypeError("Failed to introspect request_type members for DDS-to-dict conversion.")

                    # Get reply data from concrete implementation, passing the dictionary
                    reply_data = await self.agent.process_request(request_dict)
                    
                    # Create reply
                    reply = dds.DynamicData(self.agent.reply_type)
                    for key, value in reply_data.items():
                        reply[key] = value
                        
                    # Send reply
                    self.agent.replier.send_reply(reply, info)
                    logger.info(f"Sent reply: {reply}")
                except Exception as e:
                    logger.error(f"Error processing request: {e}")
                    logger.error(traceback.format_exc())
                    # Send error reply
                    reply = dds.DynamicData(self.agent.reply_type)
                    reply["status"] = 1  # Error status
                    reply["message"] = f"Error: {str(e)}"
                    self.agent.replier.send_reply(reply, info)
        
        # Create replier with listener
        self.replier = rpc.Replier(
            request_type=self.request_type,
            reply_type=self.reply_type,
            participant=self.app.participant,
            service_name=self.rpc_service_name
        )
        
        # Set listener on replier's DataReader with status mask for data available
        self.request_listener = RequestListener(self)
        mask = dds.StatusMask.DATA_AVAILABLE
        self.replier.request_datareader.set_listener(self.request_listener, mask)
        
        # Store discovered functions
        # self.discovered_functions = [] # Removed as per event-driven plan

    @abstractmethod
    async def process_request(self, request: Any) -> Dict[str, Any]:
        """Process the request and return reply data as a dictionary"""
        pass

    async def run(self):
        """Main agent loop"""
        try:
            # Announce presence
            logger.info("Announcing agent presence...")
            await self.announce_self()
            
            # Main loop - just keep the event loop running
            logger.info(f"{self.agent_name} listening for requests (Ctrl+C to exit)...")
            shutdown_event = asyncio.Event()
            await shutdown_event.wait()
                
        except KeyboardInterrupt:
            logger.info(f"\nShutting down {self.agent_name}...")
            await self.close()
            sys.exit(0)

    async def close(self):
        """Clean up resources"""
        try:
            # Close replier first
            if hasattr(self, 'replier') and not getattr(self.replier, '_closed', False):
                self.replier.close()
                
            # Close app last since it handles registration
            if hasattr(self, 'app') and self.app is not None and not getattr(self.app, '_closed', False):
                await self.app.close()
                
            logger.info(f"GenesisAgent {self.agent_name} closed successfully")
        except Exception as e:
            logger.error(f"Error closing GenesisAgent: {str(e)}")
            logger.error(traceback.format_exc())

    # Sync version of close for backward compatibility
    def close_sync(self):
        """Synchronous version of close for backward compatibility"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.close())
        finally:
            loop.close()

    async def announce_self(self):
        """Publish a GenesisRegistration announcement for this agent."""
        try:
            logger.info(f"Starting announce_self for agent {self.agent_name}")
            
            # Create registration dynamic data
            registration = dds.DynamicData(self.app.registration_type)
            registration["message"] = f"Agent {self.agent_name} ({self.base_service_name}) announcing presence"
            registration["prefered_name"] = self.agent_name
            registration["default_capable"] = 1 # Assuming this means it can handle default requests for its service type
            registration["instance_id"] = self.app.agent_id
            registration["service_name"] = self.rpc_service_name # This is the name clients connect to for RPC
            # TODO: If IDL is updated, add a separate field for self.base_service_name for better type discovery by interfaces.
            # For now, CLI will see self.rpc_service_name as 'Service' and can use it to connect.
            
            logger.debug(f"Created registration announcement: message='{registration['message']}', prefered_name='{registration['prefered_name']}', default_capable={registration['default_capable']}, instance_id='{registration['instance_id']}', service_name='{registration['service_name']}' (base_service_name: {self.base_service_name})")
            
            # Write and flush the registration announcement
            logger.debug("🔍 TRACE: About to write registration announcement...")
            write_result = self.registration_writer.write(registration)
            logger.debug(f"✅ TRACE: Registration announcement write result: {write_result}")
            
            try:
                logger.debug("🔍 TRACE: About to flush registration writer...")
                # Get writer status before flush
                status = self.registration_writer.datawriter_protocol_status
                logger.debug(f"📊 TRACE: Writer status before flush - Sent")
                
                self.registration_writer.flush()
                
                # Get writer status after flush
                status = self.registration_writer.datawriter_protocol_status
                logger.debug(f"📊 TRACE: Writer status after flush - Sent")
                logger.debug("✅ TRACE: Registration writer flushed successfully")
                logger.info("Successfully announced agent presence")
            except Exception as flush_error:
                logger.error(f"💥 TRACE: Error flushing registration writer: {flush_error}")
                logger.error(traceback.format_exc())
                
        except Exception as e:
            logger.error(f"Error in announce_self: {e}")
            logger.error(traceback.format_exc())

class GenesisAnthropicChatAgent(GenesisAgent, AnthropicChatAgent):
    """Genesis agent that uses Anthropic's Claude model"""
    def __init__(self, model_name: str = "claude-3-opus-20240229", api_key: Optional[str] = None,
                 system_prompt: Optional[str] = None, max_history: int = 10):
        GenesisAgent.__init__(self, "Claude", "Chat")
        AnthropicChatAgent.__init__(self, model_name, api_key, system_prompt, max_history)
        
    async def process_request(self, request: Any) -> Dict[str, Any]:
        """Process chat request using Claude"""
        message = request["message"]
        conversation_id = request["conversation_id"]
        
        response, status = await self.generate_response(message, conversation_id)
        
        return {
            "response": response,
            "status": status
        } 
```

## genesis_lib/function_discovery.py

**Author:** Jason

```python
"""
Genesis Function Discovery System

This module provides the core function discovery and registration system for the Genesis
framework, enabling dynamic discovery and matching of functions across the distributed
network. It implements a DDS-based discovery mechanism that allows functions to be
advertised, discovered, and matched based on capabilities and requirements.

Key responsibilities include:
- DDS-based function capability advertisement and discovery
- Function registration and metadata management
- Intelligent function matching using LLM analysis
- Function validation and schema management
- Service integration and lifecycle management

Known Limitations:
- Current implementation may lead to recursive function discovery due to its deep
  integration in the library stack. This can cause functions to discover each other
  in unintended ways. Future versions will address this by:
  1. Moving function discovery to a higher level in the framework
  2. Implementing clearer boundaries between function providers and consumers
  3. Adding explicit discovery scoping and filtering

Copyright (c) 2025, RTI & Jason Upchurch
"""

#!/usr/bin/env python3

import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
import json
import uuid
import time
import rti.connextdds as dds
import rti.rpc as rpc
import re
import os
from genesis_lib.utils import get_datamodel_path
import asyncio
import sys
import traceback

# Configure root logger to handle all loggers
# logging.basicConfig( # REMOVE THIS BLOCK
#     level=logging.DEBUG,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.StreamHandler()
#     ]
# )

# Configure function discovery logger specifically
logger = logging.getLogger("function_discovery")
# logger.setLevel(logging.DEBUG) # REMOVE - Let the script control the level

# Set all genesis_lib loggers to DEBUG
# for name in ['genesis_lib', 'genesis_lib.function_discovery', 'genesis_lib.agent', 'genesis_lib.monitored_agent', 'genesis_lib.genesis_app']:
#     logging.getLogger(name).setLevel(logging.DEBUG) # REMOVE THIS LOOP

@dataclass
class FunctionInfo:
    """Information about a registered function"""
    function_id: str
    name: str
    description: str
    function: Callable
    schema: Dict[str, Any]
    categories: List[str]
    performance_metrics: Dict[str, Any]
    security_requirements: Dict[str, Any]
    match_info: Optional[Dict[str, Any]] = None
    classification: Optional[Dict[str, Any]] = None
    operation_type: Optional[str] = None  # One of: transformation, analysis, generation, calculation
    common_patterns: Optional[Dict[str, Any]] = None  # Common validation patterns used by this function

    def get_validation_patterns(self) -> Dict[str, Any]:
        """
        Get validation patterns for this function.
        
        Returns:
            Dictionary of validation patterns
        """
        if not self.common_patterns:
            return {}
            
        # Common validation patterns
        patterns = {
            "text": {
                "min_length": 1,
                "max_length": None,
                "pattern": None
            },
            "letter": {
                "min_length": 1,
                "max_length": 1,
                "pattern": "^[a-zA-Z]$"
            },
            "count": {
                "minimum": 0,
                "maximum": 1000
            },
            "number": {
                "minimum": None,
                "maximum": None
            }
        }
        
        # Update with function-specific patterns
        for pattern_type, pattern in self.common_patterns.items():
            if pattern_type in patterns:
                patterns[pattern_type].update(pattern)
                
        return patterns

    def validate_input(self, parameter_name: str, value: Any) -> None:
        """
        Validate input using common patterns.
        
        Args:
            parameter_name: Name of the parameter to validate
            value: Value to validate
            
        Raises:
            ValueError: If validation fails
        """
        if not self.common_patterns or parameter_name not in self.common_patterns:
            return
            
        pattern = self.common_patterns[parameter_name]
        pattern_type = pattern.get("type", "text")
        
        if pattern_type == "text":
            if not isinstance(value, str):
                raise ValueError(f"{parameter_name} must be a string")
                
            if pattern.get("min_length") and len(value) < pattern["min_length"]:
                raise ValueError(f"{parameter_name} must be at least {pattern['min_length']} character(s)")
                
            if pattern.get("max_length") and len(value) > pattern["max_length"]:
                raise ValueError(f"{parameter_name} cannot exceed {pattern['max_length']} character(s)")
                
            if pattern.get("pattern") and not re.match(pattern["pattern"], value):
                raise ValueError(f"{parameter_name} must match pattern: {pattern['pattern']}")
                
        elif pattern_type in ["number", "integer"]:
            if not isinstance(value, (int, float)):
                raise ValueError(f"{parameter_name} must be a number")
                
            if pattern.get("minimum") is not None and value < pattern["minimum"]:
                raise ValueError(f"{parameter_name} must be at least {pattern['minimum']}")
                
            if pattern.get("maximum") is not None and value > pattern["maximum"]:
                raise ValueError(f"{parameter_name} cannot exceed {pattern['maximum']}")

class FunctionMatcher:
    """Matches functions based on LLM analysis of requirements and available functions"""
    
    def __init__(self, llm_client=None):
        """Initialize the matcher with optional LLM client"""
        self.logger = logging.getLogger("function_matcher")
        self.llm_client = llm_client
    
    def find_matching_functions(self,
                              user_request: str,
                              available_functions: List[Dict[str, Any]],
                              min_similarity: float = 0.7) -> List[Dict[str, Any]]:
        """
        Find functions that match the user's request using LLM analysis.
        
        Args:
            user_request: The user's natural language request
            available_functions: List of available function metadata
            min_similarity: Minimum similarity score (0-1)
            
        Returns:
            List of matching function metadata with relevance scores
        """
        if not self.llm_client:
            self.logger.warning("No LLM client provided, falling back to basic matching")
            return self._fallback_matching(user_request, available_functions)
        
        # Create prompt for LLM
        prompt = f"""Given the following user request:

{user_request}

And the following functions:

{json.dumps([{
    "function_name": f["name"],
    "function_description": f.get("description", "")
} for f in available_functions], indent=2)}

For each relevant function, return a JSON array where each object has:
- function_name: The name of the matching function
- domain: The primary domain/category this function belongs to (e.g., "weather", "mathematics")
- operation_type: The type of operation this function performs (e.g., "lookup", "calculation")

Only include functions that are actually relevant to the request. Do not return anything else."""

        # Log the prompt being sent to the LLM
        self.logger.info(
            "LLM Classification Prompt",
            extra={
                "user_request": user_request,
                "prompt": prompt,
                "available_functions": [f["name"] for f in available_functions]
            }
        )

        try:
            # Get LLM response
            response = self.llm_client.generate_response(prompt, "function_matching")
            
            # Log the raw LLM response for monitoring
            self.logger.info(
                "LLM Function Classification Response",
                extra={
                    "user_request": user_request,
                    "raw_response": response[0],
                    "response_status": response[1],
                    "available_functions": [f["name"] for f in available_functions]
                }
            )
            
            # Parse response
            matches = json.loads(response[0])
            
            # Convert matches to full metadata
            result = []
            for match in matches:
                func = next((f for f in available_functions if f["name"] == match["function_name"]), None)
                if func:
                    # Add match info
                    func["match_info"] = {
                        "relevance_score": 1.0,  # Since we're just doing exact matches
                        "explanation": "Function name matched by LLM",
                        "inferred_params": {},  # Parameter inference happens later
                        "considerations": [],
                        "domain": match.get("domain", "unknown"),
                        "operation_type": match.get("operation_type", "unknown")
                    }
                    result.append(func)
            
            # Log the processed matches for monitoring
            self.logger.info(
                "Processed Function Matches",
                extra={
                    "user_request": user_request,
                    "matches": result,
                    "min_similarity": min_similarity
                }
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "Error in LLM-based matching",
                extra={
                    "user_request": user_request,
                    "error": str(e),
                    "available_functions": [f["name"] for f in available_functions]
                }
            )
            return self._fallback_matching(user_request, available_functions)
    
    def _prepare_function_descriptions(self, functions: List[Dict[str, Any]]) -> str:
        """Prepare function descriptions for LLM analysis"""
        descriptions = []
        for func in functions:
            desc = f"Function: {func['name']}\n"
            desc += f"Description: {func.get('description', '')}\n"
            desc += "Parameters:\n"
            
            # Add parameter descriptions
            if "parameter_schema" in func and "properties" in func["parameter_schema"]:
                for param_name, param_schema in func["parameter_schema"]["properties"].items():
                    desc += f"- {param_name}: {param_schema.get('description', param_schema.get('type', 'unknown'))}"
                    if param_schema.get("required", False):
                        desc += " (required)"
                    desc += "\n"
            
            # Add performance and security info if available
            if "performance_metrics" in func:
                desc += "Performance:\n"
                for metric, value in func["performance_metrics"].items():
                    desc += f"- {metric}: {value}\n"
            
            if "security_requirements" in func:
                desc += "Security:\n"
                for req, value in func["security_requirements"].items():
                    desc += f"- {req}: {value}\n"
            
            descriptions.append(desc)
        
        return "\n".join(descriptions)
    
    def _convert_matches_to_metadata(self, 
                                   matches: List[Dict[str, Any]], 
                                   available_functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert LLM matches to function metadata format"""
        result = []
        for match in matches:
            # Find the original function metadata
            func = next((f for f in available_functions if f["name"] == match["function_name"]), None)
            if func:
                # Add match information
                func["match_info"] = {
                    "relevance_score": match["relevance_score"],
                    "explanation": match["explanation"],
                    "inferred_params": match["inferred_params"],
                    "considerations": match["considerations"],
                    "domain": match.get("domain", "unknown"),
                    "operation_type": match.get("operation_type", "unknown")
                }
                result.append(func)
        return result
    
    def _fallback_matching(self, user_request: str, available_functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fallback to basic matching if LLM is not available"""
        # Simple text-based matching as fallback
        matches = []
        request_lower = user_request.lower()
        request_words = set(request_lower.split())
        
        for func in available_functions:
            # Check function name and description
            name_match = func["name"].lower() in request_lower
            desc_match = func.get("description", "").lower() in request_lower
            
            # Check for word matches in both name and description
            func_name_words = set(func["name"].lower().split())
            func_desc_words = set(func.get("description", "").lower().split())
            
            # Calculate word overlap
            name_word_overlap = bool(func_name_words & request_words)
            desc_word_overlap = bool(func_desc_words & request_words)
            
            if name_match or desc_match or name_word_overlap or desc_word_overlap:
                # Calculate a simple relevance score based on matches
                if name_match and desc_match:
                    relevance_score = 0.5
                elif name_match or desc_match:
                    relevance_score = 0.5
                elif name_word_overlap and desc_word_overlap:
                    relevance_score = 0.5
                elif name_word_overlap or desc_word_overlap:
                    relevance_score = 0.4
                else:
                    relevance_score = 0.3
                
                # Try to infer parameters from the request
                inferred_params = {}
                if "parameter_schema" in func and "properties" in func["parameter_schema"]:
                    for param_name, param_schema in func["parameter_schema"]["properties"].items():
                        # Look for parameter values in the request
                        param_desc = param_schema.get("description", "").lower()
                        if param_desc in request_lower:
                            # Extract the value after the parameter description
                            value_start = request_lower.find(param_desc) + len(param_desc)
                            value_end = request_lower.find(" ", value_start)
                            if value_end == -1:
                                value_end = len(request_lower)
                            value = request_lower[value_start:value_end].strip()
                            if value:
                                inferred_params[param_name] = value
                
                # Log the fallback matching details
                self.logger.info(
                    "Fallback Matching Details",
                    extra={
                        "user_request": user_request,
                        "function_name": func["name"],
                        "name_match": name_match,
                        "desc_match": desc_match,
                        "name_word_overlap": name_word_overlap,
                        "desc_word_overlap": desc_word_overlap,
                        "relevance_score": relevance_score,
                        "inferred_params": inferred_params
                    }
                )
                
                func["match_info"] = {
                    "relevance_score": relevance_score,
                    "explanation": "Basic text matching",
                    "inferred_params": inferred_params,
                    "considerations": ["Using basic text matching - results may be less accurate"],
                    "domain": "unknown",
                    "operation_type": "unknown"
                }
                matches.append(func)
        
        # Sort matches by relevance score
        matches.sort(key=lambda x: x["match_info"]["relevance_score"], reverse=True)
        
        return matches 

class FunctionRegistry:
    """
    Registry for functions that can be called by the agent.
    
    This implementation supports DDS-based distributed function discovery
    and execution, where functions can be provided by:
    1. Other agents with specific expertise
    2. Traditional ML models wrapped as function providers
    3. Planning agents for complex task decomposition
    4. Simple procedural code exposed as functions
    
    The distributed implementation uses DDS topics for:
    - Function capability advertisement
    - Function discovery and matching
    - Function execution requests via DDS RPC
    - Function execution results via DDS RPC
    """
    
    def __init__(self, participant=None, domain_id=0, enable_discovery_listener: bool = True):
        """
        Initialize the function registry.
        
        Args:
            participant: DDS participant (if None, will create one)
            domain_id: DDS domain ID
            enable_discovery_listener: If True, creates DDS reader to discover external functions. Defaults to True.
        """
        self.functions = {}  # Dict[str, FunctionInfo]
        self.function_by_name = {}  # Dict[str, str] mapping names to IDs
        self.function_by_category = {}  # Dict[str, List[str]] mapping categories to IDs
        self.discovered_functions = {}  # Dict[str, Dict] of functions from other providers
        self.service_base = None  # Reference to EnhancedServiceBase
        
        # Event to signal when the first function capability has been discovered
        self._discovery_event = asyncio.Event()
        
        # Initialize function matcher with LLM support
        self.matcher = FunctionMatcher()
        self.enable_discovery_listener = enable_discovery_listener
        
        # Create DDS participant if not provided
        if participant is None:
            participant = dds.DomainParticipant(domain_id)
        
        # Store participant reference
        self.participant = participant
        
        # Create publisher (always needed for advertising own functions)
        self.publisher = dds.Publisher(participant)
        
        # Get types from XML
        config_path = get_datamodel_path()
        self.type_provider = dds.QosProvider(config_path)
        self.capability_type = self.type_provider.type("genesis_lib", "FunctionCapability")
        
        # Create topics
        # Try to find the topic first, create if not found
        try:
            # find_topics returns all topics for the participant
            all_topics = participant.find_topics()
            found_topic = None
            for topic in all_topics:
                # Check if the topic name matches
                if topic.name == "FunctionCapability":
                     # Optional: Check type name if necessary
                     # if topic.type_name == self.capability_type.name:
                    found_topic = topic
                    break # Found the topic
            
            if found_topic:
                self.capability_topic = found_topic
                logger.debug("===== DDS TRACE: Found existing FunctionCapability topic. =====")
            else:
                 # Topic not found, create it
                logger.debug("===== DDS TRACE: FunctionCapability topic not found, creating new one... =====")
                self.capability_topic = dds.DynamicData.Topic(
                    participant=participant,
                    topic_name="FunctionCapability",
                    topic_type=self.capability_type
                )
                logger.debug("===== DDS TRACE: Created new FunctionCapability topic. =====")

        except dds.Error as e:
            # Handle potential errors during find_topics or create_topic
            logger.error(f"===== DDS TRACE: DDS Error finding/creating FunctionCapability topic: {e} ====")
            raise
        except Exception as e:
            # Catch any other unexpected errors
            logger.error(f"===== DDS TRACE: Unexpected error during topic find/create: {e} ====")
            raise
        
        # Create DataWriter for capability advertisement (always needed)
        writer_qos = dds.QosProvider.default.datawriter_qos
        writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        writer_qos.history.kind = dds.HistoryKind.KEEP_LAST
        writer_qos.history.depth = 500
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        writer_qos.liveliness.kind = dds.LivelinessKind.AUTOMATIC
        writer_qos.liveliness.lease_duration = dds.Duration(seconds=2)
        
        self.capability_writer = dds.DynamicData.DataWriter(
            pub=self.publisher,
            topic=self.capability_topic,
            qos=writer_qos,
            mask=dds.StatusMask.ALL
        )

        if self.enable_discovery_listener:
            # Create subscriber
            self.subscriber = dds.Subscriber(participant)
            
            # Get types for execution (only if discovery is enabled)
            self.execution_request_type = self.type_provider.type("genesis_lib", "FunctionExecutionRequest")
            self.execution_reply_type = self.type_provider.type("genesis_lib", "FunctionExecutionReply")

            # Create DataReader for capability discovery
            reader_qos = dds.QosProvider.default.datareader_qos
            reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
            reader_qos.history.kind = dds.HistoryKind.KEEP_LAST
            reader_qos.history.depth = 500
            reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            reader_qos.liveliness.kind = dds.LivelinessKind.AUTOMATIC
            reader_qos.liveliness.lease_duration = dds.Duration(seconds=2)
            
            self.capability_listener = FunctionCapabilityListener(self)
            self.capability_reader = dds.DynamicData.DataReader(
                topic=self.capability_topic,
                qos=reader_qos,
                listener=self.capability_listener,
                subscriber=self.subscriber,
                mask=dds.StatusMask.ALL
            )
            
            # Create RPC client for function execution
            self.execution_client = rpc.Requester(
                request_type=self.execution_request_type,
                reply_type=self.execution_reply_type,
                participant=participant,
                service_name="FunctionExecution"
            )
        else:
            self.subscriber = None
            self.capability_reader = None
            self.capability_listener = None
            self.execution_client = None
            # Ensure discovered_functions is initialized if discovery is off,
            # though it's already initialized above.
            self.discovered_functions = {}
            logger.info("FunctionRegistry initialized with discovery listener DISABLED.")
    
    def register_function(self, 
                         func: Callable,
                         description: str,
                         parameter_descriptions: Dict[str, Any],
                         capabilities: List[str] = None,
                         performance_metrics: Dict[str, Any] = None,
                         security_requirements: Dict[str, Any] = None) -> str:
        """
        Register a function with the registry.
        
        Args:
            func: The function to register
            description: Human-readable description of the function
            parameter_descriptions: JSON Schema for function parameters
            capabilities: List of capability tags
            performance_metrics: Performance characteristics
            security_requirements: Security requirements
            
        Returns:
            Function ID of the registered function
        """
        # Generate function ID
        function_id = str(uuid.uuid4())
        
        # Log start of registration process
        logger.info(f"Starting function registration in FunctionRegistry",
                   extra={
                       "function_name": func.__name__,
                       "function_id": function_id,
                       "capabilities": capabilities,
                       "has_performance_metrics": bool(performance_metrics),
                       "has_security_requirements": bool(security_requirements)
                   })
        
        # Log detailed function information
        logger.debug(f"Detailed function registration information",
                    extra={
                        "function_name": func.__name__,
                        "function_id": function_id,
                        "description": description,
                        "parameter_schema": parameter_descriptions,
                        "capabilities": capabilities,
                        "performance_metrics": performance_metrics,
                        "security_requirements": security_requirements
                    })
        
        try:
            # Create function info
            logger.debug(f"Creating FunctionInfo object for '{func.__name__}'")
            function_info = FunctionInfo(
                function_id=function_id,
                name=func.__name__,
                description=description,
                function=func,
                schema=parameter_descriptions,
                categories=capabilities or [],
                performance_metrics=performance_metrics or {},
                security_requirements=security_requirements or {}
            )
            
            # Store function info
            logger.debug(f"Storing function info for '{func.__name__}' in registry")
            self.functions[function_id] = function_info
            self.function_by_name[function_info.name] = function_id
            
            # Update category index
            logger.debug(f"Updating category index for '{func.__name__}'")
            for category in function_info.categories:
                if category not in self.function_by_category:
                    self.function_by_category[category] = []
                self.function_by_category[category].append(function_id)
                logger.debug(f"Added function '{func.__name__}' to category '{category}'")
            
            # Advertise function capability
            logger.info(f"Advertising function capability for '{func.__name__}'")
            self._advertise_function(function_info)
            
            # Log successful registration
            logger.info(f"Successfully registered function '{func.__name__}'",
                       extra={
                           "function_id": function_id,
                           "function_name": func.__name__,
                           "categories": list(function_info.categories),
                           "registered_categories_count": len(function_info.categories)
                       })
            
            return function_id
            
        except Exception as e:
            # Log registration failure with detailed error info
            logger.error(f"Failed to register function '{func.__name__}'",
                        extra={
                            "function_id": function_id,
                            "function_name": func.__name__,
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "traceback": logging.traceback.format_exc()
                        })
            raise
    
    def find_matching_functions(self,
                              user_request: str,
                              min_similarity: float = 0.7) -> List[FunctionInfo]:
        """
        Find functions that match the user's request.
        
        Args:
            user_request: The user's natural language request
            min_similarity: Minimum similarity score (0-1)
            
        Returns:
            List of matching FunctionInfo objects
        """
        # Convert functions to format expected by matcher
        available_functions = [
            {
                "name": func.name,
                "description": func.description,
                "parameter_schema": func.schema,
                "capabilities": func.categories,
                "performance_metrics": func.performance_metrics,
                "security_requirements": func.security_requirements
            }
            for func in self.functions.values()
        ]
        
        # Find matches using the matcher
        matches = self.matcher.find_matching_functions(
            user_request=user_request,
            available_functions=available_functions,
            min_similarity=min_similarity
        )
        
        # Convert matches back to FunctionInfo objects
        result = []
        for match in matches:
            function_id = self.function_by_name.get(match["name"])
            if function_id and function_id in self.functions:
                func_info = self.functions[function_id]
                func_info.match_info = match.get("match_info", {})
                result.append(func_info)
        
        return result
    
    def _advertise_function(self, function_info: FunctionInfo):
        """Advertise function capability via DDS"""
        logger.debug(f"===== DDS TRACE: Preparing DDS data for advertising function: {function_info.name} ({function_info.function_id}) =====")
        capability = dds.DynamicData(self.capability_type)
        capability['function_id'] = function_info.function_id
        capability['name'] = function_info.name
        capability['description'] = function_info.description
        capability['provider_id'] = str(self.capability_writer.instance_handle)  # Use DataWriter GUID
        capability['parameter_schema'] = json.dumps(function_info.schema)
        capability['capabilities'] = json.dumps(function_info.categories)
        capability['performance_metrics'] = json.dumps(function_info.performance_metrics)
        capability['security_requirements'] = json.dumps(function_info.security_requirements)
        capability['classification'] = json.dumps(function_info.classification or {})
        capability['last_seen'] = int(time.time() * 1000)
        
        # Add the service name from the service_base reference
        if self.service_base and hasattr(self.service_base, 'service_name'):
            capability['service_name'] = self.service_base.service_name
        else:
            logger.warning(f"Could not determine service_name when advertising function {function_info.name}")
            capability['service_name'] = "UnknownService" # Default if service name is not found
        
        logger.debug(f"===== DDS TRACE: Publishing FunctionCapability for {function_info.name} ({function_info.function_id}): {capability} =====")
        try:
            self.capability_writer.write(capability)
            self.capability_writer.flush()
            logger.debug(f"===== DDS TRACE: Successfully published FunctionCapability for {function_info.name} =====")
        except Exception as e:
            logger.error(f"===== DDS TRACE: Error publishing FunctionCapability for {function_info.name}: {e} ====", exc_info=True)
            # Optionally re-raise or handle
    
    def handle_capability_advertisement(self, capability: dds.DynamicData, info: dds.SampleInfo):
        """Handle received function capability data"""
        function_id_str = "unknown_id"
        try:
            function_id_str = capability.get_string("function_id") # Get ID for logging early
            logger.debug(f"===== DDS TRACE: handle_capability_advertisement received data for function_id: {function_id_str} =====")

            # Check if instance state is ALIVE before processing
            if info.state.instance_state != dds.InstanceState.ALIVE:
                logger.debug(f"Ignoring non-alive capability sample: {info.state.instance_state}")
                return
            
            # Extract required fields
            function_id = capability["function_id"]
            name = capability["name"]
            provider_id = capability["provider_id"]
            description = capability.get_string("description") # Use get_string for safety
            schema_str = capability.get_string("parameter_schema") # Use get_string for safety
            capabilities_str = capability.get_string("capabilities") # Use get_string for safety
            service_name = capability.get_string("service_name") # Get service name
            
            # Basic validation
            if not all([function_id, name, provider_id]):
                logger.warning(f"Received capability advertisement with missing required fields")
                return

            # Deserialize JSON strings safely
            schema = json.loads(schema_str) if schema_str else {}
            capabilities = json.loads(capabilities_str) if capabilities_str else []
            
            # Store or update the discovered function
            # Use a dictionary to store structured info
            self.discovered_functions[function_id] = {
                "name": name,
                "description": description,
                "provider_id": provider_id,
                "schema": schema,
                "capabilities": capabilities,
                "service_name": service_name, # Store service name
                "capability": capability # Store the raw capability object for potential future use
            }
            
            logger.info(f"Updated/Added discovered function: {name} ({function_id}) from provider {provider_id} for service {service_name}")
            
            # Signal that at least one function has been discovered
            if not self._discovery_event.is_set():
                logger.debug(f"===== DDS TRACE: Setting _discovery_event for function_id: {function_id} =====")
                self._discovery_event.set()
                logger.debug("===== DDS TRACE: Discovery event set (first function discovered). =====")
            else:
                logger.debug(f"===== DDS TRACE: _discovery_event already set (function_id: {function_id}). =====")

        except KeyError as e:
            logger.error(f"===== DDS TRACE: Missing key in capability data (function_id: {function_id_str}): {e} ====")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON in capability data: {e}")
        except Exception as e: # Add a general except block for the try
            logger.error(f"Error handling capability advertisement for function_id {function_id_str}: {e}")
            logger.error(logging.traceback.format_exc())
    
    def handle_capability_removal(self, reader: dds.DynamicData.DataReader):
        """Handle removal of function capabilities when a provider goes offline"""
        try:
            samples = reader.take()
            for data, info in samples:
                if data and info.state.instance_state != dds.InstanceState.ALIVE:
                    function_id = data['function_id']
                    if function_id in self.discovered_functions:
                        function_info = self.discovered_functions[function_id]
                        
                        # Build metadata for service base
                        metadata = {
                            "function_id": function_id,
                            "function_name": function_info['name'],
                            "provider_id": function_info['provider_id']
                        }
                        
                        # Notify EnhancedServiceBase about the removal
                        if self.service_base is not None:
                            self.service_base.handle_function_removal(
                                function_name=function_info['name'],
                                metadata=metadata
                            )
                        
                        logger.info(f"Removing function {function_id} due to provider going offline")
                        del self.discovered_functions[function_id]
        except Exception as e:
            logger.error(f"Error handling capability removal: {e}")
    
    def get_function_by_id(self, function_id: str) -> Optional[FunctionInfo]:
        """
        Get function by ID.
        
        Args:
            function_id: ID of function to retrieve
            
        Returns:
            FunctionInfo if found, None otherwise
        """
        return self.functions.get(function_id)
    
    def get_function_by_name(self, name: str) -> Optional[FunctionInfo]:
        """
        Get a function by its name.
        
        Args:
            name: The name of the function to retrieve
            
        Returns:
            The FunctionInfo object if found, None otherwise
        """
        function_id = self.function_by_name.get(name)
        if function_id:
            return self.functions.get(function_id)
        return None
    
    def get_all_discovered_functions(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns a shallow copy of the currently discovered functions on the network.
        The dictionary maps function_id to its details.
        """
        return dict(self.discovered_functions)

    def remove_discovered_function(self, function_id: str):
        """
        Removes a function from the discovered_functions cache.
        Typically called when a function provider is no longer available.
        """
        if function_id in self.discovered_functions:
            removed_function_name = self.discovered_functions[function_id].get("name", "unknown_function")
            del self.discovered_functions[function_id]
            logger.debug(f"===== DDS TRACE: Removed function {removed_function_name} ({function_id}) from discovered functions cache. =====")
        else:
            logger.warning(f"===== DDS TRACE: Attempted to remove non-existent function ID {function_id} from cache. =====")

    def close(self):
        """Clean up resources"""
        print("===== PRINT TRACE: FunctionRegistry.close() ENTERED =====", flush=True) # ADDED FOR DEBUGGING
        logger.debug("===== DDS TRACE: FunctionRegistry.close() ENTERED LOGGER =====") # ADDED FOR DEBUGGING

        if hasattr(self, '_closed') and self._closed:
            logger.debug("FunctionRegistry already closed.")
            return

        logger.debug("Closing FunctionRegistry and its resources")
        try:
            # Detach and delete StatusCondition and WaitSet first
            logger.debug("===== DDS TRACE: FunctionRegistry.close() - WaitSet/StatusCondition cleanup START ====")
            if hasattr(self, 'status_condition') and self.status_condition:
                logger.debug("===== DDS TRACE: FunctionRegistry.close() - 'status_condition' attribute exists. Disabling... =====")
                try:
                    self.status_condition.enabled_statuses = dds.StatusMask.NONE
                    logger.debug("===== DDS TRACE: FunctionRegistry.close() - status_condition.enabled_statuses set to NONE. =====")
                except Exception as sc_disable_ex:
                    logger.error(f"===== DDS TRACE: FunctionRegistry.close() - EXCEPTION during status_condition disable: {sc_disable_ex} =====")

            if hasattr(self, 'waitset') and self.waitset:
                logger.debug("===== DDS TRACE: FunctionRegistry.close() - 'waitset' attribute exists. =====")
                if hasattr(self, 'status_condition') and self.status_condition: # Check again as it might have been set to None
                    is_attached_before = self.status_condition.is_attached
                    logger.debug(f"===== DDS TRACE: FunctionRegistry.close() - StatusCondition.is_attached BEFORE detach: {is_attached_before} =====")
                    if is_attached_before:
                        try:
                            self.waitset.detach(self.status_condition)
                            logger.debug("===== DDS TRACE: FunctionRegistry.close() - waitset.detach(status_condition) CALLED. =====")
                            is_attached_after = self.status_condition.is_attached 
                            logger.debug(f"===== DDS TRACE: FunctionRegistry.close() - StatusCondition.is_attached AFTER detach: {is_attached_after} =====")
                        except Exception as detach_ex:
                            logger.error(f"===== DDS TRACE: FunctionRegistry.close() - EXCEPTION during waitset.detach(): {detach_ex} =====")
                    else:
                        logger.debug("===== DDS TRACE: FunctionRegistry.close() - StatusCondition was NOT attached, skipping detach. =====")
                else:
                    logger.debug("===== DDS TRACE: FunctionRegistry.close() - 'status_condition' is None or does not exist when trying to detach from waitset. =====")
                self.waitset = None # Allow garbage collection
                logger.debug("===== DDS TRACE: FunctionRegistry.close() - self.waitset set to None. =====")
            else:
                logger.debug("===== DDS TRACE: FunctionRegistry.close() - 'waitset' attribute does NOT exist. =====")
            
            if hasattr(self, 'status_condition') and self.status_condition: # Ensure it's nulled if not already
                self.status_condition = None # Allow garbage collection
                logger.debug("===== DDS TRACE: FunctionRegistry.close() - self.status_condition set to None (final check). =====")

            logger.debug("===== DDS TRACE: FunctionRegistry.close() - WaitSet/StatusCondition cleanup END ====")

            # Close DDS entities
            if hasattr(self, 'execution_client') and self.execution_client:
                self.execution_client.close()
            if hasattr(self, 'capability_reader') and self.capability_reader:
                self.capability_reader.close()
            
            # capability_writer and capability_topic are always created (or should be)
            if hasattr(self, 'capability_writer') and self.capability_writer:
                self.capability_writer.close()
            if hasattr(self, 'capability_topic') and self.capability_topic: # Topic is found or created
                self.capability_topic.close()

            if hasattr(self, 'subscriber') and self.subscriber:
                self.subscriber.close()
            
            # Publisher is always created
            if hasattr(self, 'publisher') and self.publisher:
                self.publisher.close()
            
            # Clear references
            self.capability_writer = None
            self.capability_reader = None
            self.capability_topic = None
            self.subscriber = None
            self.publisher = None
            self.execution_client = None

            logger.debug("===== DDS TRACE: FunctionRegistry.close() - DDS entities closed. =====")
        except Exception as e:
            logger.error(f"===== DDS TRACE: Error closing FunctionRegistry: {e} =====")
            logger.error(traceback.format_exc())

        logger.debug("===== DDS TRACE: FunctionRegistry.close() - Cleanup completed. =====")
        self._closed = True

class FunctionCapabilityListener(dds.DynamicData.NoOpDataReaderListener):
    """Listener for function capability advertisements"""

    def __init__(self, registry):
        """Initialize listener with a reference to the registry"""
        super().__init__()
        self.registry = registry
        logger.debug("FunctionCapabilityListener initialized")

    def on_subscription_matched(self, reader, info):
        """Handle subscription matches"""
        logger.debug(f"Capability subscription matched: {info.current_count} total writers")
        # Optionally, trigger an initial check or event if needed
        # maybe set the discovery event here if count > 0?
        # if info.current_count > 0 and not self.registry._discovery_event.is_set():
        #     self.registry._discovery_event.set()
        #     logger.info("Discovery event set via on_subscription_matched.")

    def on_data_available(self, reader):
        """Handle incoming capability data"""
        logger.debug("===== DDS TRACE: FunctionCapabilityListener.on_data_available entered =====")
        try:
            samples = reader.read() # Take all available samples
            logger.debug(f"===== DDS TRACE: Read {len(samples)} FunctionCapability samples =====")
            # Print sample details for debugging
            for sample, info in samples:
                logger.debug("===== DDS TRACE: Sample details =====")
                logger.debug(f"Sample data: {sample}")
                logger.debug(f"Sample info: {info}")
                logger.debug(f"Sample state: {info.state.sample_state}")
                logger.debug(f"Instance state: {info.state.instance_state}")
                logger.debug("===== DDS TRACE: End sample details =====")
            for capability_data, info in samples:
                # Check if the sample contains valid data that hasn't been read before
                if info.state.sample_state == dds.SampleState.NOT_READ: # FIX: Check for NOT_READ
                    # This sample contains valid data for a new or updated function
                    log_fid = "N/A"
                    if capability_data:
                        try:
                             log_fid = capability_data.get_string("function_id") or "ID_NOT_IN_DATA"
                        except Exception:
                             log_fid = "ERROR_GETTING_ID"
                    logger.debug(f"===== DDS TRACE: Processing READ sample - FuncID: {log_fid} =====")
                    # Re-log state for this specific case
                    logger.debug(f"===== DDS TRACE:   SampleState: {str(info.state.sample_state)}, InstanceState: {str(info.state.instance_state)} =====")

                    # Process the valid data
                    self.registry.handle_capability_advertisement(capability_data, info)

                # Separately check if the instance associated with the sample is no longer alive
                # This handles cases where the sample itself might not be marked as READ anymore,
                # but we still need to know the instance was disposed or unregistered.
                if info.state.instance_state != dds.InstanceState.ALIVE:
                    log_fid = "N/A"
                    key_holder = dds.DynamicData(self.registry.capability_type)
                    try:
                        reader.get_key_value(key_holder, info.instance_handle)
                        log_fid = key_holder.get_string("function_id") or "ID_NOT_IN_DATA"
                    except Exception:
                        log_fid = "ERROR_GETTING_ID"

                    logger.debug(f"===== DDS TRACE: Processing Non-ALIVE sample - FuncID: {log_fid} =====")
                    # Re-log state for this specific case
                    logger.debug(f"===== DDS TRACE:   SampleState: {str(info.state.sample_state)}, InstanceState: {str(info.state.instance_state)} =====")

                    # Process the removal
                    try:
                        # Attempt to get the key value from the instance handle
                        # reader.get_key_value(key_holder, info.instance_handle) # Already done above for logging
                        function_id_to_remove = log_fid if log_fid not in ["N/A", "ID_NOT_IN_DATA", "ERROR_GETTING_ID"] else None

                        if function_id_to_remove:
                            logger.debug(f"===== DDS TRACE: Instance for function ID {function_id_to_remove} no longer alive (state: {info.state.instance_state}). Attempting removal from registry. =====")
                            # Check if already removed to avoid redundant logging
                            if function_id_to_remove in self.registry.discovered_functions:
                                self.registry.remove_discovered_function(function_id_to_remove)
                            # else: # Optionally log if already removed
                            #    logger.debug(f"===== DDS TRACE: Function ID {function_id_to_remove} already removed (instance state: {info.state.instance_state}). =====")
                        else:
                            # This case should be rare if function_id is indeed the key
                            logger.warning(f"===== DDS TRACE: Could not retrieve function_id (key) for disposed/unregistered instance handle {info.instance_handle}. Cannot remove. =====")
                    except dds.Error as e: # Catch specific DDS errors
                        logger.error(f"===== DDS TRACE: DDS Error getting key for disposed/unregistered instance handle {info.instance_handle}: {e} =====")
                    except Exception as e: # Catch other unexpected errors
                        logger.error(f"===== DDS TRACE: Unexpected error getting key/removing for instance handle {info.instance_handle}: {e} =====")
                # else:
                    # Potentially other states, e.g. sample_state != READ and instance_state == ALIVE.
                    # logger.debug(f"===== DDS TRACE: Ignoring sample with info.state.sample_state={info.state.sample_state} and info.instance_state={info.instance_state} =====")

            logger.debug("===== DDS TRACE: Finished processing FunctionCapability samples in on_data_available =====")
        except dds.Error as e: # Catch DDS errors from reader.take()
            logger.error(f"DDS Error in on_data_available (e.g., during take()): {e}")
            logger.error(logging.traceback.format_exc())
        except Exception as e: # Catch other unexpected errors
            logger.error(f"Unexpected error in on_data_available: {e}")
            logger.error(logging.traceback.format_exc())
```

## genesis_lib/genesis_monitoring.py

**Author:** Jason

```python
"""
Genesis Monitoring System

This module provides the core monitoring infrastructure for the Genesis framework,
enabling real-time observation and logging of all distributed components. It implements
a comprehensive DDS-based monitoring system that captures and processes events from
agents, interfaces, and services across the network.

Key responsibilities include:
- Real-time log aggregation and distribution via DDS
- Component lifecycle event monitoring and tracking
- Function call and execution monitoring
- Chain event tracking for multi-step operations
- Liveliness monitoring for network health
- Centralized logging with source identification
- Event filtering and querying capabilities

The monitoring system subscribes to various DDS topics:
- LogMessage: For centralized logging across all components
- ComponentLifecycleEvent: For tracking component states and transitions
- ChainEvent: For monitoring function call chains and workflows
- LivelinessUpdate: For network health and component presence
- MonitoringEvent: For general monitoring and status updates

This system enables comprehensive visibility into the Genesis network's operation,
facilitating debugging, performance monitoring, and system health tracking.

Copyright (c) 2025, RTI & Jason Upchurch
"""

#!/usr/bin/env python3
import rti.connextdds as dds
import logging
import uuid
import time
import threading
import sys
import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import inspect
import queue
from genesis_lib.utils import get_datamodel_path

# Define log level mapping
LOG_LEVEL_MAP = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO",
    logging.WARNING: "WARNING",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "CRITICAL"
}

class DDSLogHandler(logging.Handler):
    """
    A custom logging handler that publishes log messages via DDS.
    This allows for centralized logging in a distributed system.
    """
    def __init__(self, log_publisher, source_id=None, source_name=None):
        """
        Initialize the DDS log handler.
        
        Args:
            log_publisher: The LogPublisher instance to use for publishing logs
            source_id: Unique identifier for the log source (defaults to a generated UUID)
            source_name: Human-readable name for the log source
        """
        super().__init__()
        self.log_publisher = log_publisher
        self.source_id = source_id or str(uuid.uuid4())
        self.source_name = source_name or f"Source-{self.source_id[:8]}"
        
        # Set a default formatter
        self.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
    
    def emit(self, record):
        """
        Emit a log record by publishing it via DDS.
        
        Args:
            record: The log record to emit
        """
        try:
            # Format the message
            msg = self.format(record)
            
            # Get caller information
            frame = inspect.currentframe()
            if frame:
                frame = frame.f_back
                while frame and frame.f_code.co_filename == __file__:
                    frame = frame.f_back
                
                if frame:
                    file_name = os.path.basename(frame.f_code.co_filename)
                    line_number = frame.f_lineno
                    function_name = frame.f_code.co_name
                else:
                    file_name = record.filename
                    line_number = record.lineno
                    function_name = record.funcName
            else:
                file_name = record.filename
                line_number = record.lineno
                function_name = record.funcName
            
            # Publish the log message
            self.log_publisher.publish_log(
                level=record.levelno,
                message=msg,
                logger_name=record.name,
                thread_id=str(record.thread),
                thread_name=record.threadName,
                file_name=file_name,
                line_number=line_number,
                function_name=function_name
            )
        except Exception as e:
            # Fallback to stderr if DDS publishing fails
            sys.stderr.write(f"Error in DDSLogHandler: {e}\n")
            sys.stderr.write(f"Original log message: {record.getMessage()}\n")


class LogPublisher:
    """
    Publishes log messages via DDS to enable centralized logging
    in a distributed system.
    """
    def __init__(self, participant=None, domain_id=0, source_id=None, source_name=None):
        """
        Initialize the log publisher.
        
        Args:
            participant: DDS participant to use (creates one if None)
            domain_id: DDS domain ID to use if creating a participant
            source_id: Unique identifier for the log source
            source_name: Human-readable name for the log source
        """
        self.source_id = source_id or str(uuid.uuid4())
        self.source_name = source_name or f"Source-{self.source_id[:8]}"
        
        # Create or use provided participant
        self.owns_participant = participant is None
        if self.owns_participant:
            participant_qos = dds.QosProvider.default.participant_qos
            self.participant = dds.DomainParticipant(domain_id, qos=participant_qos)
        else:
            self.participant = participant
        
        # Get log message type from XML
        config_path = get_datamodel_path()
        self.type_provider = dds.QosProvider(config_path)
        self.log_type = self.type_provider.type("genesis_lib", "LogMessage")
        
        # Create log topic
        self.log_topic = dds.DynamicData.Topic(
            self.participant,
            "GenesisLogs",
            self.log_type
        )
        
        # Create publisher
        self.publisher = dds.Publisher(
            self.participant,
            qos=dds.QosProvider.default.publisher_qos
        )
        
        # Configure writer QoS
        writer_qos = dds.QosProvider.default.datawriter_qos
        writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        writer_qos.history.kind = dds.HistoryKind.KEEP_LAST
        writer_qos.history.depth = 1000  # Keep more history for logs
        
        # Create log writer
        self.log_writer = dds.DynamicData.DataWriter(
            self.publisher,
            self.log_topic,
            qos=writer_qos
        )
        
        # Create a queue for asynchronous log publishing to avoid deadlocks
        self.log_queue = queue.Queue()
        self.publish_thread = threading.Thread(target=self._publish_worker, daemon=True)
        self.publish_thread.start()
    
    def _publish_worker(self):
        """Worker thread that processes the log queue and publishes messages"""
        while True:
            try:
                # Get log data from queue
                log_data = self.log_queue.get()
                
                # Write log message
                self.log_writer.write(log_data)
                
                # Mark task as done
                self.log_queue.task_done()
            except Exception as e:
                # Fallback to stderr if DDS publishing fails
                sys.stderr.write(f"Error in log publisher worker: {e}\n")
            
            # Small sleep to prevent CPU spinning
            time.sleep(0.001)
    
    def publish_log(self, level: int, message: str, logger_name: str = "",
                   thread_id: str = "", thread_name: str = "",
                   file_name: str = "", line_number: int = 0,
                   function_name: str = ""):
        """
        Publish a log message via DDS.
        
        Args:
            level: Log level (e.g., logging.INFO)
            message: Log message text
            logger_name: Name of the logger
            thread_id: ID of the thread that generated the log
            thread_name: Name of the thread that generated the log
            file_name: Source file where the log was generated
            line_number: Line number where the log was generated
            function_name: Function where the log was generated
        """
        try:
            # Create log message
            log_data = dds.DynamicData(self.log_type)
            log_data["log_id"] = str(uuid.uuid4())
            log_data["timestamp"] = int(time.time() * 1000)  # milliseconds
            log_data["source_id"] = self.source_id
            log_data["source_name"] = self.source_name
            log_data["level"] = level
            log_data["level_name"] = LOG_LEVEL_MAP.get(level, "UNKNOWN")
            log_data["message"] = message
            log_data["logger_name"] = logger_name
            log_data["thread_id"] = thread_id
            log_data["thread_name"] = thread_name
            log_data["file_name"] = file_name
            log_data["line_number"] = line_number
            log_data["function_name"] = function_name
            
            # Add to queue for asynchronous publishing
            self.log_queue.put(log_data)
        except Exception as e:
            # Fallback to stderr if DDS publishing fails
            sys.stderr.write(f"Error publishing log via DDS: {e}\n")
            sys.stderr.write(f"Original log message: {message}\n")
    
    def close(self):
        """Clean up DDS resources."""
        # Wait for queue to be processed
        self.log_queue.join()
        
        if hasattr(self, 'log_writer'):
            self.log_writer.close()
        if hasattr(self, 'publisher'):
            self.publisher.close()
        if hasattr(self, 'log_topic'):
            self.log_topic.close()
        if self.owns_participant and hasattr(self, 'participant'):
            self.participant.close()


class LogSubscriber:
    """
    Subscribes to log messages via DDS to enable centralized monitoring
    of logs from distributed components.
    """
    def __init__(self, participant=None, domain_id=0, callback=None):
        """
        Initialize the log subscriber.
        
        Args:
            participant: DDS participant to use (creates one if None)
            domain_id: DDS domain ID to use if creating a participant
            callback: Function to call when a log message is received
        """
        self.callback = callback
        
        # Create or use provided participant
        self.owns_participant = participant is None
        if self.owns_participant:
            participant_qos = dds.QosProvider.default.participant_qos
            self.participant = dds.DomainParticipant(domain_id, qos=participant_qos)
        else:
            self.participant = participant
        
        # Get log message type from XML
        config_path = get_datamodel_path()
        self.type_provider = dds.QosProvider(config_path)
        self.log_type = self.type_provider.type("genesis_lib", "LogMessage")
        
        # Create log topic
        self.log_topic = dds.DynamicData.Topic(
            self.participant,
            "GenesisLogs",
            self.log_type
        )
        
        # Create subscriber
        self.subscriber = dds.Subscriber(
            self.participant,
            qos=dds.QosProvider.default.subscriber_qos
        )
        
        # Configure reader QoS
        reader_qos = dds.QosProvider.default.datareader_qos
        reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        reader_qos.history.kind = dds.HistoryKind.KEEP_LAST
        reader_qos.history.depth = 1000  # Keep more history for logs
        
        # Create log reader with listener
        self.listener = LogListener(self._on_log_received)
        self.log_reader = dds.DynamicData.DataReader(
            self.subscriber,
            self.log_topic,
            qos=reader_qos,
            listener=self.listener
        )
        
        # Store received logs
        self.logs = []
        self.logs_lock = threading.Lock()
    
    def _on_log_received(self, log_data):
        """
        Handle received log messages.
        
        Args:
            log_data: The received log message data
        """
        with self.logs_lock:
            # Convert to dictionary for easier handling
            log_dict = {
                "log_id": log_data["log_id"],
                "timestamp": log_data["timestamp"],
                "source_id": log_data["source_id"],
                "source_name": log_data["source_name"],
                "level": log_data["level"],
                "level_name": log_data["level_name"],
                "message": log_data["message"],
                "logger_name": log_data["logger_name"],
                "thread_id": log_data["thread_id"],
                "thread_name": log_data["thread_name"],
                "file_name": log_data["file_name"],
                "line_number": log_data["line_number"],
                "function_name": log_data["function_name"]
            }
            
            # Add to logs list
            self.logs.append(log_dict)
            
            # Call callback if provided
            if self.callback:
                self.callback(log_dict)
    
    def get_logs(self, max_count=None, level_filter=None, source_filter=None):
        """
        Get received logs with optional filtering.
        
        Args:
            max_count: Maximum number of logs to return
            level_filter: Minimum log level to include
            source_filter: Source ID or name to filter by
            
        Returns:
            List of log dictionaries
        """
        with self.logs_lock:
            filtered_logs = self.logs
            
            # Apply level filter
            if level_filter is not None:
                filtered_logs = [log for log in filtered_logs if log["level"] >= level_filter]
            
            # Apply source filter
            if source_filter is not None:
                filtered_logs = [
                    log for log in filtered_logs 
                    if source_filter in (log["source_id"], log["source_name"])
                ]
            
            # Apply count limit
            if max_count is not None:
                filtered_logs = filtered_logs[-max_count:]
            
            return filtered_logs
    
    def clear_logs(self):
        """Clear the stored logs."""
        with self.logs_lock:
            self.logs = []
    
    def close(self):
        """Clean up DDS resources."""
        if hasattr(self, 'log_reader'):
            self.log_reader.close()
        if hasattr(self, 'subscriber'):
            self.subscriber.close()
        if hasattr(self, 'log_topic'):
            self.log_topic.close()
        if self.owns_participant and hasattr(self, 'participant'):
            self.participant.close()


class LogListener(dds.DynamicData.NoOpDataReaderListener):
    """Listener for log messages."""
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
    
    def on_data_available(self, reader):
        """Handle data available event."""
        try:
            # Read all available samples
            samples = reader.take()
            for data, info in samples:
                if data is None or info.state.instance_state != dds.InstanceState.ALIVE:
                    continue
                
                # Call callback with log data
                self.callback(data)
        except Exception as e:
            sys.stderr.write(f"Error in LogListener: {e}\n")


class MonitoringSubscriber:
    """
    Subscribes to monitoring events via DDS to enable centralized monitoring
    of function calls, discoveries, and status updates.
    """
    def __init__(self, participant=None, domain_id=0, callback=None):
        """
        Initialize the monitoring subscriber.
        
        Args:
            participant: DDS participant to use (creates one if None)
            domain_id: DDS domain ID to use if creating a participant
            callback: Function to call when a monitoring event is received
        """
        self.callback = callback
        
        # Create or use provided participant
        self.owns_participant = participant is None
        if self.owns_participant:
            participant_qos = dds.QosProvider.default.participant_qos
            self.participant = dds.DomainParticipant(domain_id, qos=participant_qos)
        else:
            self.participant = participant
        
        # Get monitoring event type from XML
        config_path = get_datamodel_path()
        self.type_provider = dds.QosProvider(config_path)
        self.event_type = self.type_provider.type("genesis_lib", "MonitoringEvent")
        
        # Create monitoring topic
        self.event_topic = dds.DynamicData.Topic(
            self.participant,
            "MonitoringEvent",
            self.event_type
        )
        
        # Create subscriber
        self.subscriber = dds.Subscriber(
            self.participant,
            qos=dds.QosProvider.default.subscriber_qos
        )
        
        # Configure reader QoS
        reader_qos = dds.QosProvider.default.datareader_qos
        reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        reader_qos.history.kind = dds.HistoryKind.KEEP_LAST
        reader_qos.history.depth = 1000  # Keep more history for events
        
        # Create event reader with listener
        self.event_reader = dds.DynamicData.DataReader(
            self.subscriber,
            self.event_topic,
            qos=reader_qos,
            listener=MonitoringListener(self._on_event_received)
        )
        
        # Store events for querying
        self.events = []
        self.events_lock = threading.Lock()
    
    def _on_event_received(self, event_data):
        """Process received monitoring event."""
        try:
            # Convert DDS data to Python dict
            event = {
                "event_id": event_data["event_id"],
                "timestamp": event_data["timestamp"],
                "event_type": str(event_data["event_type"]),
                "entity_type": str(event_data["entity_type"]),
                "entity_id": event_data["entity_id"],
                "metadata": event_data["metadata"],
                "call_data": event_data["call_data"],
                "result_data": event_data["result_data"],
                "status_data": event_data["status_data"]
            }
            
            # Store event
            with self.events_lock:
                self.events.append(event)
            
            # Call callback if provided
            if self.callback:
                self.callback(event)
        except Exception as e:
            sys.stderr.write(f"Error processing monitoring event: {e}\n")
    
    def get_events(self, max_count=None, event_type=None, entity_type=None):
        """
        Get stored events with optional filtering.
        
        Args:
            max_count: Maximum number of events to return
            event_type: Filter by event type
            entity_type: Filter by entity type
        
        Returns:
            List of events matching the filters
        """
        with self.events_lock:
            filtered = self.events
            
            if event_type:
                filtered = [e for e in filtered if e["event_type"] == event_type]
            
            if entity_type:
                filtered = [e for e in filtered if e["entity_type"] == entity_type]
            
            if max_count:
                filtered = filtered[-max_count:]
            
            return filtered
    
    def clear_events(self):
        """Clear stored events."""
        with self.events_lock:
            self.events = []
    
    def close(self):
        """Clean up DDS resources."""
        if hasattr(self, 'event_reader'):
            self.event_reader.close()
        if hasattr(self, 'subscriber'):
            self.subscriber.close()
        if hasattr(self, 'event_topic'):
            self.event_topic.close()
        if self.owns_participant and hasattr(self, 'participant'):
            self.participant.close()


class MonitoringListener(dds.DynamicData.NoOpDataReaderListener):
    """Listener for monitoring events."""
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
    
    def on_data_available(self, reader):
        """Process available monitoring events."""
        try:
            for sample in reader.take():
                if sample.info.valid:
                    self.callback(sample.data)
        except Exception as e:
            sys.stderr.write(f"Error in monitoring listener: {e}\n")


def configure_dds_logging(logger_name=None, participant=None, domain_id=0, 
                         source_id=None, source_name=None, log_level=logging.INFO):
    """
    Configure a logger to use DDS-based logging.
    
    Args:
        logger_name: Name of the logger to configure (None for root logger)
        participant: DDS participant to use (creates one if None)
        domain_id: DDS domain ID to use if creating a participant
        source_id: Unique identifier for the log source
        source_name: Human-readable name for the log source
        log_level: Minimum log level to publish
        
    Returns:
        Tuple of (logger, log_publisher, log_handler)
    """
    # Get the logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)
    
    # Create log publisher
    log_publisher = LogPublisher(
        participant=participant,
        domain_id=domain_id,
        source_id=source_id,
        source_name=source_name
    )
    
    # Create and add DDS log handler
    handler = DDSLogHandler(
        log_publisher=log_publisher,
        source_id=source_id,
        source_name=source_name
    )
    handler.setLevel(log_level)
    logger.addHandler(handler)
    
    return logger, log_publisher, handler


# Example usage of the monitoring system
if __name__ == "__main__":
    # This is a simple monitoring application that displays logs from all components
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="GENESIS Monitoring Application")
    parser.add_argument("--domain", type=int, default=0, help="DDS domain ID")
    parser.add_argument("--level", type=str, default="INFO", 
                       choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                       help="Minimum log level to display")
    args = parser.parse_args()
    
    # Map log level string to int
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    log_level = level_map[args.level]
    
    # Configure local logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("MonitoringApp")
    
    # Create log subscriber
    def log_callback(log_dict):
        # Format timestamp
        timestamp = datetime.fromtimestamp(log_dict["timestamp"] / 1000).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        # Format and print log message
        print(f"[{timestamp}] [{log_dict['level_name']}] [{log_dict['source_name']}] {log_dict['message']}")
        
        # Print additional details for higher log levels
        if log_dict["level"] >= logging.WARNING:
            print(f"  File: {log_dict['file_name']}:{log_dict['line_number']} in {log_dict['function_name']}")
            print(f"  Logger: {log_dict['logger_name']}")
            print(f"  Thread: {log_dict['thread_name']} ({log_dict['thread_id']})")
            print()
    
    subscriber = LogSubscriber(
        domain_id=args.domain,
        callback=log_callback
    )
    
    logger.info(f"Monitoring application started on domain {args.domain}")
    logger.info(f"Displaying logs with level {args.level} and above")
    logger.info("Press Ctrl+C to exit")
    
    try:
        # Main loop - just keep the application alive
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("Shutting down monitoring application")
        subscriber.close()
        sys.exit(0) 
```

## genesis_lib/function_client.py

**Author:** Jason

```python
"""
Genesis Function Client

This module provides a generic function client implementation for the Genesis framework,
enabling dynamic discovery and invocation of functions across the distributed network.
It serves as a key component in the function calling infrastructure, allowing agents
to discover and utilize functions without prior knowledge of their implementation.

Key responsibilities include:
- Dynamic discovery of available functions in the distributed system
- Automatic service client management and lifecycle
- Intelligent function routing based on service type
- Schema validation and function metadata management
- Seamless integration with the Genesis RPC system

The GenericFunctionClient enables agents to discover and call any function service
without requiring prior knowledge of specific functions, making the Genesis network
more flexible and adaptable to changing capabilities.

Copyright (c) 2025, RTI & Jason Upchurch
"""

#!/usr/bin/env python3

import logging
import asyncio
import json
import time
import uuid
from typing import Dict, Any, List, Optional
import rti.connextdds as dds
from genesis_lib.rpc_client import GenesisRPCClient
from genesis_lib.function_discovery import FunctionRegistry

# Configure logging
logger = logging.getLogger("genesis_function_client")

class GenericFunctionClient:
    """
    A truly generic function client that can discover and call any function service
    without prior knowledge of the specific functions.
    """
    
    def __init__(self, function_registry: Optional[FunctionRegistry] = None):
        """
        Initialize the generic function client.
        
        Args:
            function_registry: Optional existing FunctionRegistry instance to use.
                             If None, a new one will be created.
        """
        logger.info("Initializing GenericFunctionClient")
        
        # Use provided registry or create new one
        self.function_registry = function_registry or FunctionRegistry()
        
        # Store discovered functions
        self.discovered_functions = {}
        
        # Store service-specific clients
        self.service_clients = {}
        
    async def discover_functions(self, timeout_seconds: int = 10) -> Dict[str, Any]:
        """
        Discover available functions in the distributed system.
        
        Args:
            timeout_seconds: How long to wait for functions to be discovered
            
        Returns:
            Dictionary of discovered functions
        """
        logger.info("Discovering all available functions")
        start_time = time.time()
        
        # Keep checking until we find all types of functions or timeout
        calculator_found = False
        letter_counter_found = False
        text_processor_found = False
        
        while time.time() - start_time < timeout_seconds:
            # Update discovered functions
            self.discovered_functions = self.function_registry.discovered_functions.copy()
            
            # Check if we've found all the functions we're looking for
            for func_id, func_info in self.discovered_functions.items():
                if isinstance(func_info, dict):
                    name = func_info.get('name', '').lower()
                    if 'calculator' in name:
                        calculator_found = True
                    elif 'letter' in name and 'counter' in name:
                        letter_counter_found = True
                    elif 'text' in name and 'processor' in name:
                        text_processor_found = True
            
            # If we've found all functions, break early
            if calculator_found and letter_counter_found and text_processor_found:
                break
                
            # Wait a bit before checking again
            await asyncio.sleep(0.5)
        
        # Log the discovered functions, even if none were found
        if not self.discovered_functions:
            logger.info("No functions discovered in the distributed system")
            return {}
        
        logger.info(f"Discovered {len(self.discovered_functions)} functions")
        for func_id, func_info in self.discovered_functions.items():
            if isinstance(func_info, dict):
                logger.info(f"  - {func_id}: {func_info.get('name', 'unknown')} - {func_info.get('description', 'No description')}")
            else:
                logger.info(f"  - {func_id}: {func_info}")
        
        return self.discovered_functions
    
    def get_service_client(self, service_name: str) -> GenesisRPCClient:
        """
        Get or create a client for a specific service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            RPC client for the service
        """
        if service_name not in self.service_clients:
            logger.info(f"Creating new client for service: {service_name}")
            client = GenesisRPCClient(service_name=service_name)
            # Set a reasonable timeout (10 seconds)
            client.timeout = dds.Duration(seconds=10)
            self.service_clients[service_name] = client
        
        return self.service_clients[service_name]
    
    async def call_function(self, function_id: str, **kwargs) -> Dict[str, Any]:
        """
        Call a function by its ID with the given arguments.
        
        Args:
            function_id: ID of the function to call
            **kwargs: Arguments to pass to the function
            
        Returns:
            Function result
            
        Raises:
            ValueError: If the function is not found
            RuntimeError: If the function call fails
        """
        if function_id not in self.discovered_functions:
            raise ValueError(f"Function not found: {function_id}")
        
        # Get function info
        func_info = self.discovered_functions[function_id]
        
        # Extract function name and provider ID
        if isinstance(func_info, dict):
            function_name = func_info.get('name')
            provider_id = func_info.get('provider_id')
        else:
            raise RuntimeError(f"Invalid function info format for {function_id}")
        
        if not function_name:
            raise RuntimeError(f"Function name not found for {function_id}")
        
        # Determine the service name based on the function name or provider ID
        service_name = "CalculatorService"  # Default service
        
        # Map function names to their respective services
        if function_name in ['count_letter', 'count_multiple_letters', 'get_letter_frequency']:
            service_name = "LetterCounterService"
        elif function_name in ['transform_case', 'analyze_text', 'generate_text']:
            service_name = "TextProcessorService"
        
        # If we have a provider ID, use it to determine the service name more accurately
        if provider_id:
            # Extract service name from provider ID if possible
            # This is a more reliable method if the provider ID contains service information
            logger.info(f"Using provider ID to determine service: {provider_id}")
        
        logger.info(f"Using service name: {service_name} for function: {function_name}")
        
        # Get or create a client for this service
        client = self.get_service_client(service_name)
        
        # Wait for the service to be discovered
        logger.info(f"Waiting for service {service_name} to be discovered")
        try:
            await client.wait_for_service(timeout_seconds=5)
        except TimeoutError as e:
            logger.warning(f"Service discovery timed out, but attempting call anyway: {str(e)}")
        
        # Call the function through RPC
        logger.info(f"Calling function {function_name} via RPC")
        try:
            return await client.call_function(function_name, **kwargs)
        except Exception as e:
            raise RuntimeError(f"Error calling function {function_name}: {str(e)}")
    
    def get_function_schema(self, function_id: str) -> Dict[str, Any]:
        """
        Get the schema for a specific function.
        
        Args:
            function_id: ID of the function
            
        Returns:
            Function schema
            
        Raises:
            ValueError: If the function is not found
        """
        if function_id not in self.discovered_functions:
            raise ValueError(f"Function not found: {function_id}")
        
        return self.discovered_functions[function_id].schema
    
    def list_available_functions(self) -> List[Dict[str, Any]]:
        """
        List all available functions with their descriptions and schemas.
        
        Returns:
            List of function information dictionaries
        """
        result = []
        for func_id, func_info in self.discovered_functions.items():
            if isinstance(func_info, dict):
                # Get the schema directly from the function info
                schema = func_info.get('schema', {})
                
                # Determine the service name based on the function name
                service_name = "CalculatorService"  # Default service
                function_name = func_info.get('name', func_id)
                
                if function_name in ['count_letter', 'count_multiple_letters', 'get_letter_frequency']:
                    service_name = "LetterCounterService"
                elif function_name in ['transform_case', 'analyze_text', 'generate_text']:
                    service_name = "TextProcessorService"
                
                # If we have a provider ID, it might contain service information
                provider_id = func_info.get('provider_id')
                if provider_id:
                    logger.debug(f"Provider ID for {function_name}: {provider_id}")
                
                result.append({
                    "function_id": func_id,
                    "name": function_name,
                    "description": func_info.get('description', 'No description'),
                    "schema": schema,
                    "service_name": service_name
                })
            else:
                # Handle non-dictionary function info (unlikely but for robustness)
                result.append({
                    "function_id": func_id,
                    "name": str(func_info),
                    "description": "Unknown function format",
                    "schema": {},
                    "service_name": "UnknownService"
                })
        return result
    
    def close(self):
        """Close all client resources"""
        logger.info("Cleaning up client resources...")
        for client in self.service_clients.values():
            client.close()
        logger.info("Client cleanup complete.") 
```

## genesis_lib/openai_genesis_agent.py

**Author:** Jason

```python
#!/usr/bin/env python3
"""
OpenAI Genesis Agent Implementation

This module defines the OpenAIGenesisAgent class, which extends the MonitoredAgent
to provide an agent implementation specifically utilizing the OpenAI API.
It integrates OpenAI's chat completion capabilities, including function calling,
with the Genesis framework's monitoring and function discovery features.

Copyright (c) 2025, RTI & Jason Upchurch
"""

"""
OpenAI Genesis agent with function calling capabilities.
This agent provides a flexible and configurable interface for creating OpenAI-based agents
with support for function discovery, classification, and execution.
"""

import os
import sys
import logging
import json
import asyncio
import time
import traceback
import uuid
from openai import OpenAI
from typing import Dict, Any, List, Optional

from genesis_lib.monitored_agent import MonitoredAgent
from genesis_lib.function_classifier import FunctionClassifier
from genesis_lib.generic_function_client import GenericFunctionClient

# Configure logging
# logging.basicConfig(  # REMOVE THIS BLOCK
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
logger = logging.getLogger("openai_genesis_agent")

class OpenAIGenesisAgent(MonitoredAgent):
    """An agent that uses OpenAI API with Genesis function calls"""
    
    def __init__(self, model_name="gpt-4o", classifier_model_name="gpt-4o-mini", 
                 domain_id: int = 0, agent_name: str = "OpenAIAgent", 
                 base_service_name: str = "OpenAIChat", service_instance_tag: Optional[str] = None, 
                 description: str = None, enable_tracing: bool = False):
        """Initialize the agent with the specified models
        
        Args:
            model_name: OpenAI model to use (default: gpt-4o)
            classifier_model_name: Model to use for function classification (default: gpt-4o-mini)
            domain_id: DDS domain ID (default: 0)
            agent_name: Name of the agent (default: "OpenAIAgent")
            base_service_name: The fundamental type of service (default: "OpenAIChat")
            service_instance_tag: Optional tag for unique RPC service name instance
            description: Optional description of the agent
            enable_tracing: Whether to enable detailed tracing logs (default: False)
        """
        # Store tracing configuration
        self.enable_tracing = enable_tracing
        
        if self.enable_tracing:
            logger.debug(f"Initializing OpenAIGenesisAgent with model {model_name}")
        
        # Store model configuration
        self.model_config = {
            "model_name": model_name,
            "classifier_model_name": classifier_model_name
        }
        
        # Initialize monitored agent base class
        super().__init__(
            agent_name=agent_name,
            base_service_name=base_service_name,
            service_instance_tag=service_instance_tag,
            agent_type="SPECIALIZED_AGENT",  # This is a specialized AI agent
            description=description or f"An OpenAI-powered agent using {model_name} model, providing {base_service_name} service",
            domain_id=domain_id
        )
        
        # Get API key from environment
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.api_key)
        
        # Initialize generic client for function discovery, passing the agent's participant
        # self.generic_client = GenericFunctionClient(participant=self.app.participant)
        # Ensure GenericFunctionClient uses the SAME FunctionRegistry as the GenesisApp
        logger.debug(f"===== TRACING: Initializing GenericFunctionClient using agent app's FunctionRegistry: {id(self.app.function_registry)} =====")
        self.generic_client = GenericFunctionClient(function_registry=self.app.function_registry)
        self.function_cache = {}  # Cache for discovered functions
        
        # Initialize function classifier
        self.function_classifier = FunctionClassifier(llm_client=self.client)
        
        # Set system prompts for different scenarios
        self.function_based_system_prompt = """You are a helpful assistant that can perform various operations using remote services.
You have access to a set of functions that can help you solve problems.
When a function is available that can help with a task, you should use it rather than trying to solve the problem yourself.
This is especially important for mathematical calculations and data processing tasks.
Always explain your reasoning and the steps you're taking."""

        self.general_system_prompt = """You are a helpful and engaging AI assistant. You can:
- Answer questions and provide information
- Tell jokes and engage in casual conversation
- Help with creative tasks like writing and brainstorming
- Provide explanations and teach concepts
- Assist with problem-solving and decision making
Be friendly, professional, and maintain a helpful tone while being concise and clear in your responses."""

        # Start with general prompt, will switch to function-based if functions are discovered
        self.system_prompt = self.general_system_prompt
        
        # Set OpenAI-specific capabilities
        self.set_agent_capabilities(
            supported_tasks=["text_generation", "conversation"],
            additional_capabilities=self.model_config
        )
        
        if self.enable_tracing:
            logger.debug("OpenAIGenesisAgent initialized successfully")
    
    async def _ensure_functions_discovered(self):
        """Ensure functions are discovered before use. Relies on GenericFunctionClient to asynchronously update its list.
        This method populates the agent's function_cache based on the current list from GenericFunctionClient ON EVERY CALL.
        """
        logger.debug("===== TRACING: Attempting to populate function cache from GenericFunctionClient... =====")
        
        functions = self.generic_client.list_available_functions()
        
        # Reset function cache for fresh population
        self.function_cache = {}

        if not functions:
            logger.debug("===== TRACING: No functions currently listed by GenericFunctionClient. General prompt will be used. =====")
            self.system_prompt = self.general_system_prompt
            return
        
        logger.debug(f"===== TRACING: {len(functions)} functions listed by GenericFunctionClient. Populating cache. System prompt set to function-based. =====")
        self.system_prompt = self.function_based_system_prompt

        for func_data in functions: # Iterate over list of dicts
            # func_data should be a dictionary from the list returned by GenericFunctionClient
            # It has keys like 'name', 'description', 'schema', 'function_id'
            func_id = func_data["function_id"]
            self.function_cache[func_data["name"]] = {
                "function_id": func_id,
                "description": func_data["description"],
                "schema": func_data["schema"],
                "provider_id": func_data.get("provider_id"),
                "classification": { # Default classification, can be overridden if func_data has it
                    "entity_type": "function",
                    "domain": ["unknown"],
                    "operation_type": func_data.get("operation_type", "unknown"),
                    "io_types": {
                        "input": ["unknown"],
                        "output": ["unknown"]
                    },
                    "performance": {
                        "latency": "unknown",
                        "throughput": "unknown"
                    },
                    "security": {
                        "level": "public",
                        "authentication": "none"
                    }
                }
            }
            # If func_data itself contains a 'classification' field, merge it or use it
            if "classification" in func_data and isinstance(func_data["classification"], dict):
                self.function_cache[func_data["name"]]["classification"].update(func_data["classification"])

            
            logger.debug("===== TRACING: Processing discovered function for cache =====")
            logger.debug(f"Name: {func_data['name']}")
            logger.debug(f"ID: {func_id}")
            logger.debug(f"Description: {func_data['description']}")
            logger.debug(f"Schema: {json.dumps(func_data['schema'], indent=2)}")
            logger.debug("=" * 80)
            
            # Publish discovery event (consider if this is too noisy here - it's already done by FunctionRegistry)
            # For now, let's keep it to see if OpenAIGenesisAgent "sees" them
            self.publish_monitoring_event(
                "AGENT_DISCOVERY", # This event type might need review for semantic correctness here
                metadata={
                    "function_id": func_id,
                    "function_name": func_data["name"],
                    "provider_id": func_data.get("provider_id"),
                    "source": "OpenAIGenesisAgent._ensure_functions_discovered"
                }
            )
    
    def _get_function_schemas_for_openai(self, relevant_functions: Optional[List[str]] = None):
        """Convert discovered functions to OpenAI function schemas format"""
        logger.debug("===== TRACING: Converting function schemas for OpenAI =======")
        function_schemas = []
        
        for name, func_info in self.function_cache.items():
            # If relevant_functions is provided, only include those functions
            if relevant_functions is not None and name not in relevant_functions:
                continue
                
            schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": func_info["description"],
                    "parameters": func_info["schema"]
                }
            }
            function_schemas.append(schema)
            logger.debug(f"===== TRACING: Added schema for function: {name} =====")
        
        return function_schemas
    
    async def _call_function(self, function_name: str, **kwargs) -> Any:
        """Call a function using the generic client"""
        logger.debug(f"===== TRACING: Calling function {function_name} =====")
        logger.debug(f"===== TRACING: Function arguments: {json.dumps(kwargs, indent=2)} =====")
        
        if function_name not in self.function_cache:
            error_msg = f"Function not found: {function_name}"
            logger.error(f"===== TRACING: {error_msg} =====")
            raise ValueError(error_msg)
        
        try:
            # Call the function through the generic client
            start_time = time.time()
            result = await self.generic_client.call_function(
                self.function_cache[function_name]["function_id"],
                **kwargs
            )
            end_time = time.time()
            
            logger.debug(f"===== TRACING: Function call completed in {end_time - start_time:.2f} seconds =====")
            logger.debug(f"===== TRACING: Function result: {result} =====")
            
            # Extract result value if in dict format
            if isinstance(result, dict) and "result" in result:
                return result["result"]
            return result
            
        except Exception as e:
            logger.error(f"===== TRACING: Error calling function {function_name}: {str(e)} =====")
            logger.error(traceback.format_exc())
            raise
    
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process a user request and return a response"""
        user_message = request.get("message", "")
        logger.debug(f"===== TRACING: Processing request: {user_message} =====")
        
        try:
            # Ensure functions are discovered
            await self._ensure_functions_discovered()
            
            # Generate chain and call IDs for tracking
            chain_id = str(uuid.uuid4())
            call_id = str(uuid.uuid4())
            
            # If no functions are available, proceed with basic response
            if not self.function_cache:
                logger.debug("===== TRACING: No functions available, proceeding with general conversation =====")
                
                # Create chain event for LLM call start
                self._publish_llm_call_start(
                    chain_id=chain_id,
                    call_id=call_id,
                    model_identifier=f"openai.{self.model_config['model_name']}"
                )
                
                # Process with general conversation
                response = self.client.chat.completions.create(
                    model=self.model_config['model_name'],
                    messages=[
                        {"role": "system", "content": self.general_system_prompt},
                        {"role": "user", "content": user_message}
                    ]
                )
                
                # Create chain event for LLM call completion
                self._publish_llm_call_complete(
                    chain_id=chain_id,
                    call_id=call_id,
                    model_identifier=f"openai.{self.model_config['model_name']}"
                )
                
                return {
                    "message": response.choices[0].message.content,
                    "status": 0
                }
            
            # Phase 1: Function Classification
            # Create chain event for classification LLM call start
            self._publish_llm_call_start(
                chain_id=chain_id,
                call_id=call_id,
                model_identifier=f"openai.{self.model_config['classifier_model_name']}.classifier"
            )
            
            # Get available functions
            available_functions = [
                {
                    "name": name,
                    "description": info["description"],
                    "schema": info["schema"],
                    "classification": info.get("classification", {})
                }
                for name, info in self.function_cache.items()
            ]
            
            # Classify functions based on user query
            relevant_functions = self.function_classifier.classify_functions(
                user_message,
                available_functions,
                self.model_config['classifier_model_name']
            )
            
            # Create chain event for classification LLM call completion
            self._publish_llm_call_complete(
                chain_id=chain_id,
                call_id=call_id,
                model_identifier=f"openai.{self.model_config['classifier_model_name']}.classifier"
            )
            
            # Publish classification results for each relevant function
            for func in relevant_functions:
                # Create chain event for classification result
                self._publish_classification_result(
                    chain_id=chain_id,
                    call_id=call_id,
                    classified_function_name=func["name"],
                    classified_function_id=self.function_cache[func["name"]]["function_id"]
                )
                
                # Create component lifecycle event for function classification
                self.publish_component_lifecycle_event(
                    category="STATE_CHANGE",
                    previous_state="READY",
                    new_state="BUSY",
                    reason=f"CLASSIFICATION.RELEVANT: Function '{func['name']}' for query: {user_message[:100]}",
                    capabilities=json.dumps({
                        "function_name": func["name"],
                        "description": func["description"],
                        "classification": func["classification"]
                    })
                )
            
            # Get function schemas for relevant functions
            relevant_function_names = [func["name"] for func in relevant_functions]
            function_schemas = self._get_function_schemas_for_openai(relevant_function_names)
            
            if not function_schemas:
                logger.warning("===== TRACING: No relevant functions found, processing without functions =====")
                
                # Create chain event for LLM call start
                self._publish_llm_call_start(
                    chain_id=chain_id,
                    call_id=call_id,
                    model_identifier=f"openai.{self.model_config['model_name']}"
                )
                
                # Process without functions
                response = self.client.chat.completions.create(
                    model=self.model_config['model_name'],
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_message}
                    ]
                )
                
                # Create chain event for LLM call completion
                self._publish_llm_call_complete(
                    chain_id=chain_id,
                    call_id=call_id,
                    model_identifier=f"openai.{self.model_config['model_name']}"
                )
                
                return {
                    "message": response.choices[0].message.content,
                    "status": 0
                }
            
            # Phase 2: Function Execution
            logger.debug("===== TRACING: Calling OpenAI API with function schemas =====")
            
            # Create chain event for LLM call start
            self._publish_llm_call_start(
                chain_id=chain_id,
                call_id=call_id,
                model_identifier=f"openai.{self.model_config['model_name']}"
            )
            
            response = self.client.chat.completions.create(
                model=self.model_config['model_name'],
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message}
                ],
                tools=function_schemas,
                tool_choice="auto"
            )

            logger.debug(f"=====!!!!! TRACING: OpenAI response: {response} !!!!!=====")
            
            # Create chain event for LLM call completion
            self._publish_llm_call_complete(
                chain_id=chain_id,
                call_id=call_id,
                model_identifier=f"openai.{self.model_config['model_name']}"
            )
            
            # Extract the response
            message = response.choices[0].message
            
            # Check if the model wants to call a function
            if message.tool_calls:
                logger.debug(f"===== TRACING: Model requested function call(s): {len(message.tool_calls)} =======")
                
                # Process each function call
                function_responses = []
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    logger.debug(f"===== TRACING: Processing function call: {function_name} =====")
                    
                    # Call the function
                    try:
                        # Create chain event for function call start
                        self._publish_function_call_start(
                            chain_id=chain_id,
                            call_id=call_id,
                            function_name=function_name,
                            function_id=self.function_cache[function_name]["function_id"],
                            target_provider_id=self.function_cache[function_name].get("provider_id")
                        )
                        
                        # Call the function through the generic client
                        start_time = time.time()
                        function_result = await self._call_function(function_name, **function_args)
                        end_time = time.time()
                        
                        # Create chain event for function call completion
                        self._publish_function_call_complete(
                            chain_id=chain_id,
                            call_id=call_id,
                            function_name=function_name,
                            function_id=self.function_cache[function_name]["function_id"],
                            source_provider_id=self.function_cache[function_name].get("provider_id")
                        )
                        
                        logger.debug(f"===== TRACING: Function call completed in {end_time - start_time:.2f} seconds =====")
                        logger.debug(f"===== TRACING: Function result: {function_result} =====")
                        
                        # Extract result value if in dict format
                        if isinstance(function_result, dict) and "result" in function_result:
                            function_result = function_result["result"]
                            
                        function_responses.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": str(function_result)
                        })
                        logger.debug(f"===== TRACING: Function {function_name} returned: {function_result} =====")
                    except Exception as e:
                        logger.error(f"===== TRACING: Error calling function {function_name}: {str(e)} =====")
                        function_responses.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": f"Error: {str(e)}"
                        })
                
                # If we have function responses, send them back to the model
                if function_responses:
                    # Create a new conversation with the function responses
                    logger.debug("===== TRACING: Sending function responses back to OpenAI =====")
                    
                    # Create chain event for second LLM call start
                    self._publish_llm_call_start(
                        chain_id=chain_id,
                        call_id=call_id,
                        model_identifier=f"openai.{self.model_config['model_name']}"
                    )
                    
                    second_response = self.client.chat.completions.create(
                        model=self.model_config['model_name'],
                        messages=[
                            {"role": "system", "content": self.system_prompt},
                            {"role": "user", "content": user_message},
                            message,  # The assistant's message requesting the function call
                            *function_responses  # The function responses
                        ]
                    )
                    
                    # Create chain event for second LLM call completion
                    self._publish_llm_call_complete(
                        chain_id=chain_id,
                        call_id=call_id,
                        model_identifier=f"openai.{self.model_config['model_name']}"
                    )
                    
                    # Extract the final response
                    final_message = second_response.choices[0].message.content
                    logger.debug(f"===== TRACING: Final response: {final_message} =====")
                    return {"message": final_message, "status": 0}
            
            # If no function call, just return the response
            text_response = message.content
            logger.debug(f"===== TRACING: Response (no function call): {text_response} =====")
            return {"message": text_response, "status": 0}
                
        except Exception as e:
            logger.error(f"===== TRACING: Error processing request: {str(e)} =======")
            logger.error(traceback.format_exc())
            return {"message": f"Error: {str(e)}", "status": 1}
    
    async def close(self):
        """Clean up resources"""
        try:
            # Close OpenAI-specific resources
            if hasattr(self, 'generic_client') and self.generic_client is not None:
                if asyncio.iscoroutinefunction(self.generic_client.close):
                    await self.generic_client.close()
                else:
                    self.generic_client.close()
            
            # Close base class resources
            await super().close()
            
            logger.debug(f"OpenAIGenesisAgent closed successfully")
        except Exception as e:
            logger.error(f"Error closing OpenAIGenesisAgent: {str(e)}")
            logger.error(traceback.format_exc())

    async def process_message(self, message: str) -> str:
        """
        Process a message using OpenAI and return the response.
        This method is monitored by the Genesis framework.
        
        Args:
            message: The message to process
            
        Returns:
            The agent's response to the message
        """
        try:
            # Process the message using OpenAI's process_request method
            response = await self.process_request({"message": message})
            
            # Publish a monitoring event for the successful response
            self.publish_monitoring_event(
                event_type="AGENT_RESPONSE",
                result_data={"response": response}
            )
            
            return response.get("message", "No response generated")
            
        except Exception as e:
            # Publish a monitoring event for the error
            self.publish_monitoring_event(
                event_type="AGENT_STATUS",
                status_data={"error": str(e)}
            )
            raise

async def run_test():
    """Test the OpenAIGenesisAgent"""
    agent = None
    try:
        # Create agent
        agent = OpenAIGenesisAgent()
        
        # Test with a single request to test the calculator service
        test_message = "What is 31337 multiplied by 424242?"
        
        logger.info(f"\n===== Testing agent with message: {test_message} =====")
        
        # Process request
        result = await agent.process_request({"message": test_message})
        
        # Print result
        if 'status' in result:
            logger.info(f"Result status: {result['status']}")
        logger.info(f"Response: {result['message']}")
        logger.info("=" * 50)
        
        return 0
    except Exception as e:
        logger.error(f"Error in test: {str(e)}", exc_info=True)
        return 1
    finally:
        # Clean up
        if agent:
            await agent.close()

def main():
    """Main entry point"""
    try:
        return asyncio.run(run_test())
    except KeyboardInterrupt:
        logger.info("Test interrupted")
        return 0
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main()) 
```

## genesis_lib/function_patterns.py

**Author:** Jason

```python
"""
Function success and failure patterns for the GENESIS distributed system.

NOTE: This module is not currently in use in the codebase. It is kept for potential future use
when a more robust pattern-based error handling system is needed. The current implementation
handles errors directly in:
- GenericFunctionClient for function discovery and calling
- OpenAIGenesisAgent for agent-specific error handling
- utils/function_utils.py for function utilities

The module provides useful abstractions for:
- Pattern-based success/failure detection
- Structured error handling with recovery hints
- Type-based and regex-based pattern matching
- Centralized pattern registry
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import re

@dataclass
class SuccessPattern:
    """Pattern for identifying successful function execution"""
    pattern_type: str  # "regex", "value_range", "type_check", etc.
    pattern: Any  # The actual pattern to match
    description: str  # Human-readable description of what success looks like

@dataclass
class FailurePattern:
    """Pattern for identifying function failures"""
    pattern_type: str  # "regex", "exception", "value_range", etc.
    pattern: Any  # The actual pattern to match
    error_code: str  # Unique error code
    description: str  # Human-readable description of the failure
    recovery_hint: Optional[str] = None  # Optional hint for recovery

class FunctionPatternRegistry:
    """Registry for function success and failure patterns"""
    
    def __init__(self):
        self.success_patterns: Dict[str, List[SuccessPattern]] = {}
        self.failure_patterns: Dict[str, List[FailurePattern]] = {}
    
    def register_patterns(self,
                         function_id: str,
                         success_patterns: Optional[List[SuccessPattern]] = None,
                         failure_patterns: Optional[List[FailurePattern]] = None):
        """
        Register success and failure patterns for a function.
        
        Args:
            function_id: Unique identifier for the function
            success_patterns: List of patterns indicating successful execution
            failure_patterns: List of patterns indicating failures
        """
        if success_patterns:
            self.success_patterns[function_id] = success_patterns
        if failure_patterns:
            self.failure_patterns[function_id] = failure_patterns
    
    def check_result(self, function_id: str, result: Any) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Check if a function result matches success or failure patterns.
        
        Args:
            function_id: ID of the function to check
            result: Result to check against patterns
            
        Returns:
            Tuple of (is_success, error_code, recovery_hint)
        """
        # Check failure patterns first (they take precedence)
        if function_id in self.failure_patterns:
            for pattern in self.failure_patterns[function_id]:
                if self._matches_pattern(result, pattern):
                    return False, pattern.error_code, pattern.recovery_hint
        
        # Check success patterns
        if function_id in self.success_patterns:
            all_patterns_match = True
            for pattern in self.success_patterns[function_id]:
                if not self._matches_pattern(result, pattern):
                    all_patterns_match = False
                    break
            if all_patterns_match:
                return True, None, None
            return False, None, None
        
        # Default to success if no patterns match
        return True, None, None
    
    def _matches_pattern(self, result: Any, pattern: SuccessPattern | FailurePattern) -> bool:
        """Check if a result matches a pattern"""
        if pattern.pattern_type == "regex":
            if isinstance(result, str):
                return bool(re.search(pattern.pattern, result))
            return False
        
        elif pattern.pattern_type == "value_range":
            if isinstance(result, (int, float)):
                min_val, max_val = pattern.pattern
                return min_val <= result <= max_val
            return False
        
        elif pattern.pattern_type == "type_check":
            return isinstance(result, pattern.pattern)
        
        elif pattern.pattern_type == "exception":
            if isinstance(pattern.pattern, type):
                return isinstance(result, pattern.pattern)
            return isinstance(result, Exception) and isinstance(result, type(pattern.pattern))
        
        return False

# Example patterns for common functions
CALCULATOR_PATTERNS = {
    "add": {
        "success": [
            SuccessPattern(
                pattern_type="type_check",
                pattern=(int, float),
                description="Result should be a number"
            ),
        ],
        "failure": [
            FailurePattern(
                pattern_type="exception",
                pattern=TypeError,
                error_code="CALC_TYPE_ERROR",
                description="Invalid argument types",
                recovery_hint="Ensure both arguments are numbers"
            ),
            FailurePattern(
                pattern_type="regex",
                pattern=r"overflow|too large",
                error_code="CALC_OVERFLOW",
                description="Number too large",
                recovery_hint="Use smaller numbers"
            )
        ]
    },
    "divide": {
        "success": [
            SuccessPattern(
                pattern_type="type_check",
                pattern=(int, float),
                description="Result should be a number"
            )
        ],
        "failure": [
            FailurePattern(
                pattern_type="exception",
                pattern=ZeroDivisionError,
                error_code="CALC_DIV_ZERO",
                description="Division by zero",
                recovery_hint="Ensure denominator is not zero"
            )
        ]
    }
}

LETTER_COUNTER_PATTERNS = {
    "count_letter": {
        "success": [
            SuccessPattern(
                pattern_type="type_check",
                pattern=int,
                description="Result should be a non-negative integer"
            ),
            SuccessPattern(
                pattern_type="value_range",
                pattern=(0, float('inf')),
                description="Count should be non-negative"
            )
        ],
        "failure": [
            FailurePattern(
                pattern_type="exception",
                pattern=ValueError,
                error_code="LETTER_INVALID",
                description="Invalid letter parameter",
                recovery_hint="Ensure letter parameter is a single character"
            )
        ]
    },
    "count_multiple_letters": {
        "success": [
            SuccessPattern(
                pattern_type="type_check",
                pattern=dict,
                description="Result should be a dictionary of counts"
            )
        ],
        "failure": [
            FailurePattern(
                pattern_type="exception",
                pattern=ValueError,
                error_code="LETTERS_INVALID",
                description="Invalid letters parameter",
                recovery_hint="Ensure all letters are single characters"
            )
        ]
    }
}

# Create global pattern registry
pattern_registry = FunctionPatternRegistry()

# Register common patterns
def register_common_patterns():
    """Register patterns for common functions"""
    for func_name, patterns in CALCULATOR_PATTERNS.items():
        pattern_registry.register_patterns(
            func_name,
            success_patterns=patterns.get("success"),
            failure_patterns=patterns.get("failure")
        )
    
    for func_name, patterns in LETTER_COUNTER_PATTERNS.items():
        pattern_registry.register_patterns(
            func_name,
            success_patterns=patterns.get("success"),
            failure_patterns=patterns.get("failure")
        )

# Register patterns on module import
register_common_patterns() 
```

## genesis_lib/enhanced_service_base.py

**Author:** Jason

```python
#!/usr/bin/env python3
"""
Genesis Enhanced Service Base

This module provides the core base class for all services in the Genesis framework,
implementing automatic function discovery, registration, and monitoring capabilities.
It serves as the foundation for exposing functions to large language models and agents
within the Genesis network.

Key responsibilities include:
- Automatic function registration and discovery for LLM tool use
- Comprehensive monitoring and event tracking
- Function capability advertisement and lifecycle management
- Enhanced error handling and resource management
- Integration with the Genesis monitoring system
- Support for function decorators and automatic schema generation

The EnhancedServiceBase class enables services to:
1. Automatically expose their functions to LLMs and agents
2. Track function calls, results, and errors
3. Monitor service and function lifecycle events
4. Manage function capabilities and discovery
5. Handle complex RPC interactions with proper monitoring

This is the primary integration point for services that want to participate
in the Genesis network's function calling ecosystem.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import logging
import asyncio
import json
from typing import Dict, Any, List, Optional, Callable
from genesis_lib.rpc_service import GenesisRPCService
from genesis_lib.function_discovery import FunctionRegistry, FunctionCapabilityListener
import rti.connextdds as dds
from genesis_lib.datamodel import FunctionRequest, FunctionReply
import re
import uuid
import time
import os
from genesis_lib.utils import get_datamodel_path

# Monitoring event type constants
EVENT_TYPE_MAP = {
    "FUNCTION_DISCOVERY": 0,  # Legacy discovery event
    "FUNCTION_CALL": 1,
    "FUNCTION_RESULT": 2,
    "FUNCTION_STATUS": 3,
    "FUNCTION_DISCOVERY_V2": 4  # New discovery event format
}

ENTITY_TYPE_MAP = {
    "FUNCTION": 0,
    "SERVICE": 1,
    "NODE": 2
}


# Configure logging
logger = logging.getLogger("enhanced_service_base")

class EnhancedFunctionCapabilityListener(FunctionCapabilityListener):
    def __init__(self, registry, service_base):
        super().__init__(registry)
        self.service_base = service_base

    def on_subscription_matched(self, reader, info):
        """Handle subscription matches"""
        # First check if this is a FunctionCapability topic match
        if reader.topic_name != "FunctionCapability":
            print(f"Ignoring subscription match for topic: {reader.topic_name}")
            return
            
        # Now we know this is a FunctionCapability topic match
        remote_guid = str(info.last_publication_handle)
        self_guid = str(self.registry.capability_writer.instance_handle) or "0"
        
        # Format the reason string for edge discovery
        edge_reason = f"provider={self_guid} client={remote_guid} function={remote_guid}"
        edge_capabilities = {
            "edge_type": "function_connection",
            "source_id": self_guid,
            "target_id": remote_guid,
            "topic": reader.topic_name
        }
        
        # Publish edge discovery event
        self.service_base.publish_component_lifecycle_event(
            previous_state="DISCOVERING",
            new_state="DISCOVERING",
            reason=edge_reason,
            capabilities=json.dumps(edge_capabilities),
            component_id=self_guid,
            event_category="EDGE_DISCOVERY",
            source_id=self_guid,
            target_id=remote_guid,
            connection_type="function_connection"
        )
        
       # print(f"FunctionCapability subscription matched with remote GUID: {remote_guid}")
       # print(f"FunctionCapability subscription matched with self GUID:   {self_guid}")

class EnhancedServiceBase(GenesisRPCService):
    """
    Enhanced base class for GENESIS RPC services.
    
    This class abstracts common functionality for:
    1. Function registration and discovery
    2. Monitoring event publication
    3. Error handling
    4. Resource management
    
    Services that extend this class need to:
    1. Call super().__init__(service_name="YourServiceName")
    2. Register their functions using register_enhanced_function()
    3. Implement their function methods with the standard pattern
    """
    
    def __init__(self, service_name: str, capabilities: List[str], participant=None, domain_id=0, registry: FunctionRegistry = None):
        """
        Initialize the enhanced service base.
        
        Args:
            service_name: Unique name for the service
            capabilities: List of service capabilities for discovery
            registry: Optional FunctionRegistry instance. If None, creates a new one.
        """
        # Initialize the base RPC service
        super().__init__(service_name=service_name)
        
        # Store service name as instance variable
        self.service_name = service_name
        
        # Create DDS participant if not provided
        if participant is None:
            participant = dds.DomainParticipant(domain_id)
        
        # Store participant reference
        self.participant = participant
        
        # Create subscriber
        self.subscriber = dds.Subscriber(participant)
        
        # Create publisher
        self.publisher = dds.Publisher(participant)

        # Use Python IDL types from datamodel.py
        self.request_type = FunctionRequest
        self.reply_type = FunctionReply
        
        # Get types from XML for monitoring
        config_path = get_datamodel_path()
        self.type_provider = dds.QosProvider(config_path)
        
        # Set up monitoring
        self.monitoring_type = self.type_provider.type("genesis_lib", "MonitoringEvent")
        self.monitoring_topic = dds.DynamicData.Topic(
            participant,
            "MonitoringEvent",
            self.monitoring_type
        )
        
        # Create monitoring publisher with QoS
        publisher_qos = dds.QosProvider.default.publisher_qos
        publisher_qos.partition.name = [""]  # Default partition
        self.monitoring_publisher = dds.Publisher(
            participant=participant,
            qos=publisher_qos
        )
        
        # Create monitoring writer with QoS
        writer_qos = dds.QosProvider.default.datawriter_qos
        writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        self.monitoring_writer = dds.DynamicData.DataWriter(
            pub=self.monitoring_publisher,
            topic=self.monitoring_topic,
            qos=writer_qos
        )
        
        # Set up enhanced monitoring (V2) - MOVED UP before registry initialization
        # Create topics for new monitoring types
        self.component_lifecycle_type = self.type_provider.type("genesis_lib", "ComponentLifecycleEvent")
        self.chain_event_type = self.type_provider.type("genesis_lib", "ChainEvent")
        self.liveliness_type = self.type_provider.type("genesis_lib", "LivelinessUpdate")

        # Create topics
        self.component_lifecycle_topic = dds.DynamicData.Topic(
            participant,
            "ComponentLifecycleEvent",
            self.component_lifecycle_type
        )
        self.chain_event_topic = dds.DynamicData.Topic(
            participant,
            "ChainEvent",
            self.chain_event_type
        )
        self.liveliness_topic = dds.DynamicData.Topic(
            participant,
            "LivelinessUpdate",
            self.liveliness_type
        )

        # Create writers with QoS
        writer_qos = dds.QosProvider.default.datawriter_qos
        writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE

        # Create writers for each monitoring type
        self.component_lifecycle_writer = dds.DynamicData.DataWriter(
            pub=self.monitoring_publisher,
            topic=self.component_lifecycle_topic,
            qos=writer_qos
        )
        self.chain_event_writer = dds.DynamicData.DataWriter(
            pub=self.monitoring_publisher,
            topic=self.chain_event_topic,
            qos=writer_qos
        )
        self.liveliness_writer = dds.DynamicData.DataWriter(
            pub=self.monitoring_publisher,
            topic=self.liveliness_topic,
            qos=writer_qos
        )
        
        # Now we can auto-register decorated functions
        self._auto_register_decorated_functions()
        
        # Initialize the function registry and store reference to self
        self.registry = registry if registry is not None else FunctionRegistry(
            participant=self.participant, 
            domain_id=domain_id,
            enable_discovery_listener=False # Service does not discover others
        )
        self.registry.service_base = self  # Set this instance as the service base

        # If discovery is disabled in the registry, its capability_reader will be None.
        # The EnhancedFunctionCapabilityListener (now removed) logic or any logic
        # relying on self.registry.capability_reader would need careful checking,
        # but currently, no such logic remains directly in EnhancedServiceBase.
        # The base listener is only created/attached within FunctionRegistry if enabled.

        # Now set app_guid using the capability writer's instance handle (writer is always created)
        self.app_guid = str(self.registry.capability_writer.instance_handle)
        
        # Store service capabilities
        self.service_capabilities = capabilities
        
        # Flag to track if functions have been advertised
        self._functions_advertised = False

        # Track call IDs for correlation between calls and results
        self._call_ids = {}

        # Initialize logger
        self.logger = logging.getLogger("enhanced_service_base")
    
    # ---------------------------------------------------------------------- #
    # Decorator auto‑scan                                                    #
    # ---------------------------------------------------------------------- #
    def _auto_register_decorated_functions(self):
        """
        Detect methods that carry __genesis_meta__ (set by @genesis_function)
        and register them via existing register_enhanced_function().
        """
        for attr in dir(self):
            fn = getattr(self, attr)
            meta = getattr(fn, "__genesis_meta__", None)
            if not meta:
                continue
            if fn.__name__ in self.functions:          # Already registered?
                continue
            self.register_enhanced_function(
                fn,
                meta["description"],
                meta["parameters"],
                operation_type=meta.get("operation_type"),
                common_patterns=meta.get("common_patterns"),
            )
    def register_enhanced_function(self, 
                                  func: Callable, 
                                  description: str, 
                                  parameters: Dict[str, Any],
                                  operation_type: Optional[str] = None,
                                  common_patterns: Optional[Dict[str, Any]] = None):
        """
        Register a function with enhanced metadata.
        
        This method wraps the standard register_function method and adds
        additional metadata for monitoring and discovery.
        
        Args:
            func: The function to register
            description: A description of what the function does
            parameters: JSON schema for the function parameters (either a dict or JSON string)
            operation_type: Type of operation (e.g., "calculation", "transformation")
            common_patterns: Common validation patterns used by this function
            
        Returns:
            The registered function (allows use as a decorator)
        """
        # Get the function name before wrapping
        func_name = func.__name__
        
        # Log start of registration process
        logger.info(f"Starting enhanced function registration for '{func_name}'", 
                   extra={
                       "service_name": self.service_name,
                       "function_name": func_name,
                       "operation_type": operation_type,
                       "has_common_patterns": bool(common_patterns)
                   })
        
        # Convert parameters to dict if it's a JSON string
        if isinstance(parameters, str):
            try:
                parameters = json.loads(parameters)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON schema string for function '{func_name}'")
                raise
        
        # Log function metadata
        logger.debug(f"Function metadata for '{func_name}'",
                    extra={
                        "description": description,
                        "parameters": parameters,
                        "operation_type": operation_type,
                        "common_patterns": common_patterns
                    })
        
        try:
            # Create the wrapper with the original function name
            logger.debug(f"Creating function wrapper for '{func_name}'")
            wrapped_func = self.function_wrapper(func_name)(func)
            wrapped_func.__name__ = func_name  # Preserve the original function name
            
            # Log wrapper creation success
            logger.debug(f"Successfully created wrapper for '{func_name}'")
            
            # Register the wrapped function with the base class
            logger.info(f"Registering wrapped function '{func_name}' with base class")
            result = self.register_function(
                func=wrapped_func,  # Register the wrapped function
                description=description,
                parameters=parameters,  # Pass as dict, register_function will handle serialization
                operation_type=operation_type,
                common_patterns=common_patterns
            )
            
            # Log successful registration
            logger.info(f"Successfully registered enhanced function '{func_name}'",
                       extra={
                           "service_name": self.service_name,
                           "function_name": func_name,
                           "registration_result": bool(result)
                       })
            
            return result
            
        except Exception as e:
            # Log registration failure with detailed error info
            logger.error(f"Failed to register enhanced function '{func_name}'",
                        extra={
                            "service_name": self.service_name,
                            "function_name": func_name,
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "traceback": logging.traceback.format_exc()
                        })
            raise
    
    def _publish_monitoring_event(self, event_type: str, function_name: str, 
                               call_data: Optional[Dict[str, Any]] = None,
                               result_data: Optional[Dict[str, Any]] = None,
                               status_data: Optional[Dict[str, Any]] = None,
                               metadata: Optional[Dict[str, Any]] = None,
                               request_info: Optional[Any] = None) -> None:
        """
        Publish a monitoring event.
        
        Args:
            event_type: Type of event (FUNCTION_DISCOVERY, FUNCTION_CALL, etc.)
            function_name: Name of the function involved
            call_data: Data about the function call (if applicable)
            result_data: Data about the function result (if applicable)
            status_data: Data about the function status (if applicable)
            metadata: Additional metadata about the event
            request_info: Request information containing client ID
        """
        event = dds.DynamicData(self.monitoring_type)
        event["event_id"] = str(uuid.uuid4())
        event["timestamp"] = int(time.time() * 1000)
        
        # Set event type and entity type
        event["event_type"] = EVENT_TYPE_MAP[event_type]
        
        # Set entity type based on event type and metadata
        if metadata and metadata.get("event") in ["node_join", "node_ready", "node_discovery"]:
            event["entity_type"] = ENTITY_TYPE_MAP["NODE"]
        else:
            event["entity_type"] = ENTITY_TYPE_MAP["FUNCTION"]
            
        event["entity_id"] = function_name
        
        # Build base metadata
        base_metadata = {
            "provider_id": str(self.participant.instance_handle),
            "client_id": str(request_info.publication_handle) if request_info else "unknown"
        }
        
        # Add event-specific metadata
        if event_type == "FUNCTION_DISCOVERY":
            base_metadata.update({
                "event": "discovery",
                "status": "available",
                "message": f"Function '{function_name}' available"
            })
        elif event_type == "FUNCTION_DISCOVERY_V2":
            base_metadata.update({
                "event": "discovery_v2",
                "status": "published",
                "message": f"Function '{function_name}' published"
            })
        elif event_type == "FUNCTION_CALL":
            call_id = f"call_{uuid.uuid4().hex[:8]}"
            base_metadata["call_id"] = call_id
            if request_info:
                # Store call_id for later correlation
                self._call_ids[str(request_info.publication_handle)] = call_id
            if call_data:
                args_str = ", ".join(f"{k}={v}" for k, v in call_data.items())
                base_metadata["message"] = f"Call received: {function_name}({args_str})"
        elif event_type == "FUNCTION_RESULT":
            if request_info:
                # Retrieve and remove call_id for this request
                call_id = self._call_ids.pop(str(request_info.publication_handle), None)
                if call_id:
                    base_metadata["call_id"] = call_id
            if result_data:
                result_str = str(result_data.get("result", "unknown"))
                base_metadata["message"] = f"Result sent: {function_name} = {result_str}"
        
        # Merge with provided metadata
        if metadata:
            base_metadata.update(metadata)
            
        event["metadata"] = json.dumps(base_metadata)
        if call_data:
            event["call_data"] = json.dumps(call_data)
        if result_data:
            event["result_data"] = json.dumps(result_data)
        if status_data:
            event["status_data"] = json.dumps(status_data)
        
        self.monitoring_writer.write(event)
        self.monitoring_writer.flush()

    def publish_component_lifecycle_event(self, 
                                       previous_state: str,
                                       new_state: str,
                                       reason: str = "",
                                       capabilities: str = "",
                                       chain_id: str = "",
                                       call_id: str = "",
                                       component_id: str = None,
                                       event_category: str = "",
                                       source_id: str = "",
                                       target_id: str = "",
                                       connection_type: str = ""):
        """
        Publish a component lifecycle event.
        """
        try:
            # Map state strings to enum values
            states = {
                "JOINING": 0,
                "DISCOVERING": 1,
                "READY": 2,
                "BUSY": 3,
                "DEGRADED": 4,
                "OFFLINE": 5
            }

            # Map event categories to enum values
            event_categories = {
                "NODE_DISCOVERY": 0,
                "EDGE_DISCOVERY": 1,
                "STATE_CHANGE": 2,
                "AGENT_INIT": 3,
                "AGENT_READY": 4,
                "AGENT_SHUTDOWN": 5,
                "DDS_ENDPOINT": 6
            }

            # Create event
            event = dds.DynamicData(self.component_lifecycle_type)
            
            # Set component ID (use provided or app GUID)
            event["component_id"] = component_id if component_id else self.app_guid
            
            # Set component type (FUNCTION for calculator service)
            event["component_type"] = 3  # FUNCTION enum value
            
            # Set states
            event["previous_state"] = states[previous_state]
            event["new_state"] = states[new_state]
            
            # Set other fields
            event["timestamp"] = int(time.time() * 1000)
            event["reason"] = reason
            event["capabilities"] = capabilities
            event["chain_id"] = chain_id
            event["call_id"] = call_id
            
            # Set event category and related fields
            if event_category:
                event["event_category"] = event_categories[event_category]
                event["source_id"] = source_id if source_id else self.app_guid
                
                if event_category == "EDGE_DISCOVERY":
                    event["target_id"] = target_id
                    event["connection_type"] = connection_type if connection_type else "function_connection"
                elif event_category == "STATE_CHANGE":
                    event["target_id"] = source_id if source_id else self.app_guid
                    event["connection_type"] = ""
                else:
                    event["target_id"] = target_id if target_id else ""
                    event["connection_type"] = ""
            else:
                # Default to NODE_DISCOVERY if no category provided
                event["event_category"] = event_categories["NODE_DISCOVERY"]
                event["source_id"] = source_id if source_id else self.app_guid
                event["target_id"] = target_id if target_id else ""
                event["connection_type"] = ""

            # Write and flush the event
            self.component_lifecycle_writer.write(event)
            self.component_lifecycle_writer.flush()
            
        except Exception as e:
            logger.error(f"Error publishing component lifecycle event: {e}")
            logger.error(f"Event category was: {event_category}")
    
    def _advertise_functions(self):
        """
        Advertise registered functions to the function registry.
        
        This method:
        1. Iterates through all registered functions
        2. Builds metadata for each function
        3. Registers the function with the registry
        4. Publishes monitoring events for function discovery
        """
        if self._functions_advertised:
            logger.warning("===== DDS TRACE: Functions already advertised, skipping. =====")
            return

        logger.info("===== DDS TRACE: Starting function advertisement process... =====")

        # Get total number of functions for tracking first/last
        total_functions = len(self.functions)
        logger.info(f"===== DDS TRACE: Found {total_functions} functions to advertise. =====")

        # Publish initial node join event (both old and new monitoring)
        self._publish_monitoring_event(
            event_type="FUNCTION_STATUS",
            function_name=self.service_name,
            metadata={
                "service": self.__class__.__name__,
                "provider_id": self.app_guid,
                "message": f"Function app (id={self.app_guid}) joined domain",
                "event": "node_join"
            },
            status_data={"status": "joined", "state": "initializing"}
        )

        # First publish node discovery event
        self.publish_component_lifecycle_event(
            previous_state="DISCOVERING",
            new_state="DISCOVERING",
            reason=f"Function app {self.app_guid} discovered",
            capabilities=json.dumps(self.service_capabilities),
            event_category="NODE_DISCOVERY",
            source_id=self.app_guid,
            target_id=self.app_guid
        )

        # Then publish initialization event
        self.publish_component_lifecycle_event(
            previous_state="OFFLINE",
            new_state="JOINING",
            reason=f"Function app initialization started",
            capabilities=json.dumps(self.service_capabilities),
            event_category="AGENT_INIT",
            source_id=self.app_guid,
            target_id=self.app_guid
        )

        # Transition to discovering state
        self.publish_component_lifecycle_event(
            previous_state="JOINING",
            new_state="DISCOVERING",
            reason=f"Function app discovering functions",
            capabilities=json.dumps(self.service_capabilities),
            event_category="NODE_DISCOVERY",
            source_id=self.app_guid,
            target_id=self.app_guid
        )
        
        for i, (func_name, func_data) in enumerate(self.functions.items(), 1):
            logger.info(f"===== DDS TRACE: Preparing to advertise function {i}/{total_functions}: {func_name} =====")
            # Get schema from the function data
            schema = json.loads(func_data["tool"].function.parameters)
            
            # Get description
            description = func_data["tool"].function.description
            
            # Get capabilities
            capabilities = self.service_capabilities.copy()
            if func_data.get("operation_type"):
                capabilities.append(func_data["operation_type"])
            
            # Create capabilities dictionary with function name
            capabilities_dict = {
                "capabilities": capabilities,
                "function_name": func_name,  # Add function name
                "description": description
            }
            
            # Generate a random UUID for the function node
            function_id = str(uuid.uuid4())
            
            # Publish discovery event for each function
            self.publish_component_lifecycle_event(
                previous_state="DISCOVERING",
                new_state="DISCOVERING",
                reason=f"Function '{func_name}' available",
                capabilities=json.dumps(capabilities_dict),  # Use the dictionary
                component_id=function_id,
                event_category="NODE_DISCOVERY",
                source_id=function_id,
                target_id=function_id
            )

            # Publish edge discovery event between function app and function node
            edge_reason = f"provider={self.app_guid} client={function_id} function={function_id} name={func_name}"
            edge_capabilities = {
                "edge_type": "function_connection",
                "source_id": self.app_guid,
                "target_id": function_id,
                "function_name": func_name
            }
            
            # Publish edge discovery event using app_guid
            self.publish_component_lifecycle_event(
                previous_state="DISCOVERING",
                new_state="DISCOVERING",
                reason=edge_reason,
                capabilities=json.dumps(edge_capabilities),
                component_id=self.app_guid,
                event_category="EDGE_DISCOVERY",
                source_id=self.app_guid,
                target_id=function_id,
                connection_type="function_connection"
            )
            
            # Register with the function registry
            self.registry.register_function(
                func=func_data["implementation"],
                description=description,
                parameter_descriptions=schema,
                capabilities=capabilities,
                performance_metrics={"latency": "low"},
                security_requirements={"level": "public"}
            )
            
            logger.info(f"Advertised function: {func_name}")
            
            # If this is the first function, announce DDS connection
            if i == 1:
                logger.info(f"{self.__class__.__name__} connected to DDS")
            
            # If this is the last function, announce all functions published
            if i == total_functions:
                logger.info(f"All {self.__class__.__name__} functions published")
                # Publish final ready state
                self._publish_monitoring_event(
                    event_type="FUNCTION_STATUS",
                    function_name=self.service_name,
                    metadata={
                        "service": self.__class__.__name__,
                        "provider_id": self.app_guid,
                        "message": f"Function app (id={self.app_guid}) ready for calls",
                        "event": "node_ready"
                    },
                    status_data={"status": "ready", "state": "available"}
                )
                
                # Publish component lifecycle event for ready state
                self.publish_component_lifecycle_event(
                    previous_state="DISCOVERING",
                    new_state="READY",
                    reason=f"All {self.__class__.__name__} functions published and ready for calls",
                    capabilities=json.dumps(self.service_capabilities),
                    event_category="AGENT_READY",
                    source_id=self.app_guid,
                    target_id=self.app_guid
                )
        
        # Mark functions as advertised
        self._functions_advertised = True
        logger.info("===== DDS TRACE: Finished function advertisement process. =====")
    
    def publish_function_call_event(self, function_name: str, call_data: Dict[str, Any], request_info=None):
        """
        Publish a function call event.
        
        Args:
            function_name: Name of the function being called
            call_data: Data about the function call
            request_info: Request information containing client ID
        """
        self._publish_monitoring_event(
            event_type="FUNCTION_CALL",
            function_name=function_name,
            call_data=call_data,
            request_info=request_info
        )
    
    def publish_function_result_event(self, function_name: str, result_data: Dict[str, Any], request_info=None):
        """
        Publish a function result event.
        
        Args:
            function_name: Name of the function that produced the result
            result_data: Data about the function result
            request_info: Request information containing client ID
        """
        self._publish_monitoring_event(
            event_type="FUNCTION_RESULT",
            function_name=function_name,
            result_data=result_data,
            request_info=request_info
        )
    
    def publish_function_error_event(self, function_name: str, error: Exception, request_info=None):
        """
        Publish a function error event.
        
        Args:
            function_name: Name of the function that produced the error
            error: The exception that occurred
            request_info: Request information containing client ID
        """
        self._publish_monitoring_event(
            event_type="FUNCTION_STATUS",
            function_name=function_name,
            status_data={"error": str(error)},
            request_info=request_info
        )
    
    def function_wrapper(self, func_name: str):
        """
        Create a wrapper for a function that handles monitoring events.
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                # Extract request_info from kwargs
                request_info = kwargs.get('request_info')
                
                # Create call_data from args and kwargs
                call_data = {}
                # Add positional arguments (excluding self)
                if len(args) > 1:
                    func_params = func.__code__.co_varnames[1:func.__code__.co_argcount]
                    for i, param in enumerate(func_params):
                        if i < len(args) - 1:
                            call_data[param] = args[i + 1]
                
                # Add keyword arguments (excluding request_info)
                for k, v in kwargs.items():
                    if k != 'request_info':
                        call_data[k] = v
                
                try:
                    # Generate a unique chain ID for this call
                    chain_id = str(uuid.uuid4())
                    # Get the DDS RPC call ID from request_info
                    call_id = str(request_info.publication_handle) if request_info else str(uuid.uuid4())
                    
                    # Publish state change to BUSY with chain correlation
                    self.publish_component_lifecycle_event(
                        previous_state="READY",
                        new_state="BUSY",
                        reason=f"Processing function call: {func_name}({', '.join(f'{k}={v}' for k,v in call_data.items())})",
                        capabilities=json.dumps(self.service_capabilities),
                        chain_id=chain_id,
                        call_id=call_id
                    )
                    
                    # Create and publish chain event for function call start
                    chain_event = dds.DynamicData(self.chain_event_type)
                    chain_event["chain_id"] = chain_id
                    chain_event["call_id"] = call_id
                    chain_event["interface_id"] = str(request_info.publication_handle) if request_info else ""
                    chain_event["primary_agent_id"] = ""  # Set if using agents
                    chain_event["specialized_agent_ids"] = ""  # Set if using specialized agents
                    chain_event["function_id"] = func_name  # Use actual function name instead of app GUID
                    chain_event["query_id"] = str(uuid.uuid4())
                    chain_event["timestamp"] = int(time.time() * 1000)
                    chain_event["event_type"] = "CALL_START"
                    chain_event["source_id"] = str(request_info.publication_handle) if request_info else "unknown"
                    chain_event["target_id"] = self.app_guid
                    chain_event["status"] = 0  # 0 = Started
                    
                    self.chain_event_writer.write(chain_event)
                    self.chain_event_writer.flush()
                    
                    # Call the function
                    result = func(*args, **kwargs)
                    
                    # Create and publish chain event for function call completion
                    chain_event = dds.DynamicData(self.chain_event_type)
                    chain_event["chain_id"] = chain_id  # Same chain_id as start event
                    chain_event["call_id"] = call_id
                    chain_event["interface_id"] = str(request_info.publication_handle) if request_info else ""
                    chain_event["primary_agent_id"] = ""
                    chain_event["specialized_agent_ids"] = ""
                    chain_event["function_id"] = func_name  # Use actual function name instead of app GUID
                    chain_event["query_id"] = str(uuid.uuid4())
                    chain_event["timestamp"] = int(time.time() * 1000)
                    chain_event["event_type"] = "CALL_COMPLETE"
                    chain_event["source_id"] = self.app_guid
                    chain_event["target_id"] = str(request_info.publication_handle) if request_info else "unknown"
                    chain_event["status"] = 1  # 1 = Completed
                    
                    self.chain_event_writer.write(chain_event)
                    self.chain_event_writer.flush()
                    
                    # Publish state change back to READY with chain correlation
                    self.publish_component_lifecycle_event(
                        previous_state="BUSY",
                        new_state="READY",
                        reason=f"Completed function call: {func_name} = {result}",
                        capabilities=json.dumps(self.service_capabilities),
                        chain_id=chain_id,
                        call_id=call_id
                    )
                    
                    return result
                except Exception as e:
                    # Create and publish chain event for function call error
                    chain_event = dds.DynamicData(self.chain_event_type)
                    chain_event["chain_id"] = chain_id
                    chain_event["call_id"] = call_id
                    chain_event["interface_id"] = str(request_info.publication_handle) if request_info else ""
                    chain_event["primary_agent_id"] = ""
                    chain_event["specialized_agent_ids"] = ""
                    chain_event["function_id"] = func_name  # Use actual function name instead of app GUID
                    chain_event["query_id"] = str(uuid.uuid4())
                    chain_event["timestamp"] = int(time.time() * 1000)
                    chain_event["event_type"] = "CALL_ERROR"
                    chain_event["source_id"] = self.app_guid
                    chain_event["target_id"] = str(request_info.publication_handle) if request_info else "unknown"
                    chain_event["status"] = 2  # 2 = Error
                    
                    self.chain_event_writer.write(chain_event)
                    self.chain_event_writer.flush()
                    
                    # Publish state change to DEGRADED with chain correlation
                    self.publish_component_lifecycle_event(
                        previous_state="BUSY",
                        new_state="DEGRADED",
                        reason=f"Error in function {func_name}: {str(e)}",
                        capabilities=json.dumps(self.service_capabilities),
                        chain_id=chain_id,
                        call_id=call_id
                    )
                    raise
            
            return wrapper
        
        return decorator
    
    async def run(self):
        """
        Run the service and handle incoming requests.
        
        This method:
        1. Advertises functions if they haven't been advertised yet
        2. Calls the base class run method
        3. Ensures proper cleanup of resources
        """
        # Advertise functions if they haven't been advertised yet
        if not self._functions_advertised:
            self._advertise_functions()
            
        try:
            await super().run()
        finally:
            # Clean up registry
            if hasattr(self, 'registry'):
                self.registry.close()

    def handle_function_discovery(self, function_name: str, metadata: Dict[str, Any], status_data: Dict[str, Any]):
        """
        Handle function discovery events from the registry.
        
        Args:
            function_name: Name of the discovered function
            metadata: Metadata about the function and discovery event
            status_data: Status information about the function
        """
        function_id = metadata.get('function_id', str(uuid.uuid4()))

        # For function providers (like calculator service)
        if self.service_name.lower() in ["calculator", "calculatorservice", "textprocessor", "textprocessorservice"]:
            # Only handle our own functions
            if function_id in self.registry.functions:
                # First, publish the function availability event with the function's ID
                reason = f"Function '{function_name}' (id={function_id}) [Function '{function_name}' available]"

                # Publish new monitoring event for function availability using function_id
                self.publish_component_lifecycle_event(
                    previous_state="DISCOVERING",
                    new_state="DISCOVERING",
                    reason=reason,
                    capabilities=json.dumps(self.service_capabilities),
                    component_id=function_id,
                    event_category="NODE_DISCOVERY",
                    source_id=function_id,
                    target_id=function_id
                )
                
                # Then create an edge between the function and its hosting app
                edge_reason = f"provider={self.app_guid} client={function_id} function={function_id} name={function_name}"
                
                # Publish edge discovery event using app_guid
                self.publish_component_lifecycle_event(
                    previous_state="DISCOVERING",
                    new_state="DISCOVERING",
                    reason=edge_reason,
                    capabilities=json.dumps(self.service_capabilities),
                    component_id=self.app_guid,
                    event_category="EDGE_DISCOVERY",
                    source_id=self.app_guid,
                    target_id=function_id,
                    connection_type="function_connection"
                )
            return

        # For agents and other services that discover external functions
        if function_id not in self.registry.functions:  # Only handle functions we don't own
            self.last_discovered_function = function_name
            # Format the reason string for external edge discovery
            reason = f"provider={metadata['provider_id']} client={metadata['client_id']} function={function_id} name={function_name}"
            
            # Publish edge discovery event
            self.publish_component_lifecycle_event(
                previous_state="DISCOVERING",
                new_state="DISCOVERING",
                reason=reason,
                capabilities=json.dumps(self.service_capabilities),
                component_id=metadata['client_id'],  # Use client_id for the edge event
                event_category="EDGE_DISCOVERY",
                source_id=self.app_guid,
                target_id=metadata['client_id'],
                connection_type="function_connection"
            )

    def handle_function_removal(self, function_name: str, metadata: Dict[str, Any]):
        """
        Handle function removal events from the registry.
        
        Args:
            function_name: Name of the removed function
            metadata: Metadata about the function and removal event
        """
        self._publish_monitoring_event(
            event_type="FUNCTION_STATUS",
            function_name=function_name,
            metadata=metadata,
            status_data={"status": "removed", "state": "unavailable"}
        )

    def close(self):
        """Clean up all service resources"""
        logger.info(f"Closing {self.service_name}...")
        
        # Close registry if it exists
        if hasattr(self, 'registry'):
            self.registry.close()
            
        # Close base class resources
        super().close()
            
        logger.info(f"{self.service_name} closed successfully")

# Example of how to use the enhanced service base
if __name__ == "__main__":
    # This is just an example and won't be executed when imported
    class ExampleService(EnhancedServiceBase):
        def __init__(self):
            super().__init__(service_name="ExampleService", capabilities=["example", "demo"])
            
            # Register functions
            self.register_enhanced_function(
                self.example_function,
                "Example function",
                {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text input"}
                    },
                    "required": ["text"]
                },
                operation_type="example"
            )
            
            # Advertise functions
            self._advertise_functions()
        
        def example_function(self, text: str, request_info=None) -> Dict[str, Any]:
            # Function implementation
            return {"result": text.upper()}
    
    # Run the example service
    service = ExampleService()
    asyncio.run(service.run()) 
```

## genesis_lib/decorators.py

**Author:** Jason

```python
from __future__ import annotations

#!/usr/bin/env python3

"""
Genesis Function Decorator System

This module provides a powerful decorator system for automatically generating and managing
function schemas within the Genesis framework. It enables seamless integration between
Python functions and large language models by automatically inferring and validating
function signatures, parameters, and documentation.

Key features:
- Automatic schema generation from Python type hints and docstrings
- Support for complex type annotations (Unions, Lists, Dicts)
- Parameter validation and coercion using Pydantic models
- OpenAI-compatible function schema generation
- Intelligent parameter description extraction from docstrings

The @genesis_function decorator allows developers to expose their functions to LLMs
without manually writing JSON schemas, making the Genesis network more accessible
and maintainable.

Example:
    @genesis_function
    def calculate_sum(a: int, b: int) -> int:
        \"\"\"Add two numbers together.
        
        Args:
            a: First number to add
            b: Second number to add
        \"\"\"
        return a + b

Copyright (c) 2025, RTI & Jason Upchurch
"""

import json, inspect, typing, re
from typing import Any, Callable, Dict, Optional, Type, Union, get_origin, get_args

__all__ = ["genesis_function", "infer_schema_from_annotations", "validate_args"]

# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _extract_param_descriptions(docstring: Optional[str]) -> Dict[str, str]:
    """Extract parameter descriptions from docstring Args section."""
    if not docstring:
        return {}
    
    # Find the Args section
    args_match = re.search(r'Args:\s*\n(.*?)(?=\n\s*\n|\Z)', docstring, re.DOTALL)
    if not args_match:
        return {}
    
    args_section = args_match.group(1)
    descriptions = {}
    
    # Parse each parameter line
    for line in args_section.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # Match parameter name and description
        param_match = re.match(r'(\w+):\s*(.*)', line)
        if param_match:
            param_name, description = param_match.groups()
            descriptions[param_name] = description.strip()
    
    return descriptions

def _python_type_to_json(t) -> Union[str, Dict[str, Any]]:
    """Convert Python type to JSON schema type with support for complex types."""
    # Handle Union types (including Optional)
    if get_origin(t) is Union:
        types = [arg for arg in get_args(t) if arg is not type(None)]
        if len(types) == 1:
            return _python_type_to_json(types[0])
        return {"oneOf": [_python_type_to_json(arg) for arg in types]}
    
    # Handle List/Sequence types
    if get_origin(t) in (list, typing.List, typing.Sequence):
        item_type = get_args(t)[0]
        return {"type": "array", "items": _python_type_to_json(item_type)}
    
    # Handle Dict types
    if get_origin(t) in (dict, typing.Dict):
        key_type, value_type = get_args(t)
        if key_type is str:  # Only support string keys for now
            return {
                "type": "object",
                "additionalProperties": _python_type_to_json(value_type)
            }
        return "object"  # Fallback for non-string keys
    
    # Basic types
    type_map = {
        int: "integer",
        float: "number",
        str: "string",
        bool: "boolean",
        type(None): "null",
        Dict: "object",
        dict: "object",
        Any: "object"
    }
    
    return type_map.get(t, "string")

def infer_schema_from_annotations(fn: Callable) -> Dict[str, Any]:
    """Draft‑07 JSON‑Schema synthesised from type annotations and docstring."""
    sig = inspect.signature(fn)
    hints = typing.get_type_hints(fn)
    descriptions = _extract_param_descriptions(fn.__doc__)

    props = {}
    required = []
    
    for name, param in sig.parameters.items():
        if name in ("self", "request_info"):
            continue
            
        typ = hints.get(name, Any)
        type_info = _python_type_to_json(typ)
        
        # Create schema with type and description
        if isinstance(type_info, str):
            schema = {
                "type": type_info,
                "description": descriptions.get(name, "")
            }
        else:
            schema = {
                **type_info,  # This includes type and any additional info
                "description": descriptions.get(name, "")
            }
        
        # Add example if available in docstring
        if name in descriptions and "example" in descriptions[name].lower():
            example_match = re.search(r'example:\s*([^\n]+)', descriptions[name], re.IGNORECASE)
            if example_match:
                try:
                    schema["example"] = eval(example_match.group(1))
                except:
                    pass
        
        props[name] = schema
        if param.default is inspect._empty:
            required.append(name)

    # Create the full schema in the format expected by the function registry
    schema = {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False  # Prevent additional properties
    }
    
    # Convert to JSON string and back to ensure it's serializable
    return json.loads(json.dumps(schema))

def validate_args(fn: Callable, kwargs: Dict[str, Any]) -> None:
    """If a Pydantic model was supplied, validate/coerce kwargs in‑place."""
    model = getattr(fn, "__genesis_meta__", {}).get("pydantic_model")
    if model:
        obj = model(**{k: v for k, v in kwargs.items() if k != "request_info"})
        kwargs.update(obj.model_dump())

# --------------------------------------------------------------------------- #
# Decorator                                                                   #
# --------------------------------------------------------------------------- #
def genesis_function(
    *,
    description: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    model: Optional[Type] = None,
    operation_type: Optional[str] = None,
    common_patterns: Optional[Dict[str, Any]] = None,
):
    """
    Attach JSON‑schema & metadata to a function so EnhancedServiceBase can
    auto‑register it.
    
    The schema can be provided in three ways:
    1. Explicitly via the parameters argument
    2. Via a Pydantic model using the model argument
    3. Implicitly inferred from type hints and docstring (default)
    """
    def decorator(fn: Callable):
        # Build / derive schema
        if model is not None:
            schema = json.loads(model.schema_json())
        elif parameters is not None:
            schema = parameters
        else:
            schema = infer_schema_from_annotations(fn)

        # Ensure schema is serialized as JSON string
        schema_str = json.dumps(schema)

        fn.__genesis_meta__ = {
            "description": description or (fn.__doc__ or ""),
            "parameters": schema_str,  # Store as JSON string
            "operation_type": operation_type,
            "common_patterns": common_patterns,
            "pydantic_model": model,
        }
        return fn
    return decorator

```

## genesis_lib/config/datamodel.xml

**Author:** Jason

```xml
<?xml version="1.0" encoding="UTF-8"?>
<dds xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:noNamespaceSchemaLocation="http://community.rti.com/schema/7.3.0/rti_dds_qos_profiles.xsd"
     version="7.3.0">
  <type_library name="genesis_lib">

    <!-- agent registration  -->
    <struct name= "genesis_agent_registration_announce">
      <member name="message" type="string" stringMaxLength="2048" />
      <member name="prefered_name" type="string" stringMaxLength="256" />
      <member name="default_capable" type="int32"/>
      <member name="instance_id" type="string" key="true" stringMaxLength="128"/>
      <member name="service_name" type="string" stringMaxLength="256"/>
    </struct>

    <!-- Below are the two NLP communication types, interface to agent and agent to agent.  Right now they're at 8K, But it should probably be either Unbounded or... Better yet, Add Streaming like we had in version 0.1.-->
    <!-- interface to agent communication -->
    <struct name="InterfaceAgentRequest">
      <member name="message" type="string" stringMaxLength="8192"/>
      <member name="conversation_id" type="string" stringMaxLength="128"/>
    </struct>

    <struct name="InterfaceAgentReply">
      <member name="message" type="string" stringMaxLength="8192"/>
      <member name="status" type="int32"/>
      <member name="conversation_id" type="string" stringMaxLength="128"/>
    </struct>

        <!-- Agent to agent communication -->
    <struct name="AgentAgentRequest">
      <member name="message" type="string" stringMaxLength="8192"/>
      <member name="conversation_id" type="string" stringMaxLength="128"/>
    </struct>

    <struct name="AgentAgentReply">
      <member name="message" type="string" stringMaxLength="8192"/>
      <member name="status" type="int32"/>
      <member name="conversation_id" type="string" stringMaxLength="128"/>
    </struct>

    <!-- Monitoring and Logging interface -->
    <struct name="LogMessage">
      <member name="log_id" type="string" stringMaxLength="128"/>
      <member name="timestamp" type="int64"/>
      <member name="source_id" type="string" stringMaxLength="128"/>
      <member name="source_name" type="string" stringMaxLength="256"/>
      <member name="level" type="int32"/>
      <member name="level_name" type="string" stringMaxLength="32"/>
      <member name="message" type="string" stringMaxLength="8192"/>
      <member name="logger_name" type="string" stringMaxLength="256"/>
      <member name="thread_id" type="string" stringMaxLength="128"/>
      <member name="thread_name" type="string" stringMaxLength="256"/>
      <member name="file_name" type="string" stringMaxLength="256"/>
      <member name="line_number" type="int32"/>
      <member name="function_name" type="string" stringMaxLength="256"/>
    </struct>

    <!-- Function Discovery and Advertisement -->
    <struct name="FunctionCapability">
      <member name="function_id" type="string" key="true" stringMaxLength="128"/>
      <member name="name" type="string" stringMaxLength="256"/>
      <member name="description" type="string" stringMaxLength="2048"/>
      <member name="provider_id" type="string" stringMaxLength="128"/>
      <member name="parameter_schema" type="string" stringMaxLength="8192"/>
      <member name="capabilities" type="string" stringMaxLength="2048"/>
      <member name="performance_metrics" type="string" stringMaxLength="2048"/>
      <member name="security_requirements" type="string" stringMaxLength="2048"/>
      <member name="classification" type="string" stringMaxLength="2048"/>
      <member name="last_seen" type="int64"/>
      <member name="service_name" type="string" stringMaxLength="256"/>
    </struct>

    <!-- Agent Discovery and Advertisement -->
    <struct name="AgentCapability">
      <member name="agent_id" type="string" key="true" stringMaxLength="128"/>
      <member name="name" type="string" stringMaxLength="256"/>
      <member name="description" type="string" stringMaxLength="2048"/>
      <member name="agent_type" type="string" stringMaxLength="128"/>
      <member name="service_name" type="string" stringMaxLength="128"/>
      <member name="last_seen" type="int64"/>
    </struct>

    <!-- Function Execution Request/Reply -->
    <struct name="FunctionExecutionRequest">
      <member name="request_id" type="string" stringMaxLength="128"/>
      <member name="function_id" type="string" stringMaxLength="128"/>
      <member name="parameters" type="string" stringMaxLength="8192"/>
      <member name="timestamp" type="int64"/>
      <member name="metadata" type="string" stringMaxLength="2048"/>
    </struct>

    <struct name="FunctionExecutionReply">
      <member name="request_id" type="string" stringMaxLength="128"/>
      <member name="function_id" type="string" stringMaxLength="128"/>
      <member name="result" type="string" stringMaxLength="8192"/>
      <member name="status" type="int32"/>
      <member name="error_message" type="string" stringMaxLength="2048"/>
      <member name="timestamp" type="int64"/>
      <member name="metadata" type="string" stringMaxLength="2048"/>
    </struct>

    <!-- Test service interface -->
    <struct name="TestRequest">
      <member name="message" type="string" stringMaxLength="8192"/>
    </struct>

    <struct name="TestReply">
      <member name="message" type="string" stringMaxLength="8192"/>
      <member name="status" type="int32"/>
    </struct>

    <!-- LLM Function Schema -->
    <struct name="LLMFunctionSchema">
      <member name="function_id" type="string" key="true" stringMaxLength="128"/>
      <member name="name" type="string" stringMaxLength="256"/>
      <member name="description" type="string" stringMaxLength="2048"/>
      <member name="parameters_schema" type="string" stringMaxLength="8192"/>
      <member name="returns_schema" type="string" stringMaxLength="2048"/>
      <member name="provider_id" type="string" stringMaxLength="128"/>
      <member name="version" type="string" stringMaxLength="64"/>
      <member name="tags" type="string" stringMaxLength="1024"/>
    </struct>

    <!-- Function Monitoring Events -->
    <enum name="EventType">
      <enumerator name="FUNCTION_DISCOVERY"/>
      <enumerator name="FUNCTION_CALL"/>
      <enumerator name="FUNCTION_RESULT"/>
      <enumerator name="FUNCTION_STATUS"/>
      <enumerator name="FUNCTION_DISCOVERY_V2"/>
    </enum>

    <enum name="EntityType">
      <enumerator name="FUNCTION"/>
      <enumerator name="AGENT"/>
      <enumerator name="SPECIALIZED_AGENT"/>
      <enumerator name="INTERFACE"/>
    </enum>

    <struct name="MonitoringEvent">
      <member name="event_id" type="string" key="true" stringMaxLength="128"/>
      <member name="timestamp" type="int64"/>
      <member name="event_type" type="nonBasic" nonBasicTypeName="EventType"/>
      <member name="entity_type" type="nonBasic" nonBasicTypeName="EntityType"/>
      <member name="entity_id" type="string" stringMaxLength="128"/>
      <member name="metadata" type="string" stringMaxLength="2048"/>
      <member name="call_data" type="string" stringMaxLength="8192"/>
      <member name="result_data" type="string" stringMaxLength="8192"/>
      <member name="status_data" type="string" stringMaxLength="2048"/>
    </struct>

    <!-- New Enhanced Monitoring Types -->
    <enum name="ComponentType">
      <enumerator name="INTERFACE"/>
      <enumerator name="PRIMARY_AGENT"/>
      <enumerator name="SPECIALIZED_AGENT"/>
      <enumerator name="FUNCTION"/>
    </enum>

    <enum name="ComponentState">
      <enumerator name="JOINING"/>
      <enumerator name="DISCOVERING"/>
      <enumerator name="READY"/>
      <enumerator name="BUSY"/>
      <enumerator name="DEGRADED"/>
      <enumerator name="OFFLINE"/>
    </enum>

    <enum name="EventCategory">
      <enumerator name="NODE_DISCOVERY"/>      <!-- Node/Agent/Component discovery -->
      <enumerator name="EDGE_DISCOVERY"/>      <!-- Connection/Relationship discovery -->
      <enumerator name="STATE_CHANGE"/>        <!-- Component state transitions -->
      <enumerator name="AGENT_INIT"/>          <!-- Agent initialization -->
      <enumerator name="AGENT_READY"/>         <!-- Agent ready state -->
      <enumerator name="AGENT_SHUTDOWN"/>      <!-- Agent shutdown -->
      <enumerator name="DDS_ENDPOINT"/>        <!-- DDS endpoint discovery -->
    </enum>

    <struct name="ComponentLifecycleEvent">
      <member name="component_id" type="string" key="true" stringMaxLength="128"/>
      <member name="component_type" type="nonBasic" nonBasicTypeName="ComponentType"/>
      <member name="previous_state" type="nonBasic" nonBasicTypeName="ComponentState"/>
      <member name="new_state" type="nonBasic" nonBasicTypeName="ComponentState"/>
      <member name="timestamp" type="int64"/>
      <member name="reason" type="string" stringMaxLength="1024"/>
      <member name="capabilities" type="string" stringMaxLength="2048"/>
      <member name="chain_id" type="string" stringMaxLength="128"/>
      <member name="call_id" type="string" stringMaxLength="128"/>
      <member name="event_category" type="nonBasic" nonBasicTypeName="EventCategory"/>
      <member name="source_id" type="string" stringMaxLength="128"/>
      <member name="target_id" type="string" stringMaxLength="128"/>
      <member name="connection_type" type="string" stringMaxLength="128"/>
    </struct>

    <struct name="ChainEvent">
      <member name="chain_id" type="string" key="true" stringMaxLength="128"/>
      <member name="call_id" type="string" stringMaxLength="128"/>
      <member name="interface_id" type="string" stringMaxLength="128"/>
      <member name="primary_agent_id" type="string" stringMaxLength="128"/>
      <member name="specialized_agent_ids" type="string" stringMaxLength="2048"/>
      <member name="function_id" type="string" stringMaxLength="128"/>
      <member name="query_id" type="string" stringMaxLength="128"/>
      <member name="timestamp" type="int64"/>
      <member name="event_type" type="string" stringMaxLength="128"/>
      <member name="source_id" type="string" stringMaxLength="128"/>
      <member name="target_id" type="string" stringMaxLength="128"/>
      <member name="status" type="int32"/>
    </struct>

    <struct name="LivelinessUpdate">
      <member name="component_id" type="string" key="true" stringMaxLength="128"/>
      <member name="component_type" type="nonBasic" nonBasicTypeName="ComponentType"/>
      <member name="state" type="nonBasic" nonBasicTypeName="ComponentState"/>
      <member name="last_active" type="int64"/>
      <member name="health_metrics" type="string" stringMaxLength="1024"/>
    </struct>

  </type_library>

</dds>
```

## genesis_lib/config/USER_QOS_PROFILES.xml

**Author:** Jason

```xml
<?xml version="1.0"?>

<!--
 (c) 2005-2015 Copyright, Real-Time Innovations, Inc.  All rights reserved.
 RTI grants Licensee a license to use, modify, compile, and create derivative
 works of the Software.  Licensee has the right to distribute object form only
 for use with RTI products.  The Software is provided "as is", with no warranty
 of any type, including any warranty for fitness for any purpose. RTI is under
 no obligation to maintain or support the Software.  RTI shall not be liable for
 any incidental or consequential damages arising out of the use or inability to
 use the software.
 -->
<dds xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:noNamespaceSchemaLocation="http://community.rti.com/schema/6.0.0/rti_dds_qos_profiles.xsd"
     version="6.0.0">
    <!-- QoS Library containing the QoS profile used in the generated example.

        A QoS library is a named set of QoS profiles.
    -->
    <qos_library name="cft_Library">

        <!-- QoS profile used to configure reliable communication between the DataWriter
             and DataReader created in the example code.

             A QoS profile groups a set of related QoS.
        -->
        <qos_profile name="cft_Profile" is_default_qos="true">
            <!-- QoS used to configure the data writer created in the example code -->
            <datawriter_qos>
                <reliability>
                    <kind>RELIABLE_RELIABILITY_QOS</kind>
                </reliability>
                <!-- Enabled transient local durability to provide history to
                     late-joiners. -->
                <durability>
                    <kind>TRANSIENT_LOCAL_DURABILITY_QOS</kind>
                </durability>
                <!-- The last twenty samples are saved for late joiners -->
                <history>
                    <kind>KEEP_LAST_HISTORY_QOS</kind>
                    <depth>500</depth>
                </history>
                <!-- Set the publishing mode to asynchronous -->
                <publish_mode>
                    <kind>ASYNCHRONOUS_PUBLISH_MODE_QOS</kind>
                </publish_mode>
            </datawriter_qos>

            <!-- QoS used to configure the data reader created in the example code -->
            <datareader_qos>
                <reliability>
                    <kind>RELIABLE_RELIABILITY_QOS</kind>
                </reliability>
                <!-- Enabled transient local durability to get history when
                     late-joining the DDS domain. -->
                <durability>
                    <kind>TRANSIENT_LOCAL_DURABILITY_QOS</kind>
                </durability>
                <!-- The last twenty samples are saved for late joiners -->
                <history>
                    <kind>KEEP_LAST_HISTORY_QOS</kind>
                    <depth>500</depth>
                </history>
            </datareader_qos>

            <participant_qos>
                <!-- Use UDPv4 transport only to avoid shared memory issues on macOS -->
                <transport_builtin>
                    <mask>UDPv4</mask>
                </transport_builtin>
                <participant_name>
                    <name>RTI Content Filtered Topic STRINGMATCH</name>
                </participant_name>
            </participant_qos>
        </qos_profile>

    </qos_library>
</dds>
```

## genesis_lib/utils/openai_utils.py

**Author:** Jason

```python
"""
Utility functions for working with OpenAI APIs in the Genesis framework
"""

import logging
import json
import traceback
from typing import List, Dict, Any, Tuple, Optional, Callable

logger = logging.getLogger(__name__)

def convert_functions_to_openai_schema(functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert discovered Genesis functions to OpenAI function schemas format.
    
    Args:
        functions: List of function metadata from Genesis function discovery
        
    Returns:
        List of function schemas in OpenAI's expected format
    """
    logger.info("===== TRACING: Converting function schemas for OpenAI =====")
    function_schemas = []
    
    for func in functions:
        function_schemas.append({
            "type": "function",
            "function": {
                "name": func["name"],
                "description": func["description"],
                "parameters": func["schema"]
            }
        })
        logger.info(f"===== TRACING: Added schema for function: {func['name']} =====")
    
    logger.info(f"===== TRACING: Total function schemas for OpenAI: {len(function_schemas)} =====")
    return function_schemas

def generate_response_with_functions(
    client: Any,
    message: str,
    model_name: str,
    system_prompt: str,
    relevant_functions: List[Dict],
    call_function_handler: Callable,
    conversation_history: Optional[List[Dict]] = None,
    conversation_id: Optional[str] = None
) -> Tuple[str, int, bool, Optional[List[Dict]]]:
    """
    Generate a response using OpenAI API with function calling capabilities.
    
    Args:
        client: OpenAI client instance
        message: The user's message
        model_name: The model to use (e.g., "gpt-3.5-turbo")
        system_prompt: The system prompt to use
        relevant_functions: List of relevant function metadata
        call_function_handler: Function to call when the model requests a function call
        conversation_history: Optional conversation history (list of message objects)
        conversation_id: Optional conversation ID for tracking
        
    Returns:
        Tuple of (response, status, used_functions, updated_conversation_history)
    """
    logger.info(f"===== TRACING: Processing request with functions: {message} =====")
    
    try:
        # Get function schemas for OpenAI from relevant functions
        function_schemas = convert_functions_to_openai_schema(relevant_functions)
        
        # Initialize messages with system prompt and user message
        messages = []
        
        # Add system message
        messages.append({"role": "system", "content": system_prompt})
        
        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history)
        
        # Add current user message
        messages.append({"role": "user", "content": message})
        
        # If no function schemas available, process without functions
        if not function_schemas:
            logger.warning("===== TRACING: No function schemas available, processing without functions =====")
            response = client.chat.completions.create(
                model=model_name,
                messages=messages
            )
            
            # Update conversation history
            if conversation_history is not None:
                conversation_history.append({"role": "user", "content": message})
                conversation_history.append({"role": "assistant", "content": response.choices[0].message.content})
            
            return response.choices[0].message.content, 0, False, conversation_history
        
        # Call OpenAI API with function calling
        logger.info("===== TRACING: Calling OpenAI API with function schemas =====")
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=function_schemas,
            tool_choice="auto"
        )
        
        # Extract the response
        message_obj = response.choices[0].message
        
        # Update conversation history with user message
        if conversation_history is not None:
            conversation_history.append({"role": "user", "content": message})
        
        # Check if the model wants to call a function
        if message_obj.tool_calls:
            logger.info(f"===== TRACING: Model requested function call(s): {len(message_obj.tool_calls)} =====")
            
            # Update conversation history with assistant's function call
            if conversation_history is not None:
                conversation_history.append(message_obj.model_dump())
            
            # Process each function call
            function_responses = []
            for tool_call in message_obj.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                logger.info(f"===== TRACING: Processing function call: {function_name} =====")
                
                # Call the function using the provided handler
                try:
                    function_result = call_function_handler(function_name, **function_args)
                    function_response = {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": str(function_result)
                    }
                    function_responses.append(function_response)
                    logger.info(f"===== TRACING: Function {function_name} returned: {function_result} =====")
                    
                    # Update conversation history with function response
                    if conversation_history is not None:
                        conversation_history.append(function_response)
                except Exception as e:
                    logger.error(f"===== TRACING: Error calling function {function_name}: {str(e)} =====")
                    error_message = f"Error: {str(e)}"
                    function_response = {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": error_message
                    }
                    function_responses.append(function_response)
                    
                    # Update conversation history with error response
                    if conversation_history is not None:
                        conversation_history.append(function_response)
            
            # If we have function responses, send them back to the model
            if function_responses:
                # Create a new conversation with the function responses
                logger.info("===== TRACING: Sending function responses back to OpenAI =====")
                second_response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        *([m for m in conversation_history if m["role"] != "system"] if conversation_history else []),
                        {"role": "user", "content": message},
                        message_obj,  # The assistant's message requesting the function call
                        *function_responses  # The function responses
                    ]
                )
                
                # Extract the final response
                final_message = second_response.choices[0].message.content
                logger.info(f"===== TRACING: Final response: {final_message} =====")
                
                # Update conversation history with final assistant response
                if conversation_history is not None:
                    conversation_history.append({"role": "assistant", "content": final_message})
                
                return final_message, 0, True, conversation_history
        
        # If no function call, just return the response
        text_response = message_obj.content
        logger.info(f"===== TRACING: Response (no function call): {text_response} =====")
        
        # Update conversation history with assistant response
        if conversation_history is not None:
            conversation_history.append({"role": "assistant", "content": text_response})
        
        return text_response, 0, False, conversation_history
            
    except Exception as e:
        logger.error(f"===== TRACING: Error processing request: {str(e)} =====")
        logger.error(traceback.format_exc())
        return f"Error: {str(e)}", 1, False, conversation_history 
```

## genesis_lib/utils/function_utils.py

**Author:** Jason

```python
#!/usr/bin/env python3

import asyncio
import json
import logging
import queue
import threading
import time
import traceback
from typing import Any, Dict, Optional, Tuple, Union, List

logger = logging.getLogger(__name__)

def call_function_thread_safe(
    function_client: Any,
    function_name: str,
    function_id: str,
    service_name: str,
    timeout: float = 10.0,
    **kwargs
) -> Any:
    """
    Call a function by name with the given arguments using a separate thread
    to avoid DDS exclusive area problems.
    
    Args:
        function_client: The client to use for calling functions
        function_name: Name of the function to call (for logging)
        function_id: ID of the function to call
        service_name: Name of the service providing the function (for logging)
        timeout: Maximum time to wait for function execution (seconds)
        **kwargs: Arguments to pass to the function
        
    Returns:
        Function result
        
    Raises:
        ValueError: If function is not found
        RuntimeError: If function execution fails or times out
    """
    logger.info(f"===== TRACING: Executing function call to {function_name} ({function_id}) on service {service_name} =====")
    
    # Create a queue for thread communication
    result_queue = queue.Queue()
    
    # Define the function to run in a separate thread
    def call_function_thread():
        try:
            # Create event loop for async calls
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Call the function using the client
                start_time = time.time()
                result = loop.run_until_complete(function_client.call_function(function_id, **kwargs))
                end_time = time.time()
                logger.info(f"===== TRACING: Function call completed in {end_time - start_time:.2f} seconds =====")
                
                # Extract the result value
                if isinstance(result, dict) and "result" in result:
                    logger.info(f"===== TRACING: Function result: {result['result']} =====")
                    result_queue.put(("success", result["result"]))
                else:
                    logger.info(f"===== TRACING: Function raw result: {result} =====")
                    result_queue.put(("success", result))
            except Exception as e:
                logger.error(f"===== TRACING: Error calling function {function_name}: {str(e)} =====")
                logger.error(traceback.format_exc())
                result_queue.put(("error", str(e)))
            finally:
                # Clean up
                loop.close()
        except Exception as e:
            logger.error(f"===== TRACING: Thread error: {str(e)} =====")
            result_queue.put(("error", str(e)))
    
    # Start the thread
    thread = threading.Thread(target=call_function_thread)
    thread.daemon = True
    thread.start()
    
    # Wait for the thread to complete with timeout
    thread.join(timeout=timeout)
    
    # Check if we have a result
    try:
        status, result = result_queue.get(block=False)
        if status == "success":
            return result
        else:
            raise RuntimeError(f"Function execution failed: {result}")
    except queue.Empty:
        logger.error("===== TRACING: Function call timed out =====")
        raise RuntimeError(f"Function call to {function_name} timed out after {timeout} seconds")

def find_function_by_name(available_functions: list, function_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Find a function by name in the list of available functions.
    
    Args:
        available_functions: List of available functions
        function_name: Name of the function to find
        
    Returns:
        Tuple of (function_id, service_name) if found, (None, None) otherwise
    """
    for func in available_functions:
        if func.get("name") == function_name:
            return func.get("function_id"), func.get("service_name")
    return None, None

def filter_functions_by_relevance(
    message: str, 
    available_functions: list, 
    function_classifier: Any,
    model_name: str = None
) -> List[Dict]:
    """
    Filter functions based on their relevance to the user's message.
    
    Args:
        message: The user's message
        available_functions: List of available functions
        function_classifier: The function classifier to use
        model_name: Optional model name to use for classification
        
    Returns:
        List of relevant function metadata dictionaries
    """
    logger.info(f"===== TRACING: Filtering functions by relevance for message: {message} =====")
    
    # If no functions are available, return an empty list
    if not available_functions:
        logger.warning("===== TRACING: No functions available to filter =====")
        return []
    
    # Use the function classifier to filter functions
    try:
        # Pass model_name if provided
        if model_name:
            relevant_functions = function_classifier.classify_functions(
                message, 
                available_functions,
                model_name=model_name
            )
        else:
            relevant_functions = function_classifier.classify_functions(
                message, 
                available_functions
            )
            
        logger.info(f"===== TRACING: Found {len(relevant_functions)} relevant functions =====")
        for func in relevant_functions:
            logger.info(f"===== TRACING: Relevant function: {func.get('name')} =====")
        return relevant_functions
    except Exception as e:
        logger.error(f"===== TRACING: Error filtering functions: {str(e)} =====")
        logger.error(traceback.format_exc())
        # In case of error, return all functions
        return available_functions 
```
