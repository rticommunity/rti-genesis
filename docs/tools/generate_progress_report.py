#!/usr/bin/env python3
"""
Generate a project progress report by scanning planning docs and correlating
them with implementation files. Uses git history to extract creation/last
update dates and commit counts.

Outputs: docs/reports/project_progress_report.md
"""

import subprocess
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"

# Planning docs to track
PLANNING_DOCS = [
    DOCS / "planning" / "unified_monitoring_system_plan.md",
    DOCS / "planning" / "event_driven_function_discovery_plan.md",
    DOCS / "planning" / "monitoring_v3_implementation_plan.md",
    DOCS / "planning" / "graph_topology_abstraction_plan.md",
    DOCS / "planning" / "function_injection_plan.md",
    DOCS / "planning" / "genesis_implementation_plan.md",
]

# Map plan docs to related implementation files/folders
RELATED_IMPL = {
    "unified_monitoring_system_plan.md": [
        "genesis_lib/graph_monitoring.py",
        "genesis_lib/graph_state.py",
        "genesis_lib/monitored_agent.py",
        "genesis_lib/monitored_interface.py",
        "genesis_lib/enhanced_service_base.py",
    ],
    "event_driven_function_discovery_plan.md": [
        "genesis_lib/function_discovery.py",
    ],
    "monitoring_v3_implementation_plan.md": [
        "genesis_lib/graph_monitoring.py",
        "genesis_lib/graph_state.py",
        "genesis_lib/enhanced_service_base.py",
    ],
    "graph_topology_abstraction_plan.md": [
        "examples/GraphInterface/server.py",
        "feature_development/interface_abstraction/",
        "genesis_lib/web/",
    ],
    "function_injection_plan.md": [
        "genesis_lib/decorators.py",
        "genesis_lib/schema_generators.py",
        "genesis_lib/openai_genesis_agent.py",
    ],
    "genesis_implementation_plan.md": [
        "genesis_lib/",
    ],
}

def git(*args, cwd=ROOT):
    return subprocess.check_output(["git", *args], cwd=str(cwd)).decode().strip()

def first_commit_date(path: Path) -> str:
    try:
        out = git("log", "--follow", "--format=%ad", "--date=short", "--", str(path))
        return out.splitlines()[0] if out else "N/A"
    except Exception:
        return "N/A"

def last_commit_date(path: Path) -> str:
    try:
        out = git("log", "-1", "--format=%ad", "--date=short", "--", str(path))
        return out if out else "N/A"
    except Exception:
        return "N/A"

def commit_count(path: Path) -> int:
    try:
        out = git("rev-list", "--count", "HEAD", "--", str(path))
        return int(out) if out else 0
    except Exception:
        return 0

def contributors(path: Path) -> int:
    try:
        out = git("shortlog", "-sn", "--", str(path))
        return len(out.splitlines())
    except Exception:
        return 0

def get_status_for(doc_path: Path) -> str:
    status_file = DOCS / "docs_status.md"
    try:
        text = status_file.read_text()
        # Simple containment by basename
        name = doc_path.as_posix()
        base = doc_path.name
        if base in text and "Up-to-Date" in text:
            return "Up-to-date"
        if base in text and "Needs Major Update" in text:
            return "Needs major update"
        if base in text and "Needs Minor Update" in text:
            return "Needs minor update"
        if base in text and "Merge/Consolidate Candidates" in text:
            return "Merge candidate"
        if base in text and "Backlog/Planning" in text:
            return "Active planning"
        if base in text and "Historical/Background" in text:
            return "Historical"
    except Exception:
        pass
    return "Unclassified"

def section_for_impl(rel_path: str) -> dict:
    p = ROOT / rel_path
    exists = p.exists()
    if p.is_dir():
        # For dirs, compute last commit and count across the dir
        created = first_commit_date(p)
        updated = last_commit_date(p)
        count = commit_count(p)
        contrib = contributors(p)
    else:
        created = first_commit_date(p)
        updated = last_commit_date(p)
        count = commit_count(p)
        contrib = contributors(p)
    return {
        "path": rel_path,
        "exists": exists,
        "created": created,
        "updated": updated,
        "commits": count,
        "contributors": contrib,
    }

def build_report() -> str:
    ts = datetime.utcnow().strftime("%Y-%m-%d")
    lines = []
    lines.append(f"# Project Progress Report ({ts})")
    lines.append("")
    lines.append("This report summarizes planning documents, their history, current status, and related implementation artifacts.")
    lines.append("")
    for doc in PLANNING_DOCS:
        rel = doc.relative_to(ROOT).as_posix()
        if not doc.exists():
            continue
        created = first_commit_date(doc)
        updated = last_commit_date(doc)
        count = commit_count(doc)
        contrib = contributors(doc)
        status = get_status_for(doc)
        lines.append(f"## {rel}")
        lines.append(f"- Status: {status}")
        lines.append(f"- Created: {created}  |  Last Updated: {updated}  |  Commits: {count}  |  Contributors: {contrib}")
        # Related implementation
        impls = RELATED_IMPL.get(doc.name, [])
        if impls:
            lines.append("- Related Implementation:")
            for imp in impls:
                info = section_for_impl(imp)
                exists_flag = "✅" if info["exists"] else "❌"
                lines.append(
                    f"  - {exists_flag} `{info['path']}` — Created: {info['created']} | Updated: {info['updated']} | Commits: {info['commits']} | Contributors: {info['contributors']}"
                )
        lines.append("")
    return "\n".join(lines)

def main():
    out_dir = DOCS / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "project_progress_report.md"
    report = build_report()
    report_path.write_text(report)
    print(f"Wrote {report_path}")

if __name__ == "__main__":
    main()

