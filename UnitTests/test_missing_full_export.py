"""Unit tests for MissingFullExport.py."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import MissingFullExport as mfe


def _args(**overrides):
    base = {
        "take": 2,
        "skip": 0,
        "fetch_all": False,
        "state": None,
        "age_min": None,
        "age_max": None,
        "sex": None,
        "race_ethnicity": None,
        "max_workers": 2,
        "output": "unused.json",
        "print_json": False,
    }
    base.update(overrides)
    return type("Args", (), base)()


def _case(i: int) -> dict:
    return {
        "id": i,
        "idFormatted": f"MP{i:05d}",
        "subjectIdentification": {"firstName": f"First{i}", "lastName": f"Last{i}"},
        "subjectDescription": {"sex": {"name": "Female"}},
        "sighting": {"address": {"city": "Testville", "state": {"displayName": "CA"}}},
        "circumstances": {"circumstancesOfDisappearance": "Example details"},
    }


class HelperTests(unittest.TestCase):
    def test_build_case_link(self):
        case = {"id": 163404}
        self.assertEqual(
            mfe.build_case_link(case),
            "https://www.namus.gov/MissingPersons/Case#/163404?nav",
        )

    def test_enrich_case_adds_link(self):
        c = mfe.enrich_case(_case(10))
        self.assertEqual(c["Case Link"], "https://www.namus.gov/MissingPersons/Case#/10?nav")


class FetchTests(unittest.TestCase):
    @patch.object(mfe.mp, "fetch_case_detail")
    @patch.object(mfe.mp, "search_missing_persons")
    def test_fetch_single_page_enriches_all_cases(self, search_mock, detail_mock):
        search_mock.return_value = {
            "count": 2,
            "results": [{"namus2Number": 100}, {"namus2Number": 101}],
        }
        detail_mock.side_effect = [_case(100), _case(101)]

        result = mfe.fetch_missing_details(_args(fetch_all=False))

        self.assertEqual(result["search_count"], 2)
        self.assertEqual(result["returned"], 2)
        self.assertEqual(result["cases"][0]["Case Link"], "https://www.namus.gov/MissingPersons/Case#/100?nav")

    @patch.object(mfe.mp, "fetch_case_detail")
    @patch.object(mfe.mp, "search_missing_persons")
    def test_fetch_all_pages(self, search_mock, detail_mock):
        search_mock.side_effect = [
            {"count": 3, "results": [{"namus2Number": 1}, {"namus2Number": 2}]},
            {"count": 3, "results": [{"namus2Number": 3}]},
        ]
        detail_mock.side_effect = [_case(1), _case(2), _case(3)]

        result = mfe.fetch_missing_details(_args(fetch_all=True, take=2))

        self.assertEqual(result["returned"], 3)
        self.assertEqual({c["id"] for c in result["cases"]}, {1, 2, 3})


if __name__ == "__main__":
    unittest.main(verbosity=2)

