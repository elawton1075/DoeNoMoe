"""Tests for the --parsed output of MissingFullExport.py and UnidentifiedFullExport.py."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

import MissingFullExport as missing_export
import UnidentifiedFullExport as unidentified_export

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _run_main(module, fetch_name: str, raw_case: dict, extra_args: list) -> dict:
    """Run module.main() with the fetch stubbed, and return the JSON it wrote."""
    fetch_result = {"search_count": 1, "returned": 1, "cases": [dict(raw_case)]}
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "out.json"
        with patch.object(module, fetch_name, return_value=fetch_result), redirect_stderr(io.StringIO()):
            module.main(["--output", str(output), *extra_args])
        return json.loads(output.read_text(encoding="utf-8"))


class MissingFullExportParsedTests(unittest.TestCase):
    def setUp(self):
        self.raw = {k: v for k, v in _fixture("missing_full_case_response.json").items() if k != "Case Set"}

    def test_default_output_is_raw_payload(self):
        written = _run_main(missing_export, "fetch_missing_details", self.raw, [])

        case = written["cases"][0]
        self.assertIn("subjectIdentification", case)
        self.assertNotIn("Breakdown", case)

    def test_parsed_output_has_breakdown_and_prunes_raw_blobs(self):
        written = _run_main(missing_export, "fetch_missing_details", self.raw, ["--parsed"])

        case = written["cases"][0]
        self.assertEqual(case["Case Set"], "Missing Persons")
        self.assertEqual(case["Breakdown"]["Demographics"]["Name"], "IRIE SAWYER HEINES")
        self.assertEqual(case["Eye Color"], "Blue")
        self.assertNotIn("subjectIdentification", case)
        # Search metadata from the export is preserved.
        self.assertEqual(written["search_count"], 1)
        self.assertEqual(written["returned"], 1)


class UnidentifiedFullExportParsedTests(unittest.TestCase):
    def setUp(self):
        self.raw = {
            k: v
            for k, v in _fixture("unidentified_full_case_response_alt.json").items()
            if k != "Case Set"
        }

    def test_default_output_is_raw_payload(self):
        written = _run_main(unidentified_export, "fetch_unidentified_details", self.raw, [])

        case = written["cases"][0]
        self.assertIn("investigatingAgencies", case)
        self.assertNotIn("Breakdown", case)

    def test_parsed_output_has_breakdown_and_prunes_raw_blobs(self):
        written = _run_main(unidentified_export, "fetch_unidentified_details", self.raw, ["--parsed"])

        case = written["cases"][0]
        self.assertEqual(case["Case Set"], "Unidentified Persons")
        self.assertEqual(case["Breakdown"]["Circumstances"]["City"], "Columbia")
        self.assertEqual(
            case["Investigating Agency Summary"],
            "Richland County Coroner's Office, South Carolina Law Enforcement Division",
        )
        self.assertNotIn("investigatingAgencies", case)
        self.assertEqual(written["returned"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)



