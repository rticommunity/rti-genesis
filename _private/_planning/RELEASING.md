# Releasing Genesis LIB (Draft)

This draft describes manual steps for TestPyPI and PyPI releases without changing current behavior. It is safe to keep in the repo until migration.

## Prerequisites

- Python 3.10
- Accounts: TestPyPI and PyPI, API tokens stored as env vars (`TEST_PYPI_TOKEN`, `PYPI_TOKEN`).
- `build`, `twine` installed in your virtualenv.
- DDS installed and configured if running integration checks.

## Versioning

- Follow SemVer. Update version in `setup.py` (temporary) and changelog.
- Tag format: `vMAJOR.MINOR.PATCH`.

## Build

```bash
rm -rf dist build *.egg-info
python -m build  # uses pyproject [build-system] and setup.py
```

## TestPyPI Upload

```bash
python -m twine upload --repository testpypi dist/*
# or
twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

Verify with a clean venv:

```bash
python -m venv .venv-test
source .venv-test/bin/activate
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple genesis-lib
python -c "import genesis_lib, sys; print('ok', genesis_lib.__version__)"
```

## PyPI Upload

After validation on TestPyPI:

```bash
twine upload dist/*
```

## Post-Release

- Push git tag and GitHub release notes.
- Update docs site and example repo dependency pins.
- Announce deprecations (if any) and next milestone.

## CI (Future)

- GitHub Actions templates live under `docs/planning/workflows/` and are not active.
- Plan: publish on tag push; build matrix for Python 3.10; optional self-hosted runner for DDS tests.

