#!/usr/bin/env python3
"""
Bisection script to find which test causes pollution or creates artifacts.

Inspired by obra/superpowers systematic debugging methodology.

Usage:
    ./scripts/find_polluter.py <artifact> <test_pattern>

Examples:
    # Find which test creates .git directory in source
    ./scripts/find_polluter.py '.git' 'tests/**/*_test.py'

    # Find which test creates unwanted files
    ./scripts/find_polluter.py 'unwanted_file.txt' 'tests/integration/**/*.py'

    # Find which test pollutes database
    ./scripts/find_polluter.py 'pollution_marker' 'tests/api/**/*.py'

How it works:
    1. Runs tests one-by-one
    2. After each test, checks if artifact exists
    3. Stops at first test that creates the artifact
    4. Reports the polluter with details

Requirements:
    - pytest installed
    - Tests must be idempotent (can run in isolation)
"""

import subprocess
import sys
import glob
from pathlib import Path
from typing import Optional
import argparse


def check_artifact_exists(artifact: str) -> bool:
    """Check if artifact exists in workspace."""
    return Path(artifact).exists()


def cleanup_artifact(artifact: str) -> None:
    """Remove artifact if it exists."""
    path = Path(artifact)
    if path.exists():
        if path.is_file():
            path.unlink()
            print(f"✓ Cleaned up artifact: {artifact}")
        elif path.is_dir():
            import shutil
            shutil.rmtree(path)
            print(f"✓ Cleaned up directory: {artifact}")


def run_single_test(test_file: str, verbose: bool = False) -> tuple[bool, str]:
    """
    Run a single test file.

    Returns:
        (success, output): Whether test passed and its output
    """
    cmd = ["pytest", test_file, "-v" if verbose else "-q"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout per test
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, f"Test timed out after 120 seconds"
    except Exception as e:
        return False, f"Error running test: {str(e)}"


def find_polluter(
    artifact: str,
    test_pattern: str,
    cleanup: bool = True,
    verbose: bool = False
) -> Optional[str]:
    """
    Find which test creates the specified artifact.

    Args:
        artifact: Path to artifact to check for
        test_pattern: Glob pattern for test files
        cleanup: Whether to cleanup artifact between tests
        verbose: Show test output

    Returns:
        Path to polluting test file, or None if not found
    """
    # Get all test files matching pattern
    test_files = []
    for pattern_part in test_pattern.split():
        test_files.extend(glob.glob(pattern_part, recursive=True))

    test_files = sorted(set(test_files))  # Remove duplicates

    if not test_files:
        print(f"❌ No test files found matching pattern: {test_pattern}")
        return None

    print(f"🔍 Searching for polluter among {len(test_files)} test files...")
    print(f"📝 Looking for artifact: {artifact}")
    print()

    # Initial cleanup
    if check_artifact_exists(artifact):
        print(f"⚠️  Artifact exists before tests. Cleaning up...")
        cleanup_artifact(artifact)
        print()

    # Run tests one by one
    for i, test_file in enumerate(test_files, 1):
        print(f"[{i}/{len(test_files)}] Testing: {test_file}")

        # Run the test
        success, output = run_single_test(test_file, verbose)

        if verbose:
            print(output)

        # Check if artifact was created
        if check_artifact_exists(artifact):
            print()
            print("=" * 70)
            print("🎯 POLLUTER FOUND!")
            print("=" * 70)
            print(f"Test file: {test_file}")
            print(f"Artifact: {artifact}")
            print()
            print("Test output:")
            print("-" * 70)
            print(output)
            print("-" * 70)
            print()
            print("Next steps:")
            print("1. Read the test file to understand what it does")
            print("2. Use DEBUG_PROTOCOL.md Phase 1 to investigate root cause")
            print("3. Add cleanup in test teardown or fix the pollution source")
            print()
            return test_file

        # Cleanup between tests if requested
        if cleanup and check_artifact_exists(artifact):
            cleanup_artifact(artifact)

        # Progress indicator
        if not verbose:
            print(f"  ✓ No pollution (test {'passed' if success else 'failed'})")

    print()
    print("❌ No polluter found among tested files.")
    print("Possible reasons:")
    print("  - Artifact created by multiple tests in combination")
    print("  - Artifact created outside test suite")
    print("  - Test pattern doesn't include the polluter")
    print()
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Find which test creates an unwanted artifact (file/directory)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Find test creating .git directory
  %(prog)s .git 'tests/**/*_test.py'

  # Find test creating unwanted files
  %(prog)s unwanted.txt 'tests/integration/**/*.py'

  # Verbose mode to see test output
  %(prog)s -v pollution_marker 'tests/**/*.py'

  # Don't cleanup between tests
  %(prog)s --no-cleanup artifact.txt 'tests/**/*.py'
        """
    )

    parser.add_argument(
        "artifact",
        help="Path to artifact (file/directory) to check for"
    )

    parser.add_argument(
        "test_pattern",
        help="Glob pattern for test files (e.g., 'tests/**/*_test.py')"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show test output while running"
    )

    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Don't cleanup artifact between tests"
    )

    args = parser.parse_args()

    # Run bisection
    polluter = find_polluter(
        artifact=args.artifact,
        test_pattern=args.test_pattern,
        cleanup=not args.no_cleanup,
        verbose=args.verbose
    )

    # Exit with appropriate code
    sys.exit(0 if polluter else 1)


if __name__ == "__main__":
    main()
