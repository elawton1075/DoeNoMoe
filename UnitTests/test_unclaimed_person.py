"""
Unit tests for UnclaimedPerson.py

Mocked by default; set RUN_LIVE_NAMUS=1 to hit the real NamUs API.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

import UnclaimedPerson as ucp

SEARCH_CONDITIONS = [
    {"name": "California_born_1950_1970",  "kwargs": dict(take=100, state="CA", year_of_birth_min=1950, year_of_birth_max=1970)},
    {"name": "Texas_male",                 "kwargs": dict(take=100, state="TX", sex="Male")},
    {"name": "Florida_female_white",       "kwargs": dict(take=100, state="FL", sex="Female", race_ethnicity="White / Caucasian")},
    {"name": "NewYork_recent_adults",      "kwargs": dict(take=100, state="NY", age_min=25, age_max=60)},
    {"name": "Nationwide_unresolved",      "kwargs": dict(take=100, only_unresolved=True)},
]


def _fake_search_response(count: int = 100):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "count": count,
        "results": [{"namus2Number": i} for i in range(count)],
    }
    resp.raise_for_status = MagicMock()
    return resp


def _fake_case_detail(
    i: int,
    state: str = "CA",
    city: str = "Testville",
    sex: str = "Male",
    ethnicity: str = "White / Caucasian",
    year_of_birth: int = 1960,
    date_body_found: str = "2020-06-15",
    resolved: bool = False,
    first: str = "Carl",
    last: str = "Baxter",
) -> dict:
    return {
        "id": i,
        "idFormatted": f"UCP{i:05d}",
        "caseIsResolved": resolved,
        "subjectIdentification": {
            "firstName": first,
            "lastName": last,
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


class BuildSearchParamsTests(unittest.TestCase):
    def test_defaults(self):
        p = ucp.build_search_params()
        self.assertEqual(p["take"], 100)
        self.assertEqual(p["skip"], 0)
        self.assertNotIn("state", p)

    def test_all_filters_recorded(self):
        p = ucp.build_search_params(
            state="CA", sex="Male", race_ethnicity="White / Caucasian",
            year_of_birth_min=1950, year_of_birth_max=1970,
            age_min=30, age_max=60, only_unresolved=True,
        )
        self.assertEqual(p["state"], "CA")
        self.assertEqual(p["yearOfBirthMin"], 1950)
        self.assertEqual(p["yearOfBirthMax"], 1970)
        self.assertEqual(p["ageMin"], 30)
        self.assertEqual(p["ageMax"], 60)
        f = p["_client_filters"]
        self.assertEqual(f["state"], "CA")
        self.assertEqual(f["sex"], "Male")
        self.assertEqual(f["race_ethnicity"], "White / Caucasian")
        self.assertEqual(f["year_of_birth_min"], 1950)
        self.assertEqual(f["only_unresolved"], True)

    def test_server_payload_only_allowed_keys(self):
        p = ucp.build_search_params(state="CA", sex="Male", year_of_birth_min=1950, take=25)
        payload = ucp._server_payload(p)
        self.assertEqual(set(payload.keys()), {"take", "skip", "projections", "predicates", "orderBy"})
        self.assertEqual(payload["projections"], ["namus2Number"])
        self.assertEqual(payload["take"], 25)


class ProcessTests(unittest.TestCase):
    def test_normalizes_details(self):
        details = [_fake_case_detail(i) for i in range(3)]
        rows = ucp.process_unclaimed_persons_data(details)
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
        c = _fake_case_detail(1)
        c["subjectIdentification"]["yearOfBirth"] = None
        row = ucp._normalize_case(c)
        self.assertEqual(row["Age at Recovery"], "N/A")
        self.assertEqual(row["Year of Birth"], "N/A")

    def test_city_fallback_to_geolocation(self):
        c = _fake_case_detail(1, city="")
        c["circumstances"]["address"]["city"] = None
        c["circumstances"]["publicGeolocation"] = {
            "formattedAddress": "Fulton County, GA, USA"
        }
        row = ucp._normalize_case(c)
        self.assertTrue(row["Location"].startswith("Fulton County"))

    def test_empty(self):
        self.assertEqual(ucp.process_unclaimed_persons_data({"results": []}), [])
        self.assertEqual(ucp.process_unclaimed_persons_data({}), [])
        self.assertEqual(ucp.process_unclaimed_persons_data([]), [])


class MockedSearchTests(unittest.TestCase):
    def test_search_uses_allowed_projection(self):
        for cond in SEARCH_CONDITIONS:
            with self.subTest(condition=cond["name"]):
                params = ucp.build_search_params(**cond["kwargs"])
                with patch.object(ucp.requests, "post", return_value=_fake_search_response(100)) as post:
                    raw = ucp.search_unclaimed_persons(params)
                post.assert_called_once()
                sent = post.call_args.kwargs["json"]
                self.assertEqual(sent["take"], 100)
                self.assertEqual(sent["projections"], ["namus2Number"])
                self.assertNotIn("state", sent)
                self.assertNotIn("sex", sent)
                self.assertNotIn("_client_filters", sent)
                self.assertEqual(raw["count"], 100)
                self.assertEqual(len(raw["results"]), 100)

    def test_raises_on_http_error(self):
        bad = MagicMock()
        bad.raise_for_status.side_effect = ucp.requests.HTTPError("500")
        with patch.object(ucp.requests, "post", return_value=bad):
            with self.assertRaises(ucp.requests.HTTPError):
                ucp.search_unclaimed_persons(ucp.build_search_params())

    def test_fetch_cases_state_filter(self):
        details = {
            i: _fake_case_detail(i, state="CA" if i % 2 == 0 else "TX")
            for i in range(4)
        }
        fake_search = {"count": 4, "results": [{"namus2Number": i} for i in range(4)]}
        with patch.object(ucp, "search_unclaimed_persons", return_value=fake_search):
            rows = ucp.fetch_cases(
                ucp.build_search_params(take=4, state="CA"),
                detail_fetcher=lambda i: details[i],
            )
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertIn("CA", r["Location"])

    def test_fetch_cases_year_of_birth_range(self):
        details = {
            0: _fake_case_detail(0, year_of_birth=1940),
            1: _fake_case_detail(1, year_of_birth=1960),
            2: _fake_case_detail(2, year_of_birth=1980),
            3: _fake_case_detail(3, year_of_birth=2000),
        }
        fake_search = {"count": 4, "results": [{"namus2Number": i} for i in range(4)]}
        with patch.object(ucp, "search_unclaimed_persons", return_value=fake_search):
            rows = ucp.fetch_cases(
                ucp.build_search_params(take=4, year_of_birth_min=1950, year_of_birth_max=1985),
                detail_fetcher=lambda i: details[i],
            )
        self.assertEqual({r["Case Number"] for r in rows}, {"UCP00001", "UCP00002"})

    def test_fetch_cases_age_at_recovery(self):
        # yob=1960, found 2020 → age 60; yob=1990, found 2020 → age 30; yob=1975, found 2000 → age 25
        details = {
            0: _fake_case_detail(0, year_of_birth=1960, date_body_found="2020-01-01"),
            1: _fake_case_detail(1, year_of_birth=1990, date_body_found="2020-01-01"),
            2: _fake_case_detail(2, year_of_birth=1975, date_body_found="2000-01-01"),
        }
        fake_search = {"count": 3, "results": [{"namus2Number": i} for i in range(3)]}
        with patch.object(ucp, "search_unclaimed_persons", return_value=fake_search):
            rows = ucp.fetch_cases(
                ucp.build_search_params(take=3, age_min=28, age_max=45),
                detail_fetcher=lambda i: details[i],
            )
        self.assertEqual({r["Case Number"] for r in rows}, {"UCP00001"})

    def test_fetch_cases_only_unresolved(self):
        details = {
            0: _fake_case_detail(0, resolved=False),
            1: _fake_case_detail(1, resolved=True),
            2: _fake_case_detail(2, resolved=False),
        }
        fake_search = {"count": 3, "results": [{"namus2Number": i} for i in range(3)]}
        with patch.object(ucp, "search_unclaimed_persons", return_value=fake_search):
            rows = ucp.fetch_cases(
                ucp.build_search_params(take=3, only_unresolved=True),
                detail_fetcher=lambda i: details[i],
            )
        self.assertEqual({r["Case Number"] for r in rows}, {"UCP00000", "UCP00002"})


@unittest.skipUnless(
    os.environ.get("RUN_LIVE_NAMUS") == "1",
    "Set RUN_LIVE_NAMUS=1 to hit the live NamUs API.",
)
class LiveNamUsTests(unittest.TestCase):
    def test_live_small_search(self):
        params = ucp.build_search_params(take=5)
        raw = ucp.search_unclaimed_persons(params)
        self.assertIn("results", raw)
        self.assertLessEqual(len(raw["results"]), 5)
        if raw["results"]:
            detail = ucp.fetch_case_detail(raw["results"][0]["namus2Number"])
            self.assertIn("subjectIdentification", detail)


if __name__ == "__main__":
    unittest.main(verbosity=2)

