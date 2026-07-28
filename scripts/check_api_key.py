#!/usr/bin/env python3
"""
Offline helper to validate DATA_GOV_IN_API_KEY format.
Does NOT make network calls, does NOT print the key.

Usage (locally, NOT in GitHub Actions):
  export DATA_GOV_IN_API_KEY=your_key_here
  python scripts/check_api_key.py
"""
import os
import re
import argparse
import sys


def validate(key: str):
    key = key.strip()
    issues = []
    if not key:
        return False, ["empty"], key
    if key.startswith("'") or key.startswith('"') or key.endswith("'") or key.endswith('"'):
        issues.append("has surrounding quotes - remove them")
    if " " in key or "\n" in key or "\t" in key:
        issues.append("contains spaces/newlines - paste only raw key")
    if len(key) < 30:
        issues.append(f"too short ({len(key)} chars) - expected ~50+")
    if not re.fullmatch(r"[a-fA-F0-9]+", key):
        if not re.fullmatch(r"[A-Za-z0-9-_]+", key):
            issues.append("contains invalid characters")
    return (len(issues) == 0), issues, key


def main():
    parser = argparse.ArgumentParser(description="Validate data.gov.in API key format offline")
    parser.add_argument("--key-file", help="Path to file containing key")
    parser.add_argument("--key", help="Key value (avoid in shell history)")
    args = parser.parse_args()

    key = ""
    if args.key:
        key = args.key
    elif args.key_file:
        try:
            key = open(args.key_file, "r", encoding="utf-8").read().strip()
        except Exception as e:
            print(f"Failed to read key file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        key = os.environ.get("DATA_GOV_IN_API_KEY", "")

    ok, issues, cleaned = validate(key)
    length = len(cleaned)
    has_quotes = cleaned.startswith("'") or cleaned.startswith('"') or cleaned.endswith("'") or cleaned.endswith('"')
    has_spaces = " " in cleaned or "\n" in cleaned or "\t" in cleaned
    is_hex = bool(re.fullmatch(r"[a-fA-F0-9]+", cleaned))

    print(f"Length: {length}")
    print(f"Has quotes: {has_quotes}")
    print(f"Has spaces: {has_spaces}")
    print(f"Is hex-like: {is_hex}")

    if ok:
        print("✅ Format looks OK. If you still get 403, check email verification or regenerate key on data.gov.in")
    else:
        print("❌ Issues found:")
        for i in issues:
            print(f"  - {i}")
        print("\nFix: Go to GitHub repo -> Settings -> Secrets -> Actions -> click pencil on DATA_GOV_IN_API_KEY -> paste raw key -> Save")
        print("Then Actions tab -> Multi-Daily Mandi Price Update -> Run workflow")
    # Never print key


if __name__ == "__main__":
    main()
