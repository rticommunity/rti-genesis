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
        "flask",
        "flask-socketio",
        "tabulate",
        "anthropic",
        "openai",
        "jsonschema",
        "rti-connext",
    ],
    entry_points={
        'console_scripts': [
            'genesis-monitor=genesis_lib.genesis_monitoring:main',
            'genesis-graph-viewer=genesis_lib.web.graph_viewer:run_viewer',
        ],
    },
)
