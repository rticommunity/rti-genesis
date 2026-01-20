# GENESIS Installation Guide

This guide covers the complete installation process for GENESIS, including RTI Connext DDS setup.

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **Operating System** | macOS or Linux |
| **Python** | 3.10.x (required) |
| **RTI Connext DDS** | 7.3.0 or later |
| **API Keys** | OpenAI and/or Anthropic (for AI features) |

---

## Quick Start

If you already have RTI Connext DDS installed:

```bash
# 1. Run the setup script
./setup.sh

# 2. Activate the virtual environment
source .venv/bin/activate

# 3. Verify RTI configuration
./rti_setup.sh --verify
```

---

## Step 1: Install RTI Connext DDS

GENESIS requires RTI Connext DDS. Use our helper script to streamline the process:

### Option A: Interactive Setup (Recommended)

```bash
./rti_setup.sh
```

This launches an interactive menu to:
- Check for existing installations
- Open the license request page (with 60-day eval pre-selected)
- Configure environment variables
- Install license files
- Verify your setup

### Option B: Command-Line Options

```bash
# Check if RTI Connext is already installed
./rti_setup.sh --check

# Request a new license (opens browser with 60-day eval pre-selected)
./rti_setup.sh --request

# Configure environment after installation
./rti_setup.sh --configure

# Install a license file
./rti_setup.sh --license

# Full verification
./rti_setup.sh --verify

# Show download instructions
./rti_setup.sh --instructions
```

### Manual Installation Steps

If you prefer manual setup:

#### 1. Request a License

1. Visit [https://www.rti.com/get-connext](https://www.rti.com/get-connext)
2. Select **"Free 60-day standard evaluation"**
3. Fill out the form and complete the reCAPTCHA
4. Click Submit
5. You'll be redirected to a download page

#### 2. Download the Software

Download the **host bundle** for your platform:

| Platform | File |
|----------|------|
| macOS (Apple Silicon) | `rti_connext_dds-7.3.0-pro-host-arm64Darwin.dmg` |
| macOS (Intel) | `rti_connext_dds-7.3.0-pro-host-x64Darwin.dmg` |
| Linux (x64) | `rti_connext_dds-7.3.0-pro-host-x64Linux.run` |

#### 3. Install

**macOS:**
```bash
# Mount the DMG and run the installer
# Default installation: /Applications/rti_connext_dds-7.3.0
```

**Linux:**
```bash
chmod +x rti_connext_dds-7.3.0-pro-host-x64Linux.run
./rti_connext_dds-7.3.0-pro-host-x64Linux.run
# Follow the installation wizard
```

#### 4. Get Your License File

- Check your email for `rti_license.dat` (usually arrives within minutes)
- Copy it to your RTI installation directory

```bash
cp ~/Downloads/rti_license.dat /Applications/rti_connext_dds-7.3.0/
```

#### 5. Configure Environment Variables

Add to your `~/.bashrc`, `~/.zshrc`, or `~/.profile`:

**macOS (Apple Silicon):**
```bash
export NDDSHOME="/Applications/rti_connext_dds-7.3.0"
export PATH="$NDDSHOME/bin:$PATH"
export DYLD_LIBRARY_PATH="$NDDSHOME/lib/arm64Darwin20clang12.0:$DYLD_LIBRARY_PATH"
```

**macOS (Intel):**
```bash
export NDDSHOME="/Applications/rti_connext_dds-7.3.0"
export PATH="$NDDSHOME/bin:$PATH"
export DYLD_LIBRARY_PATH="$NDDSHOME/lib/x64Darwin17clang9.0:$DYLD_LIBRARY_PATH"
```

**Linux:**
```bash
export NDDSHOME="$HOME/rti_connext_dds-7.3.0"
export PATH="$NDDSHOME/bin:$PATH"
export LD_LIBRARY_PATH="$NDDSHOME/lib/x64Linux4gcc7.3.0:$LD_LIBRARY_PATH"
```

Then reload your shell:
```bash
source ~/.zshrc  # or ~/.bashrc
```

---

## Step 2: Install GENESIS

```bash
# Create and activate virtual environment
python3.10 -m venv .venv
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install GENESIS
pip install .

# Verify installation
python -c "import genesis_lib; print('OK:', genesis_lib.__file__)"
```

Or use the automated setup:
```bash
./setup.sh
```

---

## Step 3: Configure API Keys

Set your LLM API keys:

```bash
export OPENAI_API_KEY="your_openai_key"
export ANTHROPIC_API_KEY="your_anthropic_key"
```

Add these to your shell configuration for persistence.

---

## Step 4: Verify Everything

```bash
# Verify RTI setup
./rti_setup.sh --verify

# Quick import test
python -c "import genesis_lib; print('OK')"

# Check rtiddsspy is accessible
rtiddsspy --help

# Run the test suite (optional)
cd tests && ./run_all_tests.sh
```

---

## RTI License Types

| License Type | Best For | Duration | Limits |
|--------------|----------|----------|--------|
| **60-Day Evaluation** | Full prototyping | 60 days | None |
| **Connext Express** | Small deployments | Perpetual | Participant-limited |
| **University Program** | Research/academia | Perpetual | Non-commercial |

> **Recommendation:** Start with the 60-day evaluation for full functionality. Contact RTI for extensions or production licenses.

---

## Troubleshooting

### NDDSHOME not set
```bash
# Run the configuration helper
./rti_setup.sh --configure
```

### rtiddsspy not found
Ensure NDDSHOME is set and the bin directory is in your PATH:
```bash
export PATH="$NDDSHOME/bin:$PATH"
```

### License file not found
```bash
# Install license using helper
./rti_setup.sh --license

# Or manually copy
cp /path/to/rti_license.dat $NDDSHOME/
```

### Python version mismatch
GENESIS requires Python 3.10.x:
```bash
python3.10 --version  # Should show 3.10.x
```

### QoS mismatch in DDS tests
Ensure `spy_transient.xml` is present in the project root.

---

## Directory Structure

After installation, your setup should look like:

```
Genesis_LIB/
├── .venv/                  # Python virtual environment
├── genesis_lib/            # Core library
├── examples/               # Example agents and services
├── tests/                  # Test suite
├── rti_setup.sh           # RTI setup helper
├── setup.sh               # Python setup script
├── spy_transient.xml      # DDS QoS configuration
└── INSTALL.md             # This file
```

---

## Next Steps

- Read [QUICKSTART.md](QUICKSTART.md) to build your first agent
- Explore [examples/](examples/) for working demonstrations
- Check [docs/](docs/) for detailed documentation

---

## Support

For RTI Connext issues: [RTI Support](https://www.rti.com/support)

For GENESIS issues: [genesis@rti.com](mailto:genesis@rti.com)

---

*(c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.*

*RTI grants Licensee a license to use, modify, compile, and create derivative works of the Software. Licensee has the right to distribute object form only for use with RTI products. The Software is provided "as is", with no warranty of any type, including any warranty for fitness for any purpose. RTI is under no obligation to maintain or support the Software. RTI shall not be liable for any incidental or consequential damages arising out of the use or inability to use the software.*
