#!/usr/bin/env bash
# Copyright (c) 2025, RTI & Jason Upchurch
set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════════
# GENESIS Setup Script
# ═══════════════════════════════════════════════════════════════════════════════
# This script sets up the GENESIS Python environment.
# Run ./rti_setup.sh first if you haven't installed RTI Connext DDS.
# ═══════════════════════════════════════════════════════════════════════════════

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}${BOLD}                    GENESIS Setup                              ${NC}${BLUE}║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Check for RTI Connext DDS
# ─────────────────────────────────────────────────────────────────────────────

check_rti() {
    # Check NDDSHOME
    if [[ -n "${NDDSHOME:-}" ]] && [[ -d "$NDDSHOME" ]]; then
        return 0
    fi

    # Check common paths
    local paths=(
        "/Applications/rti_connext_dds-7.5.0"
        "/Applications/rti_connext_dds-7.4.0"
        "/Applications/rti_connext_dds-7.3.0"
        "$HOME/rti_connext_dds-7.5.0"
        "$HOME/rti_connext_dds-7.4.0"
        "$HOME/rti_connext_dds-7.3.0"
        "/opt/rti_connext_dds-7.5.0"
        "/opt/rti_connext_dds-7.4.0"
        "/opt/rti_connext_dds-7.3.0"
    )

    for path in "${paths[@]}"; do
        if [[ -d "$path" ]]; then
            return 0
        fi
    done

    return 1
}

echo -e "${CYAN}Step 1: Checking for RTI Connext DDS${NC}"
echo ""

if ! check_rti; then
    echo -e "  ${YELLOW}⚠  RTI Connext DDS not found${NC}"
    echo ""
    echo -e "  GENESIS requires RTI Connext DDS to run."
    echo -e "  Don't worry - we have a wizard to help you set it up!"
    echo ""
    echo -e "  ${BOLD}Run this command first:${NC}"
    echo ""
    echo -e "    ${CYAN}./rti_setup.sh${NC}"
    echo ""
    echo -e "  The wizard will guide you through getting a free 60-day license"
    echo -e "  and installing RTI Connext DDS."
    echo ""
    echo -e "  After that completes, run ${CYAN}./setup.sh${NC} again."
    echo ""
    exit 1
fi

if [[ -n "${NDDSHOME:-}" ]]; then
    echo -e "  ${GREEN}✓${NC} RTI Connext DDS found: ${NDDSHOME}"
else
    echo -e "  ${GREEN}✓${NC} RTI Connext DDS installation detected"
    echo -e "  ${YELLOW}⚠${NC} NDDSHOME not set - you may need to open a new terminal"
fi
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Check Python Version
# ─────────────────────────────────────────────────────────────────────────────

echo -e "${CYAN}Step 2: Checking Python version${NC}"
echo ""

PYV=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "")

if [[ "$PYV" == "3.10" ]]; then
    echo -e "  ${GREEN}✓${NC} Python 3.10 detected"
elif [[ -n "$PYV" ]]; then
    echo -e "  ${YELLOW}⚠${NC} Python $PYV detected (3.10 recommended)"
else
    echo -e "  ${RED}✗${NC} Python 3 not found"
    echo ""
    echo -e "  Please install Python 3.10 and try again."
    exit 1
fi
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Create Virtual Environment
# ─────────────────────────────────────────────────────────────────────────────

echo -e "${CYAN}Step 3: Setting up Python environment${NC}"
echo ""

if [[ ! -d .venv ]]; then
    echo -e "  Creating virtual environment (.venv)..."
    if command -v python3.10 &> /dev/null; then
        python3.10 -m venv .venv
    else
        python3 -m venv .venv
    fi
    echo -e "  ${GREEN}✓${NC} Virtual environment created"
else
    echo -e "  ${GREEN}✓${NC} Virtual environment exists"
fi

# shellcheck disable=SC1091
source .venv/bin/activate
echo -e "  ${GREEN}✓${NC} Virtual environment activated"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Install Dependencies
# ─────────────────────────────────────────────────────────────────────────────

echo -e "${CYAN}Step 4: Installing GENESIS${NC}"
echo ""

echo -e "  Upgrading pip..."
pip install --upgrade pip >/dev/null 2>&1 || true

echo -e "  Installing genesis-lib..."
pip install . >/dev/null 2>&1

echo -e "  ${GREEN}✓${NC} GENESIS installed"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Verify Installation
# ─────────────────────────────────────────────────────────────────────────────

echo -e "${CYAN}Step 5: Verifying installation${NC}"
echo ""

if python -c "import genesis_lib" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} genesis_lib imports successfully"
else
    echo -e "  ${RED}✗${NC} Failed to import genesis_lib"
    exit 1
fi

if command -v genesis-monitor &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} genesis-monitor CLI available"
else
    echo -e "  ${YELLOW}⚠${NC} genesis-monitor CLI not in PATH"
fi

# Check DDS connectivity
if [[ -n "${NDDSHOME:-}" ]] && [[ -x "$NDDSHOME/bin/rtiddsspy" ]]; then
    echo -e "  ${GREEN}✓${NC} rtiddsspy available"
else
    echo -e "  ${YELLOW}⚠${NC} rtiddsspy not accessible (DDS features may be limited)"
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────────────────────────────────────

echo -e "${GREEN}═══════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}                    SETUP COMPLETE!                                ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}To activate the environment later:${NC}"
echo -e "    ${CYAN}source $PROJECT_ROOT/.venv/bin/activate${NC}"
echo ""
echo -e "  ${BOLD}To run the demo:${NC}"
echo -e "    ${CYAN}cd examples/MultiAgent && ./run_interactive_demo.sh${NC}"
echo ""
echo -e "  ${BOLD}To run tests:${NC}"
echo -e "    ${CYAN}cd tests && ./run_all_tests.sh${NC}"
echo ""
echo -e "  ${BOLD}Documentation:${NC}"
echo -e "    • ${CYAN}QUICKSTART.md${NC} - Get started quickly"
echo -e "    • ${CYAN}docs/${NC} - Full documentation"
echo ""
