# Genesis Examples

Runnable examples and demo topologies built on `genesis-lib`.

## Prerequisites

- Install RTI Connext DDS (7.3.0+) and configure env (see DDS Setup).
- `pip install genesis-lib` (from PyPI)

## Running

Each example has a README and scripts under `run_scripts/`.

```bash
./run_scripts/run_all_tests.sh
```

## Troubleshooting

- Verify DDS tools: `rtiddsspy -v`
- Check `NDDSHOME` and library paths

## Contributing

Please propose new examples via PRs; keep dependencies minimal.

