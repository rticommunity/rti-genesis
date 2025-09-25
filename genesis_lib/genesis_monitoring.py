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
            "rti/connext/genesis/monitoring/MonitoringEvent",
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