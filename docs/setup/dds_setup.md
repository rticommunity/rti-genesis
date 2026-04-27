# RTI Connext DDS Setup

Genesis relies on RTI Connext DDS. Install and configure DDS before running the library or examples.

Supported version: 7.3.0+

## 1) Install Connext DDS

- Download and install from RTI. Default install locations:
  - macOS/Linux: `$HOME/rti_connext_dds-7.3.0`
  - Windows: `C:\\path\\to\\rti_connext_dds-7.3.0`
- Connext Express: Planned default license (TBD). A future revision will include steps to obtain/activate Express.

## 2) Configure Environment

Set `NDDSHOME` and platform-specific library paths. Prefer using RTI’s `rtisetenv` helper.

macOS (zsh/bash):
```bash
export NDDSHOME="$HOME/rti_connext_dds-7.3.0"
source "$NDDSHOME/resource/scripts/rtisetenv_mac.sh"
# If needed: export DYLD_LIBRARY_PATH="$NDDSHOME/lib/macosx:$DYLD_LIBRARY_PATH"
```

Linux (bash):
```bash
export NDDSHOME="$HOME/rti_connext_dds-7.3.0"
source "$NDDSHOME/resource/scripts/rtisetenv_x64Linux4gcc7.3.0.bash"
# If needed: export LD_LIBRARY_PATH="$NDDSHOME/lib/x64Linux4gcc7.3.0:$LD_LIBRARY_PATH"
```

Windows (PowerShell):
```powershell
$env:NDDSHOME="C:\\path\\to\\rti_connext_dds-7.3.0"
# Consider running the RTI-provided batch file matching your platform
# and verify Path includes the appropriate bin directory.
```

License file (if applicable):
```bash
export RTI_LICENSE_FILE="$NDDSHOME/rti_license.dat"
```

## 3) Verify Installation

CLI tools:
```bash
rtiddsspy -v
rtiddsgen -version
```

Python quick check (example):
```bash
python - <<'PY'
print('NDDSHOME=', __import__('os').environ.get('NDDSHOME'))
print('ok')
PY
```

## 4) Troubleshooting

- Ensure `NDDSHOME` points to the install root (no trailing slashes).
- Verify library paths (`DYLD_LIBRARY_PATH` on macOS, `LD_LIBRARY_PATH` on Linux) include the correct architecture dir.
- On macOS, address Gatekeeper by allowing RTI binaries to run if prompted.
- On Windows, ensure DLL directories are on `Path` for the current shell.

## 5) CI Considerations

- Use a self-hosted runner or prebuilt image with DDS installed for full tests.
- Public CI may skip DDS-heavy tests; clearly mark and document them.

