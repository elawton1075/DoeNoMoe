"""
CaseOrchestrator.py

Higher level script that runs Missing and Unidentified full export flows and
combines their full payload results. Unclaimed is intentionally skipped for now.

Cases are parsed once into typed ParsedCase objects. Text output is formatted
from those objects, and JSON output serializes them.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from CaseModels import ParsedCase, ValueRange
from CaseParser import CaseParser
import MissingFullExport as missing_full_export
import UnidentifiedFullExport as unidentified_full_export

_case_parser = CaseParser()


def parse_case_set(case_set: str, payload: Dict[str, Any]) -> List[ParsedCase]:
    """Parse every case in an export payload, leaving the input untouched."""
    return _case_parser.parse_case_objects(payload.get("cases", []), case_set)


def fetch_parsed_cases(args: argparse.Namespace) -> Dict[str, List[ParsedCase]]:
    """Fetch Missing and Unidentified full exports in parallel, parsed per case set."""
    jobs = [
        ("Missing Persons", missing_full_export.fetch_missing_details),
        ("Unidentified Persons", unidentified_full_export.fetch_unidentified_details),
    ]

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = [(case_set, pool.submit(fetcher, args)) for case_set, fetcher in jobs]
        return {
            case_set: parse_case_set(case_set, future.result())
            for case_set, future in futures
        }


def combine_case_sets(parsed_by_set: Dict[str, List[ParsedCase]]) -> Dict[str, Any]:
    """Serialize parsed cases into the combined counts, total, and cases payload."""
    cases = [
        parsed.to_output_dict(CaseParser.PRUNED_PARSED_BLOBS)
        for rows in parsed_by_set.values()
        for parsed in rows
    ]
    return {
        "counts": {case_set: len(rows) for case_set, rows in parsed_by_set.items()},
        "total": len(cases),
        "cases": cases,
    }


def fetch_all_case_sets(args: argparse.Namespace) -> Dict[str, Any]:
    """Fetch Missing and Unidentified full exports and return the combined payload."""
    return combine_case_sets(fetch_parsed_cases(args))


# A NamedValue serializes to exactly these keys. It is shown as one readable name.
_NAMED_VALUE_KEYS = {"ID", "Name", "Localized Name", "Display Name"}

# The report shows only these fields for each investigating agency.
_AGENCY_REPORT_FIELDS = ("Name", "City", "State")


def is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def simplify(value: Any) -> Any:
    """Collapse ranges and lookup values to one line and drop anything empty."""
    if isinstance(value, ValueRange):
        return value.range_text if value.is_known else None
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, str):
        # Free text can span several lines, so join it to keep the indentation readable.
        return " ".join(line.strip() for line in value.splitlines() if line.strip())
    if isinstance(value, dict):
        if set(value) == _NAMED_VALUE_KEYS:
            return value["Display Name"] or value["Localized Name"] or value["Name"] or None
        simplified = {key: simplify(item) for key, item in value.items()}
        return {key: item for key, item in simplified.items() if not is_empty(item)}
    if isinstance(value, list):
        simplified_items = [simplify(item) for item in value]
        return [item for item in simplified_items if not is_empty(item)]
    return value


def render_mapping(mapping: Dict[str, Any], indent: int) -> List[str]:
    pad = "  " * indent
    lines: List[str] = []
    for label, item in mapping.items():
        if isinstance(item, dict):
            lines.append(f"{pad}{label}:")
            lines.extend(render_mapping(item, indent + 1))
        elif isinstance(item, list):
            lines.append(f"{pad}{label}:")
            lines.extend(render_list(item, indent + 1))
        else:
            lines.append(f"{pad}{label}: {item}")
    return lines


def render_list(items: List[Any], indent: int) -> List[str]:
    pad = "  " * indent
    lines: List[str] = []
    for number, item in enumerate(items, start=1):
        if isinstance(item, dict):
            lines.append(f"{pad}{number}.")
            lines.extend(render_mapping(item, indent + 1))
        else:
            lines.append(f"{pad}{number}. {item}")
    return lines


def format_case_text(parsed: ParsedCase) -> str:
    """Readable multi-line report of everything in one parsed case.

    Sections follow the CaseBreakdown models. Empty values are left out, and a
    section with nothing to show prints "None".
    """
    b = parsed.breakdown
    details = b.to_dict()

    # Date of birth is shown with the ages, so it is not repeated under Demographics.
    demographics = {k: v for k, v in details["Demographics"].items() if k != "Date of Birth"}
    ages = {
        "Date of Birth": b.demographics.date_of_birth,
        "Age When Missing": b.age.when_missing,
        "Age Now": b.age.now,
        "Projected Age At Death": b.age.projected_age_at_death,
        "Projected Birth Years": b.age.projected_birth_years,
    }

    sections: Dict[str, Any] = {
        "Identifiers": details["Identifiers"],
        "Demographics": demographics,
        "Age": ages,
        "Physical Description": details["Physical Description"],
        "Clothing and Accessories": details["Clothing and Accessories"]["Items"],
        "Physical Features": details["Physical Features"]["Items"],
        "Circumstances": details["Circumstances"],
        "Investigating Agencies": [
            {key: agency[key] for key in _AGENCY_REPORT_FIELDS}
            for agency in details["Investigating Agencies"]
        ],
        "Media": details["Media"],
        "Vehicles": {"Count": b.vehicles_count},
    }

    title = b.demographics.name or b.identifiers.case_number or "Unknown"
    lines = [f"{b.identifiers.case_set}: {title}"]
    for heading, content in sections.items():
        content = simplify(content)
        if is_empty(content):
            lines.append(f"{heading}: None")
            continue
        lines.append(f"{heading}:")
        if isinstance(content, list):
            lines.extend(render_list(content, 1))
        else:
            lines.extend(render_mapping(content, 1))
    return "\n".join(lines)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Query Missing and Unidentified NamUs case sets using full-export flows."
    )
    p.add_argument("--take", type=int, default=5, help="Cases to return per case set (default 5)")
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
    args = parse_args(argv)
    parsed_by_set = fetch_parsed_cases(args)

    print(f"Total returned: {sum(len(rows) for rows in parsed_by_set.values())}", file=sys.stderr)
    for case_set, rows in parsed_by_set.items():
        print(f"{case_set}: {len(rows)}", file=sys.stderr)

    if args.json:
        print(json.dumps(combine_case_sets(parsed_by_set), indent=2, default=str))
    else:
        for rows in parsed_by_set.values():
            for parsed in rows:
                print(format_case_text(parsed))
                print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

