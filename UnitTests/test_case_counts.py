"""Unit tests for CaseCounts.py."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import CaseCounts as case_counts


class BuildCaseSetParamsTests(unittest.TestCase):
    def test_builds_all_three_param_blocks(self):
        args = case_counts._parse_args([
            "--take", "5",
            "--state", "CA",
            "--status", "Unidentified Deceased",
            "--yob-min", "1960",
            "--only-unresolved",
        ])

        params = case_counts.build_case_set_params(args)

        self.assertIn("Missing Persons", params)
        self.assertIn("Unidentified Persons", params)
        self.assertIn("Unclaimed Persons", params)
        self.assertEqual(params["Missing Persons"]["take"], 5)
        self.assertEqual(params["Unidentified Persons"].get("status"), "Unidentified Deceased")
        self.assertEqual(params["Unclaimed Persons"].get("yearOfBirthMin"), 1960)
        self.assertTrue(params["Unclaimed Persons"]["_client_filters"]["only_unresolved"])


class FetchCountsTests(unittest.TestCase):
    @patch.object(case_counts.unclaimed_person, "search_unclaimed_persons")
    @patch.object(case_counts.unidentified_person, "search_unidentified_persons")
    @patch.object(case_counts.missing_person, "search_missing_persons")
    def test_merges_counts(self, mp_search, up_search, ucp_search):
        mp_search.return_value = {"count": 10, "results": [{"namus2Number": 1}]}
        up_search.return_value = {"count": 20, "results": [{"namus2Number": 2}]}
        ucp_search.return_value = {"count": 30, "results": [{"namus2Number": 3}]}

        args = case_counts._parse_args([])
        result = case_counts.fetch_counts(args)

        self.assertEqual(result["counts"]["Missing Persons"], 10)
        self.assertEqual(result["counts"]["Unidentified Persons"], 20)
        self.assertEqual(result["counts"]["Unclaimed Persons"], 30)
        self.assertEqual(result["total"], 60)

    @patch.object(case_counts.unclaimed_person, "search_unclaimed_persons")
    @patch.object(case_counts.unidentified_person, "search_unidentified_persons")
    @patch.object(case_counts.missing_person, "search_missing_persons")
    def test_missing_count_defaults_to_zero(self, mp_search, up_search, ucp_search):
        mp_search.return_value = {}
        up_search.return_value = {"count": None}
        ucp_search.return_value = {"count": 4}

        args = case_counts._parse_args([])
        result = case_counts.fetch_counts(args)

        self.assertEqual(result["counts"]["Missing Persons"], 0)
        self.assertEqual(result["counts"]["Unidentified Persons"], 0)
        self.assertEqual(result["counts"]["Unclaimed Persons"], 4)
        self.assertEqual(result["total"], 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)

