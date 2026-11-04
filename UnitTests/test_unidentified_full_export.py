"""Unit tests for UnidentifiedFullExport.py."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import UnidentifiedFullExport as ufe


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
        "status": None,
        "max_workers": 2,
        "output": "unused.json",
        "print_json": False,
    }
    base.update(overrides)
    return type("Args", (), base)()


def _case(i: int, has_photo: bool = False) -> dict:
    payload = {
        "id": i,
        "caseIdentification": {"caseNumber": f"CN-{i}"},
        "subjectDescription": {"estimatedAgeFrom": 20, "estimatedAgeTo": 30},
        "circumstances": {"status": {"name": "Unidentified Deceased"}},
        "images": [],
        "defaultImage": {},
        "hrefDefaultImageThumbnail": "",
        "hrefDefaultImagePoster": "",
    }
    if has_photo:
        payload["images"] = [{"id": i * 10}]
    return payload


class HelperTests(unittest.TestCase):
    def test_build_case_link(self):
        case = {"id": 163354}
        self.assertEqual(
            ufe.build_case_link(case),
            "https://www.namus.gov/UnidentifiedPersons/Case#/163354?nav",
        )

    def test_has_case_photo_true_when_images_present(self):
        self.assertTrue(ufe.has_case_photo(_case(1, has_photo=True)))

    def test_has_case_photo_true_when_default_image_present(self):
        c = _case(1)
        c["defaultImage"] = {"id": 99}
        self.assertTrue(ufe.has_case_photo(c))

    def test_has_case_photo_false_when_no_photo_fields(self):
        self.assertFalse(ufe.has_case_photo(_case(1, has_photo=False)))


class FetchTests(unittest.TestCase):
    @patch.object(ufe.up, "fetch_case_detail")
    @patch.object(ufe.up, "search_unidentified_persons")
    def test_fetch_single_page_enriches_all_cases(self, search_mock, detail_mock):
        search_mock.return_value = {
            "count": 2,
            "results": [{"namus2Number": 100}, {"namus2Number": 101}],
        }
        detail_mock.side_effect = [_case(100, has_photo=True), _case(101, has_photo=False)]

        result = ufe.fetch_unidentified_details(_args(fetch_all=False))

        self.assertEqual(result["search_count"], 2)
        self.assertEqual(result["returned"], 2)
        self.assertEqual(result["cases"][0]["Case Link"], "https://www.namus.gov/UnidentifiedPersons/Case#/100?nav")
        self.assertTrue(result["cases"][0]["Has Photo"])
        self.assertFalse(result["cases"][1]["Has Photo"])

    @patch.object(ufe.up, "fetch_case_detail")
    @patch.object(ufe.up, "search_unidentified_persons")
    def test_fetch_all_pages(self, search_mock, detail_mock):
        search_mock.side_effect = [
            {"count": 3, "results": [{"namus2Number": 1}, {"namus2Number": 2}]},
            {"count": 3, "results": [{"namus2Number": 3}]},
        ]
        detail_mock.side_effect = [_case(1), _case(2), _case(3)]

        result = ufe.fetch_unidentified_details(_args(fetch_all=True, take=2))

        self.assertEqual(result["returned"], 3)
        self.assertEqual({c["id"] for c in result["cases"]}, {1, 2, 3})


if __name__ == "__main__":
    unittest.main(verbosity=2)


