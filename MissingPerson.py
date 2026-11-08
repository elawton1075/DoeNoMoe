"""
MissingPerson.py

Query the NamUs Missing Persons public API and return normalized case records.

The NamUs Search endpoint was redesigned and now only exposes the
`namus2Number` field for projection/prediction. Rich case data must be
fetched from the per-case detail endpoint. Filtering by state / age / sex
therefore happens client-side after fetching details.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Iterable, List, Optional

import requests

NAMUS_BASE_URL = "https://www.namus.gov/api/CaseSets/NamUs/MissingPersons"
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
    "Referer": "https://www.namus.gov/MissingPersons/Search",
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
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a NamUs search request.

    The modern Search API only supports pagination + ordering on ``namus2Number``.
    Filters such as ``state``, ``sex`` and age are recorded under
    ``_client_filters`` and applied by :func:`fetch_cases` after per-case
    details are fetched.
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
        },
    }
    # Legacy/compat keys some callers/tests inspect on the returned dict.
    if state:
        params["state"] = state
    if sex:
        params["sex"] = sex
    if race_ethnicity:
        params["raceEthnicity"] = race_ethnicity
    if age_min is not None or age_max is not None:
        params["computedMissingMinAge"] = age_min if age_min is not None else 0
        params["computedMissingMaxAge"] = age_max if age_max is not None else 120
    if extra:
        params.update(extra)
    return params


def server_payload(search_params: Dict[str, Any]) -> Dict[str, Any]:
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
def search_missing_persons(
    search_params: Dict[str, Any],
    session: Optional[requests.Session] = None,
    timeout: int = 30,
    url: str = NAMUS_SEARCH_URL,
) -> Dict[str, Any]:
    """POST to the NamUs Search endpoint and return parsed JSON.

    Response shape: ``{"count": int, "results": [{"namus2Number": int, ...}]}``.
    """
    http = session or requests
    payload = server_payload(search_params)
    response = http.post(url, headers=DEFAULT_HEADERS, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def fetch_case_detail(
    namus2_number: int,
    session: Optional[requests.Session] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """GET a single case's full detail record."""
    http = session or requests
    response = http.get(
        NAMUS_CASE_URL.format(id=namus2_number),
        headers=DEFAULT_HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Normalization + filtering
# ---------------------------------------------------------------------------
def extract_state(case: Dict[str, Any]) -> str:
    address = ((case.get("sighting") or {}).get("address")) or {}
    state = address.get("state")
    if isinstance(state, dict):
        return state.get("displayName") or state.get("name") or "N/A"
    return state or "N/A"


def extract_city(case: Dict[str, Any]) -> str:
    address = ((case.get("sighting") or {}).get("address")) or {}
    return address.get("city") or "N/A"


def extract_sex(case: Dict[str, Any]) -> str:
    sex = (case.get("subjectDescription") or {}).get("sex")
    if isinstance(sex, dict):
        return sex.get("name") or "N/A"
    # Older/mocked shape.
    sex = (case.get("subjectIdentification") or {}).get("sex")
    if isinstance(sex, dict):
        return sex.get("name") or "N/A"
    return sex or "N/A"


def extract_age(case: Dict[str, Any]) -> Any:
    subj = case.get("subjectIdentification") or {}
    return (
        subj.get("computedMissingMinAge")
        or subj.get("currentMinAge")
        or case.get("age")
        or "N/A"
    )


def normalize_case(case: Dict[str, Any]) -> Dict[str, Any]:
    subj = case.get("subjectIdentification") or {}
    name = " ".join(
        p for p in (subj.get("firstName"), subj.get("lastName")) if p
    ).strip() or case.get("name", "N/A")
    details = (case.get("circumstances") or {}).get(
        "circumstancesOfDisappearance"
    ) or case.get("details", "No details available")
    return {
        "Case Number": case.get("idFormatted")
        or case.get("caseNumber")
        or (f"MP{case['id']}" if case.get("id") else "N/A"),
        "Name": name,
        "Date of Birth": subj.get("computedDateOfBirth")
        or case.get("dateOfBirth", "N/A"),
        "Age": extract_age(case),
        "Sex": extract_sex(case),
        "Location": f"{extract_city(case)}, {extract_state(case)}",
        "Details": details,
    }


def process_missing_persons_data(
    data: "Dict[str, Any] | Iterable[Dict[str, Any]]",
) -> List[Dict[str, Any]]:
    """Normalize NamUs case records into a flat list of dicts.

    Accepts either a Search response dict (``results`` or legacy ``cases`` key)
    or an iterable of case-detail dicts.
    """
    if isinstance(data, dict):
        cases = data.get("results") or data.get("cases") or []
    else:
        cases = list(data)
    return [normalize_case(c) for c in cases]


def matches_filters(case: Dict[str, Any], flt: Dict[str, Any]) -> bool:
    if not flt:
        return True
    state = flt.get("state")
    if state and extract_state(case).upper() != state.upper():
        return False
    sex = flt.get("sex")
    if sex and extract_sex(case).lower() != sex.lower():
        return False
    age = extract_age(case)
    if isinstance(age, (int, float)):
        if flt.get("age_min") is not None and age < flt["age_min"]:
            return False
        if flt.get("age_max") is not None and age > flt["age_max"]:
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
        raw = search_missing_persons(search_params, session=session)
        ids = [row["namus2Number"] for row in raw.get("results", []) if "namus2Number" in row]

        get_detail = detail_fetcher or (lambda i: fetch_case_detail(i, session=session))
        details: List[Dict[str, Any]] = []
        if ids:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                details = list(pool.map(get_detail, ids))

        flt = search_params.get("_client_filters") or {}
        filtered = [c for c in details if matches_filters(c, flt)]
        return process_missing_persons_data(filtered)
    finally:
        if owns_session:
            session.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Query NamUs Missing Persons.")
    p.add_argument("--take", type=int, default=100)
    p.add_argument("--skip", type=int, default=0)
    p.add_argument("--state", default=None, help="Two-letter state code (client-side filter)")
    p.add_argument("--age-min", type=int, default=None)
    p.add_argument("--age-max", type=int, default=None)
    p.add_argument("--sex", default=None)
    p.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    params = build_search_params(
        take=args.take,
        skip=args.skip,
        state=args.state,
        age_min=args.age_min,
        age_max=args.age_max,
        sex=args.sex,
    )
    print(f"Query: {server_payload(params)}", file=sys.stderr)
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
