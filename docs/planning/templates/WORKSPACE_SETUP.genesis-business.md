# Genesis Business Workspace Setup (Draft)

This guide shows how to assemble a local workspace so tools and AI agents can see `genesis-business`, `genesis-lib`, and `genesis-examples` together.

## Option 1: Git Submodules

```bash
mkdir -p external
git submodule add https://github.com/org/genesis-lib external/genesis-lib
git submodule add https://github.com/org/genesis-examples external/genesis-examples
# Initialize when cloning:
git submodule update --init --recursive
```

Update to latest main branches:
```bash
git submodule update --remote --merge
```

## Option 2: On-Demand Clone Script

Create `scripts/clone_repos.sh` in this repo (not versioned by default) to clone siblings:

```bash
#!/usr/bin/env bash
set -euo pipefail
mkdir -p external
cd external
[ -d genesis-lib ] || git clone git@github.com:org/genesis-lib.git
[ -d genesis-examples ] || git clone git@github.com:org/genesis-examples.git
```

Run it before opening the workspace with your AI tool.

## Notes

- Keep `external/` out of packaging and reporting outputs unless explicitly needed.
- Use read-only deploy keys if you do not need write access from the local environment.

