#!/usr/bin/env python3
"""Fail unless the Home Assistant suite actually executed every test it collected.

pytest exits 0 when a suite collects nothing or skips everything, so a missing or mismatched
``pytest-homeassistant`` installation can look green. CI writes a JUnit report and this gate turns
"zero tests" and "any skips" into a failure, naming the skipped tests so the cause is visible.

    python scripts/check-ha-suite-ran.py ha-junit.xml
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _counts(root: ET.Element) -> tuple[int, int, int, int, list[str]]:
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    tests = failures = errors = skipped = 0
    skipped_names: list[str] = []
    for suite in suites:
        tests += int(suite.get("tests", 0))
        failures += int(suite.get("failures", 0))
        errors += int(suite.get("errors", 0))
        skipped += int(suite.get("skipped", 0))
        for case in suite.iter("testcase"):
            if case.find("skipped") is not None:
                skipped_names.append(f"{case.get('classname', '')}::{case.get('name', '')}")
    return tests, failures, errors, skipped, skipped_names


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check-ha-suite-ran.py <junit.xml>", file=sys.stderr)
        return 2
    report = Path(argv[1])
    if not report.is_file():
        print(f"::error::no JUnit report at {report}: the Home Assistant suite did not run")
        return 1
    tests, failures, errors, skipped, skipped_names = _counts(ET.parse(report).getroot())
    if tests == 0:
        print("::error::the Home Assistant suite executed no tests")
        return 1
    if failures or errors:
        print(f"::error::the Home Assistant suite reported {failures} failures and {errors} errors")
        return 1
    if skipped:
        print(f"::error::the Home Assistant suite skipped {skipped} test(s); CI must run them all")
        for name in skipped_names:
            print(f"  skipped: {name}")
        return 1
    print(f"Home Assistant suite: {tests} tests executed, 0 failed, 0 errors, 0 skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
