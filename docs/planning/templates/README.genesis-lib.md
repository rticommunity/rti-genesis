# Genesis LIB

Core Python library for building Genesis networks on top of RTI Connext DDS.

## Install

1) Install RTI Connext DDS (7.3.0+) and configure env (see DDS Setup).
2) `pip install genesis-lib`

Optional providers: `pip install genesis-lib[openai,anthropic]`

## Quickstart

```python
from genesis_lib.interface import Interface

iface = Interface(...)
iface.run()
```

## DDS Setup

See the shared guide in this repo’s docs.

## Development

- Python 3.10
- `pytest`, `mypy`, `ruff`
- Run unit tests locally; DDS-heavy tests may require local DDS install.

## License

TBD

