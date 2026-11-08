"""
Data parsing tests.

Raw NamUs case payloads in, typed CaseModels values out: which source field
becomes which model value, how ages and birth years are projected, and how the
typed object is built without touching its input.
"""

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
    ValueRange,
)
from CaseParser import CaseParser, has_case_photo
import CaseOrchestrator as orchestrator

FIXTURE_DIR = Path(__file__).parent / "fixtures"


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


class ValueRangeTests(unittest.TestCase):
    """The range primitive every age and birth-year value is built from."""

    def test_no_values(self):
        value = ValueRange()
        self.assertFalse(value.is_known)
        self.assertEqual(value.range_text, "N/A")
        self.assertEqual(value.to_dict(), {"Min": None, "Max": None})

    def test_single_value(self):
        self.assertEqual(ValueRange(22, 22).range_text, "22")

    def test_range(self):
        value = ValueRange(22, 30)
        self.assertTrue(value.is_known)
        self.assertEqual(value.range_text, "22-30")
        self.assertEqual(value.to_dict(), {"Min": 22, "Max": 30})

    def test_only_one_bound(self):
        self.assertEqual(ValueRange(None, 30).range_text, "30")
        self.assertEqual(ValueRange(22, None).range_text, "22")
        self.assertTrue(ValueRange(None, 30).is_known)

    def test_zero_is_a_real_value(self):
        self.assertTrue(ValueRange(0, 0).is_known)
        self.assertEqual(ValueRange(0, 0).range_text, "0")
        self.assertEqual(ValueRange(0, 2).range_text, "0-2")

    def test_reversed_bounds_are_ordered(self):
        self.assertEqual(ValueRange(30, 22).range_text, "22-30")

    def test_overlaps(self):
        self.assertTrue(ValueRange(2009, 2010).overlaps(ValueRange(2008, 2010)))
        self.assertTrue(ValueRange(2008, 2010).overlaps(ValueRange(2009, 2010)))
        self.assertTrue(ValueRange(2000, 2005).overlaps(ValueRange(2005, 2010)))  # shared edge
        self.assertTrue(ValueRange(2010, 2010).overlaps(ValueRange(2009, 2011)))

    def test_does_not_overlap(self):
        self.assertFalse(ValueRange(1969, 1978).overlaps(ValueRange(2009, 2010)))
        self.assertFalse(ValueRange(2000, 2004).overlaps(ValueRange(2005, 2010)))

    def test_unknown_range_never_overlaps(self):
        self.assertFalse(ValueRange().overlaps(ValueRange(2009, 2010)))
        self.assertFalse(ValueRange(2009, 2010).overlaps(ValueRange()))
        self.assertFalse(ValueRange().overlaps(ValueRange()))

    def test_single_bound_overlaps_as_a_point(self):
        self.assertTrue(ValueRange(None, 2010).overlaps(ValueRange(2009, 2011)))
        self.assertFalse(ValueRange(None, 2020).overlaps(ValueRange(2009, 2011)))


class CaseParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = CaseParser()

    def test_parse_missing_case(self):
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

        parsed = self.parser.parse_case(raw, "Missing Persons")

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

        parsed = self.parser.parse_case(raw, "Unidentified Persons")

        # Found in 2000 aged 22 to 30: born 1969 (oldest) through 1978 (youngest).
        self.assertEqual(parsed["Breakdown"]["Age"]["Projected Birth Years"], {"Min": 1969, "Max": 1978})
        self.assertEqual(parsed["Breakdown"]["Age"]["When Missing"], {"Min": None, "Max": None})
        self.assertEqual(parsed["Breakdown"]["Age"]["Now"], {"Min": None, "Max": None})
        self.assertEqual(parsed["Investigating Agency Summary"], "Agency Three")

    def test_parse_unidentified_full_response_fixture(self):
        raw = _load_fixture("unidentified_full_case_response_alt.json")

        parsed = self.parser.parse_case(raw, "Unidentified Persons")

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
        raw = _load_fixture("unidentified_full_case_response_alt.json")

        parsed_obj = self.parser.parse_case_object(raw, "Unidentified Persons")

        self.assertIsInstance(parsed_obj, ParsedCase)
        self.assertEqual(parsed_obj.breakdown.identifiers.id, 163353)
        self.assertEqual(parsed_obj.breakdown.physical_description.eye_color, "Brown")
        self.assertEqual(parsed_obj.breakdown.physical_description.hair_color, "Black")
        self.assertEqual(parsed_obj.breakdown.clothing_and_accessories.count, 2)
        self.assertEqual(parsed_obj.breakdown.media.image_count, 3)
        self.assertEqual(len(parsed_obj.breakdown.investigating_agencies), 2)


class CaseParserFixtureTests(unittest.TestCase):
    """Parse every fixture case and verify each parsed field."""

    def setUp(self):
        self.parser = CaseParser()

    def test_fixture_directory_has_cases(self):
        self.assertGreaterEqual(len(sorted(FIXTURE_DIR.glob("*.json"))), 2)

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


class HasCasePhotoTests(unittest.TestCase):
    """Photo presence is parsed from image content or image URL pointers."""

    def _case(self, **overrides) -> dict:
        case = {
            "images": [],
            "defaultImage": {},
            "hrefDefaultImageThumbnail": "",
            "hrefDefaultImagePoster": "",
        }
        case.update(overrides)
        return case

    def test_true_when_images_present(self):
        self.assertTrue(has_case_photo(self._case(images=[{"id": 10}])))

    def test_true_when_default_image_present(self):
        self.assertTrue(has_case_photo(self._case(defaultImage={"id": 99})))

    def test_true_when_only_default_image_urls_are_present(self):
        # NamUs routinely ships images: [] with usable href pointers, so an empty
        # image list is not evidence that the case has no photo.
        self.assertTrue(has_case_photo(self._case(hrefDefaultImageThumbnail="/api/.../Thumbnail")))
        self.assertTrue(has_case_photo(self._case(hrefDefaultImagePoster="/api/.../Poster")))

    def test_false_when_no_photo_fields(self):
        self.assertFalse(has_case_photo(self._case()))

    def test_empty_default_image_is_not_a_photo(self):
        self.assertFalse(has_case_photo(self._case(defaultImage={})))


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


if __name__ == "__main__":
    unittest.main(verbosity=2)