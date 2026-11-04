"""Unit tests for CaseOrchestrator.py."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import CaseOrchestrator as orchestrator


class ParseArgsTests(unittest.TestCase):
    def test_parses_full_export_flags(self):
        args = orchestrator._parse_args([
            "--take", "5",
            "--state", "CA",
            "--status", "Unidentified Deceased",
            "--fetch-all",
            "--max-workers", "4",
        ])
        self.assertEqual(args.take, 5)
        self.assertEqual(args.state, "CA")
        self.assertEqual(args.status, "Unidentified Deceased")
        self.assertTrue(args.fetch_all)
        self.assertEqual(args.max_workers, 4)


class FetchAllCaseSetsTests(unittest.TestCase):
    @patch.object(orchestrator.unidentified_full_export, "fetch_unidentified_details")
    @patch.object(orchestrator.missing_full_export, "fetch_missing_details")
    def test_merges_and_tags_results(self, mp_fetch, up_fetch):
        mp_fetch.return_value = {
            "cases": [
                {
                    "Case Link": "https://www.namus.gov/MissingPersons/Case#/1?nav",
                    "subjectIdentification": {
                        "computedMissingMinAge": 12,
                        "computedMissingMaxAge": 14,
                    },
                    "physicalDescription": {
                        "eyeColor": {"name": "Brown"},
                        "hairColor": {"name": "Black"},
                    },
                    "clothingAndAccessoriesArticles": [
                        {
                            "articleType": {"name": "Shirt"},
                            "color": {"name": "Blue"},
                            "description": "Cotton tee",
                        }
                    ],
                    "physicalFeatureDescriptions": [
                        {
                            "physicalFeatureType": {"name": "Scar"},
                            "description": "Small scar on left cheek",
                        }
                    ],
                    "investigatingAgencies": [{"name": "Agency One"}, {"name": "Agency Two"}],
                }
            ]
        }
        up_fetch.return_value = {
            "cases": [
                {
                    "Case Link": "https://www.namus.gov/UnidentifiedPersons/Case#/2?nav",
                    "subjectDescription": {"estimatedAgeFrom": 22, "estimatedAgeTo": 30},
                    "physicalDescription": {
                        "eyeColor": {"name": "Blue"},
                        "hairColor": {"name": "Brown"},
                    },
                    "clothingAndAccessoriesArticles": [],
                    "physicalFeatureDescriptions": [],
                    "investigatingAgencies": [{"name": "Agency Three"}],
                }
            ]
        }

        args = orchestrator._parse_args(["--take", "1"])
        combined = orchestrator.fetch_all_case_sets(args)

        self.assertEqual(combined["total"], 2)
        self.assertEqual(combined["counts"]["Missing Persons"], 1)
        self.assertEqual(combined["counts"]["Unidentified Persons"], 1)
        self.assertNotIn("Unclaimed Persons", combined["counts"])

        case_sets = [row["Case Set"] for row in combined["cases"]]
        self.assertEqual(
            case_sets,
            ["Missing Persons", "Unidentified Persons"],
        )

        missing_breakdown = combined["cases"][0]["Breakdown"]
        self.assertEqual(missing_breakdown["Age"]["Min"], 12)
        self.assertEqual(missing_breakdown["Age"]["Max"], 14)
        self.assertEqual(missing_breakdown["Clothing and Accessories"]["Count"], 1)
        self.assertEqual(missing_breakdown["Physical Features"]["Count"], 1)
        self.assertEqual(missing_breakdown["Clothing and Accessories"]["Items"][0]["Type"], "Shirt")
        self.assertEqual(missing_breakdown["Physical Features"]["Items"][0]["Type"], "Scar")
        self.assertEqual(
            missing_breakdown["Physical Features"]["Items"][0]["Description"],
            "Small scar on left cheek",
        )
        self.assertEqual(missing_breakdown["Eye Color"], "Brown")
        self.assertEqual(missing_breakdown["Hair Color"], "Black")
        self.assertEqual(missing_breakdown["Physical Features Summary"], "Scar")
        self.assertEqual(
            missing_breakdown["Investigating Agencies Summary"],
            "Agency One, Agency Two",
        )
        self.assertEqual(combined["cases"][0]["Eye Color"], "Brown")
        self.assertEqual(combined["cases"][0]["Hair Color"], "Black")
        self.assertEqual(combined["cases"][0]["Investigating Agency Summary"], "Agency One, Agency Two")
        self.assertNotIn("physicalDescription", combined["cases"][0])
        self.assertNotIn("physicalFeatureDescriptions", combined["cases"][0])
        self.assertNotIn("clothingAndAccessoriesArticles", combined["cases"][0])
        self.assertNotIn("investigatingAgencies", combined["cases"][0])
        self.assertNotIn("subjectIdentification", combined["cases"][0])
        self.assertNotIn("subjectDescription", combined["cases"][0])
        self.assertNotIn("circumstances", combined["cases"][0])

        unidentified_breakdown = combined["cases"][1]["Breakdown"]
        self.assertEqual(unidentified_breakdown["Age"]["Min"], 22)
        self.assertEqual(unidentified_breakdown["Age"]["Max"], 30)
        self.assertEqual(unidentified_breakdown["Investigating Agencies Summary"], "Agency Three")

    @patch.object(orchestrator.unidentified_full_export, "fetch_unidentified_details")
    @patch.object(orchestrator.missing_full_export, "fetch_missing_details")
    def test_empty_results(self, mp_fetch, up_fetch):
        mp_fetch.return_value = {"cases": []}
        up_fetch.return_value = {"cases": []}

        args = orchestrator._parse_args([])
        combined = orchestrator.fetch_all_case_sets(args)

        self.assertEqual(combined["total"], 0)
        self.assertEqual(combined["cases"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

