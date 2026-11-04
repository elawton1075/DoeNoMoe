"""Unit tests for CaseParser.py."""

from __future__ import annotations

import unittest

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

        self.assertEqual(parsed["Breakdown"]["Age"]["Min"], 12)
        self.assertEqual(parsed["Breakdown"]["Age"]["Max"], 13)
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
            "physicalDescription": {
                "eyeColor": {"name": "Blue"},
                "hairColor": {"name": "Brown"},
            },
            "investigatingAgencies": [{"name": "Agency Three"}],
        }

        parsed = parser.parse_case(raw, "Unidentified Persons")

        self.assertEqual(parsed["Breakdown"]["Age"]["Min"], 22)
        self.assertEqual(parsed["Breakdown"]["Age"]["Max"], 30)
        self.assertEqual(parsed["Investigating Agency Summary"], "Agency Three")


if __name__ == "__main__":
    unittest.main(verbosity=2)

