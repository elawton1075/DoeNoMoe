"""
Unit tests for UnidentifiedPerson.py

Mocked by default; set RUN_LIVE_NAMUS=1 to hit the real NamUs API.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

import UnidentifiedPerson as up

SEARCH_CONDITIONS = [
    {"name": "California_adults",     "kwargs": dict(take=100, state="CA", age_min=18, age_max=65)},
    {"name": "Texas_juveniles",       "kwargs": dict(take=100, state="TX", age_min=0,  age_max=17)},
    {"name": "Florida_seniors_female","kwargs": dict(take=100, state="FL", age_min=65, age_max=120, sex="Female")},
    {"name": "NewYork_male_deceased", "kwargs": dict(take=100, state="NY", sex="Male", status="Unidentified Deceased")},
    {"name": "Nationwide_all",        "kwargs": dict(take=100)},
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


class BuildSearchParamsTests(unittest.TestCase):
    def test_defaults(self):
        p = up.build_search_params()
        self.assertEqual(p["take"], 100)
        self.assertEqual(p["skip"], 0)
        self.assertNotIn("state", p)

    def test_state_age_sex(self):
        p = up.build_search_params(state="CA", age_min=18, age_max=65, sex="Male")
        self.assertEqual(p["state"], "CA")
        self.assertEqual(p["estimatedAgeMin"], 18)
        self.assertEqual(p["estimatedAgeMax"], 65)
        self.assertEqual(p["_client_filters"]["sex"], "Male")

    def test_status_and_ethnicity(self):
        p = up.build_search_params(status="Unidentified Deceased", race_ethnicity="Other")
        self.assertEqual(p["status"], "Unidentified Deceased")
        self.assertEqual(p["raceEthnicity"], "Other")

    def test_server_payload_only_allowed_keys(self):
        p = up.build_search_params(state="CA", age_min=18, sex="Male", take=25, status="X")
        payload = up._server_payload(p)
        self.assertEqual(set(payload.keys()), {"take", "skip", "projections", "predicates", "orderBy"})
        self.assertEqual(payload["projections"], ["namus2Number"])
        self.assertEqual(payload["take"], 25)


class ProcessTests(unittest.TestCase):
    def test_normalizes_details(self):
        details = [_fake_case_detail(i, condition="Not recognizable") for i in range(5)]
        rows = up.process_unidentified_persons_data(details)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["Case Number"], "UP00000")
        self.assertEqual(rows[0]["Sex"], "Female")
        self.assertEqual(rows[0]["Estimated Age"], "20-30")
        self.assertIn("Testville", rows[0]["Location"])
        self.assertIn("CA", rows[0]["Location"])
        self.assertEqual(rows[0]["Status"], "Unidentified Deceased")
        self.assertEqual(rows[0]["Condition of Remains"], "Not recognizable")

    def test_empty(self):
        self.assertEqual(up.process_unidentified_persons_data({"results": []}), [])
        self.assertEqual(up.process_unidentified_persons_data({}), [])
        self.assertEqual(up.process_unidentified_persons_data([]), [])

    def test_age_formatting_single(self):
        c = _fake_case_detail(1, age_from=42, age_to=42)
        self.assertEqual(up._normalize_case(c)["Estimated Age"], "42")

    def test_age_formatting_missing(self):
        c = _fake_case_detail(1)
        c["subjectDescription"]["estimatedAgeFrom"] = None
        c["subjectDescription"]["estimatedAgeTo"] = None
        self.assertEqual(up._normalize_case(c)["Estimated Age"], "N/A")


class MockedSearchTests(unittest.TestCase):
    def test_search_uses_allowed_projection(self):
        for cond in SEARCH_CONDITIONS:
            with self.subTest(condition=cond["name"]):
                params = up.build_search_params(**cond["kwargs"])
                with patch.object(up.requests, "post", return_value=_fake_search_response(100)) as post:
                    raw = up.search_unidentified_persons(params)
                post.assert_called_once()
                sent = post.call_args.kwargs["json"]
                self.assertEqual(sent["take"], 100)
                self.assertEqual(sent["projections"], ["namus2Number"])
                self.assertNotIn("state", sent)
                self.assertNotIn("status", sent)
                self.assertNotIn("_client_filters", sent)
                self.assertEqual(raw["count"], 100)
                self.assertEqual(len(raw["results"]), 100)

    def test_raises_on_http_error(self):
        bad = MagicMock()
        bad.raise_for_status.side_effect = up.requests.HTTPError("500")
        with patch.object(up.requests, "post", return_value=bad):
            with self.assertRaises(up.requests.HTTPError):
                up.search_unidentified_persons(up.build_search_params())

    def test_fetch_cases_state_filter(self):
        details_by_id = {
            i: _fake_case_detail(i, state="CA" if i % 2 == 0 else "TX")
            for i in range(4)
        }
        fake_search = {"count": 4, "results": [{"namus2Number": i} for i in range(4)]}
        with patch.object(up, "search_unidentified_persons", return_value=fake_search):
            rows = up.fetch_cases(
                up.build_search_params(take=4, state="CA"),
                detail_fetcher=lambda i: details_by_id[i],
            )
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertIn("CA", r["Location"])

    def test_fetch_cases_age_overlap_filter(self):
        # Case ages: 5-10, 15-20, 25-30, 40-50. Query 18-28 → overlaps 15-20 and 25-30.
        details = {
            0: _fake_case_detail(0, age_from=5,  age_to=10),
            1: _fake_case_detail(1, age_from=15, age_to=20),
            2: _fake_case_detail(2, age_from=25, age_to=30),
            3: _fake_case_detail(3, age_from=40, age_to=50),
        }
        fake_search = {"count": 4, "results": [{"namus2Number": i} for i in range(4)]}
        with patch.object(up, "search_unidentified_persons", return_value=fake_search):
            rows = up.fetch_cases(
                up.build_search_params(take=4, age_min=18, age_max=28),
                detail_fetcher=lambda i: details[i],
            )
        cases = {r["Case Number"] for r in rows}
        self.assertEqual(cases, {"UP00001", "UP00002"})

    def test_fetch_cases_status_and_sex(self):
        details = {
            0: _fake_case_detail(0, sex="Male",   status="Unidentified Deceased"),
            1: _fake_case_detail(1, sex="Female", status="Unidentified Deceased"),
            2: _fake_case_detail(2, sex="Male",   status="Unidentified Living"),
        }
        fake_search = {"count": 3, "results": [{"namus2Number": i} for i in range(3)]}
        with patch.object(up, "search_unidentified_persons", return_value=fake_search):
            rows = up.fetch_cases(
                up.build_search_params(take=3, sex="Male", status="Unidentified Deceased"),
                detail_fetcher=lambda i: details[i],
            )
        self.assertEqual({r["Case Number"] for r in rows}, {"UP00000"})

    def test_fetch_cases_excludes_not_recognizable(self):
        details = {
            0: _fake_case_detail(0, condition="Not recognizable"),
            1: _fake_case_detail(1, condition="Recognizable"),
        }
        fake_search = {"count": 2, "results": [{"namus2Number": 0}, {"namus2Number": 1}]}
        with patch.object(up, "search_unidentified_persons", return_value=fake_search):
            rows = up.fetch_cases(
                up.build_search_params(take=2),
                detail_fetcher=lambda i: details[i],
            )
        self.assertEqual({r["Case Number"] for r in rows}, {"UP00001"})

    def test_fetch_cases_excludes_not_recognizable_with_extra_text(self):
        details = {
            0: _fake_case_detail(0, condition="Not recognizable, advanced decomposition"),
            1: _fake_case_detail(1, condition="Recognizable, partial facial features"),
        }
        fake_search = {"count": 2, "results": [{"namus2Number": 0}, {"namus2Number": 1}]}
        with patch.object(up, "search_unidentified_persons", return_value=fake_search):
            rows = up.fetch_cases(
                up.build_search_params(take=2),
                detail_fetcher=lambda i: details[i],
            )
        self.assertEqual({r["Case Number"] for r in rows}, {"UP00001"})


@unittest.skipUnless(
    os.environ.get("RUN_LIVE_NAMUS") == "1",
    "Set RUN_LIVE_NAMUS=1 to hit the live NamUs API.",
)
class LiveNamUsTests(unittest.TestCase):
    def test_live_small_search(self):
        params = up.build_search_params(take=5)
        raw = up.search_unidentified_persons(params)
        self.assertIn("results", raw)
        self.assertLessEqual(len(raw["results"]), 5)
        if raw["results"]:
            detail = up.fetch_case_detail(raw["results"][0]["namus2Number"])
            self.assertIn("subjectDescription", detail)


if __name__ == "__main__":
    unittest.main(verbosity=2)

