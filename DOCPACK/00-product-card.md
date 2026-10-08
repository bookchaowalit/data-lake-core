---
title: Solo Empire Data Lake Runtime — Product Card
doc_id: CARD-solo-empire-data-lake
doc_type: product-card
verdict: showcase
version: 0.1
date: 2026-10-08
status: ร่างเพื่อพิจารณา
owner: Product owner (Book Dev)
---

# Solo Empire Data Lake Runtime — Product Card

## 1. สรุปคุณค่าในหนึ่งประโยค

แพ็กเกจ Python ที่ให้ primitive กลาง (landing → Bronze Parquet → manifest/lineage → DuckDB) แก่ repo `book-*-data` ทุกตัว เพื่อให้รันแยกจาก Solo Empire monorepo ได้

## 2. ปัญหาและผู้ใช้เป้าหมาย

- data product หลายสิบ repo ต้องใช้ algorithm lake เดียวกันโดยไม่ copy โค้ดไปทุกที่
- ผู้ใช้: repo ข้อมูลของเจ้าของ (`book-crypto-data`, `book-stock-data` และตระกูล intake)

## 3. สิ่งที่ทำได้จริงตอนนี้

- `src/data_lake/`: `storage`, `ingest`, `parquet`, `query`, `silver`, `product_adapter`, `product_store`, `iceberg` (ทางเลือก)
- รองรับ filesystem lake และ `s3://` (R2/S3) ผ่าน DuckDB `httpfs`; credential มาจาก runtime เท่านั้น
- `scripts/check_parity.py` เทียบ AST กับต้นฉบับใน `infra/scripts/data_lake` ของ monorepo; `test_standalone_parity.py` ยืนยันว่ารันได้โดยไม่มี monorepo
- test 5 ไฟล์

## 4. หลักฐานสถานะ

- Stack: Python
- Commits: 11 (แรก 2026-08-08 → ล่าสุด 2026-10-03), branch `main`; working tree สะอาด
- Source: 15 ไฟล์ / 4,619 บรรทัด; test 5 ไฟล์
- CI: 1 workflow
- Deploy config: ไม่มี
- Live URL: ไม่พบใน repo

## 5. คุณค่าและจุดต่าง

- ทำให้ data product ติดตั้งแยกได้ และมีกลไกกัน drift ที่ชัด
- ไม่ใช่ผลิตภัณฑ์ต่อผู้ใช้; ไม่มีมุมรายได้ (มี `LICENSE` จึงอาจเปิดเป็น open source ได้ **[สมมติฐาน]**)

## 6. ช่องว่างสำคัญ

- เป็นสำเนาของโค้ดใน `infra/scripts/data_lake` (canonical) จึงมีต้นทุนซิงก์สองทาง
- ยังไม่มี release tag ที่ repo อื่น pin อยู่ **[ต้องยืนยัน]**

## 7. คำตัดสิน

**showcase** — จำเป็นต่อการแยก data product ออกจาก monorepo และเป็นหลักฐาน platform engineering ที่ดี แต่เป็นไลบรารีสนับสนุน ไม่ใช่ product

ถ้าเลิกแยก data product ออกจาก monorepo ให้เปลี่ยนเป็น `merge` โดย canonical คือ `infra/scripts/data_lake`

## 8. ขั้นต่อไป

1. ออก release tag แรกและให้ repo `book-*-data` pin ตาม tag
2. รัน parity check ใน CI ของ monorepo

## การอนุมัติ

| บทบาท | สถานะ | วันที่ | ลงนาม |
|---|---|---|---|
| Product owner (Book Dev) | รอพิจารณา | — | ________ |

## แหล่งข้อมูล

- `README.md`
- `src/data_lake/`
- `scripts/check_parity.py`
- `tests/test_standalone_parity.py`
