"""Unit tests for CaseOrchestrator.py."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import ANY, patch

import CaseOrchestrator as orchestrator
from CaseModels import ParsedCase


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

    def test_take_defaults_to_five_per_case_set(self):
        self.assertEqual(orchestrator._parse_args([]).take, 5)


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
                        "currentMinAge": 15,
                        "currentMaxAge": 17,
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
                    "circumstances": {"dateFound": "2000-06-01"},
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
        self.assertEqual(missing_breakdown["Age"]["When Missing"], {"Min": 12, "Max": 14})
        self.assertEqual(missing_breakdown["Age"]["Now"], {"Min": 15, "Max": 17})
        self.assertEqual(missing_breakdown["Clothing and Accessories"]["Count"], 1)
        self.assertEqual(missing_breakdown["Physical Features"]["Count"], 1)
        self.assertEqual(missing_breakdown["Clothing and Accessories"]["Items"][0]["Type"], "Shirt")
        self.assertEqual(missing_breakdown["Physical Features"]["Items"][0]["Type"], "Scar")
        self.assertEqual(
            missing_breakdown["Physical Features"]["Items"][0]["Description"],
            "Small scar on left cheek",
        )
        self.assertEqual(missing_breakdown["Physical Description"]["Eye Color"], "Brown")
        self.assertEqual(missing_breakdown["Physical Description"]["Hair Color"], "Black")
        self.assertEqual(
            [a["Name"] for a in missing_breakdown["Investigating Agencies"]],
            ["Agency One", "Agency Two"],
        )
        for duplicated in (
            "Eye Color",
            "Hair Color",
            "Physical Features Summary",
            "Investigating Agencies Summary",
        ):
            self.assertNotIn(duplicated, missing_breakdown)
        self.assertEqual(combined["cases"][0]["Eye Color"], "Brown")
        self.assertEqual(combined["cases"][0]["Hair Color"], "Black")
        self.assertEqual(combined["cases"][0]["Physical Features Summary"], "Scar")
        self.assertEqual(combined["cases"][0]["Investigating Agency Summary"], "Agency One, Agency Two")
        self.assertNotIn("physicalDescription", combined["cases"][0])
        self.assertNotIn("physicalFeatureDescriptions", combined["cases"][0])
        self.assertNotIn("clothingAndAccessoriesArticles", combined["cases"][0])
        self.assertNotIn("investigatingAgencies", combined["cases"][0])
        self.assertNotIn("subjectIdentification", combined["cases"][0])
        self.assertNotIn("subjectDescription", combined["cases"][0])
        self.assertNotIn("circumstances", combined["cases"][0])

        unidentified_breakdown = combined["cases"][1]["Breakdown"]
        # Found in 2000 aged 22 to 30: born 1969 through 1978.
        self.assertEqual(unidentified_breakdown["Age"]["Projected Birth Years"], {"Min": 1969, "Max": 1978})
        self.assertEqual(
            [a["Name"] for a in unidentified_breakdown["Investigating Agencies"]],
            ["Agency Three"],
        )
        self.assertEqual(combined["cases"][1]["Investigating Agency Summary"], "Agency Three")

    @patch.object(orchestrator.unidentified_full_export, "fetch_unidentified_details")
    @patch.object(orchestrator.missing_full_export, "fetch_missing_details")
    def test_empty_results(self, mp_fetch, up_fetch):
        mp_fetch.return_value = {"cases": []}
        up_fetch.return_value = {"cases": []}

        args = orchestrator._parse_args([])
        combined = orchestrator.fetch_all_case_sets(args)

        self.assertEqual(combined["total"], 0)
        self.assertEqual(combined["cases"], [])

    @patch.object(orchestrator.unidentified_full_export, "fetch_unidentified_details")
    @patch.object(orchestrator.missing_full_export, "fetch_missing_details")
    def test_fetch_parsed_cases_returns_typed_objects(self, mp_fetch, up_fetch):
        mp_fetch.return_value = {"cases": [{"id": 1}]}
        up_fetch.return_value = {"cases": [{"id": 2}, {"id": 3}]}

        args = orchestrator._parse_args([])
        parsed_by_set = orchestrator.fetch_parsed_cases(args)

        self.assertEqual(list(parsed_by_set), ["Missing Persons", "Unidentified Persons"])
        self.assertEqual(len(parsed_by_set["Missing Persons"]), 1)
        self.assertEqual(len(parsed_by_set["Unidentified Persons"]), 2)
        for rows in parsed_by_set.values():
            for parsed in rows:
                self.assertIsInstance(parsed, ParsedCase)

        # JSON output is just the typed objects serialized.
        combined = orchestrator.combine_case_sets(parsed_by_set)
        self.assertEqual(combined["total"], 3)
        self.assertEqual(
            combined["counts"],
            {"Missing Persons": 1, "Unidentified Persons": 2},
        )
        self.assertEqual([c["id"] for c in combined["cases"]], [1, 2, 3])


class ParseCaseSetTests(unittest.TestCase):
    def test_does_not_mutate_input_payload(self):
        row = {
            "id": 1,
            "physicalDescription": {"eyeColor": {"name": "Brown"}},
            "investigatingAgencies": [{"name": "Agency One"}],
        }
        payload = {"cases": [row]}

        parsed = orchestrator.parse_case_set("Missing Persons", payload)

        self.assertIsInstance(parsed[0], ParsedCase)
        self.assertEqual(parsed[0].breakdown.identifiers.case_set, "Missing Persons")
        self.assertEqual(parsed[0].breakdown.eye_color, "Brown")
        # The raw payload keeps its original shape.
        self.assertNotIn("Case Set", row)
        self.assertIn("physicalDescription", row)
        self.assertIn("investigatingAgencies", row)

    def test_missing_cases_key_returns_empty_list(self):
        self.assertEqual(orchestrator.parse_case_set("Missing Persons", {}), [])


class FormatCaseTextTests(unittest.TestCase):
    def test_formats_live_fixture_case(self):
        fixture = Path(__file__).parent / "fixtures" / "unidentified_full_case_response_alt.json"
        raw = json.loads(fixture.read_text(encoding="utf-8"))
        parsed = orchestrator.parse_case_set("Unidentified Persons", {"cases": [raw]})[0]

        lines = orchestrator.format_case_text(parsed).splitlines()

        self.assertEqual(lines[0], "Unidentified Persons: 86-0099")
        for expected in (
            "Identifiers:",
            "  Case Number: 86-0099",
            "  Case Link: https://www.namus.gov/UnidentifiedPersons/Case#/163353?nav",
            "  Case Resolved: No",
            "Demographics:",
            "  Sex: Male",
            "Age: None",
            "  Height Min Inches: 70",
            "  Eye Color: Brown",
            "  Hair Color: Black",
            "Physical Features: None",
            "Circumstances:",
            "  Status: Unidentified Deceased",
            "  Date Found: 1986-03-04",
            "  City: Columbia",
            "  County: Richland",
            "  State: SC",
            "Clothing and Accessories:",
            "    Category: Accessories",
            "    Description: Reddish-brown pullover short sleeved shirt Blue work pants "
            "Black socks w/white ring around tops. Black belt.",
            "Investigating Agencies:",
            "    Name: Richland County Coroner's Office",
            "    City: Columbia",
            "    State: SC",
            "    Name: South Carolina Law Enforcement Division",
            "Media:",
            "  Has Photo: Yes",
            "  Image Count: 3",
            "Vehicles:",
            "  Count: 0",
        ):
            self.assertIn(expected, lines)

        # Empty values are left out, so there is no blank "Name:" line under Demographics.
        self.assertNotIn("  Name:", lines)
        self.assertFalse(any("Top Level Keys" in line for line in lines))
        # Agencies show only name, city, and state. The case number is under Identifiers.
        self.assertFalse(any(("Selection" in line or "Agency Type" in line) for line in lines))
        self.assertEqual(sum("Case Number:" in line for line in lines), 1)
        self.assertFalse(any("Formatted ID" in line for line in lines))
        # Multi line free text is joined onto one line.
        self.assertTrue(all(not line.startswith("Blue work pants") for line in lines))

    def test_formats_live_missing_person_fixture(self):
        fixture = Path(__file__).parent / "fixtures" / "missing_full_case_response.json"
        raw = json.loads(fixture.read_text(encoding="utf-8"))
        parsed = orchestrator.parse_case_set("Missing Persons", {"cases": [raw]})[0]

        lines = orchestrator.format_case_text(parsed).splitlines()

        self.assertEqual(lines[0], "Missing Persons: IRIE SAWYER HEINES")
        for expected in (
            "  Case Link: https://www.namus.gov/MissingPersons/Case#/163404?nav",
            "Demographics:",
            "  First Name: IRIE",
            "  Middle Name: SAWYER",
            "  Last Name: HEINES",
            "  Sex: Female",
            "Age:",
            "  Age When Missing: 16",
            "  Age Now: 16",
            "  Projected Birth Years: 2009-2010",
            "  Eye Color: Blue",
            "  Head Hair: HAIR IS BLACK, BLONDE, AND PINK",
            "Physical Features:",
            "    Type: Tattoo",
            "  Date Last Contact: 2026-10-03",
            "  City: Yulee",
            "  County: Nassau",
            "    Name: Nassau County Sheriff's Office",
            "  Has Photo: Yes",
        ):
            self.assertIn(expected, lines)
        self.assertFalse(any(line.startswith("  Date of Birth") for line in lines))



    def test_formats_unidentified_case_with_projected_birth_years(self):
        fixture = Path(__file__).parent / "fixtures" / "unidentified_full_case_response.json"
        raw = json.loads(fixture.read_text(encoding="utf-8"))
        parsed = orchestrator.parse_case_set("Unidentified Persons", {"cases": [raw]})[0]

        text = orchestrator.format_case_text(parsed).splitlines()

        # Found 2024-10-10, estimated age 25 to 35.
        self.assertIn("  Projected Birth Years: 1988-1999", text)
        self.assertIn("  Projected Age At Death: 25-35", text)
        self.assertNotIn("Age: None", text)
        self.assertFalse(any(line.strip().startswith(("Age When Missing", "Age Now")) for line in text))


    def test_shows_date_of_birth_when_known(self):
        raw = {
            "subjectIdentification": {
                "firstName": "Jane",
                "dateOfBirth": "2010-05-17",
                "computedMissingMinAge": 15,
                "computedMissingMaxAge": 15,
            },
        }
        parsed = orchestrator.parse_case_set("Missing Persons", {"cases": [raw]})[0]

        text = orchestrator.format_case_text(parsed).splitlines()

        self.assertIn("  Date of Birth: 2010-05-17", text)
        self.assertIn("  Projected Birth Years: 2010", text)
        # Shown once, with the ages, and not repeated under Demographics.
        self.assertEqual(sum("Date of Birth" in line for line in text), 1)
        self.assertLess(text.index("Age:"), text.index("  Date of Birth: 2010-05-17"))

    def test_omits_date_of_birth_when_unknown(self):
        parsed = orchestrator.parse_case_set("Missing Persons", {"cases": [{}]})[0]

        text = orchestrator.format_case_text(parsed).splitlines()

        self.assertFalse(any("Date of Birth" in line for line in text))
        self.assertIn("Age: None", text)
        self.assertIn("Clothing and Accessories: None", text)
        self.assertEqual(text[0], "Missing Persons: Unknown")


class MissingFullExportPipelineTests(unittest.TestCase):
    """Run the real MissingFullExport, with only the NamUs HTTP calls stubbed."""

    @patch.object(orchestrator.unidentified_full_export, "fetch_unidentified_details")
    @patch.object(orchestrator.missing_full_export.mp, "fetch_case_detail")
    @patch.object(orchestrator.missing_full_export.mp, "search_missing_persons")
    def test_missing_full_export_feeds_orchestrator_and_parser(self, search, detail, up_fetch):
        fixture_path = Path(__file__).parent / "fixtures" / "missing_full_case_response.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        # What NamUs returns before the export adds its own fields.
        api_payload = {k: v for k, v in fixture.items() if k not in ("Case Link", "Case Set")}

        search.return_value = {"count": 1, "results": [{"namus2Number": 163404}]}
        detail.return_value = api_payload
        up_fetch.return_value = {"cases": []}

        combined = orchestrator.fetch_all_case_sets(orchestrator._parse_args(["--take", "1"]))

        search.assert_called_once()
        detail.assert_called_once_with(163404, session=ANY)
        self.assertEqual(combined["counts"], {"Missing Persons": 1, "Unidentified Persons": 0})

        case = combined["cases"][0]
        # The link comes from MissingFullExport.build_case_link, not the fixture.
        self.assertEqual(case["Case Link"], fixture["Case Link"])
        self.assertEqual(case["Case Set"], "Missing Persons")
        self.assertEqual(case["Breakdown"]["Identifiers"]["Case Link"], fixture["Case Link"])
        self.assertEqual(case["Breakdown"]["Demographics"]["Name"], "IRIE SAWYER HEINES")
        self.assertEqual(case["Breakdown"]["Circumstances"]["Date Last Contact"], "2026-10-03")
        self.assertEqual(case["Investigating Agency Summary"], "Nassau County Sheriff's Office")


if __name__ == "__main__":
    unittest.main(verbosity=2)

