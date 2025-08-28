# Documentation Index

This folder is organized to make technical docs easy to find and keep business materials separate.

- guides/: How‑to and conceptual guides (function flow, RPC usage, API overviews)
- reference/: Canonical references and specs (DDS RPC cheat sheets, identifiers)
- agents/: Agent‑facing docs and checklists
- planning/: Roadmaps, plans, implementation checklists
  - planning/repository_separation_plan.md: Target repo split and rollout
  - planning/cross_repo_reporting_plan.md: Cross-repo metrics and agent access
  - planning/dds_setup_doc_outline.md: Draft for DDS setup doc
  - planning/RELEASING.md: Draft release steps (TestPyPI/PyPI)
  - planning/MIGRATION_CHECKLIST.md: End-to-end migration checklist
  - planning/testing_strategy.md: Preserving run_scripts and phased testing plan
  - planning/pyproject.example.toml: PEP 621 example (not active)
  - planning/workflows/: CI templates (not active)
  - planning/schemas/viewer_topology.schema.json: Viewer data contract (draft)
  - planning/schemas/repo_metrics.schema.json: Metrics JSON schema (draft)
  - planning/templates/: README templates for future repos
 - setup/: User setup guides
  - setup/dds_setup.md: RTI Connext DDS installation and environment setup
- architecture/: System design and analysis (memory, monitoring, modularity)
  - architecture.md: High-level architecture overview
  - architecture_detailed.md: Detailed architecture (APIs, files, flows)
- notes/: Misc notes, clarifications, and issue logs
- papers/: Research/white‑paper style artifacts
- tools/: Helper scripts used by documentation
  - docs/tools/github_comments.py
  - docs/tools/generate_progress_report.py
  - docs/tools/generate_repo_metrics.py
- reports/: Generated reports and reporting utilities
  - activity_metrics.md: Overall repo metrics (commits, churn, LOC)
  - project_progress_report.md: Plan ⇄ implementation correlation
  - topics/: Per-topic metrics (e.g., service_registry.md, simulation_integration.md)
- business/: SBIR reports, demos, presentations, proposals

If you notice broken links after the restructure, search/replace paths to new locations.
