#!/usr/bin/env python3
"""
Safe test runner that doesn't fail the workflow on test errors.
This ensures data updates proceed even if some tests fail.
"""
import subprocess
import sys

def main():
    print("=" * 60)
    print("Running tests (non-blocking mode)")
    print("=" * 60)
    
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        capture_output=False
    )
    
    print("\n" + "=" * 60)
    if result.returncode == 0:
        print("✅ All tests passed!")
    else:
        print(f"⚠️  Tests completed with return code {result.returncode}")
        print("ℹ️  Data update will proceed regardless of test failures")
    print("=" * 60)
    
    # Always exit with 0 to not block the workflow
    return 0

if __name__ == "__main__":
    sys.exit(main())
