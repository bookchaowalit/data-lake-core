# data-lake-core (`solo-empire-data-lake`)

Installable Python library with the shared lake-first primitives used by the
`book-*-data` product repositories: exact landing bytes + SHA-256 → Bronze
Parquet → immutable, versioned batch manifest → lineage, plus a DuckDB read path
and an optional Iceberg registration path. It is not a product API, scraper or
service, and it holds no credentials.

## Runtime status (verified 2026-10-22)

| What | Status |
|---|---|
| Kind | Library. No `[project.scripts]`; consumers import `data_lake.product_adapter`, `product_store`, `silver`, `storage` |
| Module CLIs | `python -m data_lake.ingest`, `data_lake.silver`, `data_lake.query` exist because the modules mirror data-lake-pipelines `infra/scripts/data_lake`; no workflow, crontab or task found that runs them from this package (operators run the parent copies) |
| Who schedules it | Nothing in this repo. This WSL host's crontab has no scraper or lake entries (2026-10-22). Consumers' Windows tasks cannot be verified from WSL [ต้องยืนยัน] |
| Hosted deployment | None (library; installed into consumers by commit-pinned tarball) |
| Consumers (pins found 2026-10-22) | career-job-market-data, market-data (crypto, stock, fx, defi), tech-discovery-data, tech-ai-tools-data (product retired 2026-10-23 in data-product-contracts-v3; repository to be archived), marketing-seo-ranking-data, travel-flight-price-data, opportunity-intelligence-data, content-news-scraper; all pinned at `b8f8698` before this change |
| Error reporting | Sentry is an opt-in extra only (`solo-empire-data-lake[sentry]`). The library never initialises Sentry; the job that imports it does, and library exceptions (`LakeIngestError`, `LakeUnavailable`, `StorageError`) propagate to that job's handler. No DSN configured anywhere for this package |
| Contract | Lake-first path from the architecture registry (exact landing bytes + checksum → versioned Bronze manifest → projections), pinned offline by `tests/test_lake_contract.py`; Bronze columns are `data_lake.parquet.BRONZE_COLUMNS`; manifest `manifest_version: "1"` |
| Parity | `src/data_lake` mirrors data-lake-pipelines; `scripts/check_parity.py` (AST) is in parity as of 2026-10-22 |
| Quality gates in CI | ruff, ruff format, mypy (gradual, see pyproject), offline pytest with coverage ≥ 51%, compileall, on Python 3.11 and 3.13; shared security scan |

## Product contract

- Decision or user outcome: every data product lands exact source bytes with lineage the same way, without copying lake code into each repo.
- Consumers: the `book-*-data` producer repositories listed above (Python ≥ 3.11).
- Lake layers: landing (exact bytes) → Bronze Parquet + manifest + checkpoint → Silver (`data_lake.silver` normalizers) → DuckDB reads.
- Storage: `file://`/local paths, or `s3://` (R2) with runtime-injected credentials; never in keys, manifests or logs.
- Compatibility: public module surface is pinned by `tests/test_standalone_parity.py`; consumers pin a commit tarball, never `main`.
- Known bug: `write_lineage` crashes when the lineage file is valid JSON but not an object (pinned as an expected failure in `tests/test_lake_contract.py`; fix goes to the parent first).
