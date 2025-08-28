# Cross‑Repo Reporting and AI Agent Access (Draft)

Genesis Business needs to generate reports across `genesis-lib`, `genesis-examples`, and potentially `genesis-viewer`. This plan outlines safe approaches that work even when AI agents are limited to the current repo.

## Goals

- Allow business reporting to read code and metrics from multiple repos.
- Keep public repos public; keep business repo private.
- Minimize friction for AI agents that can only see the current workspace.

## Options Overview

- A) Submodules in Business (Workspace pattern)
- B) Producer workflows push metrics into Business (artifact/PR ingestion)
- C) Business CI fetches repos (central scheduler)
- D) On‑demand local clone script (owner‑run staging)
- E) API endpoints or mirrored snapshots (last resort)

## A) Git Submodules in Business

Make `genesis-business` a workspace repo that includes the public repos as submodules.

- Structure:
  - `genesis-business/`
    - `external/genesis-lib/` (git submodule)
    - `external/genesis-examples/` (git submodule)
- Pros: AI agents see files as directories within the same workspace; offline compatible once cloned.
- Cons: Submodule UX and update discipline; read‑only for agents (good), but still requires user to initialize submodules.
- Operations:
  - Add: `git submodule add https://github.com/org/genesis-lib external/genesis-lib`
  - Init/update: `git submodule update --init --recursive`
  - Update: `git submodule update --remote --merge`
- Recommendation: Good default for interactive analysis inside Business.

## B) Producer Workflows Push Metrics into Business

Each source repo runs CI to compute metrics (e.g., `docs/tools/generate_repo_metrics.py`) and pushes JSON to the Business repo via a bot token.

- Flow:
  1. On push or nightly, `genesis-lib` computes metrics → commits PR to `genesis-business` under `metrics/genesis-lib/…`.
  2. `genesis-examples` does the same under `metrics/genesis-examples/…`.
  3. Business accumulates all metrics; agents read from `metrics/` without cross‑repo access.
- Pros: Business repo is the single source; agents do not need network or multi‑repo visibility.
- Cons: Requires PAT/secret in public repos; ensure write is restricted to a path in Business repo.
- Recommendation: Best for automated reporting and historical records.

## C) Business CI Fetches Repos (Central Scheduler)

A scheduled workflow in `genesis-business` checks out the latest `genesis-lib` and `genesis-examples`, runs metrics locally, and commits results to `metrics/`.

- Pros: Centralized secrets and policy; no write access granted to public repos.
- Cons: Requires GitHub Actions in Business repo; agents still read only Business.
- Recommendation: Strong security posture; complements Option A (submodules) for local exploration.

## D) On‑Demand Local Clone Script (Owner‑Run)

A script (kept in Business) clones the other repos into `external/` when the owner runs it locally. AI agents then see a unified workspace.

- Pros: No CI dependencies; works with non‑GitHub environments; easy to clean.
- Cons: Manual step; requires local credentials; agents may be sandboxed from network so owner must run it.
- Recommendation: Useful fallback or for air‑gapped environments.

## E) API Endpoints or Snapshots

Exposing repository state via APIs or periodic tarball snapshots stored in Business. Generally less desirable than Options B/C.

- Pros: Decouples from Git tooling.
- Cons: More infrastructure; potential security/usability issues.

## Suggested Hybrid

- Use Option B or C to keep `metrics/` current in `genesis-business` (no agent cross‑repo access needed for reporting).
- Also use Option A submodules for interactive deep dives when desired.

## Implementation Artifacts (Templates)

- Workflows:
  - `docs/planning/workflows/cross-repo-metrics.yml.txt` (Business CI pulls repos and writes `metrics/`).
  - `docs/planning/workflows/export-metrics.yml.txt` (Source repos push metrics PRs to Business).
- Schema:
  - `docs/planning/schemas/repo_metrics.schema.json` for consistent metrics JSON.
- Workspace setup:
  - `docs/planning/templates/WORKSPACE_SETUP.genesis-business.md` for submodules and local clone script recipe.

## Security & Access

- Use a dedicated machine user/PAT with least privilege to open PRs into Business.
- Restrict PR target path to `metrics/<repo>/` and enforce via CI checks.
- For Business CI, use repository secrets; avoid storing tokens in public repos.

## AI Agent Considerations

- Agents limited to current repo can:
  - Read `metrics/` JSON to generate reports without touching other repos.
  - If submodules are present and initialized, read code across repos within the same workspace.
- For read‑only modes, prefer Options B/C so the data they need lives inside Business.

