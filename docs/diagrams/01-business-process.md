# 01 — Business process (As-Is / To-Be)

data-lake-core (`solo-empire-data-lake`) คือ Python library สาธารณะที่ repo ข้อมูล `book-*-data` ติดตั้งแบบ pin commit เพื่อเก็บข้อมูลต้นทางแบบ lake-first เหมือนกันทุกตัว: เก็บ bytes ต้นทางตรงตัว + SHA-256 → Bronze Parquet → manifest และ lineage → Silver → อ่านด้วย DuckDB ไม่มี API, scraper, credentials หรือ scheduler ของตัวเอง

Last reviewed: 2026-11-28 · commit `cf04838`

## As-Is (จากโค้ดวันนี้)

```mermaid
flowchart TD
  CONS["consumer job ใน repo book-*-data (pin commit tarball)"] --> ADAPT["product_adapter.ingest_to_lake + LakeProductContract"]
  ADAPT --> ING["ingest.ingest_payload / ingest_records"]
  ING --> READ["อ่าน payload JSON / NDJSON / CSV (utf-8-sig, แยกบรรทัดด้วย CR/LF)"]
  READ --> LAND["landing: bytes ตรงตัว + SHA-256 + size"]
  LAND --> STORE{"DATA_LAKE_URI"}
  STORE -->|"file:// / local"| LOCAL["ObjectStore ในเครื่อง (put_bytes idempotent)"]
  STORE -->|"s3:// (R2)"| S3["storage.py: AWS CLI subprocess, credentials จาก runtime"]
  LOCAL --> BRONZE["parquet.write_bronze_parquet: BRONZE_COLUMNS + raw_object_key / raw_sha256"]
  S3 --> BRONZE
  BRONZE --> MAN["batch manifest version 1 (ไม่เขียนทับเมื่อ retry batch เดิม)"]
  MAN --> LIN["write_lineage"]
  MAN -.->|"ไม่บังคับ"| ICE["iceberg.register_bronze_file (catalog path ที่ระบุชัด)"]
  BRONZE --> SILVER["silver.transform_bronze_to_silver: NORMALIZERS (job, crypto, stock, fx, ohlcv, funding)"]
  BRONZE --> QUERY["query.query_parquet ผ่าน DuckDB (httpfs สำหรับ s3)"]
  SILVER --> PSTORE["product_store.load_layered_dataset: อ่าน Silver หรือ Bronze ให้ product API"]
  QUERY --> PSTORE
  ICE --> QICE["query.query_iceberg / read_iceberg_rows"]
  PARENT["data-lake-pipelines infra/scripts/data_lake (ต้นฉบับ)"] -.->|"scripts/check_parity.py (AST, รันในเครื่อง)"| ING
```

Sources: `src/data_lake/product_adapter.py` (`ingest_to_lake`, `write_lineage`, `read_bronze_rows`, `read_iceberg_rows`), `src/data_lake/ingest.py`, `src/data_lake/storage.py`, `src/data_lake/parquet.py`, `src/data_lake/silver.py`, `src/data_lake/query.py`, `src/data_lake/iceberg.py`, `src/data_lake/product_store.py`, `scripts/check_parity.py`, `README.md`, `PRODUCT.md`

ข้อเท็จจริงสำคัญจากโค้ด:

- ไม่มี `[project.scripts]`, workflow หรือ cron ใน repo นี้ที่รัน module CLI; ผู้ที่ schedule คือ consumer (Windows tasks ของ consumer [ต้องยืนยัน] ตาม `PRODUCT.md`)
- consumer ที่ pin ไว้ (2026-10-22) ทั้งหมดอยู่ที่ `b8f8698`; สอง product ถูก retire 2026-10-23 รอ archive
- `write_lineage` crash เมื่อไฟล์ lineage เป็น JSON ที่ไม่ใช่ object (pin เป็น `expectedFailure` ใน `tests/test_lake_contract.py`)
- `ingest.py` ยังลอง `from _env import PROJECT_ROOT` ก่อน fallback เป็น path ของ package

## To-Be (docs/UPGRADE-PLAN.md §Backlog; specs/001-l2-baseline/spec.md, status: in review)

To-Be ที่เขียนไว้เป็นงานปรับปรุงกระบวนการเดิม ไม่ใช่กระบวนการใหม่:

```mermaid
flowchart TD
  CONS["consumer job ใน book-*-data: extra [lake] pin commit ใหม่ที่มี fix pass 3"] --> ADAPT["product_adapter.ingest_to_lake"]
  CONS --> CTEST["lake tests ของ consumer รันแบบ standalone (import check แทน skipUnless)"]
  ADAPT --> ING["ingest: ไม่มี hidden _env parent dependency (env/arg ชัดเจน)"]
  ING --> LAND["landing + Bronze + manifest (เหมือนเดิม)"]
  LAND --> S3["S3 write path มี offline tests (mock AWS CLI, ไม่มี credential ใน argv/log)"]
  LAND --> LIN["write_lineage แทนที่ lineage ที่เป็น JSON list ได้ (AC-06)"]
  PARENT["data-lake-pipelines"] -->|"check_parity.py รันใน CI"| ING
```

Sources: `docs/UPGRADE-PLAN.md` §Backlog P1–P2, `specs/001-l2-baseline/spec.md` (Behaviour, Acceptance AC-06 ถึง AC-09)

## Gap

| ID | As-Is → To-Be | Status | Owner | Evidence |
|---|---|---|---|---|
| G1 | consumer ใช้ `skipUnless` ตาม parent checkout → extra `[lake]` ที่ pin + import check, รัน standalone | todo | claude | `docs/UPGRADE-PLAN.md` §Backlog P1 |
| G2 | parity check รันในเครื่องเท่านั้น → รันใน CI (ต้องมี read token ของ parent repo) | blocked | owner | `docs/UPGRADE-PLAN.md` §Backlog P1; `.github/workflows/ci.yml` |
| G3 | S3 write path (AWS CLI) ไม่มี offline test → mock subprocess และยืนยันไม่มี credential ใน argv/log | todo | claude | `docs/UPGRADE-PLAN.md` §Backlog P1; `src/data_lake/storage.py` |
| G4 | consumer pin `b8f8698` → bump pin ให้ได้ fix pass 3 | todo | claude | `docs/UPGRADE-PLAN.md` §Backlog P1; `PRODUCT.md` §Runtime status |
| G5 | `ingest.py` ลอง `from _env import PROJECT_ROOT` → env/arg ที่ชัดเจน | todo | claude | `docs/UPGRADE-PLAN.md` §Backlog P2; `src/data_lake/ingest.py` |
| G6 | ไม่มี type check → mypy (gradual) ใน CI | done | claude | `specs/001-l2-baseline/spec.md` Behaviour 2; `.github/workflows/ci.yml` |
| G7 | `write_lineage` crash เมื่อ lineage เป็น JSON list → แทนที่ไฟล์ได้ (fix ที่ parent ก่อนแล้ว port) | todo | claude | `specs/001-l2-baseline/spec.md` AC-06; `tests/test_lake_contract.py` `expectedFailure` |
| G8 | SPEC-001 status in review, checker/approver pending → owner อนุมัติ | decide | owner | `specs/001-l2-baseline/spec.md` Document control |
| G9 | repo ของ product ที่ retire (tech-ai-tools-data, travel-flight-price-data) ยัง pin อยู่ → archive | todo | owner | `PRODUCT.md` §Runtime status (Consumers) |

## Open questions

- ผล live parity กับ `data-lake-pipelines` ณ commit นี้ [ต้องยืนยัน] (ตรวจล่าสุด 2026-10-22, ไม่ได้รันในการรีวิวนี้)
- consumer ตัวไหน bump pin ไปแล้วหลัง 2026-10-22 [ต้องยืนยัน]
