#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from genesis_lib.monitored_interface import MonitoredInterface

async def quick_test():
    interface = MonitoredInterface('Test', 'OpenAIAgent')
    await asyncio.sleep(5)
    print(f'Found {len(interface.available_agents)} agents:')
    for agent_id, info in interface.available_agents.items():
        print(f'  - {info.get("prefered_name", "Unknown")} ({info.get("service_name", "Unknown")})')
    await interface.close()

asyncio.run(quick_test()) 