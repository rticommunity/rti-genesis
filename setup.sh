#!/bin/bash

# Exit on error
set -e

# Function to detect system architecture
detect_architecture() {
    ARCH=$(uname -m)
    OS=$(uname -s)
    
    if [ "$OS" == "Darwin" ]; then
        if [ "$ARCH" == "arm64" ]; then
            echo "arm64Darwin"
        else
            echo "x64Darwin"
        fi
    elif [ "$OS" == "Linux" ]; then
        if [ "$ARCH" == "x86_64" ]; then
            echo "x64Linux"
        elif [ "$ARCH" == "aarch64" ]; then
            echo "aarch64Linux"
        else
            echo "Unsupported Linux architecture: $ARCH"
            exit 1
        fi
    elif [[ "$OS" == *"MINGW"* ]] || [[ "$OS" == *"MSYS"* ]]; then
        # Windows in Git Bash or MSYS2
        if [ "$ARCH" == "x86_64" ]; then
            echo "x64Win64VS2022"  # Default to VS2022 for newer installations
        elif [ "$ARCH" == "i686" ]; then
            echo "i86Win32VS2022"  # Default to VS2022 for newer installations
        else
            echo "Unsupported Windows architecture: $ARCH"
            exit 1
        fi
    else
        echo "Unsupported OS/Architecture: $OS/$ARCH"
        exit 1
    fi
}

# Function to find RTI Connext DDS installations
find_rti_installations() {
    local rti_versions=()
    
    if [[ "$(uname -s)" == "Darwin" ]]; then
        # macOS
        local base_path="/Applications"
        for dir in "$base_path"/rti_connext_dds-*; do
            if [ -d "$dir" ]; then
                rti_versions+=("$dir")
            fi
        done
    elif [[ "$(uname -s)" == *"MINGW"* ]] || [[ "$(uname -s)" == *"MSYS"* ]]; then
        # Windows (Git Bash or MSYS2)
        local base_paths=(
            "/c/Program Files/rti_connext_dds-*"
            "/c/Program Files (x86)/rti_connext_dds-*"
        )
        for base_path in "${base_paths[@]}"; do
            for dir in $base_path; do
                if [ -d "$dir" ]; then
                    rti_versions+=("$dir")
                fi
            done
        done
    elif [[ "$(uname -s)" == "Linux" ]]; then
        # Linux
        local base_paths=(
            "/opt/rti_connext_dds-*"
            "/opt/rti.com/rti_connext_dds-*"
            "$HOME/rti_connext_dds-*"
        )
        for base_path in "${base_paths[@]}"; do
            for dir in $base_path; do
                if [ -d "$dir" ]; then
                    rti_versions+=("$dir")
                fi
            done
        done
    fi
    
    echo "${rti_versions[@]}"
}

# Function to get RTI environment script
get_rti_env_script() {
    local nddshome=$1
    local arch=$2
    
    # Find any bash script that starts with rtisetenv
    local script=$(find "$nddshome/resource/scripts" -name "rtisetenv*.bash" 2>/dev/null | head -n 1)
    
    if [ -n "$script" ]; then
        echo "$script"
        return 0
    fi
    
    echo ""
    return 1
}

# Function to set environment variables based on OS
set_environment_variables() {
    local nddshome=$1
    local arch=$2
    
    export NDDSHOME="$nddshome"
    
    if [[ "$(uname -s)" == "Darwin" ]]; then
        # macOS
        export PYTHONPATH="$nddshome/lib/python3.10:$PYTHONPATH"
        export LD_LIBRARY_PATH="$nddshome/lib:$LD_LIBRARY_PATH"
        export DYLD_LIBRARY_PATH="$nddshome/lib:$DYLD_LIBRARY_PATH"
    elif [[ "$(uname -s)" == *"MINGW"* ]] || [[ "$(uname -s)" == *"MSYS"* ]]; then
        # Windows
        export PYTHONPATH="$nddshome/lib/python3.10;$PYTHONPATH"
        export PATH="$nddshome/lib;$PATH"
    elif [[ "$(uname -s)" == "Linux" ]]; then
        # Linux
        export PYTHONPATH="$nddshome/lib/python3.10:$PYTHONPATH"
        export LD_LIBRARY_PATH="$nddshome/lib:$LD_LIBRARY_PATH"
    fi
}

# Main setup process
echo "Starting Genesis LIB setup..."

# Check if Python 3.10 is installed
if ! command -v python3.10 &> /dev/null; then
    echo "Python 3.10 is required but not installed. Please install Python 3.10 first."
    exit 1
fi

# Detect system architecture
ARCH=$(detect_architecture)
echo "Detected architecture: $ARCH"

# Find RTI installations
echo "Searching for RTI Connext DDS installations..."
RTI_INSTALLS=($(find_rti_installations))

if [ ${#RTI_INSTALLS[@]} -eq 0 ]; then
    echo "No RTI Connext DDS installations found in default locations"
    echo "Please enter the path to your RTI Connext DDS installation:"
    read -r NDDSHOME
elif [ ${#RTI_INSTALLS[@]} -eq 1 ]; then
    # If only one installation is found, use it automatically
    NDDSHOME="${RTI_INSTALLS[0]}"
    echo "Found RTI Connext DDS installation: $NDDSHOME"
else
    echo "Found the following RTI Connext DDS installations:"
    for i in "${!RTI_INSTALLS[@]}"; do
        echo "$((i+1)): ${RTI_INSTALLS[$i]}"
    done
    
    echo "Please select an installation (1-${#RTI_INSTALLS[@]}):"
    read -r selection
    
    if [[ $selection =~ ^[0-9]+$ ]] && [ $selection -ge 1 ] && [ $selection -le ${#RTI_INSTALLS[@]} ]; then
        NDDSHOME="${RTI_INSTALLS[$((selection-1))]}"
    else
        echo "Invalid selection. Please enter the path to your RTI Connext DDS installation:"
        read -r NDDSHOME
    fi
fi

# Verify NDDSHOME
if [ ! -d "$NDDSHOME" ]; then
    echo "Error: $NDDSHOME is not a valid directory"
    exit 1
fi

echo "Selected RTI Connext DDS installation: $NDDSHOME"

# Find and verify RTI environment script
RTI_ENV_SCRIPT=$(get_rti_env_script "$NDDSHOME" "$ARCH")
if [ -z "$RTI_ENV_SCRIPT" ]; then
    echo "Could not find RTI environment script for $ARCH"
    echo "Please enter the path to your RTI environment script:"
    read -r RTI_ENV_SCRIPT
fi

if [ ! -f "$RTI_ENV_SCRIPT" ]; then
    echo "Error: $RTI_ENV_SCRIPT is not a valid file"
    exit 1
fi

echo "Found RTI environment script: $RTI_ENV_SCRIPT"

# Create virtual environment
echo "Creating virtual environment..."
python3.10 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Install the package in development mode
echo "Installing genesis-lib in development mode..."
pip install -e .

# Set up RTI Connext DDS environment
set_environment_variables "$NDDSHOME" "$ARCH"

# Source RTI's environment setup script
echo "Sourcing RTI environment script..."
if [[ "$RTI_ENV_SCRIPT" == *.bat ]]; then
    # For Windows batch files, we need to use cmd.exe
    cmd.exe /c "$RTI_ENV_SCRIPT"
else
    source "$RTI_ENV_SCRIPT"
fi

# Check if ANTHROPIC_API_KEY is already set
if [ ! -z "$ANTHROPIC_API_KEY" ]; then
    # Strip quotes even if already set
    ANTHROPIC_API_KEY=$(echo $ANTHROPIC_API_KEY | tr -d "'" | tr -d '"')
    export ANTHROPIC_API_KEY
else
    # Try to get it from .bash_profile
    if [ -f ~/.bash_profile ]; then
        ANTHROPIC_API_KEY=$(grep -o 'ANTHROPIC_API_KEY=.*' ~/.bash_profile | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    fi
    
    # If still not set, try .env file
    if [ -z "$ANTHROPIC_API_KEY" ] && [ -f .env ]; then
        ANTHROPIC_API_KEY=$(grep -o 'ANTHROPIC_API_KEY=.*' .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    fi
    
    # Export if we found it
    if [ ! -z "$ANTHROPIC_API_KEY" ]; then
        # Remove any quotes from the API key before exporting
        ANTHROPIC_API_KEY=$(echo $ANTHROPIC_API_KEY | tr -d "'" | tr -d '"')
        export ANTHROPIC_API_KEY
    else
        echo "Warning: ANTHROPIC_API_KEY not found in environment, .bash_profile, or .env file"
    fi
fi

# Check if OPENAI_API_KEY is already set
if [ ! -z "$OPENAI_API_KEY" ]; then
    # Check if it's a placeholder value
    if [[ "$OPENAI_API_KEY" == *"your"*"key"* ]] || 
       [[ "$OPENAI_API_KEY" == *"api"*"key"* ]] || 
       [[ "$OPENAI_API_KEY" == *"openai"*"key"* ]] || 
       [[ "$OPENAI_API_KEY" == *"placeholder"* ]] || 
       [[ "$OPENAI_API_KEY" == *"<"*">"* ]]; then
        echo "Warning: OPENAI_API_KEY appears to be a placeholder value. Attempting to find a real key."
        unset OPENAI_API_KEY
    else
        # Strip quotes even if already set
        OPENAI_API_KEY=$(echo $OPENAI_API_KEY | tr -d "'" | tr -d '"')
        export OPENAI_API_KEY
    fi
fi

# If OPENAI_API_KEY is not set or was a placeholder, try to get it from .bash_profile
if [ -z "$OPENAI_API_KEY" ]; then
    # Try to get it from .bash_profile using a more robust approach
    if [ -f ~/.bash_profile ]; then
        # First try the exact export line
        OPENAI_API_KEY=$(grep 'export OPENAI_API_KEY=' ~/.bash_profile | sed 's/export OPENAI_API_KEY=//')
        
        # If that doesn't work, try a more general approach
        if [ -z "$OPENAI_API_KEY" ]; then
            OPENAI_API_KEY=$(grep 'OPENAI_API_KEY=' ~/.bash_profile | sed 's/.*OPENAI_API_KEY=//')
        fi
    fi
    
    # If still not set, try .env file
    if [ -z "$OPENAI_API_KEY" ] && [ -f .env ]; then
        OPENAI_API_KEY=$(grep 'OPENAI_API_KEY=' .env | sed 's/.*OPENAI_API_KEY=//')
    fi
    
    # Export if we found it
    if [ ! -z "$OPENAI_API_KEY" ]; then
        # Remove any quotes from the API key before exporting
        OPENAI_API_KEY=$(echo $OPENAI_API_KEY | tr -d "'" | tr -d '"')
        export OPENAI_API_KEY
    else
        echo "Warning: OPENAI_API_KEY not found in environment, .bash_profile, or .env file"
        # Set a placeholder value for testing purposes
        export OPENAI_API_KEY="your_openai_api_key_here"
    fi
fi

echo "Setup complete. RTI Connext DDS environment configured."
echo "Python Version: $(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "NDDSHOME: $NDDSHOME"
echo "PYTHONPATH: $PYTHONPATH"
if [[ "$(uname -s)" == "Darwin" ]]; then
    echo "DYLD_LIBRARY_PATH: $DYLD_LIBRARY_PATH"
elif [[ "$(uname -s)" == "Linux" ]]; then
    echo "LD_LIBRARY_PATH: $LD_LIBRARY_PATH"
fi
if [ ! -z "$ANTHROPIC_API_KEY" ]; then
    echo "ANTHROPIC_API_KEY is set"
else
    echo "ANTHROPIC_API_KEY is not set"
fi

if [ ! -z "$OPENAI_API_KEY" ]; then
    echo "OPENAI_API_KEY is set"
else
    echo "OPENAI_API_KEY is not set"
fi

echo "To activate the virtual environment, run:"
echo "source venv/bin/activate"

