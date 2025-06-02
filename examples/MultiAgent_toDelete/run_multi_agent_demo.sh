#!/bin/bash
"""
Multi-Agent Smart Assistant Ecosystem Launch Script

This script provides easy access to all components of the Genesis Multi-Agent
system, including testing, agent startup, and CLI interface.

Copyright (c) 2025, RTI & Jason Upchurch
"""

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Header
print_header() {
    echo -e "${CYAN}======================================================================${NC}"
    echo -e "${WHITE}🤖 Genesis Multi-Agent Smart Assistant Ecosystem${NC}"
    echo -e "${CYAN}======================================================================${NC}"
    echo -e "${WHITE}A production-ready multi-agent system demonstrating capability-based${NC}"
    echo -e "${WHITE}agent discovery, agent-as-tool patterns, and intelligent coordination.${NC}"
    echo -e "${CYAN}======================================================================${NC}"
}

# Check dependencies
check_dependencies() {
    echo -e "${BLUE}🔍 Checking dependencies...${NC}"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 is required but not installed${NC}"
        exit 1
    fi
    
    # Check Genesis library (try importing)
    if ! python3 -c "import sys; sys.path.insert(0, '../../..'); import genesis_lib" 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Genesis library not found in expected location${NC}"
        echo -e "${YELLOW}   Make sure you're running from the examples/MultiAgent directory${NC}"
        echo -e "${YELLOW}   and that the genesis_lib is properly installed.${NC}"
    else
        echo -e "${GREEN}✅ Genesis library found${NC}"
    fi
    
    # Check OpenAI API key
    if [ -z "$OPENAI_API_KEY" ]; then
        echo -e "${YELLOW}⚠️  OPENAI_API_KEY environment variable not set${NC}"
        echo -e "${YELLOW}   AI assistants will have limited functionality${NC}"
    else
        echo -e "${GREEN}✅ OpenAI API key configured${NC}"
    fi
    
    echo -e "${GREEN}✅ Dependency check completed${NC}"
}

# Run tests
run_tests() {
    echo -e "${BLUE}🧪 Running test suite...${NC}"
    
    echo -e "${CYAN}Running configuration tests...${NC}"
    python3 TEST/test_config.py
    
    echo -e "${CYAN}Running agent selector tests...${NC}" 
    python3 TEST/test_agent_selector.py
    
    echo -e "${CYAN}Running conversation manager tests...${NC}"
    python3 TEST/test_conversation_manager.py
    
    echo -e "${CYAN}Running CLI interface tests...${NC}"
    python3 TEST/test_cli_interface.py
    
    echo -e "${CYAN}Running integration tests...${NC}"
    python3 TEST/test_integration.py
    
    echo -e "${GREEN}🎉 All tests completed successfully!${NC}"
}

# Start CLI interface
start_cli() {
    echo -e "${BLUE}🚀 Starting CLI interface...${NC}"
    echo -e "${YELLOW}💡 The CLI will discover and connect to available agents automatically${NC}"
    echo -e "${YELLOW}💡 Press Ctrl+C to stop${NC}"
    echo ""
    
    python3 interface/cli_interface.py
}

# Start Personal Assistant agent
start_personal_assistant() {
    echo -e "${BLUE}🤖 Starting Personal Assistant agent...${NC}"
    echo -e "${YELLOW}💡 This agent will be discoverable by the CLI interface${NC}"
    echo -e "${YELLOW}💡 Press Ctrl+C to stop${NC}"
    echo ""
    
    python3 agents/general/personal_assistant.py
}

# Show system status
show_status() {
    echo -e "${BLUE}📊 System Status${NC}"
    echo -e "${CYAN}======================================================================${NC}"
    
    # Show configuration
    echo -e "${WHITE}🔧 Configuration:${NC}"
    python3 -c "
import sys, os
sys.path.insert(0, '.')
from config.system_settings import get_system_config
config = get_system_config()
print(f'   Domain ID: {config[\"domain_id\"]}')
print(f'   OpenAI Model: {config[\"openai_model\"]}')
print(f'   Debug Mode: {config[\"debug_mode\"]}')
print(f'   API Keys: {\"✅\" if config[\"openai_api_key\"] else \"❌\"} OpenAI, {\"✅\" if config[\"weather_api_key\"] else \"❌\"} Weather')
"
    
    echo ""
    echo -e "${WHITE}🤖 Available Agents:${NC}"
    python3 -c "
import sys, os
sys.path.insert(0, '.')
from config.agent_configs import get_all_general_assistants
agents = get_all_general_assistants()
for name, config in agents.items():
    print(f'   • {config[\"display_name\"]}: {config[\"description\"]}')
"
    
    echo ""
    echo -e "${WHITE}📁 Project Structure:${NC}"
    echo "   • config/          - System and agent configurations"
    echo "   • interface/       - CLI and conversation management"
    echo "   • agents/general/  - General assistant agents"
    echo "   • agents/specialized/ - Specialized domain agents (future)"
    echo "   • agents/services/ - Function services (future)"
    echo "   • TEST/            - Comprehensive test suite"
    
    echo ""
    echo -e "${WHITE}🚀 Available Commands:${NC}"
    echo "   • ./run_multi_agent_demo.sh test     - Run all tests"
    echo "   • ./run_multi_agent_demo.sh cli      - Start CLI interface"
    echo "   • ./run_multi_agent_demo.sh agent    - Start Personal Assistant"
    echo "   • ./run_multi_agent_demo.sh status   - Show this status"
    echo "   • ./run_multi_agent_demo.sh help     - Show help"
}

# Show help
show_help() {
    echo -e "${WHITE}🤖 Genesis Multi-Agent System - Usage Guide${NC}"
    echo -e "${CYAN}======================================================================${NC}"
    echo ""
    echo -e "${WHITE}COMMANDS:${NC}"
    echo -e "${GREEN}  test${NC}     - Run comprehensive test suite to validate system"
    echo -e "${GREEN}  cli${NC}      - Start interactive CLI interface for chatting with agents"
    echo -e "${GREEN}  agent${NC}    - Start Personal Assistant agent (discoverable by CLI)"
    echo -e "${GREEN}  status${NC}   - Show system status and configuration"
    echo -e "${GREEN}  help${NC}     - Show this help message"
    echo ""
    echo -e "${WHITE}TYPICAL WORKFLOW:${NC}"
    echo -e "${YELLOW}1.${NC} Run tests: ${CYAN}./run_multi_agent_demo.sh test${NC}"
    echo -e "${YELLOW}2.${NC} Start an agent in terminal 1: ${CYAN}./run_multi_agent_demo.sh agent${NC}"
    echo -e "${YELLOW}3.${NC} Start CLI in terminal 2: ${CYAN}./run_multi_agent_demo.sh cli${NC}"
    echo -e "${YELLOW}4.${NC} Select agent #1 in CLI and start chatting!"
    echo ""
    echo -e "${WHITE}REQUIREMENTS:${NC}"
    echo -e "${YELLOW}•${NC} Python 3.7+"
    echo -e "${YELLOW}•${NC} Genesis library installed"
    echo -e "${YELLOW}•${NC} OpenAI API key (set OPENAI_API_KEY environment variable)"
    echo -e "${YELLOW}•${NC} Optional: Weather API key (set OPENWEATHERMAP_API_KEY)"
    echo ""
    echo -e "${WHITE}FEATURES DEMONSTRATED:${NC}"
    echo -e "${YELLOW}•${NC} 🔄 Automatic agent discovery without manual configuration"
    echo -e "${YELLOW}•${NC} 🤖 Multi-agent collaboration on complex tasks"
    echo -e "${YELLOW}•${NC} 🛠️  Capability-based routing (agents call each other by expertise)"
    echo -e "${YELLOW}•${NC} 📊 Real-time monitoring and performance metrics"
    echo -e "${YELLOW}•${NC} 🔧 Easy extensibility (add new agents without modifying existing ones)"
    echo -e "${YELLOW}•${NC} 🖥️  Professional CLI interface with conversation management"
    echo ""
}

# Main logic
main() {
    print_header
    
    case "${1:-help}" in
        "test")
            check_dependencies
            run_tests
            ;;
        "cli")
            check_dependencies
            start_cli
            ;;
        "agent")
            check_dependencies
            start_personal_assistant
            ;;
        "status")
            check_dependencies
            show_status
            ;;
        "help"|"")
            show_help
            ;;
        *)
            echo -e "${RED}❌ Unknown command: $1${NC}"
            echo -e "${WHITE}Run './run_multi_agent_demo.sh help' for usage information${NC}"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@" 