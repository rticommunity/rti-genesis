# DDS Setup Doc Outline (Draft)

This outline defines the shared DDS installation and configuration guide referenced by both `genesis-lib` and `genesis-examples`. It treats DDS as a core requirement.

## Scope

- Target RTI Connext DDS version: 7.3.0+
- Platforms: macOS, Linux, Windows
- Audience: users running the library and examples; CI maintainers

## Install RTI Connext DDS

- Download and install RTI Connext DDS from the vendor site.
- Default install locations:
  - macOS/Linux: `$HOME/rti_connext_dds-7.3.0` (or similar)
  - Windows: `C:\path\to\rti_connext_dds-7.3.0`
- Connext Express: to be default path. Subsection will walk through obtaining/activating Express (TBD with vendor guidance).

## Environment Configuration

- Set `NDDSHOME` to the installation root.
- Add library paths:
  - Linux: add appropriate `lib` directory to `LD_LIBRARY_PATH`.
  - macOS: add appropriate `lib` directory to `DYLD_LIBRARY_PATH`.
  - Windows: add appropriate `bin` directory to `Path`.
- License file (as applicable): set `RTI_LICENSE_FILE` or follow Express guidance.
- Recommended: source vendor scripts to set env reliably:
  - `rticonnextdds-installation/scripts/rtisetenv.*` (choose the script matching your shell/platform)

## Quick Verification

- CLI tools:
  - `rtiddsspy -v`
  - `rtiddsgen -version`
- Python-level smoke check (outline): run a minimal publisher/subscriber or the project’s DDS self-check command.

## Troubleshooting

- Common issues: missing env vars, wrong architecture path, SIP/Quarantine on macOS, DLL search path on Windows.
- How to print effective env and resolve path mismatches.

## CI Considerations

- Options:
  - Self-hosted runner or build agent with Connext preinstalled.
  - Nightly/full matrix with DDS; PR jobs skip heavy DDS tests with clear markers and logs.

