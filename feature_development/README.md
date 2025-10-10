# Feature Development Workspace

This directory hosts in-progress feature work, prototypes, and scoped tests that should not affect the main library until promoted.

- `interface_abstraction/`: work toward decoupling interfaces from DDS for topology graph building and visualization.

Usage:
- Work here is isolated; keep prototypes and tests local until ready to merge into `genesis_lib` and examples.
- Prefer running tests via the provided shell runner to avoid long-lived processes.
