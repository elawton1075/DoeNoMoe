"""
Data mapping tests.

Parsed and normalized data out to the shapes callers consume: the serialized
Breakdown, the text report, the normalized case dicts, and the outbound search
payload and filter predicates that decide which rows those shapes carry.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

import CaseOrchestrator as orchestrator
import MissingFullExport as missing_export
import MissingPerson as mp
import UnclaimedPerson as ucp
import UnidentifiedFullExport as unidentified_export
import UnidentifiedPerson as up
from CaseModels import CaseAge, ParsedCase, ValueRange
from CaseParser import CaseParser

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


def _missing_case(i: int = 1, state: str = "CA", sex: str = "Female", age: int = 30) -> dict:
    return {
        "id": i,
        "idFormatted": f"MP{i:05d}",
        "subjectIdentification": {
            "firstName": f"First{i}",
            "lastName": f"Last{i}",
            "computedMissingMinAge": age,
        },
        "subjectDescription": {"sex": {"name": sex}},
        "sighting": {
            "address": {
                "city": "Testville",
                "state": {"name": "California", "displayName": state},
            },
        },
        "circumstances": {"circumstancesOfDisappearance": f"details {i}"},
    }


def _unidentified_case(
    i: int = 1,
    state: str = "CA",
    sex: str = "Female",
    ethnicity: str = "Other",
    status: str = "Unidentified Deceased",
    age_from: int = 20,
    age_to: int = 30,
    condition: str = "Recognizable",
) -> dict:
    return {
        "id": i,
        "idFormatted": f"UP{i:05d}",
        "caseIdentification": {"caseNumber": f"CN-{i}", "ncmecNumber": f"NCMEC-{i}"},
        "subjectDescription": {
            "sex": {"name": sex},
            "primaryEthnicity": {"name": ethnicity},
            "estimatedAgeFrom": age_from,
            "estimatedAgeTo": age_to,
            "estimatedAgeGroup": {"name": "Adult"},
        },
        "circumstances": {
            "status": {"name": status},
            "dateFound": "2020-01-01",
            "address": {
                "city": "Testville",
                "state": {"name": "California", "displayName": state},
            },
            "circumstancesOfRecovery": f"details {i}",
        },
        "detailsOfRecovery": {"conditionOfRemains": {"name": condition}},
    }


def _unclaimed_case(
    i: int = 1,
    state: str = "CA",
    city: str = "Testville",
    sex: str = "Male",
    ethnicity: str = "White / Caucasian",
    year_of_birth: int = 1960,
    date_body_found: str = "2020-06-15",
    resolved: bool = False,
) -> dict:
    return {
        "id": i,
        "idFormatted": f"UCP{i:05d}",
        "caseIsResolved": resolved,
        "subjectIdentification": {
            "firstName": "Carl",
            "lastName": "Baxter",
            "yearOfBirth": year_of_birth,
            "sex": {"name": sex},
            "primaryEthnicity": {"name": ethnicity},
        },
        "circumstances": {
            "dateBodyFound": date_body_found,
            "address": {
                "city": city,
                "state": {"name": "California", "displayName": state},
            },
        },
        "investigatingAgencies": [{"name": "Test County ME"}],
    }


def matches(module, case: dict, flt: dict | None = None) -> bool:
    """Apply a case-set module's client-side predicate to one raw case."""
    return module.matches_filters(case, flt or {})


class CaseAgeToDictTests(unittest.TestCase):
    def test_unidentified_only_range_is_omitted_when_unknown(self):
        age = CaseAge(
            when_missing=ValueRange(12, 13),
            now=ValueRange(16, 17),
            projected_birth_years=ValueRange(),
        )
        self.assertEqual(
            age.to_dict(),
            {
                "When Missing": {"Min": 12, "Max": 13},
                "Now": {"Min": 16, "Max": 17},
                "Projected Birth Years": {"Min": None, "Max": None},
            },
        )

    def test_projected_age_at_death_appears_when_known(self):
        age = CaseAge(
            when_missing=ValueRange(),
            now=ValueRange(),
            projected_birth_years=ValueRange(1988, 1999),
            projected_age_at_death=ValueRange(25, 35),
        )
        self.assertEqual(age.to_dict()["Projected Age At Death"], {"Min": 25, "Max": 35})


class TypedObjectSerializationTests(unittest.TestCase):
    def setUp(self):
        self.parser = CaseParser()

    def test_parse_case_includes_all_breakdown_fields_from_model(self):
        raw = _fixture("unidentified_full_case_response_alt.json")
        parsed_obj = self.parser.parse_case_object(raw, "Unidentified Persons")
        parsed_dict = self.parser.parse_case(raw, "Unidentified Persons")

        expected_breakdown = parsed_obj.breakdown.to_dict()
        self.assertEqual(parsed_dict["Breakdown"], expected_breakdown)
        self.assertEqual(set(parsed_dict["Breakdown"].keys()), set(expected_breakdown.keys()))

    def test_typed_object_matches_serialized_breakdown_for_every_fixture(self):
        for path in sorted(FIXTURE_DIR.glob("*.json")):
            with self.subTest(fixture=path.name):
                raw = json.loads(path.read_text(encoding="utf-8"))
                case_set = raw["Case Set"]
                parsed_obj = self.parser.parse_case_object(raw, case_set)
                parsed_dict = self.parser.parse_case(raw, case_set)
                self.assertIsInstance(parsed_obj, ParsedCase)
                self.assertEqual(parsed_dict["Breakdown"], parsed_obj.breakdown.to_dict())


class ParsedOutputStructureTests(unittest.TestCase):
    """Shape of the serialized case: keys in, raw blobs out, nothing stored twice."""

    def setUp(self):
        self.parser = CaseParser()
        self.fixture_paths = sorted(FIXTURE_DIR.glob("*.json"))

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


class FormatCaseTextTests(unittest.TestCase):
    def test_formats_live_fixture_case(self):
        raw = _fixture("unidentified_full_case_response_alt.json")
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
        raw = _fixture("missing_full_case_response.json")
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
        raw = _fixture("unidentified_full_case_response.json")
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


class NormalizedMissingPersonTests(unittest.TestCase):
    def test_normalizes_details(self):
        details = [_missing_case(i) for i in range(100)]
        rows = mp.process_missing_persons_data(details)
        self.assertEqual(len(rows), 100)
        self.assertEqual(rows[0]["Case Number"], "MP00000")
        self.assertEqual(rows[0]["Name"], "First0 Last0")
        self.assertIn("Testville", rows[0]["Location"])
        self.assertIn("CA", rows[0]["Location"])
        self.assertIn(rows[0]["Sex"], {"Male", "Female"})

    def test_empty(self):
        self.assertEqual(mp.process_missing_persons_data({"results": []}), [])
        self.assertEqual(mp.process_missing_persons_data({}), [])
        self.assertEqual(mp.process_missing_persons_data([]), [])

    def test_accepts_legacy_cases_key(self):
        rows = mp.process_missing_persons_data({"cases": [_missing_case(1)]})
        self.assertEqual(len(rows), 1)


class NormalizedUnidentifiedPersonTests(unittest.TestCase):
    def test_normalizes_details(self):
        details = [_unidentified_case(i) for i in range(5)]
        rows = up.process_unidentified_persons_data(details)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["Case Number"], "UP00000")
        self.assertEqual(rows[0]["Sex"], "Female")
        self.assertEqual(rows[0]["Estimated Age"], "20-30")
        self.assertIn("Testville", rows[0]["Location"])
        self.assertIn("CA", rows[0]["Location"])
        self.assertEqual(rows[0]["Status"], "Unidentified Deceased")
        self.assertEqual(rows[0]["Condition of Remains"], "Recognizable")

    def test_empty(self):
        self.assertEqual(up.process_unidentified_persons_data({"results": []}), [])
        self.assertEqual(up.process_unidentified_persons_data({}), [])
        self.assertEqual(up.process_unidentified_persons_data([]), [])

    def test_age_formatting_single(self):
        case = _unidentified_case(1, age_from=42, age_to=42)
        self.assertEqual(up.normalize_case(case)["Estimated Age"], "42")

    def test_age_formatting_missing(self):
        case = _unidentified_case(1)
        case["subjectDescription"]["estimatedAgeFrom"] = None
        case["subjectDescription"]["estimatedAgeTo"] = None
        self.assertEqual(up.normalize_case(case)["Estimated Age"], "N/A")


class NormalizedUnclaimedPersonTests(unittest.TestCase):
    def test_normalizes_details(self):
        rows = ucp.process_unclaimed_persons_data([_unclaimed_case(i) for i in range(3)])
        self.assertEqual(len(rows), 3)
        r = rows[0]
        self.assertEqual(r["Case Number"], "UCP00000")
        self.assertEqual(r["Name"], "Carl Baxter")
        self.assertEqual(r["Year of Birth"], 1960)
        self.assertEqual(r["Age at Recovery"], 60)  # 2020 - 1960
        self.assertEqual(r["Sex"], "Male")
        self.assertEqual(r["Ethnicity"], "White / Caucasian")
        self.assertEqual(r["Date Body Found"], "2020-06-15")
        self.assertEqual(r["Location"], "Testville, CA")
        self.assertEqual(r["Investigating Agency"], "Test County ME")
        self.assertIs(r["Case Resolved"], False)

    def test_age_missing_gracefully(self):
        case = _unclaimed_case(1)
        case["subjectIdentification"]["yearOfBirth"] = None
        row = ucp.normalize_case(case)
        self.assertEqual(row["Age at Recovery"], "N/A")
        self.assertEqual(row["Year of Birth"], "N/A")

    def test_city_fallback_to_geolocation(self):
        case = _unclaimed_case(1, city="")
        case["circumstances"]["address"]["city"] = None
        case["circumstances"]["publicGeolocation"] = {"formattedAddress": "Fulton County, GA, USA"}
        row = ucp.normalize_case(case)
        self.assertTrue(row["Location"].startswith("Fulton County"))

    def test_empty(self):
        self.assertEqual(ucp.process_unclaimed_persons_data({"results": []}), [])
        self.assertEqual(ucp.process_unclaimed_persons_data({}), [])
        self.assertEqual(ucp.process_unclaimed_persons_data([]), [])


class ServerPayloadMappingTests(unittest.TestCase):
    """Only the keys the Search endpoint accepts may leave the process."""

    ALLOWED_KEYS = {"take", "skip", "projections", "predicates", "orderBy"}

    def test_missing_person_payload(self):
        payload = mp.server_payload(mp.build_search_params(state="CA", age_min=18, sex="Male", take=25))
        self.assertEqual(set(payload.keys()), self.ALLOWED_KEYS)
        self.assertEqual(payload["projections"], ["namus2Number"])
        self.assertEqual(payload["take"], 25)

    def test_unidentified_person_payload(self):
        payload = up.server_payload(up.build_search_params(state="CA", age_min=18, sex="Male", take=25, status="X"))
        self.assertEqual(set(payload.keys()), self.ALLOWED_KEYS)
        self.assertEqual(payload["projections"], ["namus2Number"])
        self.assertEqual(payload["take"], 25)

    def test_unclaimed_person_payload(self):
        payload = ucp.server_payload(
            ucp.build_search_params(state="CA", sex="Male", year_of_birth_min=1950, take=25)
        )
        self.assertEqual(set(payload.keys()), self.ALLOWED_KEYS)
        self.assertEqual(payload["projections"], ["namus2Number"])
        self.assertEqual(payload["take"], 25)


class MissingPersonFilterTests(unittest.TestCase):
    def test_no_filters_keeps_every_case(self):
        self.assertTrue(mp.matches_filters(_missing_case(1), {}))

    def test_state_is_case_insensitive(self):
        self.assertTrue(mp.matches_filters(_missing_case(1, state="CA"), {"state": "ca"}))
        self.assertFalse(mp.matches_filters(_missing_case(1, state="TX"), {"state": "CA"}))

    def test_sex(self):
        self.assertTrue(mp.matches_filters(_missing_case(1, sex="Female"), {"sex": "female"}))
        self.assertFalse(mp.matches_filters(_missing_case(1, sex="Male"), {"sex": "Female"}))

    def test_age_bounds(self):
        case = _missing_case(1, age=30)
        self.assertTrue(mp.matches_filters(case, {"age_min": 18, "age_max": 65}))
        self.assertFalse(mp.matches_filters(case, {"age_min": 31}))
        self.assertFalse(mp.matches_filters(case, {"age_max": 29}))

    def test_unusable_age_skips_the_age_filter(self):
        case = _missing_case(1)
        case["subjectIdentification"].pop("computedMissingMinAge")
        self.assertTrue(mp.matches_filters(case, {"age_min": 18}))


class UnidentifiedPersonFilterTests(unittest.TestCase):
    def test_not_recognizable_is_excluded_even_without_filters(self):
        self.assertFalse(
            matches(up, _unidentified_case(1, condition="Not recognizable"))
        )

    def test_condition_text_is_matched_loosely(self):
        self.assertFalse(
            matches(up, _unidentified_case(1, condition="Not recognizable, advanced decomposition"))
        )
        self.assertTrue(
            matches(up, _unidentified_case(1, condition="Recognizable, partial facial features"))
        )

    def test_state_sex_status_and_ethnicity(self):
        case = _unidentified_case(1)
        self.assertTrue(matches(up, case, {"state": "CA", "sex": "female", "status": "unidentified deceased"}))
        self.assertFalse(matches(up, case, {"state": "TX"}))
        self.assertFalse(matches(up, case, {"sex": "Male"}))
        self.assertFalse(matches(up, case, {"status": "Unidentified Living"}))
        self.assertFalse(matches(up, case, {"race_ethnicity": "White / Caucasian"}))

    def test_age_uses_interval_overlap(self):
        # Request 18-28 overlaps 15-20 and 25-30, but not 5-10 or 40-50.
        wanted = {"age_min": 18, "age_max": 28}
        self.assertTrue(matches(up, _unidentified_case(1, age_from=15, age_to=20), wanted))
        self.assertTrue(matches(up, _unidentified_case(1, age_from=25, age_to=30), wanted))
        self.assertFalse(matches(up, _unidentified_case(1, age_from=5, age_to=10), wanted))
        self.assertFalse(matches(up, _unidentified_case(1, age_from=40, age_to=50), wanted))


class UnclaimedPersonFilterTests(unittest.TestCase):
    def test_state_sex_and_ethnicity(self):
        case = _unclaimed_case(1)
        self.assertTrue(matches(ucp, case, {"state": "ca", "sex": "male"}))
        self.assertFalse(matches(ucp, case, {"state": "TX"}))
        self.assertFalse(matches(ucp, case, {"sex": "Female"}))
        self.assertFalse(matches(ucp, case, {"race_ethnicity": "Other"}))

    def test_only_unresolved_drops_resolved_cases(self):
        self.assertTrue(matches(ucp, _unclaimed_case(1, resolved=False), {"only_unresolved": True}))
        self.assertFalse(matches(ucp, _unclaimed_case(1, resolved=True), {"only_unresolved": True}))
        self.assertTrue(matches(ucp, _unclaimed_case(1, resolved=True), {}))

    def test_year_of_birth_range(self):
        wanted = {"year_of_birth_min": 1950, "year_of_birth_max": 1985}
        self.assertTrue(matches(ucp, _unclaimed_case(1, year_of_birth=1960), wanted))
        self.assertFalse(matches(ucp, _unclaimed_case(1, year_of_birth=1940), wanted))
        self.assertFalse(matches(ucp, _unclaimed_case(1, year_of_birth=2000), wanted))

    def test_unknown_year_of_birth_is_dropped_by_a_range(self):
        case = _unclaimed_case(1)
        case["subjectIdentification"]["yearOfBirth"] = None
        self.assertFalse(matches(ucp, case, {"year_of_birth_min": 1950}))

    def test_age_at_recovery_range(self):
        # Found 2020: born 1990 is 30, born 1960 is 60.
        wanted = {"age_min": 28, "age_max": 45}
        self.assertTrue(matches(ucp, _unclaimed_case(1, year_of_birth=1990), wanted))
        self.assertFalse(matches(ucp, _unclaimed_case(1, year_of_birth=1960), wanted))

    def test_unknown_age_at_recovery_is_dropped_by_a_range(self):
        case = _unclaimed_case(1)
        case["subjectIdentification"]["yearOfBirth"] = None
        self.assertFalse(matches(ucp, case, {"age_min": 28}))


class CaseLinkMappingTests(unittest.TestCase):
    def test_missing_case_link(self):
        self.assertEqual(
            missing_export.build_case_link({"id": 163404}),
            "https://www.namus.gov/MissingPersons/Case#/163404?nav",
        )

    def test_unidentified_case_link(self):
        self.assertEqual(
            unidentified_export.build_case_link({"id": 163354}),
            "https://www.namus.gov/UnidentifiedPersons/Case#/163354?nav",
        )

    def test_enrich_case_adds_link_without_dropping_payload(self):
        enriched = missing_export.enrich_case({"id": 10, "idFormatted": "MP00010"})
        self.assertEqual(enriched["Case Link"], "https://www.namus.gov/MissingPersons/Case#/10?nav")
        self.assertEqual(enriched["idFormatted"], "MP00010")

    def test_enrich_case_adds_photo_marker(self):
        with_photo = unidentified_export.enrich_case({"id": 10, "images": [{"id": 1}]})
        without_photo = unidentified_export.enrich_case({"id": 11, "images": []})
        self.assertTrue(with_photo["Has Photo"])
        self.assertFalse(without_photo["Has Photo"])


if __name__ == "__main__":
    unittest.main(verbosity=2)