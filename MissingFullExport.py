"""
MissingFullExport.py

Fetch full detail payloads for Missing Persons cases and enrich each case with
a NamUs case link.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

import requests

import MissingPerson as mp

CASE_LINK_TEMPLATE = "https://www.namus.gov/MissingPersons/Case#/{id}?nav"


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Fetch full Missing Persons case details and enrich each record "
            "with Case Link."
        )
    )
    p.add_argument("--take", type=int, default=100, help="Search page size")
    p.add_argument("--skip", type=int, default=0, help="Search offset")
    p.add_argument("--fetch-all", action="store_true", help="Iterate through all search pages")
    p.add_argument("--state", default=None)
    p.add_argument("--age-min", type=int, default=None)
    p.add_argument("--age-max", type=int, default=None)
    p.add_argument("--sex", default=None)
    p.add_argument("--race-ethnicity", default=None)
    p.add_argument("--max-workers", type=int, default=8)
    p.add_argument("--output", default="missing_full_cases.json", help="Output JSON path")
    p.add_argument("--print-json", action="store_true", help="Also print JSON to stdout")
    return p.parse_args(argv)


def build_case_link(case: Dict[str, Any], fallback_id: Optional[int] = None) -> str:
    """Build NamUs public case link for one missing person record."""
    cid = case.get("id") or fallback_id or ""
    return CASE_LINK_TEMPLATE.format(id=cid)


def enrich_case(case: Dict[str, Any], fallback_id: Optional[int] = None) -> Dict[str, Any]:
    """Keep full case payload and add case link."""
    enriched = dict(case)
    enriched["Case Link"] = build_case_link(case, fallback_id=fallback_id)
    return enriched


def _fetch_detail_batch(
    ids: List[int],
    session: requests.Session,
    max_workers: int,
    detail_fetcher: Optional[Callable[[int], Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    if not ids:
        return []

    get_detail = detail_fetcher or (lambda i: mp.fetch_case_detail(i, session=session))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(get_detail, ids))


def fetch_missing_details(
    args: argparse.Namespace,
    session: Optional[requests.Session] = None,
    detail_fetcher: Optional[Callable[[int], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Fetch detail records and return enriched cases with full payloads."""
    owns_session = session is None
    session = session or requests.Session()
    try:
        params = mp.build_search_params(
            take=args.take,
            skip=args.skip,
            state=args.state,
            age_min=args.age_min,
            age_max=args.age_max,
            sex=args.sex,
            race_ethnicity=args.race_ethnicity,
        )

        raw_first = mp.search_missing_persons(params, session=session)
        total_search_count = int(raw_first.get("count", 0) or 0)
        ids_first = [r["namus2Number"] for r in raw_first.get("results", []) if "namus2Number" in r]

        all_ids: List[int] = list(ids_first)
        if args.fetch_all and total_search_count > 0:
            skip = args.skip + args.take
            while skip < total_search_count:
                page_params = dict(params)
                page_params["skip"] = skip
                raw_page = mp.search_missing_persons(page_params, session=session)
                page_ids = [r["namus2Number"] for r in raw_page.get("results", []) if "namus2Number" in r]
                if not page_ids:
                    break
                all_ids.extend(page_ids)
                skip += args.take

        deduped_ids = list(dict.fromkeys(all_ids))
        details = _fetch_detail_batch(
            deduped_ids,
            session=session,
            max_workers=args.max_workers,
            detail_fetcher=detail_fetcher,
        )

        enriched = [enrich_case(case, fallback_id=cid) for cid, case in zip(deduped_ids, details)]
        return {
            "search_count": total_search_count,
            "returned": len(enriched),
            "cases": enriched,
        }
    finally:
        if owns_session:
            session.close()


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    result = fetch_missing_details(args)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"Wrote {result['returned']} cases to {args.output}", file=sys.stderr)
    print(f"Search count: {result['search_count']}", file=sys.stderr)

    if args.print_json:
        print(json.dumps(result, indent=2, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())

