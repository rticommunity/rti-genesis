# Copyright (c) 2025, RTI & Jason Upchurch
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
    entry_points={
        'console_scripts': [
            'genesis-monitor=genesis_lib.genesis_monitoring:main',
            'genesis-graph-viewer=genesis_lib.web.graph_viewer:run_viewer',
        ],
    },
)
