#!/usr/bin/env python3
"""
Generate detailed repository activity metrics for reporting.

Outputs:
- docs/reports/activity_metrics.md (overall + area summaries)
- docs/reports/topics/service_registry.md (SBIR-friendly metrics section)
- docs/reports/topics/simulation_integration.md (SBIR-friendly metrics section)

Metrics:
- Overall commits, contributors, files changed, additions/deletions
- Monthly commit histogram
- Current LOC by folder (rough count)
- Per-area breakdowns with: commits, adds/dels, files changed, contributors,
  date window, top files by churn, top commit subjects, current LOC in area
"""

import subprocess
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime
import re
import os

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "docs" / "reports"
TOPIC_DIR = REPORT_DIR / "topics"

AREAS = {
    "Service Registry": [
        "genesis_lib/function_discovery.py",
        "genesis_lib/enhanced_service_base.py",
        "genesis_lib/rpc_service.py",
        "genesis_lib/rpc_client.py",
        "genesis_lib/datamodel.py",
        "genesis_lib/config/datamodel.xml",
        "genesis_lib/openai_genesis_agent.py",
    ],
    "Simulation Integration": [
        "examples/DroneGraphDemo/",
        "examples/GraphInterface/",
        "genesis_lib/graph_monitoring.py",
        "genesis_lib/graph_state.py",
        "genesis_lib/web/",
        "genesis_lib/monitored_agent.py",
        "genesis_lib/monitored_interface.py",
    ],
}

CODE_EXT = {".py", ".sh", ".xml", ".js", ".ts", ".html", ".css"}

def git(args, cwd=ROOT):
    return subprocess.check_output(["git", *args], cwd=str(cwd)).decode("utf-8", errors="ignore")

def overall_commits():
    try:
        return int(git(["rev-list", "--count", "HEAD"]).strip())
    except Exception:
        return 0

def overall_contributors():
    try:
        out = git(["shortlog", "-sn", "HEAD"]).strip().splitlines()
        return len(out), out[:10]
    except Exception:
        return 0, []

def monthly_histogram():
    try:
        out = git(["log", "--date=short", "--format=%ad"]).strip().splitlines()
        months = Counter()
        for d in out:
            if d:
                months[d[:7]] += 1
        return dict(sorted(months.items()))
    except Exception:
        return {}

def numstat(paths=None):
    args = ["log", "--numstat", "--format=%H"]
    if paths:
        args += ["--", *paths]
    try:
        out = git(args)
        adds = dels = files = 0
        for line in out.splitlines():
            if re.match(r"^[0-9-]+\t[0-9-]+\t", line):
                a, d, f = line.split("\t", 2)
                if a != "-":
                    adds += int(a)
                if d != "-":
                    dels += int(d)
                files += 1
        return adds, dels, files
    except Exception:
        return 0, 0, 0

def area_metrics(area_paths):
    adds, dels, files = numstat(area_paths)
    try:
        contrib_out = git(["shortlog", "-sn", "--"] + area_paths).strip().splitlines()
        contrib_count = len(contrib_out)
        top_contrib = contrib_out[:5]
    except Exception:
        contrib_count = 0
        top_contrib = []
    try:
        commit_count = int(git(["rev-list", "--count", "HEAD", "--"] + area_paths).strip())
    except Exception:
        commit_count = 0
    # First/last dates
    try:
        first = git(["log", "--reverse", "--format=%ad", "--date=short", "--"] + area_paths).splitlines()
        first_date = first[0] if first else "N/A"
    except Exception:
        first_date = "N/A"
    try:
        last_date = git(["log", "-1", "--format=%ad", "--date=short", "--"] + area_paths).strip()
    except Exception:
        last_date = "N/A"
    # Top files by churn
    top_files = []
    try:
        out = git(["log", "--numstat", "--format=%H", "--"] + area_paths)
        churn = defaultdict(lambda: [0, 0])  # path -> [adds, dels]
        for line in out.splitlines():
            if re.match(r"^[0-9-]+\t[0-9-]+\t", line):
                a, d, f = line.split("\t", 2)
                a = 0 if a == "-" else int(a)
                d = 0 if d == "-" else int(d)
                churn[f][0] += a
                churn[f][1] += d
        top_files = sorted(churn.items(), key=lambda kv: kv[1][0] + kv[1][1], reverse=True)[:10]
    except Exception:
        pass
    # Top commits (subjects)
    top_subjects = []
    try:
        out = git(["log", "-n", "15", "--date=short", "--format=%h|%ad|%an|%s", "--"] + area_paths)
        top_subjects = out.strip().splitlines()
    except Exception:
        pass
    # Current LOC across area
    loc = 0
    for p in area_paths:
        abs_p = ROOT / p
        if abs_p.is_dir():
            loc += current_loc_by_folder(abs_p)
        elif abs_p.exists():
            try:
                loc += sum(1 for _ in abs_p.open("r", errors="ignore"))
            except Exception:
                pass
    return {
        "adds": adds,
        "dels": dels,
        "files": files,
        "commits": commit_count,
        "contributors": contrib_count,
        "top_contrib": top_contrib,
        "first_date": first_date,
        "last_date": last_date,
        "top_files": top_files,
        "top_subjects": top_subjects,
        "loc": loc,
    }

def current_loc_by_folder(folder: Path):
    total = 0
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix in CODE_EXT:
            try:
                total += sum(1 for _ in p.open("r", errors="ignore"))
            except Exception:
                pass
    return total

def build_report():
    ts = datetime.utcnow().strftime("%Y-%m-%d")
    lines = []
    lines.append(f"# Repository Activity Metrics ({ts})\n")
    # Overall
    commits = overall_commits()
    contrib_count, top_contrib = overall_contributors()
    adds, dels, files = numstat()
    first_date = git(["log", "--reverse", "--format=%ad", "--date=short"]).splitlines()
    last_date = git(["log", "-1", "--format=%ad", "--date=short"]).strip()
    first_date = first_date[0] if first_date else "N/A"
    lines.append("## Overall\n")
    lines.append(f"- Commits: {commits}")
    lines.append(f"- Contributors: {contrib_count}")
    if top_contrib:
        lines.append("- Top Contributors:")
        for row in top_contrib:
            lines.append(f"  - {row}")
    lines.append(f"- Files changed (numstat rows): {files}")
    lines.append(f"- Additions: {adds}  |  Deletions: {dels}")
    lines.append(f"- Timeline: {first_date} → {last_date}\n")
    # Monthly histogram
    hist = monthly_histogram()
    if hist:
        lines.append("## Monthly Commits (all paths)\n")
        for month, count in hist.items():
            lines.append(f"- {month}: {count}")
        lines.append("")
    # LOC snapshot
    lines.append("## Current LOC Snapshot\n")
    for sub in ["genesis_lib", "examples", "docs"]:
        loc = current_loc_by_folder(ROOT / sub)
        lines.append(f"- {sub}: ~{loc} lines (rough count of code/text files)")
    lines.append("")
    # Per-area metrics
    lines.append("## Area Breakdowns\n")
    for area, paths in AREAS.items():
        m = area_metrics(paths)
        lines.append(f"### {area}")
        lines.append(f"- Commits: {m['commits']}")
        lines.append(f"- Files changed (numstat rows): {m['files']}")
        lines.append(f"- Additions: {m['adds']}  |  Deletions: {m['dels']}")
        lines.append(f"- Contributors: {m['contributors']}")
        lines.append(f"- Timeline: {m['first_date']} → {m['last_date']}")
        lines.append(f"- Current LOC in area: ~{m['loc']}")
        if m["top_contrib"]:
            lines.append("- Top Contributors:")
            for row in m["top_contrib"]:
                lines.append(f"  - {row}")
        if m["top_files"]:
            lines.append("- Top Files by Churn (adds+deletes):")
            for f, (a, d) in m["top_files"]:
                lines.append(f"  - {f}: +{a}/-{d}")
        if m["top_subjects"]:
            lines.append("- Recent Commits:")
            for s in m["top_subjects"]:
                lines.append(f"  - {s}")
        lines.append("")
    return "\n".join(lines)

def build_topic(area_name: str, paths):
    m = area_metrics(paths)
    lines = []
    lines.append(f"# {area_name} — Activity Metrics\n")
    lines.append(f"- Timeline: {m['first_date']} → {m['last_date']}")
    lines.append(f"- Commits: {m['commits']}  |  Files changed: {m['files']}")
    lines.append(f"- Additions: {m['adds']}  |  Deletions: {m['dels']}")
    lines.append(f"- Contributors: {m['contributors']}")
    lines.append(f"- Current LOC in area: ~{m['loc']}\n")
    if m["top_files"]:
        lines.append("## Top Files by Churn")
        for f, (a, d) in m["top_files"]:
            lines.append(f"- {f}: +{a}/-{d}")
        lines.append("")
    if m["top_subjects"]:
        lines.append("## Recent Commits")
        for s in m["top_subjects"]:
            lines.append(f"- {s}")
        lines.append("")
    lines.append("## Paths Included")
    for p in paths:
        lines.append(f"- {p}")
    return "\n".join(lines)

def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    TOPIC_DIR.mkdir(parents=True, exist_ok=True)
    out = build_report()
    path = REPORT_DIR / "activity_metrics.md"
    path.write_text(out)
    print(f"Wrote {path}")
    # Topic-specific outputs
    (TOPIC_DIR / "service_registry.md").write_text(build_topic("Service Registry", AREAS["Service Registry"]))
    print(f"Wrote {TOPIC_DIR/'service_registry.md'}")
    (TOPIC_DIR / "simulation_integration.md").write_text(build_topic("Simulation Integration", AREAS["Simulation Integration"]))
    print(f"Wrote {TOPIC_DIR/'simulation_integration.md'}")

if __name__ == "__main__":
    main()
