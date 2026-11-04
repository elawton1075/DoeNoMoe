"""Unit tests for CaseParser.py."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from CaseModels import (
    AgencyDetails,
    AgencySelection,
    InvestigatingAgency,
    NamedValue,
    ParsedCase,
)
from CaseParser import CaseParser


class CaseParserTests(unittest.TestCase):
    def test_parse_missing_case(self):
        parser = CaseParser()
        raw = {
            "id": 1,
            "idFormatted": "MP00001",
            "Case Link": "https://www.namus.gov/MissingPersons/Case#/1?nav",
            "Case Set": "Missing Persons",
            "caseIdentification": {"caseNumber": "CN-1"},
            "subjectIdentification": {
                "firstName": "Jane",
                "lastName": "Doe",
                "computedMissingMinAge": 12,
                "computedMissingMaxAge": 13,
            },
            "physicalDescription": {
                "eyeColor": {"name": "Brown"},
                "hairColor": {"name": "Black"},
            },
            "physicalFeatureDescriptions": [
                {"physicalFeatureType": {"name": "Scar"}, "description": "left cheek"}
            ],
            "investigatingAgencies": [{"name": "Agency One"}, {"name": "Agency Two"}],
            "clothingAndAccessoriesArticles": [
                {"articleType": {"name": "Shirt"}, "description": "Blue"}
            ],
        }

        parsed = parser.parse_case(raw, "Missing Persons")

        self.assertEqual(parsed["Breakdown"]["Age"]["When Missing"], {"Min": 12, "Max": 13})
        self.assertEqual(parsed["Breakdown"]["Age"]["Now"], {"Min": None, "Max": None})
        self.assertEqual(parsed["Breakdown"]["Age"]["Projected Birth Years"], {"Min": None, "Max": None})
        self.assertEqual(parsed["Eye Color"], "Brown")
        self.assertEqual(parsed["Hair Color"], "Black")
        self.assertEqual(parsed["Physical Features Summary"], "Scar")
        self.assertEqual(parsed["Investigating Agency Summary"], "Agency One, Agency Two")
        self.assertNotIn("physicalDescription", parsed)
        self.assertNotIn("subjectIdentification", parsed)

    def test_parse_unidentified_case(self):
        parser = CaseParser()
        raw = {
            "id": 2,
            "idFormatted": "UP00002",
            "Case Link": "https://www.namus.gov/UnidentifiedPersons/Case#/2?nav",
            "Case Set": "Unidentified Persons",
            "subjectDescription": {"estimatedAgeFrom": 22, "estimatedAgeTo": 30},
            "circumstances": {"dateFound": "2000-06-01"},
            "physicalDescription": {
                "eyeColor": {"name": "Blue"},
                "hairColor": {"name": "Brown"},
            },
            "investigatingAgencies": [{"name": "Agency Three"}],
        }

        parsed = parser.parse_case(raw, "Unidentified Persons")

        # Found in 2000 aged 22 to 30: born 1969 (oldest) through 1978 (youngest).
        self.assertEqual(parsed["Breakdown"]["Age"]["Projected Birth Years"], {"Min": 1969, "Max": 1978})
        self.assertEqual(parsed["Breakdown"]["Age"]["When Missing"], {"Min": None, "Max": None})
        self.assertEqual(parsed["Breakdown"]["Age"]["Now"], {"Min": None, "Max": None})
        self.assertEqual(parsed["Investigating Agency Summary"], "Agency Three")

    def test_parse_unidentified_full_response_fixture(self):
        parser = CaseParser()
        fixture_path = Path(__file__).parent / "fixtures" / "unidentified_full_case_response_alt.json"
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))

        parsed = parser.parse_case(raw, "Unidentified Persons")

        self.assertEqual(parsed["id"], 163353)
        empty = {"Min": None, "Max": None}
        self.assertEqual(
            parsed["Breakdown"]["Age"],
            {"When Missing": empty, "Now": empty, "Projected Birth Years": empty},
        )
        self.assertEqual(parsed["Eye Color"], "Brown")
        self.assertEqual(parsed["Hair Color"], "Black")
        self.assertEqual(parsed["Breakdown"]["Physical Features"]["Count"], 0)
        self.assertEqual(
            parsed["Investigating Agency Summary"],
            "Richland County Coroner's Office, South Carolina Law Enforcement Division",
        )
        self.assertEqual(parsed["Breakdown"]["Media"]["Has Photo"], True)
        self.assertEqual(parsed["Breakdown"]["Media"]["Image Count"], 3)
        self.assertEqual(parsed["Breakdown"]["Media"]["Document Count"], 0)

        self.assertNotIn("subjectDescription", parsed)
        self.assertNotIn("physicalDescription", parsed)
        self.assertNotIn("physicalFeatureDescriptions", parsed)
        self.assertNotIn("clothingAndAccessoriesArticles", parsed)
        self.assertNotIn("investigatingAgencies", parsed)

    def test_parse_case_object_returns_typed_custom_object(self):
        parser = CaseParser()
        fixture_path = Path(__file__).parent / "fixtures" / "unidentified_full_case_response_alt.json"
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))

        parsed_obj = parser.parse_case_object(raw, "Unidentified Persons")

        self.assertIsInstance(parsed_obj, ParsedCase)
        self.assertEqual(parsed_obj.breakdown.identifiers.id, 163353)
        self.assertEqual(parsed_obj.breakdown.physical_description.eye_color, "Brown")
        self.assertEqual(parsed_obj.breakdown.physical_description.hair_color, "Black")
        self.assertEqual(parsed_obj.breakdown.clothing_and_accessories.count, 2)
        self.assertEqual(parsed_obj.breakdown.media.image_count, 3)
        self.assertEqual(len(parsed_obj.breakdown.investigating_agencies), 2)

    def test_parse_case_includes_all_breakdown_fields_from_model(self):
        parser = CaseParser()
        fixture_path = Path(__file__).parent / "fixtures" / "unidentified_full_case_response_alt.json"
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))

        parsed_obj = parser.parse_case_object(raw, "Unidentified Persons")
        parsed_dict = parser.parse_case(raw, "Unidentified Persons")

        expected_breakdown = parsed_obj.breakdown.to_dict()
        self.assertEqual(parsed_dict["Breakdown"], expected_breakdown)
        self.assertEqual(set(parsed_dict["Breakdown"].keys()), set(expected_breakdown.keys()))


FIXTURE_DIR = Path(__file__).parent / "fixtures"

BREAKDOWN_KEYS = {
    "Identifiers",
    "Demographics",
    "Age",
    "Physical Description",
    "Clothing and Accessories",
    "Physical Features",
    "Circumstances",
    "Investigating Agencies",
    "Media",
    "Vehicles Count",
    "Top Level Keys",
}


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _named(id_, name, localized=None, display=None) -> dict:
    return {"ID": id_, "Name": name, "Localized Name": localized, "Display Name": display}


def _bare_agency(name: str) -> dict:
    """Expected agency when the payload only carries a name."""
    return {
        "ID": None,
        "Is Case Owner": None,
        "Name": name,
        "City": None,
        "State": None,
        "County": None,
        "Selection": None,
        "Case Number": None,
        "Date Reported": None,
    }


def _expected_163354() -> dict:
    """Expected parse of unidentified_full_case_response.json."""
    return {
        "Identifiers": {
            "ID": 163354,
            "Case Number": "UP-24-163354",
            "NCMEC Number": None,
            "NamUs Number": "163354",
            "Agency Case Number": "SO-2024-0119",
            "Case Set": "Unidentified Persons",
            "Case Link": "https://www.namus.gov/UnidentifiedPersons/Case#/163354?nav",
            "Case Resolved": False,
        },
        "Demographics": {
            "Name": "",
            "First Name": "",
            "Middle Name": "",
            "Last Name": "",
            "Date of Birth": None,
            "Year of Birth": None,
            "Sex": "Female",
            "Gender": "",
            "Primary Ethnicity": "Hispanic/Latino",
            "Primary Race": "White/Caucasian",
        },
        # Found 2024-10-10, estimated age 25 to 35: born 2024 - 35 - 1 through 2024 - 25.
        "Age": {
            "When Missing": {"Min": None, "Max": None},
            "Now": {"Min": None, "Max": None},
            "Projected Birth Years": {"Min": 1988, "Max": 1999},
            "Projected Age At Death": {"Min": 25, "Max": 35},
        },
        "Physical Description": {
            "Height Min Inches": 62,
            "Height Max Inches": 66,
            "Weight Min Pounds": 115,
            "Weight Max Pounds": 140,
            "Eye Color": "Brown",
            "Hair Color": "Black",
            "Head Hair": "Shoulder length",
            "Facial Hair": "",
            "Distinctive Features": "Mole under left eye",
        },
        "Clothing and Accessories": {
            "Count": 2,
            "Items": [
                {
                    "Category": "Top",
                    "Type": "T-shirt",
                    "Color": "Blue",
                    "Size": "",
                    "Brand": "",
                    "Description": "Blue cotton shirt",
                },
                {
                    "Category": "Jewelry",
                    "Type": "Ring",
                    "Color": "",
                    "Size": "",
                    "Brand": "",
                    "Description": "Silver ring with initials",
                },
            ],
        },
        "Physical Features": {
            "Count": 2,
            "Items": [
                {"Type": "Tattoo", "Location": "Right forearm", "Value": "", "Description": "Rose tattoo"},
                {"Type": "Scar", "Location": "Left knee", "Value": "", "Description": "Surgical scar"},
            ],
        },
        "Circumstances": {
            "Status": "Unidentified",
            "Date Found": "2024-10-10",
            "Date Body Found": None,
            "Date Last Contact": None,
            "City": "Phoenix",
            "County": "Maricopa",
            "State": "Arizona",
            "Country": "United States",
            "Zip": "85004",
            "Circumstances of Disappearance": None,
            "Circumstances of Recovery": "Found near hiking trail",
        },
        "Investigating Agencies": [
            _bare_agency("Maricopa County Office of the Medical Examiner"),
            _bare_agency("Phoenix Police Department"),
        ],
        "Media": {"Has Photo": True, "Image Count": 1, "Document Count": 1},
        "Vehicles Count": 0,
    }


def _expected_163353(raw: dict) -> dict:
    """Expected parse of unidentified_full_case_response_alt.json (live NamUs payload)."""
    circ = raw["circumstances"]
    clothing = raw["clothingAndAccessoriesArticles"]
    return {
        "Identifiers": {
            "ID": 163353,
            "Case Number": "86-0099",
            "NCMEC Number": None,
            "NamUs Number": None,
            "Agency Case Number": None,
            "Case Set": "Unidentified Persons",
            "Case Link": "https://www.namus.gov/UnidentifiedPersons/Case#/163353?nav",
            "Case Resolved": False,
        },
        "Demographics": {
            "Name": "",
            "First Name": "",
            "Middle Name": "",
            "Last Name": "",
            "Date of Birth": None,
            "Year of Birth": None,
            "Sex": "Male",
            "Gender": "",
            "Primary Ethnicity": "Black / African American",
            "Primary Race": "",
        },
        # Only an age group is given, no numeric estimate, so nothing can be projected.
        "Age": {
            "When Missing": {"Min": None, "Max": None},
            "Now": {"Min": None, "Max": None},
            "Projected Birth Years": {"Min": None, "Max": None},
        },
        "Physical Description": {
            "Height Min Inches": 70,
            "Height Max Inches": 71,
            "Weight Min Pounds": 170,
            "Weight Max Pounds": 180,
            "Eye Color": "Brown",
            "Hair Color": "Black",
            "Head Hair": "",
            "Facial Hair": "",
            "Distinctive Features": "",
        },
        "Clothing and Accessories": {
            "Count": 2,
            "Items": [
                {
                    "Category": "Accessories",
                    "Type": "",
                    "Color": "",
                    "Size": "",
                    "Brand": "",
                    "Description": clothing[0]["description"].strip(),
                },
                {
                    "Category": "Clothing",
                    "Type": "",
                    "Color": "",
                    "Size": "",
                    "Brand": "",
                    "Description": clothing[1]["description"].strip(),
                },
            ],
        },
        "Physical Features": {"Count": 0, "Items": []},
        "Circumstances": {
            "Status": "Unidentified Deceased",
            "Date Found": "1986-03-04",
            "Date Body Found": None,
            "Date Last Contact": None,
            "City": "Columbia",
            "County": "Richland",
            "State": "SC",
            "Country": "",
            "Zip": "29201",
            "Circumstances of Disappearance": None,
            "Circumstances of Recovery": circ["circumstancesOfRecovery"],
        },
        "Investigating Agencies": [
            {
                "ID": 53439,
                "Is Case Owner": False,
                "Name": "Richland County Coroner's Office",
                "City": "Columbia",
                "State": _named(5, "South Carolina", localized="SC"),
                "County": _named(2422, "Richland County", localized="Richland"),
                "Selection": {
                    "ID": 65027,
                    "Agency": {
                        "ID": 43363,
                        "Name": "Richland County Coroner's Office",
                        "Street 1": "6300 Shakespeare Road",
                        "City": "Columbia",
                        "County": _named(2422, "Richland County", localized="Richland"),
                        "Zip Code": "29223",
                        "State": _named(5, "South Carolina", localized="SC"),
                        "Phone": "8035761799",
                        "Jurisdiction": _named(3, "County", localized="County"),
                        "Agency Type": _named(3, "Coroner", localized="Coroner"),
                        "Approved": True,
                        "Website URL": "https://rccosc.com/",
                    },
                },
                "Case Number": "86-0099",
                "Date Reported": "1986-03-04",
            },
            {
                "ID": 53449,
                "Is Case Owner": False,
                "Name": "South Carolina Law Enforcement Division",
                "City": "Columbia",
                "State": _named(5, "South Carolina", localized="SC"),
                "County": _named(2422, "Richland County", localized="Richland"),
                "Selection": {
                    "ID": 65028,
                    "Agency": {
                        "ID": 43618,
                        "Name": "South Carolina Law Enforcement Division",
                        "Street 1": "4400 Broad River Road",
                        "City": "Columbia",
                        "County": _named(2422, "Richland County", localized="Richland"),
                        "Zip Code": "29210",
                        "State": _named(5, "South Carolina", localized="SC"),
                        "Phone": None,
                        "Jurisdiction": _named(2, "State", localized="State"),
                        "Agency Type": _named(1, "Law Enforcement", localized="Law Enforcement"),
                        "Approved": True,
                        "Website URL": "https://www.sled.sc.gov/",
                    },
                },
                "Case Number": "MC-88-0276",
                "Date Reported": None,
            },
        ],
        "Media": {"Has Photo": True, "Image Count": 3, "Document Count": 0},
        "Vehicles Count": 0,
    }


class CaseParserFixtureTests(unittest.TestCase):
    """Parse every fixture case and verify each parsed field."""

    def setUp(self):
        self.parser = CaseParser()
        self.fixture_paths = sorted(FIXTURE_DIR.glob("*.json"))

    def test_fixture_directory_has_cases(self):
        self.assertGreaterEqual(len(self.fixture_paths), 2)

    def test_every_fixture_parses_with_expected_structure(self):
        """Generic invariants that must hold for any fixture added to the folder."""
        for path in self.fixture_paths:
            with self.subTest(fixture=path.name):
                raw = json.loads(path.read_text(encoding="utf-8"))
                case_set = raw["Case Set"]
                parsed = self.parser.parse_case(raw, case_set)
                breakdown = parsed["Breakdown"]

                self.assertEqual(set(breakdown.keys()), BREAKDOWN_KEYS)

                # Every parsed source blob is removed from the output.
                for key in CaseParser.PRUNED_PARSED_BLOBS:
                    self.assertNotIn(key, parsed)

                # Every other raw key is preserved untouched.
                for key, value in raw.items():
                    if key in CaseParser.PRUNED_PARSED_BLOBS:
                        continue
                    self.assertIn(key, parsed)
                    self.assertEqual(parsed[key], value)

                # Flattened top level fields come from the nested models.
                self.assertEqual(parsed["Eye Color"], breakdown["Physical Description"]["Eye Color"])
                self.assertEqual(parsed["Hair Color"], breakdown["Physical Description"]["Hair Color"])
                self.assertEqual(
                    parsed["Physical Features Summary"],
                    ", ".join(dict.fromkeys(
                        i["Type"] or i["Description"] or i["Value"]
                        for i in breakdown["Physical Features"]["Items"]
                        if i["Type"] or i["Description"] or i["Value"]
                    )),
                )
                self.assertEqual(
                    parsed["Investigating Agency Summary"],
                    ", ".join(dict.fromkeys(
                        a["Name"] for a in breakdown["Investigating Agencies"] if a["Name"]
                    )),
                )

                # Every raw agency field is carried into its model.
                raw_agencies = raw.get("investigatingAgencies") or []
                self.assertEqual(len(breakdown["Investigating Agencies"]), len(raw_agencies))
                for parsed_agency, raw_agency in zip(breakdown["Investigating Agencies"], raw_agencies):
                    self.assertEqual(parsed_agency["ID"], raw_agency.get("id"))
                    self.assertEqual(parsed_agency["Is Case Owner"], raw_agency.get("isCaseOwner"))
                    self.assertEqual(parsed_agency["Name"], raw_agency.get("name"))
                    self.assertEqual(parsed_agency["City"], raw_agency.get("city"))
                    self.assertEqual(parsed_agency["Case Number"], raw_agency.get("caseNumber"))
                    self.assertEqual(parsed_agency["Date Reported"], raw_agency.get("dateReported"))
                    raw_agency_record = (raw_agency.get("selection") or {}).get("agency") or {}
                    parsed_record = (parsed_agency["Selection"] or {}).get("Agency") or {}
                    self.assertEqual(parsed_record.get("Website URL"), raw_agency_record.get("websiteUrl"))
                    self.assertEqual(parsed_record.get("Zip Code"), raw_agency_record.get("zipCode"))

                # Counts agree with the lists they summarize.
                self.assertEqual(
                    breakdown["Clothing and Accessories"]["Count"],
                    len(breakdown["Clothing and Accessories"]["Items"]),
                )
                self.assertEqual(
                    breakdown["Physical Features"]["Count"],
                    len(breakdown["Physical Features"]["Items"]),
                )
                self.assertEqual(breakdown["Clothing and Accessories"]["Count"], len(raw.get("clothingAndAccessoriesArticles") or []))
                self.assertEqual(breakdown["Physical Features"]["Count"], len(raw.get("physicalFeatureDescriptions") or []))
                self.assertEqual(len(breakdown["Investigating Agencies"]), len(raw.get("investigatingAgencies") or []))
                self.assertEqual(breakdown["Media"]["Image Count"], len(raw.get("images") or []))
                self.assertEqual(breakdown["Media"]["Document Count"], len(raw.get("documents") or []))
                self.assertEqual(breakdown["Vehicles Count"], len(raw.get("vehicles") or []))
                self.assertEqual(breakdown["Top Level Keys"], sorted(raw.keys()))

                # Identifiers always carry through id, link, and case set.
                self.assertEqual(breakdown["Identifiers"]["ID"], raw["id"])
                self.assertEqual(breakdown["Identifiers"]["Case Link"], raw["Case Link"])
                self.assertEqual(breakdown["Identifiers"]["Case Set"], case_set)

    def test_fixture_163354_parses_every_field(self):
        raw = _load_fixture("unidentified_full_case_response.json")
        parsed = self.parser.parse_case(raw, "Unidentified Persons")
        self.assertEqual(
            {k: v for k, v in parsed["Breakdown"].items() if k != "Top Level Keys"},
            _expected_163354(),
        )

    def test_fixture_163353_parses_every_field(self):
        raw = _load_fixture("unidentified_full_case_response_alt.json")
        parsed = self.parser.parse_case(raw, "Unidentified Persons")
        self.assertEqual(
            {k: v for k, v in parsed["Breakdown"].items() if k != "Top Level Keys"},
            _expected_163353(raw),
        )

    def test_breakdown_does_not_duplicate_nested_model_values(self):
        """Values owned by a nested model are not stored again on CaseBreakdown."""
        duplicated_keys = {
            "Eye Color",
            "Hair Color",
            "Physical Features Summary",
            "Investigating Agencies Summary",
        }
        for path in self.fixture_paths:
            with self.subTest(fixture=path.name):
                raw = json.loads(path.read_text(encoding="utf-8"))
                parsed_obj = self.parser.parse_case_object(raw, raw["Case Set"])
                breakdown_dict = parsed_obj.breakdown.to_dict()

                self.assertTrue(duplicated_keys.isdisjoint(breakdown_dict.keys()))
                self.assertNotIn("Status", breakdown_dict["Identifiers"])
                self.assertIn("Status", breakdown_dict["Circumstances"])

                # Derived values read straight from the nested models.
                self.assertEqual(
                    parsed_obj.breakdown.eye_color,
                    parsed_obj.breakdown.physical_description.eye_color,
                )
                self.assertEqual(
                    parsed_obj.breakdown.hair_color,
                    parsed_obj.breakdown.physical_description.hair_color,
                )
                self.assertEqual(
                    parsed_obj.breakdown.physical_features_summary,
                    parsed_obj.breakdown.physical_features.summary,
                )

    def test_missing_person_fixture_parses_key_fields(self):
        raw = _load_fixture("missing_full_case_response.json")
        parsed = self.parser.parse_case(raw, "Missing Persons")
        b = parsed["Breakdown"]

        self.assertEqual(b["Identifiers"]["ID"], 163404)
        self.assertNotIn("Formatted ID", b["Identifiers"])
        self.assertEqual(b["Identifiers"]["Case Set"], "Missing Persons")

        self.assertEqual(b["Demographics"]["Name"], "IRIE SAWYER HEINES")
        self.assertEqual(b["Demographics"]["Sex"], "Female")
        self.assertEqual(b["Demographics"]["Primary Ethnicity"], "White / Caucasian")

        # Missing cases use the known age window, not an estimate.
        # Age when she went missing and her age now are kept separately.
        self.assertEqual(b["Age"]["When Missing"], {"Min": 16, "Max": 16})
        self.assertEqual(b["Age"]["Now"], {"Min": 16, "Max": 16})
        # No birth date on file, so project it: aged 16 on 2026-10-03 means born
        # 2026 - 16 - 1 = 2009 through 2026 - 16 = 2010.
        self.assertEqual(b["Age"]["Projected Birth Years"], {"Min": 2009, "Max": 2010})

        physical = b["Physical Description"]
        self.assertEqual(physical["Height Min Inches"], 69)
        self.assertEqual(physical["Weight Min Pounds"], 120)
        self.assertEqual(physical["Eye Color"], "Blue")
        self.assertEqual(physical["Hair Color"], "Other")
        # Missing payloads call this headHairDescription.
        self.assertEqual(physical["Head Hair"], "HAIR IS BLACK, BLONDE, AND PINK")

        self.assertEqual(b["Clothing and Accessories"]["Count"], 1)
        self.assertEqual(b["Clothing and Accessories"]["Items"][0]["Category"], "Clothing")
        self.assertEqual(parsed["Physical Features Summary"], "Tattoo")

        # Missing payloads put the location and last contact date under sighting.
        circumstances = b["Circumstances"]
        self.assertEqual(circumstances["Date Last Contact"], "2026-10-03")
        self.assertEqual(circumstances["City"], "Yulee")
        self.assertEqual(circumstances["State"], "FL")
        self.assertEqual(circumstances["Zip"], "32097")

        self.assertEqual(parsed["Investigating Agency Summary"], "Nassau County Sheriff's Office")
        self.assertTrue(b["Media"]["Has Photo"])

    def test_investigating_agencies_are_typed_models(self):
        raw = _load_fixture("unidentified_full_case_response_alt.json")
        agencies = self.parser.parse_case_object(raw, "Unidentified Persons").breakdown.investigating_agencies

        self.assertEqual(len(agencies), 2)
        for agency in agencies:
            self.assertIsInstance(agency, InvestigatingAgency)
            self.assertIsInstance(agency.state, NamedValue)
            self.assertIsInstance(agency.county, NamedValue)
            self.assertIsInstance(agency.selection, AgencySelection)
            self.assertIsInstance(agency.selection.agency, AgencyDetails)
            self.assertIsInstance(agency.selection.agency.agency_type, NamedValue)

        coroner = agencies[0]
        self.assertEqual(coroner.name, "Richland County Coroner's Office")
        self.assertEqual(coroner.state.localized_name, "SC")
        self.assertEqual(coroner.county.localized_name, "Richland")
        self.assertEqual(coroner.selection.agency.agency_type.name, "Coroner")
        self.assertEqual(coroner.selection.agency.jurisdiction.name, "County")
        self.assertEqual(coroner.selection.agency.phone, "8035761799")
        self.assertTrue(coroner.selection.agency.approved)

        # The source's stateDisplayName and countyDisplayName are not stored twice.
        self.assertFalse(hasattr(coroner, "state_display_name"))
        self.assertFalse(hasattr(coroner, "county_display_name"))

    def test_typed_object_matches_serialized_breakdown_for_every_fixture(self):
        for path in self.fixture_paths:
            with self.subTest(fixture=path.name):
                raw = json.loads(path.read_text(encoding="utf-8"))
                case_set = raw["Case Set"]
                parsed_obj = self.parser.parse_case_object(raw, case_set)
                parsed_dict = self.parser.parse_case(raw, case_set)
                self.assertIsInstance(parsed_obj, ParsedCase)
                self.assertEqual(parsed_dict["Breakdown"], parsed_obj.breakdown.to_dict())


class CaseParserAgeTests(unittest.TestCase):
    def setUp(self):
        self.parser = CaseParser()

    def _age(self, raw: dict, case_set: str) -> dict:
        return self.parser.parse_case(raw, case_set)["Breakdown"]["Age"]

    def test_missing_keeps_age_when_missing_and_age_now_apart(self):
        age = self._age(
            {
                "subjectIdentification": {
                    "computedMissingMinAge": 12,
                    "computedMissingMaxAge": 13,
                    "currentMinAge": 16,
                    "currentMaxAge": 17,
                }
            },
            "Missing Persons",
        )
        self.assertEqual(age["When Missing"], {"Min": 12, "Max": 13})
        self.assertEqual(age["Now"], {"Min": 16, "Max": 17})

    def test_missing_age_zero_is_kept(self):
        age = self._age(
            {
                "subjectIdentification": {
                    "computedMissingMinAge": 0,
                    "computedMissingMaxAge": 0,
                    "currentMinAge": 2,
                    "currentMaxAge": 2,
                }
            },
            "Missing Persons",
        )
        self.assertEqual(age["When Missing"], {"Min": 0, "Max": 0})
        self.assertEqual(age["Now"], {"Min": 2, "Max": 2})

    def test_missing_single_bound_fills_the_other(self):
        age = self._age({"subjectIdentification": {"computedMissingMinAge": 14}}, "Missing Persons")
        self.assertEqual(age["When Missing"], {"Min": 14, "Max": 14})
        self.assertEqual(age["Now"], {"Min": None, "Max": None})

    def test_missing_with_no_age_data_is_empty(self):
        age = self._age({}, "Missing Persons")
        for key in ("When Missing", "Now", "Projected Birth Years"):
            self.assertEqual(age[key], {"Min": None, "Max": None})

    def test_unidentified_projects_birth_years_from_age_and_date_found(self):
        # Age 30 on 1986-03-04 means born 1955-03-05 through 1956-03-04, so a
        # 25 to 35 estimate gives 1986 - 35 - 1 = 1950 through 1986 - 25 = 1961.
        age = self._age(
            {
                "subjectDescription": {"estimatedAgeFrom": 25, "estimatedAgeTo": 35},
                "circumstances": {"dateFound": "1986-03-04"},
            },
            "Unidentified Persons",
        )
        self.assertEqual(age["Projected Birth Years"], {"Min": 1950, "Max": 1961})
        self.assertEqual(age["Projected Age At Death"], {"Min": 25, "Max": 35})
        self.assertEqual(age["When Missing"], {"Min": None, "Max": None})
        self.assertEqual(age["Now"], {"Min": None, "Max": None})

    def test_unidentified_single_estimate_bound_uses_it_for_both(self):
        age = self._age(
            {
                "subjectDescription": {"estimatedAgeFrom": 40},
                "circumstances": {"dateFound": "2000-01-01"},
            },
            "Unidentified Persons",
        )
        self.assertEqual(age["Projected Birth Years"], {"Min": 1959, "Max": 1960})

    def test_unidentified_age_zero_still_projects(self):
        age = self._age(
            {
                "subjectDescription": {"estimatedAgeFrom": 0, "estimatedAgeTo": 0},
                "circumstances": {"dateFound": "2000-01-01"},
            },
            "Unidentified Persons",
        )
        self.assertEqual(age["Projected Birth Years"], {"Min": 1999, "Max": 2000})

    def test_unidentified_without_date_found_has_no_projection(self):
        age = self._age(
            {"subjectDescription": {"estimatedAgeFrom": 25, "estimatedAgeTo": 35}},
            "Unidentified Persons",
        )
        self.assertEqual(age["Projected Birth Years"], {"Min": None, "Max": None})

    def test_unidentified_with_unreadable_date_found_has_no_projection(self):
        age = self._age(
            {
                "subjectDescription": {"estimatedAgeFrom": 25, "estimatedAgeTo": 35},
                "circumstances": {"dateFound": "unknown"},
            },
            "Unidentified Persons",
        )
        self.assertEqual(age["Projected Birth Years"], {"Min": None, "Max": None})

    def test_unidentified_without_numeric_age_has_no_projection(self):
        age = self._age({"circumstances": {"dateFound": "1986-03-04"}}, "Unidentified Persons")
        self.assertEqual(age["Projected Birth Years"], {"Min": None, "Max": None})

    def test_missing_birth_date_gives_exact_birth_year(self):
        raw = {
            "subjectIdentification": {
                "dateOfBirth": "2010-05-17",
                "computedMissingMinAge": 15,
                "computedMissingMaxAge": 16,
            },
            "sighting": {"date": "2026-10-03"},
        }
        # The exact birth date wins over projecting from the age.
        self.assertEqual(self._age(raw, "Missing Persons")["Projected Birth Years"], {"Min": 2010, "Max": 2010})

    def test_missing_computed_birth_date_is_used(self):
        raw = {"subjectIdentification": {"computedDateOfBirth": "1999-01-02"}}
        self.assertEqual(self._age(raw, "Missing Persons")["Projected Birth Years"], {"Min": 1999, "Max": 1999})

    def test_missing_year_of_birth_is_used(self):
        raw = {"subjectIdentification": {"yearOfBirth": 1985}}
        self.assertEqual(self._age(raw, "Missing Persons")["Projected Birth Years"], {"Min": 1985, "Max": 1985})

    def test_missing_projects_from_age_when_missing_and_sighting_date(self):
        raw = {
            "subjectIdentification": {"computedMissingMinAge": 15, "computedMissingMaxAge": 16},
            "sighting": {"date": "2020-06-01"},
        }
        # 2020 - 16 - 1 = 2003 through 2020 - 15 = 2005.
        self.assertEqual(self._age(raw, "Missing Persons")["Projected Birth Years"], {"Min": 2003, "Max": 2005})

    def test_missing_projection_prefers_date_of_last_contact(self):
        raw = {
            "subjectIdentification": {"computedMissingMinAge": 10, "computedMissingMaxAge": 10},
            "circumstances": {"dateOfLastContact": "2015-03-03"},
            "sighting": {"date": "2020-06-01"},
        }
        self.assertEqual(self._age(raw, "Missing Persons")["Projected Birth Years"], {"Min": 2004, "Max": 2005})

    def test_missing_without_any_date_has_no_projection(self):
        raw = {"subjectIdentification": {"computedMissingMinAge": 15, "computedMissingMaxAge": 16}}
        self.assertEqual(self._age(raw, "Missing Persons")["Projected Birth Years"], {"Min": None, "Max": None})

    def test_missing_without_birth_date_or_age_has_no_projection(self):
        raw = {"sighting": {"date": "2020-06-01"}}
        self.assertEqual(self._age(raw, "Missing Persons")["Projected Birth Years"], {"Min": None, "Max": None})

    def test_missing_and_unidentified_birth_years_can_be_compared(self):
        missing = self.parser.parse_case_object(
            _load_fixture("missing_full_case_response.json"), "Missing Persons"
        ).breakdown.age.projected_birth_years  # 2009 through 2010

        same_era = self.parser.parse_case_object(
            {
                "subjectDescription": {"estimatedAgeFrom": 10, "estimatedAgeTo": 11},
                "circumstances": {"dateFound": "2020-01-01"},
            },
            "Unidentified Persons",
        ).breakdown.age.projected_birth_years  # 2008 through 2010

        other_era = self.parser.parse_case_object(
            {
                "subjectDescription": {"estimatedAgeFrom": 22, "estimatedAgeTo": 30},
                "circumstances": {"dateFound": "2000-06-01"},
            },
            "Unidentified Persons",
        ).breakdown.age.projected_birth_years  # 1969 through 1978

        no_estimate = self.parser.parse_case_object({}, "Unidentified Persons").breakdown.age.projected_birth_years

        self.assertTrue(missing.overlaps(same_era))
        self.assertTrue(same_era.overlaps(missing))
        self.assertFalse(missing.overlaps(other_era))
        self.assertFalse(missing.overlaps(no_estimate))


if __name__ == "__main__":
    unittest.main(verbosity=2)
