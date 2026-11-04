"""
CaseOrchestrator.py

Higher level script that runs all three NamUs case-set modules and combines
normalized results into one payload.
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


def fetch_all_case_sets(args: argparse.Namespace) -> Dict[str, Any]:
    """Fetch all three case sets in parallel and return merged output."""
    params = build_case_set_params(args)

    fetcher_type = Callable[[Dict[str, Any]], List[Dict[str, Any]]]
    jobs: List[Tuple[str, fetcher_type, Dict[str, Any]]] = [
        ("Missing Persons", missing_person.fetch_cases, params["Missing Persons"]),
        ("Unidentified Persons", unidentified_person.fetch_cases, params["Unidentified Persons"]),
        ("Unclaimed Persons", unclaimed_person.fetch_cases, params["Unclaimed Persons"]),
    ]

    results_by_set: Dict[str, List[Dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        future_to_name = {
            pool.submit(fetcher, search_params): case_set
            for case_set, fetcher, search_params in jobs
        }
        for future, case_set in future_to_name.items():
            rows = future.result()
            for row in rows:
                row["Case Set"] = case_set
            results_by_set[case_set] = rows

    merged: List[Dict[str, Any]] = []
    for case_set in ["Missing Persons", "Unidentified Persons", "Unclaimed Persons"]:
        merged.extend(results_by_set.get(case_set, []))

    counts = {k: len(v) for k, v in results_by_set.items()}
    return {
        "counts": counts,
        "total": len(merged),
        "cases": merged,
    }


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Query Missing, Unidentified, and Unclaimed NamUs case sets together."
    )
    p.add_argument("--take", type=int, default=100)
    p.add_argument("--skip", type=int, default=0)
    p.add_argument("--state", default=None, help="Two-letter state code (client-side filter)")
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
    p.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    combined = fetch_all_case_sets(args)

    print(f"Total returned: {combined['total']}", file=sys.stderr)
    for case_set, count in combined["counts"].items():
        print(f"{case_set}: {count}", file=sys.stderr)

    if args.json:
        print(json.dumps(combined, indent=2, default=str))
    else:
        for case in combined["cases"]:
            print(f"Case Set: {case['Case Set']}")
            for key, value in case.items():
                if key == "Case Set":
                    continue
                print(f"{key}: {value}")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

