#!/usr/bin/env python3
# Copyright (c) 2025, RTI & Jason Upchurch
import asyncio
import logging
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from genesis_lib.monitored_interface import MonitoredInterface  # noqa: E402


async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    iface = MonitoredInterface(interface_name="DurabilityTestInterface", service_name="TestInterface")
    # Keep the interface alive without requiring any agent to exist
    await asyncio.sleep(25)
    await iface.close()


if __name__ == '__main__':
    asyncio.run(main())


