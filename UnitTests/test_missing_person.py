"""
Unit tests for MissingPerson.py

These exercise the script against a mocked NamUs API. To hit the real
NamUs endpoint (slow, does one GET per matching case), run:

    RUN_LIVE_NAMUS=1 python -m unittest test_missing_person.py -v
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

import MissingPerson as mp

# ---------------------------------------------------------------------------
# Search conditions used across tests.
# ---------------------------------------------------------------------------
SEARCH_CONDITIONS = [
    {"name": "California_adults",     "kwargs": dict(take=100, state="CA", age_min=18, age_max=65)},
    {"name": "Texas_minors",          "kwargs": dict(take=100, state="TX", age_min=0,  age_max=17)},
    {"name": "Florida_seniors_female","kwargs": dict(take=100, state="FL", age_min=65, age_max=120, sex="Female")},
    {"name": "NewYork_male",          "kwargs": dict(take=100, state="NY", sex="Male")},
    {"name": "Nationwide_all",        "kwargs": dict(take=100)},
]


# --- fakes ------------------------------------------------------------------
def _fake_search_response(count: int = 100):
    """Mimic the modern Search endpoint response shape."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "count": count,
        "results": [
            {
                "namus2Number": i,
                "link": f"/MissingPersons/Case#/{i}",
                "image": f"/api/CaseSets/NamUs/MissingPersons/Cases/{i}/Images/Default/Thumbnail",
                "missingAgeRangeValue": None,
            }
            for i in range(count)
        ],
    }
    resp.raise_for_status = MagicMock()
    return resp


def _fake_case_detail(i: int, state: str = "CA") -> dict:
    """Mimic the per-case detail endpoint response shape."""
    return {
        "id": i,
        "idFormatted": f"MP{i:05d}",
        "subjectIdentification": {
            "firstName": f"First{i}",
            "lastName": f"Last{i}",
            "computedMissingMinAge": 30,
        },
        "subjectDescription": {
            "sex": {"name": "Female" if i % 2 else "Male"},
        },
        "sighting": {
            "address": {
                "city": "Testville",
                "state": {"name": "California", "displayName": state},
            },
        },
        "circumstances": {"circumstancesOfDisappearance": f"details {i}"},
    }


# ---------------------------------------------------------------------------
class BuildSearchParamsTests(unittest.TestCase):
    def test_defaults_take_100(self):
        params = mp.build_search_params()
        self.assertEqual(params["take"], 100)
        self.assertEqual(params["skip"], 0)
        self.assertNotIn("state", params)

    def test_state_and_age_recorded_for_client_side(self):
        params = mp.build_search_params(state="CA", age_min=18, age_max=65)
        self.assertEqual(params["state"], "CA")
        self.assertEqual(params["computedMissingMinAge"], 18)
        self.assertEqual(params["computedMissingMaxAge"], 65)
        self.assertEqual(params["_client_filters"]["state"], "CA")
        self.assertEqual(params["_client_filters"]["age_min"], 18)

    def test_sex_and_race(self):
        params = mp.build_search_params(sex="Female", race_ethnicity="Hispanic / Latino")
        self.assertEqual(params["sex"], "Female")
        self.assertEqual(params["raceEthnicity"], "Hispanic / Latino")
        self.assertEqual(params["_client_filters"]["sex"], "Female")

    def test_server_payload_only_allowed_keys(self):
        params = mp.build_search_params(state="CA", age_min=18, sex="Male", take=25)
        payload = mp._server_payload(params)
        self.assertEqual(set(payload.keys()), {"take", "skip", "projections", "predicates", "orderBy"})
        self.assertEqual(payload["projections"], ["namus2Number"])
        self.assertEqual(payload["take"], 25)


class ProcessMissingPersonsDataTests(unittest.TestCase):
    def test_normalizes_details(self):
        details = [_fake_case_detail(i) for i in range(100)]
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
        rows = mp.process_missing_persons_data({"cases": [_fake_case_detail(1)]})
        self.assertEqual(len(rows), 1)


class MockedSearchTests(unittest.TestCase):
    """Run each search condition offline, requesting 100 records."""

    def test_search_uses_allowed_projection_and_take(self):
        for cond in SEARCH_CONDITIONS:
            with self.subTest(condition=cond["name"]):
                params = mp.build_search_params(**cond["kwargs"])
                self.assertEqual(params["take"], 100)

                with patch.object(mp.requests, "post", return_value=_fake_search_response(100)) as post:
                    raw = mp.search_missing_persons(params)

                post.assert_called_once()
                _, kwargs = post.call_args
                sent = kwargs["json"]
                self.assertEqual(sent["take"], 100)
                self.assertEqual(sent["projections"], ["namus2Number"])
                # Legacy/client-only keys must not be sent to the API.
                self.assertNotIn("state", sent)
                self.assertNotIn("sex", sent)
                self.assertNotIn("_client_filters", sent)
                self.assertEqual(raw["count"], 100)
                self.assertEqual(len(raw["results"]), 100)

    def test_raises_on_http_error(self):
        bad = MagicMock()
        bad.raise_for_status.side_effect = mp.requests.HTTPError("500")
        with patch.object(mp.requests, "post", return_value=bad):
            with self.assertRaises(mp.requests.HTTPError):
                mp.search_missing_persons(mp.build_search_params())

    def test_fetch_cases_end_to_end_state_filter(self):
        # Search returns 4 ids; details alternate between CA and TX.
        details_by_id = {
            i: _fake_case_detail(i, state="CA" if i % 2 == 0 else "TX")
            for i in range(4)
        }
        fake_search = {"count": 4, "results": [{"namus2Number": i} for i in range(4)]}
        with patch.object(mp, "search_missing_persons", return_value=fake_search):
            rows = mp.fetch_cases(
                mp.build_search_params(take=4, state="CA"),
                detail_fetcher=lambda i: details_by_id[i],
            )
        # Only the two CA cases survive the client-side filter.
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertIn("CA", r["Location"])

    def test_fetch_cases_no_filter_returns_all(self):
        fake_search = {"count": 3, "results": [{"namus2Number": i} for i in range(3)]}
        with patch.object(mp, "search_missing_persons", return_value=fake_search):
            rows = mp.fetch_cases(
                mp.build_search_params(take=3),
                detail_fetcher=lambda i: _fake_case_detail(i),
            )
        self.assertEqual(len(rows), 3)


@unittest.skipUnless(
    os.environ.get("RUN_LIVE_NAMUS") == "1",
    "Set RUN_LIVE_NAMUS=1 to hit the live NamUs API.",
)
class LiveNamUsTests(unittest.TestCase):
    """Optional: real network calls. Uses take=5 to keep the run fast."""

    def test_live_small_search(self):
        params = mp.build_search_params(take=5)
        raw = mp.search_missing_persons(params)
        self.assertIn("results", raw)
        self.assertLessEqual(len(raw["results"]), 5)
        if raw["results"]:
            detail = mp.fetch_case_detail(raw["results"][0]["namus2Number"])
            self.assertIn("subjectIdentification", detail)


if __name__ == "__main__":
    unittest.main(verbosity=2)

