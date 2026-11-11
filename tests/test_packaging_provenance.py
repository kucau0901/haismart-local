"""Offline packaging, provenance and CI guarantees for this fork.

No Home Assistant, no network, no hardware: plain file inspection only, so this runs in every
environment including the library-only test job. The generated ``custom_components/`` tree is
committed because HACS installs from it; these checks make the fork's identity and the build's
sync requirements explicit rather than relying on a reviewer noticing a hand edit.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "ha-haismart"
SOURCE = PACKAGE / "custom_components" / "haismart"
GENERATED = ROOT / "custom_components" / "haismart"

FORK_OWNER = "kucau0901"
UPSTREAM_OWNER = "enapt"
UPSTREAM_NAME = "Haismart (Haier local)"
VERSION = "0.73.2.2"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class HacsJsonTest(unittest.TestCase):
    def test_root_and_package_hacs_json_are_identical_forks(self) -> None:
        root = _json(ROOT / "hacs.json")
        package = _json(PACKAGE / "hacs.json")
        self.assertEqual(root, package, "HACS reads only the root hacs.json; the copies must match")
        self.assertEqual(root["name"], package["name"])
        self.assertIn(FORK_OWNER, root["name"])
        self.assertNotEqual(
            root["name"],
            UPSTREAM_NAME,
            "the fork must be distinguishable from the upstream HACS entry in the UI",
        )
        self.assertFalse(root["content_in_root"])

    def test_supported_home_assistant_floor_is_declared(self) -> None:
        floor = _json(ROOT / "hacs.json").get("homeassistant")
        self.assertIsInstance(floor, str)
        self.assertRegex(floor, r"^\d{4}\.\d+\.\d+$")


class ManifestTest(unittest.TestCase):
    def test_manifest_metadata_points_at_this_fork(self) -> None:
        source = _json(SOURCE / "manifest.json")
        self.assertEqual(source["domain"], "haismart")
        self.assertEqual(source["version"], VERSION)
        self.assertIn(f"@{FORK_OWNER}", source["codeowners"])
        self.assertIn(f"@{UPSTREAM_OWNER}", source["codeowners"], "upstream authorship stays credited")
        self.assertIn(FORK_OWNER, source["documentation"])
        self.assertIn(FORK_OWNER, source["issue_tracker"])
        self.assertNotIn(UPSTREAM_OWNER, source["documentation"])
        self.assertNotIn(UPSTREAM_OWNER, source["issue_tracker"])
        self.assertTrue(source["requirements"], "the source manifest is the pip-installable form")

    def test_generated_manifest_is_the_build_output_of_the_source(self) -> None:
        source = _json(SOURCE / "manifest.json")
        generated = _json(GENERATED / "manifest.json")
        self.assertEqual(generated["requirements"], [], "vendored build needs no pip requirements")
        source_without_requirements = {**source, "requirements": []}
        self.assertEqual(generated, source_without_requirements)
        self.assertEqual(generated["domain"], "haismart")
        self.assertEqual(generated["version"], VERSION)
        for library in ("haismart_hrdp", "haismart_extractor"):
            vendored = GENERATED / "vendor" / library
            self.assertTrue((vendored / "__init__.py").is_file(), f"{library} is not vendored")

    def test_generated_component_matches_source_except_build_steps(self) -> None:
        build_only = {"manifest.json", "__init__.py"}
        for path in sorted(SOURCE.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(SOURCE)
            if str(relative) in build_only:
                continue
            generated = GENERATED / relative
            self.assertTrue(generated.is_file(), f"{relative} missing from the generated tree")
            self.assertEqual(
                path.read_bytes(),
                generated.read_bytes(),
                f"{relative} differs; run scripts/build-hacs.sh instead of editing the generated tree",
            )
        # The build adds only the vendor shim and the stripped requirements to these two files.
        self.assertIn("_vendor", (GENERATED / "__init__.py").read_text(encoding="utf-8"))


class WorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = (ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")

    def test_ci_tests_both_current_and_target_home_assistant(self) -> None:
        for expected in (
            "2026.10.4",
            "2026.11.1",
            "pytest-homeassistant-custom-component==0.13.375",
            "pytest-homeassistant==2026.11.1",
        ):
            self.assertTrue(expected in self.workflow, f"CI workflow does not pin {expected!r}")

    def test_ci_uses_the_python_version_home_assistant_requires(self) -> None:
        self.assertNotIn('python-version: "3.13"', self.workflow)
        recent = [v for v in re.findall(r'python-version:\s*"?([\d.]+)"?', self.workflow)]
        self.assertTrue(recent, "the workflow must pin an explicit Python version")
        for version in recent:
            self.assertGreaterEqual(tuple(map(int, version.split("."))), (3, 14, 2))

    def test_ci_fails_when_the_ha_suite_does_not_really_run(self) -> None:
        for expected in ("HA_JUNIT", "check-ha-suite-ran.py", "skipped", "scripts/test.sh"):
            self.assertTrue(expected in self.workflow, f"CI workflow lacks {expected!r}")


class ReadmeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")

    def test_install_instructions_install_this_fork(self) -> None:
        for expected in (
            f"{FORK_OWNER}/haismart-local",
            f"owner={FORK_OWNER}",
            f"https://github.com/{FORK_OWNER}/haismart-local",
        ):
            self.assertTrue(expected in self.readme, f"README lacks the fork install path {expected!r}")

    def test_readme_does_not_claim_upstream_is_this_repository(self) -> None:
        self.assertTrue(
            "This is the home of the project" not in self.readme,
            "the fork must not point readers at upstream as if it were this repository",
        )
        self.assertTrue(UPSTREAM_OWNER in self.readme, "upstream attribution is retained")

    def test_duplicate_cleanup_is_record_only_and_before_migration(self) -> None:
        for expected in (
            "before upgrading",
            "hacs/repositories/remove",
            "hacs/repository/remove",
            "owner-confirmed operation",
            "Marketplace 2026.11.1 rejects",
        ):
            self.assertIn(expected, self.readme)

    def test_marketplace_migration_is_documented_with_official_links(self) -> None:
        for expected in (
            "https://www.home-assistant.io/integrations/marketplace/",
            "https://hacs.xyz/docs/marketplace/",
            "2026.11",
        ):
            self.assertTrue(expected in self.readme, f"README lacks Marketplace guidance {expected!r}")


class JunitGateTest(unittest.TestCase):
    """The CI gate that turns a silently skipped HA suite into a failure."""

    SCRIPT = ROOT / "scripts" / "check-ha-suite-ran.py"

    def _run(self, xml: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "ha-junit.xml"
            report.write_text(xml, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(self.SCRIPT), str(report)],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_rejects_a_report_that_executed_nothing(self) -> None:
        result = self._run('<testsuite name="pytest" tests="0" />')
        self.assertEqual(result.returncode, 1)
        self.assertIn("executed no tests", result.stdout)

    def test_rejects_skipped_tests_and_names_them(self) -> None:
        result = self._run(
            '<testsuite name="pytest" tests="1" skipped="1">'
            '<testcase classname="tests.test_init" name="test_setup">'
            '<skipped message="no plugin" /></testcase></testsuite>'
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("skipped 1", result.stdout)
        self.assertIn("tests.test_init::test_setup", result.stdout)

    def test_accepts_a_fully_executed_suite(self) -> None:
        result = self._run(
            '<testsuite name="pytest" tests="3">'
            "<testcase classname=\"tests.a\" name=\"one\" />"
            "<testcase classname=\"tests.a\" name=\"two\" />"
            "<testcase classname=\"tests.a\" name=\"three\" /></testsuite>"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("3 tests executed", result.stdout)

    def test_rejects_a_missing_report(self) -> None:
        result = subprocess.run(
            [sys.executable, str(self.SCRIPT), str(ROOT / "does-not-exist.xml")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("did not run", result.stdout)


if __name__ == "__main__":
    unittest.main()
