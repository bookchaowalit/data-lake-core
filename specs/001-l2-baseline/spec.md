---
id: SPEC-001
title: L2 baseline for data-lake-core
status: in review
created: 2026-10-22
owner: bookchaowalit
---

# SPEC-001: L2 baseline

## Document control

| Field | Value |
|---|---|
| Main-only | yes (ADR-0004 v1.1: red run is local, red and green commits pushed together) |
| Maker | Claude session b-data (2026-10-22) |
| Checker / approver | pending (owner) |

## Problem

The Big Loop scorecard (2026-10-22) had this repo at L0: no lockfile, no type check, no
PRODUCT.md and no Sentry declaration. CI installed with an unlocked `uv pip install -e ".[lake]"`
and had no coverage gate, so consumers (career-job-market-data, market-data and seven more
product repos) pinned a commit that was never checked for types or coverage.

## Behaviour

1. Dependencies resolve from the committed `uv.lock`; CI installs with `uv sync --frozen --all-extras`.
2. `mypy` runs in CI over `src/`, `scripts/` and `tests/` (gradual). `src/data_lake` keeps the
   parent's `# type: ignore` comments (mirrored code); three typing gaps carry targeted ignores
   (comments only, so the AST parity check is unaffected).
3. Sentry is an opt-in extra (`sentry-sdk>=2.72,<3`). The package is a library: no
   `[project.scripts]`, and no workflow, crontab or task runs its module CLIs. The consumer job
   that imports it owns `sentry_sdk.init`; library errors propagate to it. No observability
   module is added because every module in `src/data_lake` must exist in data-lake-pipelines
   (`scripts/check_parity.py` fails on package-only modules).
4. The lake-first contract is pinned offline: landing bytes are exact, the manifest records
   their SHA-256 and size, `manifest_version` is `"1"`, the Bronze object checksum and column
   list match, Bronze rows carry `raw_object_key`/`raw_sha256`, and a retried batch keeps the
   same keys and the original manifest bytes.
5. The public module surface is unchanged (no AST change in `src/data_lake`); parity with
   data-lake-pipelines stays `ok`.
6. CI fails when total coverage drops below 51% (measured 51.54%).

## Acceptance

| AC | Given / When / Then | Test |
|---|---|---|
| AC-01 | Given a payload, when it is ingested, then the landing object equals the input bytes and the manifest records their SHA-256, size and key | `tests/test_lake_contract.py::LakeFirstContractTests::test_landing_keeps_exact_bytes_and_manifest_records_their_checksum` |
| AC-02 | Given an ingest, then the manifest is version `"1"`, carries the product schema version, record count, Bronze checksum and the fixed column list | `test_manifest_is_versioned_and_describes_the_bronze_object` |
| AC-03 | Given an ingest, then every Bronze row has the fixed columns and points at the landing key and checksum | `test_bronze_rows_carry_landing_lineage_and_fixed_columns` |
| AC-04 | Given the same batch twice, then keys are identical and the manifest bytes are not rewritten | `test_retry_of_the_same_batch_is_idempotent_and_keeps_the_manifest` |
| AC-05 | Given a lineage file that is not valid JSON, then it is replaced | `LineageFileTests::test_unreadable_lineage_file_is_replaced` |
| AC-06 | Given a lineage file holding a JSON list, then it is replaced (known bug, expected failure until the parent fix is ported) | `LineageFileTests::test_lineage_file_holding_a_json_list_is_replaced` |
| AC-07 | Packaged runtime in AST parity with data-lake-pipelines | `python scripts/check_parity.py --parent ../data-lake-pipelines` → `parity: ok (9 modules …)` (local; CI skips the live check) |
| AC-08 | career-job-market-data's suite passes against this commit installed locally | see Consumer check below |
| AC-09 | CI on `main` is green on Python 3.11 and 3.13 with the coverage gate | CI run below |

## Red/green log

| AC | Red (sha · command · failure) | Green |
|---|---|---|
| AC-06 | not fixed here: `python -m pytest -q tests/test_lake_contract.py` → `AttributeError: 'list' object has no attribute 'get'` (`product_adapter.write_lineage`), kept as `expectedFailure` | fix belongs to data-lake-pipelines first (README update procedure), then port |
| AC-01..05, 07, 09 | none (characterisation of existing behaviour; no production change) | `GREEN_CI` |

## Consumer check

2026-10-22, local only (nothing committed in the consumer): a scratch clone of
career-job-market-data at `d77f385` (pins `b8f8698`), `uv sync --frozen --all-extras` on Python
3.12, then `uv pip install "solo-empire-data-lake[lake] @ file://…/dlc.tar.gz"` built with
`git archive e1ef5b1`. `FREE_ONLY=true ALLOW_EXTERNAL_NETWORK=false ALLOW_PAID_PROVIDER=false
python -m pytest -q -rs` → `42 passed, 27 subtests passed` (same as on its own pin), and
`python -m book_job_data.ingest --help` exits 0. The `e1ef5b1` tree differs from the pushed
docs tip only in this section.

## Schedule (planned replacement, D6)

Nothing is scheduled from this repository, and nothing here needs a schedule: it is a
library. The scheduled work that uses it lives in its consumers (market-data's
`setup_cron.sh`, career-job-scraper's scheduled capture, data-lake-pipelines' Windows tasks).
Planned replacement once D6 is decided: none in this repo; each consumer's hosted job installs
`solo-empire-data-lake[lake,sentry]` at a pinned commit and initialises Sentry itself.

## Out of scope

Changing `src/data_lake` behaviour (parent-first procedure), release tags, bumping consumer pins
other than market-data, Iceberg catalog labs, R2 writes.
