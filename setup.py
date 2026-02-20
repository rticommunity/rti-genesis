#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
#                                                                                    #
# RTI grants Licensee a license to use, modify, compile, and create derivative       #
# works of the Software. Licensee has the right to distribute object form only       #
# for use with RTI products. The Software is provided "as is", with no warranty      #
# of any type, including any warranty for fitness for any purpose. RTI is under no   #
# obligation to maintain or support the Software. RTI shall not be liable for any    #
# incidental or consequential damages arising out of the use or inability to use     #
# the software.                                                                      #
# ####################################################################################

from setuptools import setup, find_packages

setup(
    name="genesis-lib",
    version="0.3.0",
    packages=find_packages(),
    package_data={
        'genesis_lib': [
            'config/*',
            'web/static/*.js',
        ],
    },
    include_package_data=True,
    python_requires=">=3.10,<3.11",
    install_requires=[
        "flask>=3.1.0",
        "flask-socketio>=5.5.0",
        "tabulate>=0.9.0",
        "anthropic>=0.68.0",
        "openai>=1.100.0",
        "jsonschema>=4.25.0",
        "rti-connext>=7.5.0",
        "mcp>=1.21.0",
        "pydantic>=2.11.0",
        "pydantic-settings>=2.12.0",
        "uvicorn>=0.38.0",
        "starlette>=0.50.0",
        "httpx>=0.27.0",
    ],
    extras_require={
        "database": ["sqlalchemy>=2.0"],
    },
    entry_points={
        'console_scripts': [
            'genesis-monitor=genesis_lib.genesis_monitoring:main',
            'genesis-graph-viewer=genesis_lib.web.graph_viewer:run_viewer',
        ],
    },
)
