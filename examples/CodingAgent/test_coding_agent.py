#!/usr/bin/env python3
"""
Master integration test — runs all test layers in sequence.

Layer 1: Backend parser tests (always runs)
Layer 2: Auth tests (always runs)
Layer 3: Mock agent tests (always runs)
Layer 4+: Live and DDS tests (skipped if DDS/CLI not available)

Usage:
    python test_coding_agent.py
    python test_coding_agent.py --include-live   # also run live backend tests
"""

import argparse
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.join(SCRIPT_DIR, "tests")


def run_test(name, cmd, cwd=None):
    """Run a test command and return True if it passes."""
    print(f"\n{'='*60}")
    print(f"Running: {name}")
    print(f"{'='*60}")

    result = subprocess.run(
        cmd,
        cwd=cwd or SCRIPT_DIR,
        shell=isinstance(cmd, str),
    )

    if result.returncode == 0:
        print(f"PASS: {name}")
        return True
    else:
        print(f"FAIL: {name} (exit code {result.returncode})")
        return False


def main():
    parser = argparse.ArgumentParser(description="CodingAgent master test suite")
    parser.add_argument(
        "--include-live", action="store_true",
        help="Include live backend tests (requires CLI installed)",
    )
    args = parser.parse_args()

    results = []

    # Layer 1: Backend parser tests
    results.append(run_test(
        "Backend parser tests",
        [sys.executable, os.path.join(TESTS_DIR, "test_backends.py")],
    ))

    # Layer 2: Auth tests
    results.append(run_test(
        "Auth probing tests",
        [sys.executable, os.path.join(TESTS_DIR, "test_auth.py")],
    ))

    # Layer 3: Mock agent tests
    results.append(run_test(
        "Mock agent tests",
        [sys.executable, os.path.join(TESTS_DIR, "test_agent_mock.py")],
    ))

    # Layer 4: Live backend tests (optional)
    if args.include_live:
        results.append(run_test(
            "Live backend tests",
            [sys.executable, os.path.join(TESTS_DIR, "test_live_backend.py")],
        ))

    # Summary
    print(f"\n{'='*60}")
    print("MASTER TEST SUMMARY")
    print(f"{'='*60}")
    total = len(results)
    passed = sum(results)
    failed = total - passed
    print(f"  Passed: {passed}/{total}")
    print(f"  Failed: {failed}/{total}")

    if failed > 0:
        print("\nSome tests failed!")
        sys.exit(1)
    else:
        print("\nAll tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
