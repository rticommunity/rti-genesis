#!/usr/bin/env bash
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

set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════════
# RTI Connext DDS Setup Wizard for GENESIS
# ═══════════════════════════════════════════════════════════════════════════════
# This wizard guides you through obtaining and configuring RTI Connext DDS.
# Just follow the prompts - no technical knowledge required!
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RTI_VERSION="${RTI_VERSION:-7.3.0}"

# Pre-filled URL with 60-day evaluation selected
RTI_LICENSE_URL="https://www.rti.com/get-connext?license_type=Standard%2030-day%20evaluation%20license"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

print_banner() {
    echo ""
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}${BOLD}          RTI Connext DDS Setup Wizard for GENESIS          ${NC}${BLUE}║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    local step_num=$1
    local step_title=$2
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  STEP ${step_num}: ${step_title}${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}  ✓ $1${NC}"
}

print_error() {
    echo -e "${RED}  ✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}  ⚠ $1${NC}"
}

print_info() {
    echo -e "  $1"
}

print_bullet() {
    echo -e "    • $1"
}

wait_for_user() {
    local prompt="${1:-Press Enter to continue...}"
    echo ""
    read -p "  $prompt" _
}

ask_yes_no() {
    local prompt="$1"
    local response
    while true; do
        read -p "  $prompt (y/n): " response
        case "$response" in
            [Yy]|[Yy][Ee][Ss]) return 0 ;;
            [Nn]|[Nn][Oo]) return 1 ;;
            *) echo "  Please answer y or n." ;;
        esac
    done
}

detect_os() {
    case "$(uname -s)" in
        Darwin) echo "macos" ;;
        Linux)  echo "linux" ;;
        *)      echo "unknown" ;;
    esac
}

detect_arch() {
    case "$(uname -m)" in
        x86_64)  echo "x64" ;;
        arm64)   echo "arm64" ;;
        aarch64) echo "arm64" ;;
        *)       echo "unknown" ;;
    esac
}

open_url() {
    local url="$1"
    case "$(detect_os)" in
        macos)
            open "$url"
            ;;
        linux)
            if command -v xdg-open &> /dev/null; then
                xdg-open "$url" 2>/dev/null &
            elif command -v firefox &> /dev/null; then
                firefox "$url" 2>/dev/null &
            elif command -v google-chrome &> /dev/null; then
                google-chrome "$url" 2>/dev/null &
            else
                return 1
            fi
            ;;
        *)
            return 1
            ;;
    esac
}

# ─────────────────────────────────────────────────────────────────────────────
# Detection Functions
# ─────────────────────────────────────────────────────────────────────────────

find_rti_installation() {
    # Check NDDSHOME first
    if [[ -n "${NDDSHOME:-}" ]] && [[ -d "$NDDSHOME" ]]; then
        echo "$NDDSHOME"
        return 0
    fi

    # Common installation paths
    local search_paths=()
    case "$(detect_os)" in
        macos)
            search_paths=(
                "/Applications/rti_connext_dds-7.5.0"
                "/Applications/rti_connext_dds-7.4.0"
                "/Applications/rti_connext_dds-7.3.0"
                "$HOME/rti_connext_dds-7.5.0"
                "$HOME/rti_connext_dds-7.4.0"
                "$HOME/rti_connext_dds-7.3.0"
            )
            ;;
        linux)
            search_paths=(
                "$HOME/rti_connext_dds-7.5.0"
                "$HOME/rti_connext_dds-7.4.0"
                "$HOME/rti_connext_dds-7.3.0"
                "/opt/rti_connext_dds-7.5.0"
                "/opt/rti_connext_dds-7.4.0"
                "/opt/rti_connext_dds-7.3.0"
            )
            ;;
    esac

    for path in "${search_paths[@]}"; do
        if [[ -d "$path" ]] && [[ -f "$path/bin/rtiddsspy" || -d "$path/bin" ]]; then
            echo "$path"
            return 0
        fi
    done

    return 1
}

find_license_file() {
    local rti_home="${1:-}"
    local search_locations=(
        "$HOME/Downloads/rti_license.dat"
        "$HOME/rti_license.dat"
        "$SCRIPT_DIR/rti_license.dat"
        "./rti_license.dat"
        "/tmp/rti_license.dat"
    )

    # Add RTI home location if provided
    if [[ -n "$rti_home" ]]; then
        search_locations=("$rti_home/rti_license.dat" "${search_locations[@]}")
    fi

    for loc in "${search_locations[@]}"; do
        if [[ -f "$loc" ]]; then
            echo "$loc"
            return 0
        fi
    done

    return 1
}

# ─────────────────────────────────────────────────────────────────────────────
# Wizard Steps
# ─────────────────────────────────────────────────────────────────────────────

wizard_check_existing() {
    print_step "1" "Checking for Existing Installation"

    print_info "Looking for RTI Connext DDS on your system..."
    echo ""

    local rti_home
    if rti_home=$(find_rti_installation); then
        print_success "Found RTI Connext DDS!"
        print_info "Location: ${BOLD}$rti_home${NC}"
        echo ""

        # Check for license
        if license_path=$(find_license_file "$rti_home"); then
            print_success "License file found: $license_path"
            FOUND_RTI_HOME="$rti_home"
            FOUND_LICENSE="$license_path"
            return 0
        else
            print_warning "License file not found"
            print_info "You may need to check your email for rti_license.dat"
            FOUND_RTI_HOME="$rti_home"
            FOUND_LICENSE=""
            return 0
        fi
    else
        print_info "RTI Connext DDS is not installed yet."
        print_info "No worries! This wizard will help you get it."
        FOUND_RTI_HOME=""
        FOUND_LICENSE=""
        return 1
    fi
}

wizard_request_license() {
    print_step "2" "Request Your Free License"

    echo -e "  ${BOLD}What happens next:${NC}"
    echo ""
    print_bullet "Your web browser will open to RTI's website"
    print_bullet "The 60-day evaluation license will be PRE-SELECTED"
    print_bullet "Fill out the short form (name, email, company)"
    print_bullet "Complete the quick verification (reCAPTCHA)"
    print_bullet "Click Submit"
    echo ""
    echo -e "  ${BOLD}After you submit:${NC}"
    echo ""
    print_bullet "You'll see a download page - KEEP IT OPEN"
    print_bullet "Your license file will be emailed to you"
    echo ""

    if ask_yes_no "Ready to open the RTI website?"; then
        print_info "Opening browser..."
        if open_url "$RTI_LICENSE_URL"; then
            print_success "Browser opened!"
        else
            print_warning "Could not open browser automatically."
            echo ""
            print_info "Please open this URL manually:"
            echo ""
            echo -e "    ${CYAN}${RTI_LICENSE_URL}${NC}"
        fi

        echo ""
        echo -e "  ${YELLOW}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "  ${YELLOW}║  COMPLETE THE FORM IN YOUR BROWSER, THEN COME BACK HERE   ║${NC}"
        echo -e "  ${YELLOW}╚════════════════════════════════════════════════════════════╝${NC}"
        echo ""

        wait_for_user "Press Enter AFTER you've submitted the form..."
        return 0
    else
        print_info "No problem. You can run this wizard again anytime."
        return 1
    fi
}

wizard_download_software() {
    print_step "3" "Download the Software"

    local os=$(detect_os)
    local arch=$(detect_arch)

    echo -e "  ${BOLD}On the download page in your browser:${NC}"
    echo ""

    case "$os" in
        macos)
            print_info "Download the HOST package for macOS:"
            echo ""
            if [[ "$arch" == "arm64" ]]; then
                echo -e "    ${CYAN}rti_connext_dds-X.X.X-pro-host-arm64Darwin.dmg${NC}"
                print_info "(This is for Apple Silicon Macs - M1/M2/M3)"
            else
                echo -e "    ${CYAN}rti_connext_dds-X.X.X-pro-host-x64Darwin.dmg${NC}"
                print_info "(This is for Intel Macs)"
            fi
            echo ""
            print_info "Save it to your Downloads folder."
            ;;
        linux)
            print_info "Download the HOST package for Linux:"
            echo ""
            echo -e "    ${CYAN}rti_connext_dds-X.X.X-pro-host-x64Linux.run${NC}"
            echo ""
            print_info "Save it to your Downloads folder."
            ;;
    esac

    echo ""
    wait_for_user "Press Enter AFTER the download is complete..."
}

wizard_install_software() {
    print_step "4" "Install RTI Connext DDS"

    local os=$(detect_os)

    case "$os" in
        macos)
            echo -e "  ${BOLD}Installation steps:${NC}"
            echo ""
            print_bullet "Find the .dmg file in your Downloads folder"
            print_bullet "Double-click to open it"
            print_bullet "Double-click the installer icon inside"
            print_bullet "Follow the installation wizard"
            print_bullet "Use the DEFAULT installation location"
            echo ""
            print_info "Default location: /Applications/rti_connext_dds-7.X.X"
            ;;
        linux)
            echo -e "  ${BOLD}Installation steps:${NC}"
            echo ""
            print_info "Open a terminal and run these commands:"
            echo ""
            echo -e "    ${CYAN}cd ~/Downloads${NC}"
            echo -e "    ${CYAN}chmod +x rti_connext_dds-*.run${NC}"
            echo -e "    ${CYAN}./rti_connext_dds-*.run${NC}"
            echo ""
            print_bullet "Follow the installation wizard"
            print_bullet "Use the DEFAULT installation location"
            echo ""
            print_info "Default location: ~/rti_connext_dds-7.X.X"
            ;;
    esac

    echo ""
    echo -e "  ${YELLOW}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "  ${YELLOW}║        INSTALL THE SOFTWARE, THEN COME BACK HERE          ║${NC}"
    echo -e "  ${YELLOW}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    wait_for_user "Press Enter AFTER installation is complete..."

    # Try to find the new installation
    if rti_home=$(find_rti_installation); then
        print_success "Found installation at: $rti_home"
        FOUND_RTI_HOME="$rti_home"
    else
        print_warning "Could not auto-detect installation."
        echo ""
        read -p "  Enter the installation path (or press Enter to search again): " manual_path
        if [[ -n "$manual_path" ]] && [[ -d "$manual_path" ]]; then
            FOUND_RTI_HOME="$manual_path"
            print_success "Using: $FOUND_RTI_HOME"
        else
            print_error "Installation not found. Please verify the installation completed."
            return 1
        fi
    fi
}

wizard_install_license() {
    print_step "5" "Install Your License File"

    echo -e "  ${BOLD}Check your email for a message from RTI containing:${NC}"
    echo ""
    echo -e "    ${CYAN}rti_license.dat${NC}"
    echo ""
    print_info "This usually arrives within a few minutes of submitting the form."
    print_info "Check your spam folder if you don't see it."
    echo ""

    # Wait for user
    wait_for_user "Press Enter when you have the license file..."

    # Search for license file
    print_info "Searching for license file..."

    if license_path=$(find_license_file "$FOUND_RTI_HOME"); then
        print_success "Found license file: $license_path"
    else
        echo ""
        print_info "Common locations to save the license file:"
        print_bullet "~/Downloads/rti_license.dat"
        print_bullet "Your RTI installation folder"
        echo ""
        read -p "  Enter path to rti_license.dat: " license_path

        if [[ ! -f "$license_path" ]]; then
            print_error "File not found: $license_path"
            print_info "You can install the license later by running:"
            echo -e "    ${CYAN}./rti_setup.sh --license${NC}"
            return 1
        fi
    fi

    # Install the license
    local dest="$FOUND_RTI_HOME/rti_license.dat"
    if [[ "$license_path" != "$dest" ]]; then
        print_info "Copying license to RTI installation..."
        cp "$license_path" "$dest"
        print_success "License installed to: $dest"
    else
        print_success "License already in correct location"
    fi

    FOUND_LICENSE="$dest"
}

wizard_configure_environment() {
    print_step "6" "Configure Your Environment"

    local os=$(detect_os)
    local arch=$(detect_arch)
    local shell_rc=""
    local lib_path=""

    # Determine shell config file
    if [[ -n "${ZSH_VERSION:-}" ]] || [[ "$SHELL" == *"zsh"* ]]; then
        shell_rc="$HOME/.zshrc"
    else
        shell_rc="$HOME/.bashrc"
    fi

    # Determine library path
    case "$os" in
        macos)
            if [[ "$arch" == "arm64" ]]; then
                lib_path="arm64Darwin20clang12.0"
            else
                lib_path="x64Darwin17clang9.0"
            fi
            ;;
        linux)
            lib_path="x64Linux4gcc7.3.0"
            ;;
    esac

    echo -e "  ${BOLD}Your shell configuration file:${NC} $shell_rc"
    echo ""
    print_info "The following will be added to configure RTI Connext:"
    echo ""
    echo -e "    ${CYAN}export NDDSHOME=\"$FOUND_RTI_HOME\"${NC}"
    echo -e "    ${CYAN}export PATH=\"\$NDDSHOME/bin:\$PATH\"${NC}"
    if [[ "$os" == "macos" ]]; then
        echo -e "    ${CYAN}export DYLD_LIBRARY_PATH=\"\$NDDSHOME/lib/$lib_path:\$DYLD_LIBRARY_PATH\"${NC}"
    else
        echo -e "    ${CYAN}export LD_LIBRARY_PATH=\"\$NDDSHOME/lib/$lib_path:\$LD_LIBRARY_PATH\"${NC}"
    fi
    echo ""

    if ask_yes_no "Add these to $shell_rc?"; then
        # Check if already configured
        if grep -q "NDDSHOME" "$shell_rc" 2>/dev/null; then
            print_warning "NDDSHOME already exists in $shell_rc"
            if ask_yes_no "Replace existing configuration?"; then
                # Remove old config
                sed -i.bak '/# RTI Connext DDS/,/^$/d' "$shell_rc" 2>/dev/null || true
                sed -i.bak '/NDDSHOME/d' "$shell_rc" 2>/dev/null || true
            else
                print_info "Keeping existing configuration."
                return 0
            fi
        fi

        # Add new configuration
        {
            echo ""
            echo "# RTI Connext DDS (added by GENESIS setup wizard)"
            echo "export NDDSHOME=\"$FOUND_RTI_HOME\""
            echo "export PATH=\"\$NDDSHOME/bin:\$PATH\""
            if [[ "$os" == "macos" ]]; then
                echo "export DYLD_LIBRARY_PATH=\"\$NDDSHOME/lib/$lib_path:\$DYLD_LIBRARY_PATH\""
            else
                echo "export LD_LIBRARY_PATH=\"\$NDDSHOME/lib/$lib_path:\$LD_LIBRARY_PATH\""
            fi
            echo ""
        } >> "$shell_rc"

        print_success "Configuration added to $shell_rc"

        # Source it for current session
        export NDDSHOME="$FOUND_RTI_HOME"
        export PATH="$NDDSHOME/bin:$PATH"

        echo ""
        print_info "Environment configured for this session."
        print_info "For new terminal windows, the config will load automatically."
    else
        print_info "Skipped. You can configure manually or run this wizard again."
    fi
}

wizard_verify() {
    print_step "7" "Verify Installation"

    local errors=0

    echo -e "  ${BOLD}Running verification checks...${NC}"
    echo ""

    # Check NDDSHOME
    if [[ -n "${NDDSHOME:-}" ]] && [[ -d "$NDDSHOME" ]]; then
        print_success "NDDSHOME is set: $NDDSHOME"
    elif [[ -n "$FOUND_RTI_HOME" ]]; then
        export NDDSHOME="$FOUND_RTI_HOME"
        print_success "NDDSHOME set to: $NDDSHOME"
    else
        print_error "NDDSHOME is not set"
        ((errors++))
    fi

    # Check rtiddsspy
    if [[ -x "$NDDSHOME/bin/rtiddsspy" ]]; then
        print_success "rtiddsspy found"
    else
        print_error "rtiddsspy not found"
        ((errors++))
    fi

    # Check license
    if [[ -f "$NDDSHOME/rti_license.dat" ]]; then
        print_success "License file installed"
    elif [[ -n "$FOUND_LICENSE" ]] && [[ -f "$FOUND_LICENSE" ]]; then
        print_success "License file found: $FOUND_LICENSE"
    else
        print_warning "License file not found in RTI installation"
        ((errors++))
    fi

    echo ""

    if [[ $errors -eq 0 ]]; then
        echo -e "  ${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "  ${GREEN}║                                                            ║${NC}"
        echo -e "  ${GREEN}║     SUCCESS! RTI Connext DDS is ready for GENESIS!        ║${NC}"
        echo -e "  ${GREEN}║                                                            ║${NC}"
        echo -e "  ${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        print_info "Next step: Run ${CYAN}./setup.sh${NC} to install GENESIS"
        return 0
    else
        echo -e "  ${YELLOW}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "  ${YELLOW}║     ALMOST THERE! $errors item(s) need attention.              ║${NC}"
        echo -e "  ${YELLOW}╚════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        print_info "Run this wizard again to fix any issues."
        return 1
    fi
}

wizard_complete() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}                        SETUP COMPLETE                             ${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BOLD}Quick Reference:${NC}"
    echo ""
    echo -e "  RTI Installation:  ${CYAN}$FOUND_RTI_HOME${NC}"
    if [[ -n "$FOUND_LICENSE" ]]; then
        echo -e "  License File:      ${CYAN}$FOUND_LICENSE${NC}"
    fi
    echo ""
    echo -e "  ${BOLD}Next Steps:${NC}"
    echo ""
    print_bullet "Open a NEW terminal window (to load the environment)"
    print_bullet "Run ${CYAN}./setup.sh${NC} to install GENESIS"
    print_bullet "Run ${CYAN}./rti_setup.sh --verify${NC} to re-check anytime"
    echo ""
    echo -e "  ${BOLD}Need Help?${NC}"
    echo ""
    print_bullet "See RTI_SETUP.md for detailed documentation"
    print_bullet "Contact: genesis@rti.com"
    echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# Main Wizard Flow
# ─────────────────────────────────────────────────────────────────────────────

run_wizard() {
    FOUND_RTI_HOME=""
    FOUND_LICENSE=""

    print_banner

    echo -e "  Welcome! This wizard will help you set up RTI Connext DDS."
    echo -e "  It takes about ${BOLD}10-15 minutes${NC} to complete."
    echo ""
    echo -e "  ${BOLD}You will need:${NC}"
    print_bullet "A web browser"
    print_bullet "An email address (to receive your license)"
    echo ""

    if ! ask_yes_no "Ready to begin?"; then
        print_info "No problem! Run this script when you're ready."
        exit 0
    fi

    # Step 1: Check for existing installation
    if wizard_check_existing; then
        echo ""
        if [[ -n "$FOUND_LICENSE" ]]; then
            print_info "RTI Connext is already installed and licensed!"
            if ask_yes_no "Skip to verification?"; then
                wizard_verify
                wizard_complete
                exit 0
            fi
        else
            if ask_yes_no "RTI is installed. Skip to license installation?"; then
                wizard_install_license
                wizard_configure_environment
                wizard_verify
                wizard_complete
                exit 0
            fi
        fi
    fi

    # Step 2: Request license (opens browser)
    if ! wizard_request_license; then
        exit 0
    fi

    # Step 3: Download software
    wizard_download_software

    # Step 4: Install software
    if ! wizard_install_software; then
        print_error "Installation not detected. Please try again."
        exit 1
    fi

    # Step 5: Install license
    wizard_install_license

    # Step 6: Configure environment
    wizard_configure_environment

    # Step 7: Verify
    wizard_verify

    # Complete
    wizard_complete
}

# ─────────────────────────────────────────────────────────────────────────────
# Command Line Interface
# ─────────────────────────────────────────────────────────────────────────────

cmd_verify() {
    print_banner
    FOUND_RTI_HOME=""
    FOUND_LICENSE=""

    if rti_home=$(find_rti_installation); then
        FOUND_RTI_HOME="$rti_home"
    fi
    if license=$(find_license_file "$FOUND_RTI_HOME"); then
        FOUND_LICENSE="$license"
    fi

    wizard_verify
}

cmd_request() {
    print_banner
    wizard_request_license
}

cmd_configure() {
    print_banner
    FOUND_RTI_HOME=""

    if rti_home=$(find_rti_installation); then
        FOUND_RTI_HOME="$rti_home"
        wizard_configure_environment
    else
        print_error "RTI Connext not found. Please install it first."
        print_info "Run: ./rti_setup.sh"
        exit 1
    fi
}

cmd_license() {
    print_banner
    FOUND_RTI_HOME=""

    if rti_home=$(find_rti_installation); then
        FOUND_RTI_HOME="$rti_home"
        wizard_install_license
    else
        print_error "RTI Connext not found. Please install it first."
        print_info "Run: ./rti_setup.sh"
        exit 1
    fi
}

show_help() {
    echo "RTI Connext DDS Setup Wizard for GENESIS"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  (none)        Run the full interactive setup wizard"
    echo "  --verify      Verify RTI installation"
    echo "  --request     Open browser to request license"
    echo "  --configure   Configure environment variables"
    echo "  --license     Install license file"
    echo "  --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                 # Full guided setup"
    echo "  $0 --verify        # Check if everything is working"
    echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

main() {
    case "${1:-}" in
        --verify|-v)
            cmd_verify
            ;;
        --request|-r)
            cmd_request
            ;;
        --configure|--config|-c)
            cmd_configure
            ;;
        --license|-l)
            cmd_license
            ;;
        --help|-h)
            show_help
            ;;
        "")
            run_wizard
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
}

main "$@"
