"""Lake-first contract: exact landing bytes + checksum -> versioned Bronze manifest.

The data-product registry (architecture-docs ``data-product-contracts-v2.yaml`` and the
scraping/job contracts) requires every producer to land the exact source bytes, record
their checksum, and write a versioned, immutable Bronze manifest before any projection.
These tests pin that behaviour of the packaged runtime offline (local filesystem lake,
no network, no R2).
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from data_lake.ingest import ingest_payload
from data_lake.parquet import BRONZE_COLUMNS
from data_lake.product_adapter import LakeProductContract, write_lineage
from data_lake.query import query_parquet
from data_lake.storage import ObjectStore

RAW = b'{"items":[{"id":"bitcoin","price":67000.5},{"id":"ethereum","price":3100.25}]}'
RECORDS = [
    {"id": "bitcoin", "price": 67000.5, "event_time": "2026-10-22T00:00:00Z"},
    {"id": "ethereum", "price": 3100.25, "event_time": "2026-10-22T00:00:00Z"},
]


def _ingest(lake: str) -> dict:
    return ingest_payload(
        RAW,
        RECORDS,
        source="book-crypto-data",
        domain="markets",
        dataset="crypto_prices",
        data_lake_uri=lake,
        input_format="json",
        schema_version="crypto.v1",
        event_time_field="event_time",
        privacy_class="public",
    )


class LakeFirstContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.lake = self._tmp.name
        self.store = ObjectStore(self.lake)

    def _manifest(self, result: dict) -> dict:
        loaded: dict = json.loads(self.store.get_bytes(result["manifest_key"]))
        return loaded

    def test_landing_keeps_exact_bytes_and_manifest_records_their_checksum(
        self,
    ) -> None:
        result = _ingest(self.lake)
        self.assertEqual(self.store.get_bytes(result["raw_key"]), RAW)
        manifest = self._manifest(result)
        self.assertEqual(manifest["raw"]["sha256"], hashlib.sha256(RAW).hexdigest())
        self.assertEqual(manifest["raw"]["bytes"], len(RAW))
        self.assertEqual(manifest["raw"]["key"], result["raw_key"])

    def test_manifest_is_versioned_and_describes_the_bronze_object(self) -> None:
        result = _ingest(self.lake)
        manifest = self._manifest(result)
        self.assertEqual(manifest["manifest_version"], "1")
        self.assertEqual(manifest["schema_version"], "crypto.v1")
        self.assertEqual(manifest["record_count"], len(RECORDS))
        bronze_bytes = self.store.get_bytes(result["bronze_key"])
        self.assertEqual(
            manifest["bronze"]["sha256"], hashlib.sha256(bronze_bytes).hexdigest()
        )
        self.assertEqual(manifest["bronze"]["columns"], list(BRONZE_COLUMNS))
        self.assertEqual(manifest["checkpoint_key"], result["checkpoint_key"])

    def test_bronze_rows_carry_landing_lineage_and_fixed_columns(self) -> None:
        result = _ingest(self.lake)
        rows = query_parquet(
            str(Path(self.lake) / result["bronze_key"]), "SELECT * FROM lake_table"
        )
        self.assertEqual(len(rows), len(RECORDS))
        # The Parquet file holds exactly BRONZE_COLUMNS; DuckDB adds the hive partition
        # column (ingest_date=...) from the object key.
        self.assertIn("ingest_date=", result["bronze_key"])
        self.assertEqual(
            [c for c in rows[0] if c != "ingest_date"], list(BRONZE_COLUMNS)
        )
        sha = hashlib.sha256(RAW).hexdigest()
        for row in rows:
            self.assertEqual(row["raw_object_key"], result["raw_key"])
            self.assertEqual(row["raw_sha256"], sha)
            self.assertEqual(row["schema_version"], "crypto.v1")
            self.assertEqual(row["privacy_class"], "public")
        self.assertEqual(
            {row["source_record_id"] for row in rows}, {"bitcoin", "ethereum"}
        )

    def test_retry_of_the_same_batch_is_idempotent_and_keeps_the_manifest(self) -> None:
        first = _ingest(self.lake)
        manifest_bytes = self.store.get_bytes(first["manifest_key"])
        retry = _ingest(self.lake)
        for key in ("raw_key", "bronze_key", "manifest_key"):
            self.assertEqual(retry[key], first[key])
        self.assertTrue(retry["raw_existed"])
        self.assertTrue(retry["manifest_existed"])
        self.assertEqual(self.store.get_bytes(first["manifest_key"]), manifest_bytes)


class LineageFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data_dir = Path(self._tmp.name)
        self.contract = LakeProductContract(
            source="book-crypto-data",
            domain="markets",
            product_schema_version="crypto.v1",
            project_root=self.data_dir,
        )

    def _write(self) -> dict:
        path = write_lineage(
            self.contract,
            {"run_id": "run-1", "record_count": 2, "raw_key": "landing/x"},
            dataset="crypto_prices",
            data_dir=self.data_dir,
        )
        loaded: dict = json.loads(path.read_text(encoding="utf-8"))
        return loaded

    def test_unreadable_lineage_file_is_replaced(self) -> None:
        (self.data_dir / self.contract.lineage_filename).write_text(
            "{not json", encoding="utf-8"
        )
        body = self._write()
        self.assertEqual(body["datasets"]["crypto_prices"]["run_id"], "run-1")

    # Known bug, kept red on purpose: write_lineage calls previous.get() on whatever JSON the
    # file holds, so a lineage file that is valid JSON but not an object (e.g. "[]") raises
    # AttributeError. src/data_lake mirrors data-lake-pipelines (scripts/check_parity.py), and
    # the README procedure fixes shared algorithms in the parent first, then ports them here.
    # Remove expectedFailure when that port lands.
    @unittest.expectedFailure
    def test_lineage_file_holding_a_json_list_is_replaced(self) -> None:
        (self.data_dir / self.contract.lineage_filename).write_text(
            "[]", encoding="utf-8"
        )
        body = self._write()
        self.assertEqual(body["datasets"]["crypto_prices"]["run_id"], "run-1")


if __name__ == "__main__":
    unittest.main()
