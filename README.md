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
| `UnitTests/test_missing_person.py`       | Unit tests for `MissingPerson.py` (mocked + optional live) |
| `UnitTests/test_unidentified_person.py`  | Unit tests for `UnidentifiedPerson.py` (mocked + optional live) |
| `UnitTests/test_unclaimed_person.py`     | Unit tests for `UnclaimedPerson.py` (mocked + optional live) |
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
