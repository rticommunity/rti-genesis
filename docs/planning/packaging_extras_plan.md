# Packaging Extras Plan (Draft)

This draft outlines planned optional dependency extras for `genesis-lib`. No behavior changes yet; current `setup.py` remains the source of truth.

## Proposed Extras

- openai: OpenAI client dependencies
- anthropic: Anthropic client dependencies
- viz: Optional visualization/web UI helpers

## Example Usage

- Base: `pip install genesis-lib`
- With OpenAI: `pip install genesis-lib[openai]`

## Mapping (to be implemented later)

- Move metadata from `setup.py` to `pyproject.toml` `[project]` with `optional-dependencies`.
- Keep base install minimal; shift provider/feature-specific deps into the extras above.
- Gate tests by markers and load extras in CI as needed.

## Notes

- DDS is a core runtime requirement installed outside pip (vendor installer). We will document DDS installation and env setup in a shared "DDS Setup" doc and remove any attempt to pull `rti-connext` via pip.
- Maintain backward compatibility during migration; publish a migration note in the changelog.
