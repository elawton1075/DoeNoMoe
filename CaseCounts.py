"""
CaseCounts.py

Count entries from all three NamUs case sets without fetching case detail records.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple

import MissingPerson as missing_person
import UnclaimedPerson as unclaimed_person
import UnidentifiedPerson as unidentified_person


def build_case_set_params(args: argparse.Namespace) -> Dict[str, Dict[str, Any]]:
    """Build per-module search params from one shared CLI argument set."""
    return {
        "Missing Persons": missing_person.build_search_params(
            take=args.take,
            skip=args.skip,
            state=args.state,
            age_min=args.age_min,
            age_max=args.age_max,
            sex=args.sex,
            race_ethnicity=args.race_ethnicity,
        ),
        "Unidentified Persons": unidentified_person.build_search_params(
            take=args.take,
            skip=args.skip,
            state=args.state,
            age_min=args.age_min,
            age_max=args.age_max,
            sex=args.sex,
            race_ethnicity=args.race_ethnicity,
            status=args.status,
        ),
        "Unclaimed Persons": unclaimed_person.build_search_params(
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
        ),
    }


def fetch_counts(args: argparse.Namespace) -> Dict[str, Any]:
    """Fetch only top-level search counts for all three case sets."""
    params = build_case_set_params(args)

    searcher_type = Callable[[Dict[str, Any]], Dict[str, Any]]
    jobs: List[Tuple[str, searcher_type, Dict[str, Any]]] = [
        ("Missing Persons", missing_person.search_missing_persons, params["Missing Persons"]),
        (
            "Unidentified Persons",
            unidentified_person.search_unidentified_persons,
            params["Unidentified Persons"],
        ),
        ("Unclaimed Persons", unclaimed_person.search_unclaimed_persons, params["Unclaimed Persons"]),
    ]

    counts: Dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        future_to_name = {
            pool.submit(searcher, search_params): case_set
            for case_set, searcher, search_params in jobs
        }
        for future, case_set in future_to_name.items():
            raw = future.result()
            counts[case_set] = int(raw.get("count", 0) or 0)

    return {
        "counts": counts,
        "total": sum(counts.values()),
    }


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Count records across Missing, Unidentified, and Unclaimed NamUs case sets."
    )
    p.add_argument("--take", type=int, default=100)
    p.add_argument("--skip", type=int, default=0)
    p.add_argument("--state", default=None, help="Two-letter state code")
    p.add_argument("--age-min", type=int, default=None)
    p.add_argument("--age-max", type=int, default=None)
    p.add_argument("--sex", default=None)
    p.add_argument("--race-ethnicity", default=None)
    p.add_argument("--status", default=None, help="For Unidentified Persons only")
    p.add_argument("--yob-min", type=int, default=None, dest="year_of_birth_min")
    p.add_argument("--yob-max", type=int, default=None, dest="year_of_birth_max")
    p.add_argument(
        "--only-unresolved",
        action="store_true",
        help="For Unclaimed Persons only",
    )
    p.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    result = fetch_counts(args)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"Total: {result['total']}")
        for case_set in ["Missing Persons", "Unidentified Persons", "Unclaimed Persons"]:
            print(f"{case_set}: {result['counts'].get(case_set, 0)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

