"""Unit tests for CaseOrchestrator.py."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import CaseOrchestrator as orchestrator


class BuildCaseSetParamsTests(unittest.TestCase):
    def test_builds_all_three_param_blocks(self):
        args = orchestrator._parse_args([
            "--take", "5",
            "--state", "CA",
            "--status", "Unidentified Deceased",
            "--yob-min", "1960",
            "--only-unresolved",
        ])

        params = orchestrator.build_case_set_params(args)

        self.assertIn("Missing Persons", params)
        self.assertIn("Unidentified Persons", params)
        self.assertIn("Unclaimed Persons", params)
        self.assertEqual(params["Missing Persons"]["take"], 5)
        self.assertEqual(params["Unidentified Persons"].get("status"), "Unidentified Deceased")
        self.assertEqual(params["Unclaimed Persons"].get("yearOfBirthMin"), 1960)
        self.assertTrue(params["Unclaimed Persons"]["_client_filters"]["only_unresolved"])


class FetchAllCaseSetsTests(unittest.TestCase):
    @patch.object(orchestrator.unclaimed_person, "fetch_cases")
    @patch.object(orchestrator.unidentified_person, "fetch_cases")
    @patch.object(orchestrator.missing_person, "fetch_cases")
    def test_merges_and_tags_results(self, mp_fetch, up_fetch, ucp_fetch):
        mp_fetch.return_value = [{"Case Number": "MP00001", "Name": "A"}]
        up_fetch.return_value = [{"Case Number": "UP00001", "Status": "Unidentified Deceased"}]
        ucp_fetch.return_value = [{"Case Number": "UCP00001", "Name": "B"}]

        args = orchestrator._parse_args(["--take", "1"])
        combined = orchestrator.fetch_all_case_sets(args)

        self.assertEqual(combined["total"], 3)
        self.assertEqual(combined["counts"]["Missing Persons"], 1)
        self.assertEqual(combined["counts"]["Unidentified Persons"], 1)
        self.assertEqual(combined["counts"]["Unclaimed Persons"], 1)

        case_sets = [row["Case Set"] for row in combined["cases"]]
        self.assertEqual(
            case_sets,
            ["Missing Persons", "Unidentified Persons", "Unclaimed Persons"],
        )

    @patch.object(orchestrator.unclaimed_person, "fetch_cases")
    @patch.object(orchestrator.unidentified_person, "fetch_cases")
    @patch.object(orchestrator.missing_person, "fetch_cases")
    def test_empty_results(self, mp_fetch, up_fetch, ucp_fetch):
        mp_fetch.return_value = []
        up_fetch.return_value = []
        ucp_fetch.return_value = []

        args = orchestrator._parse_args([])
        combined = orchestrator.fetch_all_case_sets(args)

        self.assertEqual(combined["total"], 0)
        self.assertEqual(combined["cases"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

