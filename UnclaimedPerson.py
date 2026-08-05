"""
UnclaimedPerson.py

Query the NamUs Unclaimed Persons public API and return normalized case
records. Mirrors :mod:`MissingPerson` and :mod:`UnidentifiedPerson` but for
the Unclaimed Persons case set, where remains have been identified (the
person has a name) but no next-of-kin has claimed the body.

The Search endpoint only supports pagination + ordering (projection is
limited to ``namus2Number``). Rich data lives at the per-case detail
endpoint, and client-side filtering is applied by :func:`fetch_cases`.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Iterable, List, Optional

import requests

NAMUS_BASE_URL = "https://www.namus.gov/api/CaseSets/NamUs/UnclaimedPersons"
NAMUS_SEARCH_URL = f"{NAMUS_BASE_URL}/Search"
NAMUS_CASE_URL = f"{NAMUS_BASE_URL}/Cases/{{id}}"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=UTF-8",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/127.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.namus.gov/UnclaimedPersons/Search",
    "Origin": "https://www.namus.gov",
}

_ALLOWED_PROJECTION = "namus2Number"


# ---------------------------------------------------------------------------
# Parameter building
# ---------------------------------------------------------------------------
def build_search_params(
    take: int = 100,
    skip: int = 0,
    state: Optional[str] = None,
    sex: Optional[str] = None,
    race_ethnicity: Optional[str] = None,
    year_of_birth_min: Optional[int] = None,
    year_of_birth_max: Optional[int] = None,
    age_min: Optional[int] = None,
    age_max: Optional[int] = None,
    only_unresolved: bool = False,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build an Unclaimed Persons search request.

    All filters are recorded under ``_client_filters`` and applied by
    :func:`fetch_cases` after per-case details are fetched.

    ``age_min`` / ``age_max`` are compared against the person's age at
    recovery, computed from ``yearOfBirth`` and ``dateBodyFound``. Cases
    without both fields are excluded when either bound is set.
    """
    params: Dict[str, Any] = {
        "take": take,
        "skip": skip,
        "projections": [_ALLOWED_PROJECTION],
        "predicates": [],
        "orderBy": [{"name": "dateOfLastContact", "direction": "descending"}],
        "_client_filters": {
            "state": state,
            "sex": sex,
            "race_ethnicity": race_ethnicity,
            "year_of_birth_min": year_of_birth_min,
            "year_of_birth_max": year_of_birth_max,
            "age_min": age_min,
            "age_max": age_max,
            "only_unresolved": only_unresolved,
        },
    }
    if state:
        params["state"] = state
    if sex:
        params["sex"] = sex
    if race_ethnicity:
        params["raceEthnicity"] = race_ethnicity
    if year_of_birth_min is not None:
        params["yearOfBirthMin"] = year_of_birth_min
    if year_of_birth_max is not None:
        params["yearOfBirthMax"] = year_of_birth_max
    if age_min is not None:
        params["ageMin"] = age_min
    if age_max is not None:
        params["ageMax"] = age_max
    if extra:
        params.update(extra)
    return params


def _server_payload(search_params: Dict[str, Any]) -> Dict[str, Any]:
    """Extract only the keys the Search endpoint accepts."""
    allowed = {"take", "skip", "projections", "predicates", "orderBy"}
    payload = {k: v for k, v in search_params.items() if k in allowed}
    payload.setdefault("take", 100)
    payload.setdefault("skip", 0)
    payload.setdefault("projections", [_ALLOWED_PROJECTION])
    payload.setdefault("predicates", [])
    payload.setdefault(
        "orderBy",
        [{"name": "dateOfLastContact", "direction": "descending"}],
    )
    return payload


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def search_unclaimed_persons(
    search_params: Dict[str, Any],
    session: Optional[requests.Session] = None,
    timeout: int = 30,
    url: str = NAMUS_SEARCH_URL,
) -> Dict[str, Any]:
    """POST to the Unclaimed Persons Search endpoint and return JSON.

    Response shape: ``{"count": int, "results": [{"namus2Number": int, ...}]}``.
    """
    http = session or requests
    payload = _server_payload(search_params)
    response = http.post(url, headers=DEFAULT_HEADERS, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def fetch_case_detail(
    namus2_number: int,
    session: Optional[requests.Session] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """GET a single unclaimed-person case's full detail record."""
    http = session or requests
    response = http.get(
        NAMUS_CASE_URL.format(id=namus2_number),
        headers=DEFAULT_HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------
def _extract_state(case: Dict[str, Any]) -> str:
    address = ((case.get("circumstances") or {}).get("address")) or {}
    state = address.get("state")
    if isinstance(state, dict):
        return state.get("displayName") or state.get("name") or "N/A"
    return state or "N/A"


def _extract_city(case: Dict[str, Any]) -> str:
    address = ((case.get("circumstances") or {}).get("address")) or {}
    city = address.get("city")
    if city:
        return city
    # Fall back to publicGeolocation.formattedAddress if available.
    geo = (case.get("circumstances") or {}).get("publicGeolocation") or {}
    formatted = geo.get("formattedAddress")
    if formatted:
        return formatted.split(",")[0].strip() or "N/A"
    return "N/A"


def _extract_sex(case: Dict[str, Any]) -> str:
    sex = (case.get("subjectIdentification") or {}).get("sex")
    if isinstance(sex, dict):
        return sex.get("name") or "N/A"
    return sex or "N/A"


def _extract_ethnicity(case: Dict[str, Any]) -> str:
    eth = (case.get("subjectIdentification") or {}).get("primaryEthnicity")
    if isinstance(eth, dict):
        return eth.get("name") or "N/A"
    return eth or "N/A"


def _extract_year_of_birth(case: Dict[str, Any]) -> Optional[int]:
    yob = (case.get("subjectIdentification") or {}).get("yearOfBirth")
    try:
        return int(yob) if yob is not None else None
    except (TypeError, ValueError):
        return None


def _extract_date_body_found(case: Dict[str, Any]) -> str:
    return (case.get("circumstances") or {}).get("dateBodyFound") or "N/A"


def _extract_year_body_found(case: Dict[str, Any]) -> Optional[int]:
    d = (case.get("circumstances") or {}).get("dateBodyFound")
    if not d:
        return None
    try:
        return int(str(d)[:4])
    except (TypeError, ValueError):
        return None


def _extract_age_at_recovery(case: Dict[str, Any]) -> Optional[int]:
    yob = _extract_year_of_birth(case)
    yr = _extract_year_body_found(case)
    if yob is None or yr is None:
        return None
    age = yr - yob
    return age if 0 <= age <= 130 else None


def _extract_name(case: Dict[str, Any]) -> str:
    subj = case.get("subjectIdentification") or {}
    parts = [subj.get("firstName"), subj.get("middleName"), subj.get("lastName")]
    name = " ".join(p for p in parts if p).strip()
    return name or "Unknown"


def _extract_case_number(case: Dict[str, Any]) -> str:
    return (
        case.get("idFormatted")
        or case.get("caseNumber")
        or (f"UCP{case['id']}" if case.get("id") else "N/A")
    )


def _extract_agency(case: Dict[str, Any]) -> str:
    agencies = case.get("investigatingAgencies") or []
    for a in agencies:
        name = (a or {}).get("name")
        if name:
            return name
    return "N/A"


# ---------------------------------------------------------------------------
# Normalization + filtering
# ---------------------------------------------------------------------------
def _normalize_case(case: Dict[str, Any]) -> Dict[str, Any]:
    age = _extract_age_at_recovery(case)
    return {
        "Case Number": _extract_case_number(case),
        "Name": _extract_name(case),
        "Year of Birth": _extract_year_of_birth(case) or "N/A",
        "Age at Recovery": age if age is not None else "N/A",
        "Sex": _extract_sex(case),
        "Ethnicity": _extract_ethnicity(case),
        "Date Body Found": _extract_date_body_found(case),
        "Location": f"{_extract_city(case)}, {_extract_state(case)}",
        "Investigating Agency": _extract_agency(case),
        "Case Resolved": bool(case.get("caseIsResolved", False)),
    }


def process_unclaimed_persons_data(
    data: "Dict[str, Any] | Iterable[Dict[str, Any]]",
) -> List[Dict[str, Any]]:
    """Normalize NamUs Unclaimed Persons records into a flat list of dicts.

    Accepts either a Search response dict (with ``results`` key) or an
    iterable of case-detail dicts.
    """
    if isinstance(data, dict):
        cases = data.get("results") or data.get("cases") or []
    else:
        cases = list(data)
    return [_normalize_case(c) for c in cases]


def _matches_filters(case: Dict[str, Any], flt: Dict[str, Any]) -> bool:
    if not flt:
        return True
    state = flt.get("state")
    if state and _extract_state(case).upper() != state.upper():
        return False
    sex = flt.get("sex")
    if sex and _extract_sex(case).lower() != sex.lower():
        return False
    eth = flt.get("race_ethnicity")
    if eth and _extract_ethnicity(case).lower() != eth.lower():
        return False
    if flt.get("only_unresolved") and case.get("caseIsResolved"):
        return False

    yob = _extract_year_of_birth(case)
    yob_min, yob_max = flt.get("year_of_birth_min"), flt.get("year_of_birth_max")
    if yob_min is not None or yob_max is not None:
        if yob is None:
            return False
        if yob_min is not None and yob < yob_min:
            return False
        if yob_max is not None and yob > yob_max:
            return False

    amin, amax = flt.get("age_min"), flt.get("age_max")
    if amin is not None or amax is not None:
        age = _extract_age_at_recovery(case)
        if age is None:
            return False
        if amin is not None and age < amin:
            return False
        if amax is not None and age > amax:
            return False
    return True


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def fetch_cases(
    search_params: Dict[str, Any],
    session: Optional[requests.Session] = None,
    max_workers: int = 8,
    detail_fetcher: Optional[Callable[[int], Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Search + fetch details + client-side filter + normalize."""
    owns_session = session is None
    session = session or requests.Session()
    try:
        raw = search_unclaimed_persons(search_params, session=session)
        ids = [row["namus2Number"] for row in raw.get("results", []) if "namus2Number" in row]

        get_detail = detail_fetcher or (lambda i: fetch_case_detail(i, session=session))
        details: List[Dict[str, Any]] = []
        if ids:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                details = list(pool.map(get_detail, ids))

        flt = search_params.get("_client_filters") or {}
        filtered = [c for c in details if _matches_filters(c, flt)]
        return process_unclaimed_persons_data(filtered)
    finally:
        if owns_session:
            session.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Query NamUs Unclaimed Persons.")
    p.add_argument("--take", type=int, default=100)
    p.add_argument("--skip", type=int, default=0)
    p.add_argument("--state", default=None, help="Two-letter state code (client-side filter)")
    p.add_argument("--sex", default=None)
    p.add_argument("--race-ethnicity", default=None, help="e.g. 'White / Caucasian'")
    p.add_argument("--yob-min", type=int, default=None, dest="year_of_birth_min",
                   help="Earliest year of birth (inclusive)")
    p.add_argument("--yob-max", type=int, default=None, dest="year_of_birth_max",
                   help="Latest year of birth (inclusive)")
    p.add_argument("--age-min", type=int, default=None,
                   help="Minimum age at recovery (year(dateBodyFound) - yearOfBirth)")
    p.add_argument("--age-max", type=int, default=None,
                   help="Maximum age at recovery")
    p.add_argument("--only-unresolved", action="store_true",
                   help="Exclude cases already marked resolved")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    params = build_search_params(
        take=args.take,
        skip=args.skip,
        state=args.state,
        sex=args.sex,
        race_ethnicity=args.race_ethnicity,
        year_of_birth_min=args.year_of_birth_min,
        year_of_birth_max=args.year_of_birth_max,
        age_min=args.age_min,
        age_max=args.age_max,
        only_unresolved=args.only_unresolved,
    )
    print(f"Query: {_server_payload(params)}", file=sys.stderr)
    cases = fetch_cases(params)
    print(f"Returned: {len(cases)}", file=sys.stderr)

    if args.json:
        print(json.dumps(cases, indent=2, default=str))
    else:
        for case in cases:
            for k, v in case.items():
                print(f"{k}: {v}")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

