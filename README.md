# DoeNoMore

Automated matching pipeline for [NamUs](https://www.namus.gov/) — the U.S. National Missing and Unidentified Persons System.

- Missing Persons: https://www.namus.gov/MissingPersons/Search
- Unidentified Persons: https://www.namus.gov/UnidentifiedPersons/Search
- Unclaimed Persons: https://www.namus.gov/UnclaimedPersons/Search

## Background

There is some matching logic already being used within NamUs, but a good portion of matches originate from users manually searching. Web sleuths spend countless hours cross-referencing missing- and unidentified-person records. This project pulls both case sets from the public NamUs API and provides a foundation for automated matching (and eventually AI-assisted matching) so tips can be surfaced faster and families can get closure.

## Goal

There are far too many missing persons and unidentified persons; today cold cases only tend to restart with a tip or a suggested match. This project aims to automate the discovery of possible matches and (eventually) submit reports back to NamUs.

---

## Repo layout

| File | Purpose |
|---|---|
| `MissingPerson.py`                       | CLI + library for the NamUs **Missing Persons** case set |
| `UnidentifiedPerson.py`                  | CLI + library for the NamUs **Unidentified Persons** case set |
| `UnclaimedPerson.py`                     | CLI + library for the NamUs **Unclaimed Persons** case set |
| `CaseOrchestrator.py`                    | Higher-level CLI that merges Missing + Unidentified full export results |
| `CaseCounts.py`                          | Count-only CLI for Missing, Unidentified, and Unclaimed case sets |
| `UnidentifiedFullExport.py`              | Full-payload export for unidentified cases with case link and photo marker |
| `MissingFullExport.py`                   | Full-payload export for missing-person cases with case link |
| `CaseParser.py`                          | Reusable parser object for Missing + Unidentified full case payloads |
| `UnitTests/test_missing_person.py`       | Unit tests for `MissingPerson.py` (mocked + optional live) |
| `UnitTests/test_unidentified_person.py`  | Unit tests for `UnidentifiedPerson.py` (mocked + optional live) |
| `UnitTests/test_unclaimed_person.py`     | Unit tests for `UnclaimedPerson.py` (mocked + optional live) |
| `UnitTests/test_case_orchestrator.py`    | Unit tests for `CaseOrchestrator.py` |
| `UnitTests/test_case_counts.py`          | Unit tests for `CaseCounts.py` |
| `UnitTests/test_unidentified_full_export.py` | Unit tests for `UnidentifiedFullExport.py` |
| `UnitTests/test_missing_full_export.py`  | Unit tests for `MissingFullExport.py` |
| `UnitTests/test_case_parser.py`          | Unit tests for `CaseParser.py` |
| `requirements.txt`                       | Runtime dependencies |

## Requirements

- Python 3.10+ (developed against 3.14)
- `requests` (see `requirements.txt`)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you use JetBrains IDEs, point the project interpreter at `.venv/bin/python`
(**File → Project Structure → Project SDK → Add SDK → Python SDK → Existing environment**).

---

## How the NamUs API is used

The current NamUs `Search` endpoints only allow a very narrow projection
(`namus2Number`) and don't accept server-side filters for state / sex / age.
So each script does:

1. **Search** — POST to `/api/CaseSets/NamUs/{CaseSet}/Search` to get a list of
   `namus2Number` IDs (ordered by `dateOfLastContact` descending).
2. **Detail fetch** — GET `/api/CaseSets/NamUs/{CaseSet}/Cases/{id}` in parallel
   (thread pool) for each ID.
3. **Client-side filter** — apply `state`, `sex`, age, ethnicity, status filters
   against the rich detail records.
4. **Normalize** — flatten each record to a stable dict schema for downstream use.

## Usage

### Missing Persons

```bash
# Human-readable, 5 most recently updated cases
.venv/bin/python MissingPerson.py --take 5

# JSON, filter to Florida adult females
.venv/bin/python MissingPerson.py --take 100 --state FL --sex Female \
    --age-min 18 --age-max 65 --json
```

Flags: `--take`, `--skip`, `--state`, `--age-min`, `--age-max`, `--sex`, `--json`.

Normalized fields per case:
`Case Number`, `Name`, `Date of Birth`, `Age`, `Sex`, `Location`, `Details`.

### Unidentified Persons

```bash
# 3 most recent unidentified cases
.venv/bin/python UnidentifiedPerson.py --take 3

# JSON, Texas males aged 30–45, deceased
.venv/bin/python UnidentifiedPerson.py \
    --take 100 --state TX --sex Male --age-min 30 --age-max 45 \
    --status "Unidentified Deceased" --json
```

Flags: `--take`, `--skip`, `--state`, `--age-min`, `--age-max`, `--sex`,
`--race-ethnicity`, `--status`, `--json`.

Age filtering uses **interval-overlap matching** against each case's
`[estimatedAgeFrom, estimatedAgeTo]` range.

For matching workflows, cases with `Condition of Remains` equal to `Not recognizable`
are currently excluded from `fetch_cases` output.

Normalized fields per case:
`Case Number`, `NCMEC Number`, `Status`, `Estimated Age`, `Sex`, `Ethnicity`,
`Date Found`, `Location`, `Condition of Remains`, `Details`.

### Unclaimed Persons

Unclaimed cases are decedents who **have** been identified (they have a name)
but no next-of-kin has claimed the body. Because the person is named, filters
work off `yearOfBirth` and (optionally) age at recovery
(`year(dateBodyFound) - yearOfBirth`).

```bash
# 3 most recent unclaimed cases
.venv/bin/python UnclaimedPerson.py --take 3

# JSON, Georgia males born 1940–1970, still unresolved
.venv/bin/python UnclaimedPerson.py \
    --take 100 --state GA --sex Male \
    --yob-min 1940 --yob-max 1970 --only-unresolved --json

# 25-45 year-olds at time of recovery, nationwide
.venv/bin/python UnclaimedPerson.py --take 100 --age-min 25 --age-max 45
```

Flags: `--take`, `--skip`, `--state`, `--sex`, `--race-ethnicity`, `--yob-min`,
`--yob-max`, `--age-min`, `--age-max`, `--only-unresolved`, `--json`.

Normalized fields per case:
`Case Number`, `Name`, `Year of Birth`, `Age at Recovery`, `Sex`, `Ethnicity`,
`Date Body Found`, `Location`, `Investigating Agency`, `Case Resolved`.

### Using the modules as libraries

```python
import MissingPerson as mp
import UnidentifiedPerson as up
import UnclaimedPerson as ucp

# Missing persons in California
mp_cases = mp.fetch_cases(mp.build_search_params(take=50, state="CA"))

# Unidentified deceased in Texas
up_cases = up.fetch_cases(up.build_search_params(
    take=50, state="TX", status="Unidentified Deceased"
))

# Unclaimed persons in Georgia, unresolved
ucp_cases = ucp.fetch_cases(ucp.build_search_params(
    take=50, state="GA", only_unresolved=True
))
```

All three `fetch_cases` calls accept an optional `session=requests.Session()`
and a `detail_fetcher=` hook (useful for tests and for injecting a cache).

### Combined query across Missing and Unidentified full exports

```bash
# Pull Missing + Unidentified together and print a text report
.venv/bin/python CaseOrchestrator.py --take 10 --state CA

# JSON output with shared filters + Unidentified status filter
.venv/bin/python CaseOrchestrator.py \
    --take 50 --state TX --sex Male --age-min 20 --age-max 45 \
    --status "Unidentified Deceased" --fetch-all --json
```

`CaseOrchestrator.py` intentionally skips Unclaimed Persons for now.

The combined JSON payload includes:

- `counts`: number of rows returned per case set
- `total`: merged row count
- `cases`: full detail records from the export flows, each tagged with `Case Set`

Each case in `cases` also includes a `Breakdown` object with:

- `Identifiers`: ID values, case numbers, status, resolved flag, case link
- `Demographics`: name parts, date and year of birth, sex, gender, ethnicity, race
- `Age`: unified min and max values, plus estimated and missing specific min and max fields
- `Physical Description`: height and weight ranges, eye and hair attributes, distinctive features
- `Clothing and Accessories`: item count and parsed item list with category, type, color, size, brand, description
- `Physical Features`: item count and parsed item list with type, location, value, description
- `Eye Color`: parsed scalar field from nested physical description data
- `Hair Color`: parsed scalar field from nested physical description data
- `Physical Features Summary`: comma-separated summary of parsed physical feature types or descriptions
- `Circumstances`: location fields, date fields, and disappearance and recovery narratives
- `Investigating Agencies`: agency name list
- `Investigating Agencies Summary`: comma-separated agency names
- `Media`: photo presence flag, image count, document count
- `Vehicles Count`: number of vehicle records attached to the case
- `Top Level Keys`: sorted list of available top level keys in the raw case payload

For easier downstream matching, each case row also repeats these flattened fields at top level:

- `Eye Color`
- `Hair Color`
- `Physical Features Summary`
- `Investigating Agency Summary`

To avoid duplication, raw nested source blobs that are parsed into these fields
are removed from each case row in orchestrator output.

### Count entries across all three case sets

```bash
# Count all three case sets
.venv/bin/python CaseCounts.py

# Count with filters and JSON output
.venv/bin/python CaseCounts.py \
    --state CA --sex Female --age-min 18 --age-max 65 --json
```

The count payload includes:

- `counts`: top-level Search count for each case set
- `total`: sum of those counts

Current count snapshot as of November 3, 2026:

- Total: 65790
- Missing Persons: 26607
- Unidentified Persons: 15521
- Unclaimed Persons: 23662

### Export full unidentified case records with case link and photo marker

```bash
# First page of unidentified cases, write full payloads to JSON
.venv/bin/python UnidentifiedFullExport.py --take 100 --output unidentified_full_cases.json

# Fetch all pages and include filters
.venv/bin/python UnidentifiedFullExport.py \
    --fetch-all --state TX --status "Unidentified Deceased" \
    --output unidentified_full_cases.json
```

Each exported case keeps the full NamUs detail payload and adds:

- `Case Link`: public URL like `https://www.namus.gov/UnidentifiedPersons/Case#/163354?nav`
- `Has Photo`: `true` when `images`, `defaultImage`, or default-image URL fields are present

### Export full missing-person case records with case link

```bash
# First page of missing-person cases, write full payloads to JSON
.venv/bin/python MissingFullExport.py --take 100 --output missing_full_cases.json

# Fetch all pages and include filters
.venv/bin/python MissingFullExport.py \
    --fetch-all --state CA --sex Female --age-min 18 --age-max 65 \
    --output missing_full_cases.json
```

Each exported case keeps the full NamUs detail payload and adds:

- `Case Link`: public URL like `https://www.namus.gov/MissingPersons/Case#/163404?nav`

## Running tests

Tests live under `UnitTests/` (which is a Python package — has `__init__.py`).

```bash
# Fast, offline (mocked HTTP): 40 tests total
.venv/bin/python -m unittest discover -s UnitTests -t .

# Include live NamUs API calls (slow — hits real endpoints)
RUN_LIVE_NAMUS=1 .venv/bin/python -m unittest discover -s UnitTests -t .
```

## Roadmap

- [x] Fetch and normalize Missing Persons case data
- [x] Fetch and normalize Unidentified Persons case data
- [x] Fetch and normalize Unclaimed Persons case data
- [ ] Cross-set matching heuristics (age range, date consistency, geography, sex, ethnicity)
- [ ] AI-assisted narrative similarity (circumstances vs. recovery details, physical features)
- [ ] Confidence-scored match report generation
- [ ] Submission workflow back to NamUs
