#!/bin/bash
#
# Multi-Agent System Test Script
#
# This script provides both automated testing and interactive manual testing
# for the Genesis Multi-Agent system. It demonstrates the proper pattern:
#
# 1. Clean Environment: Kill existing agents
# 2. Controlled Startup: Start specific test agents
# 3. Testing Options: Automated tests OR manual interaction
# 4. Cleanup: Proper shutdown
#
# Usage:
#   ./test_multi_agent_system.sh auto     # Run automated tests
#   ./test_multi_agent_system.sh manual   # Start agents for manual testing
#   ./test_multi_agent_system.sh clean    # Just cleanup existing agents
#
# Copyright (c) 2025, RTI & Jason Upchurch
#

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
TEST_TIMEOUT=60

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Comprehensive cleanup function
cleanup_agents() {
    log_info "🧹 Performing comprehensive cleanup of agent processes..."
    
    # Method 1: Kill by specific script patterns (graceful)
    log_info "Step 1: Graceful termination by script patterns..."
    pkill -f "python.*personal_assistant.py" || true
    pkill -f "python.*weather_agent.py" || true
    pkill -f "python.*interactive_cli.py" || true
    pkill -f "python.*test_interactive_multi_agent.py" || true
    pkill -f "python.*calculator_service.py" || true
    
    # Also kill any other Genesis-related processes
    pkill -f "python.*genesis_lib" || true
    pkill -f "python.*test_functions" || true
    
    # Wait for graceful shutdown
    sleep 2
    
    # Method 2: Force kill by patterns (SIGKILL)
    log_info "Step 2: Force termination by script patterns..."
    pkill -9 -f "python.*personal_assistant.py" || true
    pkill -9 -f "python.*weather_agent.py" || true
    pkill -9 -f "python.*interactive_cli.py" || true
    pkill -9 -f "python.*test_interactive_multi_agent.py" || true
    pkill -9 -f "python.*calculator_service.py" || true
    pkill -9 -f "python.*genesis_lib" || true
    pkill -9 -f "python.*test_functions" || true
    
    # Method 3: Kill any Python processes in MultiAgentV2 directory
    log_info "Step 3: Cleaning up any Python processes in MultiAgentV2..."
    SCRIPT_NAME=$(basename "$SCRIPT_DIR")
    ps aux | grep -E "python.*$SCRIPT_NAME" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true
    
    # Method 4: Kill by PID if still running (comprehensive check)
    log_info "Step 4: Final cleanup of any remaining processes..."
    REMAINING_PIDS=$(ps aux | grep -E "(personal_assistant|weather_agent|calculator_service|genesis_lib|test_functions)" | grep -v grep | awk '{print $2}' || true)
    if [ -n "$REMAINING_PIDS" ]; then
        log_warning "Force killing remaining processes: $REMAINING_PIDS"
        echo "$REMAINING_PIDS" | xargs kill -9 2>/dev/null || true
    fi
    
    # Method 5: Clean up any orphaned DDS processes
    log_info "Step 5: Cleaning up DDS-related processes..."
    pkill -f "rtiddsspy" || true
    pkill -f "rtiddsgen" || true
    
    # Wait for processes to fully terminate
    sleep 3
    
    # Verify cleanup
    log_info "Step 6: Verifying cleanup..."
    REMAINING=$(ps aux | grep -E "(personal_assistant|weather_agent|calculator_service|genesis_lib|test_functions)" | grep -v grep | wc -l || echo "0")
    if [ "$REMAINING" -gt 0 ]; then
        log_warning "⚠️ $REMAINING processes still running after cleanup:"
        ps aux | grep -E "(personal_assistant|weather_agent|calculator_service|genesis_lib|test_functions)" | grep -v grep || true
        log_warning "Proceeding anyway - these may be from other tests"
    else
        log_success "✅ Cleanup completed - all target processes terminated"
    fi
}

# Verify clean environment
verify_clean_environment() {
    log_info "🔍 Verifying environment is clean..."
    
    # Check for any target processes
    TARGET_PROCESSES=$(ps aux | grep -E "(personal_assistant|weather_agent|calculator_service)" | grep -v grep | wc -l || echo "0")
    
    if [ "$TARGET_PROCESSES" -gt 0 ]; then
        log_warning "Found $TARGET_PROCESSES target processes still running:"
        ps aux | grep -E "(personal_assistant|weather_agent|calculator_service)" | grep -v grep || true
        
        log_info "Attempting additional cleanup..."
        cleanup_agents
        
        # Check again
        TARGET_PROCESSES=$(ps aux | grep -E "(personal_assistant|weather_agent|calculator_service)" | grep -v grep | wc -l || echo "0")
        if [ "$TARGET_PROCESSES" -gt 0 ]; then
            log_error "Unable to clean environment completely. Aborting test."
            return 1
        fi
    fi
    
    log_success "✅ Environment is clean and ready for testing"
    return 0
}

# Verify required files exist
verify_required_files() {
    log_info "📁 Verifying required files exist..."
    
    local missing_files=()
    
    # Check for agent files
    if [ ! -f "$SCRIPT_DIR/agents/personal_assistant.py" ]; then
        missing_files+=("agents/personal_assistant.py")
    fi
    
    if [ ! -f "$SCRIPT_DIR/agents/weather_agent.py" ]; then
        missing_files+=("agents/weather_agent.py")
    fi
    
    # Check for test files
    if [ ! -f "$SCRIPT_DIR/test_interactive_multi_agent.py" ]; then
        missing_files+=("test_interactive_multi_agent.py")
    fi
    
    if [ ! -f "$SCRIPT_DIR/interactive_cli.py" ]; then
        missing_files+=("interactive_cli.py")
    fi
    
    # Check for calculator service
    if [ ! -f "$PROJECT_ROOT/test_functions/calculator_service.py" ]; then
        missing_files+=("../../test_functions/calculator_service.py")
    fi
    
    # Report missing files
    if [ ${#missing_files[@]} -gt 0 ]; then
        log_error "Missing required files:"
        for file in "${missing_files[@]}"; do
            log_error "  ❌ $file"
        done
        log_error "Current directory: $(pwd)"
        log_error "Script directory: $SCRIPT_DIR"
        log_error "Project root: $PROJECT_ROOT"
        return 1
    fi
    
    log_success "✅ All required files found"
    return 0
}

# Enhanced DDS environment check
check_dds_environment() {
    log_info "🔧 Checking DDS environment..."
    
    # Check for NDDSHOME
    if [ -z "$NDDSHOME" ]; then
        log_warning "NDDSHOME not set - DDS spy tools may not be available"
    else
        log_success "NDDSHOME: $NDDSHOME"
    fi
    
    # Check for DDS processes
    DDS_PROCESSES=$(ps aux | grep -E "(rtiddsspy|nddsgen)" | grep -v grep | wc -l || echo "0")
    if [ "$DDS_PROCESSES" -gt 0 ]; then
        log_info "Found $DDS_PROCESSES existing DDS processes"
    fi
    
    return 0
}

# Start calculator service
start_calculator() {
    log_info "🧮 Starting Calculator Service..."
    
    CALC_PATH="$PROJECT_ROOT/test_functions/calculator_service.py"
    if [ ! -f "$CALC_PATH" ]; then
        log_warning "Calculator service not found at $CALC_PATH"
        return 1
    fi
    
    cd "$PROJECT_ROOT"
    python "$CALC_PATH" > /dev/null 2>&1 &
    CALC_PID=$!
    
    log_success "✅ Calculator Service started (PID: $CALC_PID)"
    sleep 2  # Let it initialize
    return 0
}

# Start agents
start_agents() {
    log_info "🚀 Starting test agents..."
    
    cd "$SCRIPT_DIR"
    
    # Start PersonalAssistant
    if [ ! -f "agents/personal_assistant.py" ]; then
        log_error "PersonalAssistant not found at agents/personal_assistant.py"
        return 1
    fi
    
    python agents/personal_assistant.py > /dev/null 2>&1 &
    PERSONAL_PID=$!
    log_success "✅ PersonalAssistant started (PID: $PERSONAL_PID)"
    
    # Start WeatherAgent
    if [ ! -f "agents/weather_agent.py" ]; then
        log_error "WeatherAgent not found at agents/weather_agent.py"
        return 1
    fi
    
    python agents/weather_agent.py > /dev/null 2>&1 &
    WEATHER_PID=$!
    log_success "✅ WeatherAgent started (PID: $WEATHER_PID)"
    
    # Wait for agents to initialize
    log_info "⏳ Waiting for agents to initialize..."
    sleep 5
    
    return 0
}

# Run automated tests
run_automated_tests() {
    log_info "🧪 Running automated test suite..."
    
    cd "$SCRIPT_DIR"
    
    # Test 1: Comprehensive multi-agent system test
    log_info "=== TEST 1: Comprehensive Multi-Agent System Test ==="
    if [ ! -f "test_interactive_multi_agent.py" ]; then
        log_error "Comprehensive test script not found at test_interactive_multi_agent.py"
        return 1
    fi
    
    log_info "Running comprehensive agent functionality tests..."
    timeout $TEST_TIMEOUT python test_interactive_multi_agent.py
    local comprehensive_exit_code=$?
    
    if [ $comprehensive_exit_code -eq 0 ]; then
        log_success "✅ Comprehensive multi-agent tests passed!"
    elif [ $comprehensive_exit_code -eq 124 ]; then
        log_error "❌ Comprehensive tests timed out after ${TEST_TIMEOUT} seconds"
        return 1
    else
        log_error "❌ Comprehensive tests failed with exit code $comprehensive_exit_code"
        return 1
    fi
    
    # Test 2: Agent-to-Agent Delegation Test (NEW - Core Genesis Feature)
    log_info "=== TEST 2: Agent-to-Agent Delegation Test ==="
    if [ ! -f "test_agent_to_agent_delegation.py" ]; then
        log_error "Agent-to-Agent delegation test not found at test_agent_to_agent_delegation.py"
        return 1
    fi
    
    log_info "Testing agent-to-agent delegation pattern..."
    log_info "Expected: Interface → PersonalAssistant → WeatherAgent → PersonalAssistant → Interface"
    
    timeout $TEST_TIMEOUT python test_agent_to_agent_delegation.py
    local delegation_exit_code=$?
    
    if [ $delegation_exit_code -eq 0 ]; then
        log_success "✅ Agent-to-Agent delegation test passed!"
    elif [ $delegation_exit_code -eq 124 ]; then
        log_error "❌ Agent-to-Agent delegation test timed out after ${TEST_TIMEOUT} seconds"
        return 1
    else
        log_error "❌ Agent-to-Agent delegation test failed with exit code $delegation_exit_code"
        return 1
    fi
    
    # All tests passed
    log_success "🎉 All automated tests completed successfully!"
    log_success "✅ Comprehensive functionality tests: PASSED"
    log_success "✅ Agent-to-agent delegation tests: PASSED"
    log_success "✅ Genesis multi-agent system is working correctly!"
    
    return 0
}

# Run manual interactive session
run_manual_test() {
    log_info "💬 Starting manual interactive test..."
    log_info "Use Ctrl+C to exit when done"
    
    cd "$SCRIPT_DIR"
    
    if [ ! -f "interactive_cli.py" ]; then
        log_error "Interactive CLI not found at interactive_cli.py"
        return 1
    fi
    
    # Run the interactive CLI
    python interactive_cli.py
    
    log_success "✅ Manual test session completed"
    return 0
}

# Check for DDS spy tool
check_dds_monitoring() {
    if command -v rtiddsspy >/dev/null 2>&1; then
        log_info "📊 DDS Spy available - you can monitor with:"
        echo "   rtiddsspy -printSample"
    else
        log_warning "DDS Spy not available in PATH"
    fi
}

# Print usage
usage() {
    echo "Usage: $0 {auto|manual|clean|help}"
    echo ""
    echo "Commands:"
    echo "  auto    - Run automated tests (starts agents, runs tests, cleans up)"
    echo "  manual  - Start agents for manual testing (interactive CLI)"
    echo "  clean   - Clean up any existing agent processes"
    echo "  help    - Show this usage information"
    echo ""
    echo "Examples:"
    echo "  $0 auto           # Full automated test suite"
    echo "  $0 manual         # Start agents and interactive CLI"
    echo "  $0 clean          # Clean up before starting fresh"
    echo ""
}

# Main execution
main() {
    case "$1" in
        auto)
            log_info "🔧 Running automated test suite with enhanced cleanup..."
            
            # Enhanced cleanup and verification
            log_info "=== PHASE 1: Environment Cleanup ==="
            cleanup_agents
            
            log_info "=== PHASE 2: Environment Verification ==="
            if ! verify_clean_environment; then
                log_error "Cannot proceed with dirty environment"
                exit 1
            fi
            
            log_info "=== PHASE 3: File Verification ==="
            if ! verify_required_files; then
                log_error "Cannot proceed with missing files"
                exit 1
            fi
            
            log_info "=== PHASE 4: DDS Environment Check ==="
            check_dds_environment
            
            log_info "=== PHASE 5: Service and Agent Startup ==="
            # Start services and agents
            start_calculator || log_warning "Calculator service failed to start"
            start_agents || { log_error "Failed to start agents"; cleanup_agents; exit 1; }
            
            log_info "=== PHASE 6: Test Execution ==="
            # Run tests
            if run_automated_tests; then
                log_success "🎉 Automated tests completed successfully!"
                exit_code=0
            else
                log_error "❌ Automated tests failed"
                exit_code=1
            fi
            
            log_info "=== PHASE 7: Final Cleanup ==="
            # Cleanup
            cleanup_agents
            exit $exit_code
            ;;
            
        manual)
            log_info "🎮 Starting manual test session with enhanced cleanup..."
            
            # Enhanced cleanup and verification
            log_info "=== PHASE 1: Environment Cleanup ==="
            cleanup_agents
            
            log_info "=== PHASE 2: Environment Verification ==="
            if ! verify_clean_environment; then
                log_error "Cannot proceed with dirty environment"
                exit 1
            fi
            
            log_info "=== PHASE 3: File Verification ==="
            if ! verify_required_files; then
                log_error "Cannot proceed with missing files"
                exit 1
            fi
            
            log_info "=== PHASE 4: DDS Environment Check ==="
            check_dds_environment
            
            log_info "=== PHASE 5: Service and Agent Startup ==="
            # Start services and agents
            start_calculator || log_warning "Calculator service failed to start"
            start_agents || { log_error "Failed to start agents"; cleanup_agents; exit 1; }
            
            # Show monitoring info
            check_dds_monitoring
            
            log_info "=== PHASE 6: Interactive Session ==="
            # Run interactive session
            if run_manual_test; then
                log_success "✅ Manual test session completed"
            else
                log_warning "Manual test session ended"
            fi
            
            log_info "=== PHASE 7: Final Cleanup ==="
            # Cleanup
            cleanup_agents
            ;;
            
        clean)
            log_info "🧽 Performing comprehensive cleanup..."
            cleanup_agents
            verify_clean_environment
            ;;
            
        help|--help|-h)
            usage
            ;;
            
        "")
            log_error "No command specified"
            usage
            exit 1
            ;;
            
        *)
            log_error "Unknown command: $1"
            usage
            exit 1
            ;;
    esac
}

# Trap for cleanup on script exit
trap cleanup_agents EXIT

# Run main function
main "$@" 