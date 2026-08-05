"""
UnidentifiedPerson.py

Query the NamUs Unidentified Persons public API and return normalized case
records. Mirrors :mod:`MissingPerson` but for the Unidentified Persons case
set, where records describe unidentified remains (no name, only estimated
age range, ethnicity, sex, date/location found, etc.).

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

NAMUS_BASE_URL = "https://www.namus.gov/api/CaseSets/NamUs/UnidentifiedPersons"
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
    "Referer": "https://www.namus.gov/UnidentifiedPersons/Search",
    "Origin": "https://www.namus.gov",
}

# The only projection field the current Search API accepts.
_ALLOWED_PROJECTION = "namus2Number"


# ---------------------------------------------------------------------------
# Parameter building
# ---------------------------------------------------------------------------
def build_search_params(
    take: int = 100,
    skip: int = 0,
    state: Optional[str] = None,
    age_min: Optional[int] = None,
    age_max: Optional[int] = None,
    sex: Optional[str] = None,
    race_ethnicity: Optional[str] = None,
    status: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build an Unidentified Persons search request.

    ``state`` / ``sex`` / age / ``race_ethnicity`` / ``status`` are recorded
    under ``_client_filters`` and applied client-side by :func:`fetch_cases`.
    Age is compared against each case's estimated age range so a case matches
    when its ``[estimatedAgeFrom, estimatedAgeTo]`` interval overlaps the
    requested ``[age_min, age_max]`` window.
    """
    params: Dict[str, Any] = {
        "take": take,
        "skip": skip,
        "projections": [_ALLOWED_PROJECTION],
        "predicates": [],
        "orderBy": [{"name": "dateOfLastContact", "direction": "descending"}],
        "_client_filters": {
            "state": state,
            "age_min": age_min,
            "age_max": age_max,
            "sex": sex,
            "race_ethnicity": race_ethnicity,
            "status": status,
        },
    }
    if state:
        params["state"] = state
    if sex:
        params["sex"] = sex
    if race_ethnicity:
        params["raceEthnicity"] = race_ethnicity
    if status:
        params["status"] = status
    if age_min is not None or age_max is not None:
        params["estimatedAgeMin"] = age_min if age_min is not None else 0
        params["estimatedAgeMax"] = age_max if age_max is not None else 120
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
def search_unidentified_persons(
    search_params: Dict[str, Any],
    session: Optional[requests.Session] = None,
    timeout: int = 30,
    url: str = NAMUS_SEARCH_URL,
) -> Dict[str, Any]:
    """POST to the Unidentified Persons Search endpoint and return JSON.

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
    """GET a single unidentified-person case's full detail record."""
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
    return address.get("city") or "N/A"


def _extract_sex(case: Dict[str, Any]) -> str:
    sex = (case.get("subjectDescription") or {}).get("sex")
    if isinstance(sex, dict):
        return sex.get("name") or "N/A"
    return sex or "N/A"


def _extract_ethnicity(case: Dict[str, Any]) -> str:
    eth = (case.get("subjectDescription") or {}).get("primaryEthnicity")
    if isinstance(eth, dict):
        return eth.get("name") or "N/A"
    return eth or "N/A"


def _extract_age_range(case: Dict[str, Any]) -> "tuple[Optional[int], Optional[int]]":
    subj = case.get("subjectDescription") or {}
    return subj.get("estimatedAgeFrom"), subj.get("estimatedAgeTo")


def _extract_status(case: Dict[str, Any]) -> str:
    status = (case.get("circumstances") or {}).get("status")
    if isinstance(status, dict):
        return status.get("name") or "N/A"
    return status or "N/A"


def _extract_date_found(case: Dict[str, Any]) -> str:
    return (case.get("circumstances") or {}).get("dateFound") or "N/A"


def _extract_case_number(case: Dict[str, Any]) -> str:
    ci = case.get("caseIdentification") or {}
    return (
        case.get("idFormatted")
        or ci.get("caseNumber")
        or (f"UP{case['id']}" if case.get("id") else "N/A")
    )


def _extract_details(case: Dict[str, Any]) -> str:
    return (case.get("circumstances") or {}).get(
        "circumstancesOfRecovery"
    ) or case.get("details", "No details available")


def _extract_condition(case: Dict[str, Any]) -> str:
    cond = (case.get("detailsOfRecovery") or {}).get("conditionOfRemains")
    if isinstance(cond, dict):
        return cond.get("name") or "N/A"
    return cond or "N/A"


# ---------------------------------------------------------------------------
# Normalization + filtering
# ---------------------------------------------------------------------------
def _format_age(case: Dict[str, Any]) -> str:
    lo, hi = _extract_age_range(case)
    if lo is None and hi is None:
        return "N/A"
    if lo == hi or hi is None:
        return str(lo)
    if lo is None:
        return f"?-{hi}"
    return f"{lo}-{hi}"


def _normalize_case(case: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "Case Number": _extract_case_number(case),
        "NCMEC Number": (case.get("caseIdentification") or {}).get("ncmecNumber", "N/A"),
        "Status": _extract_status(case),
        "Estimated Age": _format_age(case),
        "Sex": _extract_sex(case),
        "Ethnicity": _extract_ethnicity(case),
        "Date Found": _extract_date_found(case),
        "Location": f"{_extract_city(case)}, {_extract_state(case)}",
        "Condition of Remains": _extract_condition(case),
        "Details": _extract_details(case),
    }


def process_unidentified_persons_data(
    data: "Dict[str, Any] | Iterable[Dict[str, Any]]",
) -> List[Dict[str, Any]]:
    """Normalize NamUs Unidentified Persons records into a flat list of dicts.

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
    status = flt.get("status")
    if status and _extract_status(case).lower() != status.lower():
        return False
    lo, hi = _extract_age_range(case)
    amin = flt.get("age_min")
    amax = flt.get("age_max")
    # Interval-overlap match: case [lo, hi] must overlap requested [amin, amax].
    if amin is not None and hi is not None and hi < amin:
        return False
    if amax is not None and lo is not None and lo > amax:
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
        raw = search_unidentified_persons(search_params, session=session)
        ids = [row["namus2Number"] for row in raw.get("results", []) if "namus2Number" in row]

        get_detail = detail_fetcher or (lambda i: fetch_case_detail(i, session=session))
        details: List[Dict[str, Any]] = []
        if ids:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                details = list(pool.map(get_detail, ids))

        flt = search_params.get("_client_filters") or {}
        filtered = [c for c in details if _matches_filters(c, flt)]
        return process_unidentified_persons_data(filtered)
    finally:
        if owns_session:
            session.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Query NamUs Unidentified Persons.")
    p.add_argument("--take", type=int, default=100)
    p.add_argument("--skip", type=int, default=0)
    p.add_argument("--state", default=None, help="Two-letter state code (client-side filter)")
    p.add_argument("--age-min", type=int, default=None, help="Overlap match against estimated age range")
    p.add_argument("--age-max", type=int, default=None, help="Overlap match against estimated age range")
    p.add_argument("--sex", default=None)
    p.add_argument("--race-ethnicity", default=None, help="e.g. 'White / Caucasian'")
    p.add_argument("--status", default=None, help="e.g. 'Unidentified Deceased'")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    params = build_search_params(
        take=args.take,
        skip=args.skip,
        state=args.state,
        age_min=args.age_min,
        age_max=args.age_max,
        sex=args.sex,
        race_ethnicity=args.race_ethnicity,
        status=args.status,
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

