"""
CaseOrchestrator.py

Higher level script that runs Missing and Unidentified full export flows and
combines their full payload results. Unclaimed is intentionally skipped for now.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple

from CaseParser import CaseParser
import MissingFullExport as missing_full_export
import UnidentifiedFullExport as unidentified_full_export
parser = CaseParser()


def _export_case_set(
    case_set: str,
    payload: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows = payload.get("cases", [])
    for row in rows:
        row["Case Set"] = case_set
        parsed = parser.parse_case(row, case_set)
        row.clear()
        row.update(parsed)
    return rows


def fetch_all_case_sets(args: argparse.Namespace) -> Dict[str, Any]:
    """Fetch Missing and Unidentified full exports in parallel."""
    fetcher_type = Callable[[argparse.Namespace], Dict[str, Any]]
    jobs: List[Tuple[str, fetcher_type]] = [
        ("Missing Persons", missing_full_export.fetch_missing_details),
        ("Unidentified Persons", unidentified_full_export.fetch_unidentified_details),
    ]

    results_by_set: Dict[str, List[Dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        future_to_name = {
            pool.submit(fetcher, args): case_set
            for case_set, fetcher in jobs
        }
        for future, case_set in future_to_name.items():
            rows = _export_case_set(case_set, future.result())
            results_by_set[case_set] = rows

    merged: List[Dict[str, Any]] = []
    for case_set in ["Missing Persons", "Unidentified Persons"]:
        merged.extend(results_by_set.get(case_set, []))

    counts = {k: len(v) for k, v in results_by_set.items()}
    return {
        "counts": counts,
        "total": len(merged),
        "cases": merged,
    }


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Query Missing and Unidentified NamUs case sets using full-export flows."
    )
    p.add_argument("--take", type=int, default=100)
    p.add_argument("--skip", type=int, default=0)
    p.add_argument("--state", default=None, help="Two-letter state code (client-side filter)")
    p.add_argument("--age-min", type=int, default=None)
    p.add_argument("--age-max", type=int, default=None)
    p.add_argument("--sex", default=None)
    p.add_argument("--race-ethnicity", default=None)
    p.add_argument("--status", default=None, help="For Unidentified Persons only")
    p.add_argument("--fetch-all", action="store_true", help="Fetch all pages for both case sets")
    p.add_argument("--max-workers", type=int, default=8, help="Detail fetch worker count per case set")
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

