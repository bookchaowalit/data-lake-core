#!/usr/bin/env python3
"""Detect drift between this packaged runtime and the data-lake runtime copy.

The packaged ``src/data_lake`` modules are a portable copy of the parent
``data-lake-pipelines`` repository's ``infra/scripts/data_lake`` modules. They intentionally differ in
import style (relative imports, no ``sys.path`` bootstrap) and in the few
runtime loaders that must work without a parent checkout. Everything else
should stay identical, so this script compares module ASTs after stripping:

* import statements (and module-level ``try``/``if`` blocks that only import
  or bootstrap ``sys.path``),
* assignments to path-bootstrap names (``ROOT``, ``PROJECT_ROOT``, ...),
* docstrings,

and then compares each top-level function/class and the remaining statements.
Parent-only modules require explicit reasons in ``ALLOWED_PARENT_ONLY``.
Reviewed function boundaries use ``ALLOWED_DIVERGENCE`` or exact normalized
AST hash pairs in ``REVIEWED_BOUNDARY_PAIRS``.

Usage::

    SOLO_DATA_LAKE_ROOT=/path/to/data-lake-pipelines python scripts/check_parity.py
    python scripts/check_parity.py --parent /path/to/data-lake-pipelines

Exit codes: 0 in parity, 1 drift found, 2 parent checkout unavailable
(use ``--allow-missing`` to turn that into 0 for optional CI jobs).
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "src" / "data_lake"
PARENT_SUBDIR = Path("infra") / "scripts" / "data_lake"

BOOTSTRAP_NAMES = frozenset({"ROOT", "PROJECT_ROOT", "SCRIPTS_DIR", "UTILS_DIR"})

# (module, top-level name) -> reason. Keep this list short and reviewed.
ALLOWED_DIVERGENCE: dict[tuple[str, str], str] = {
    ("product_adapter", "_ensure_data_lake_on_path"): (
        "parent-only sys.path bootstrap; the package imports relatively"
    ),
    ("product_adapter", "load_ingest_runtime"): (
        "packaged loader works without a parent checkout"
    ),
    ("product_adapter", "load_query_runtime"): (
        "packaged loader works without a parent checkout"
    ),
    ("product_adapter", "load_iceberg_query_runtime"): (
        "packaged loader works without a parent checkout"
    ),
    ("product_adapter", "landing_object_bytes"): (
        "packaged replay uses ObjectStore directly (pass-1 P0 fix)"
    ),
    ("product_adapter", "_committed_bronze_keys"): (
        "loop variable renamed to avoid shadowing dataclasses.field"
    ),
}


# Parent-only operator modules reviewed from data-lake-pipelines on 2026-10-15.
# Names are explicit: a new parent module requires its own boundary decision.
ALLOWED_PARENT_ONLY: dict[str, str] = {
    "avro": "Optional streaming-lane Avro format; not part of the Bronze/query package.",
    "capture_lock": "Operator capture-runner locking.",
    "cloud_preflight": "Operator cloud-target readiness command.",
    "collection_health": "Operator coverage-audit health reporting.",
    "free_cloud_e2e": "Operator local fixture lab orchestration.",
    "hosted_cloud_e2e": "Operator-gated hosted fixture lab.",
    "hosted_integrations": "Operator hosted-integration readiness report.",
    "hosted_job_api_e2e": "Operator hosted job API smoke check.",
    "iceberg_catalog_e2e": "Operator-gated catalog registration lab.",
    "ingest_discovery_captures": "Discovery-specific replay orchestration.",
    "ingest_job_captures": "Job product replay command adapter.",
    "ingest_scraping_captures": "Cross-product capture replay orchestration.",
    "job_data_readiness": "Job product readiness command.",
    "maintenance": "Operator bounded lake audit/restore command.",
    "multi_engine_lab": "Optional multi-engine query lab orchestration.",
    "product_source_preflight": "Operator checkout availability report.",
    "publish_collection_outputs": "Operator monitor-output delivery adapter.",
    "run_collection_monitor": "Operator coverage and health coordination.",
    "run_data_product_stack": "Operator local API process orchestration.",
    "run_jobs_capture": "Job collector process orchestration.",
    "run_market_capture": "Market collector process orchestration.",
    "run_news_capture": "News collector process orchestration.",
    "run_seo_capture": "SEO collector process orchestration.",
    "scraping_coverage": "Operator requirement/collection coverage audit.",
    "silver_parity_evidence": "Operator product-level fixture evidence runner.",
    "stream_sink": "Optional streaming broker ingestion runner.",
    "windows_scraping_scheduler": "Operator Windows schedule control plane.",
    "workspace": "Operator sibling-product checkout discovery.",
}


def _stable_dump(node: ast.AST) -> str:
    """Canonical AST fields across Python versions (ignoring empty new fields)."""

    def encode(value):
        if isinstance(value, ast.AST):
            fields = {
                name: encode(item)
                for name, item in ast.iter_fields(value)
                if item is not None and item != []
            }
            return [type(value).__name__, fields]
        if isinstance(value, list):
            return [encode(item) for item in value]
        if isinstance(value, bytes):
            return {"bytes": value.hex()}
        if value is Ellipsis:
            return {"constant": "Ellipsis"}
        return value

    return json.dumps(encode(node), sort_keys=True, separators=(",", ":"))


def _fingerprint(definition: str | None) -> str | None:
    return (
        hashlib.sha256(definition.encode()).hexdigest()
        if definition is not None
        else None
    )


# Exact normalized AST pairs, not permission to ignore future changes to a function.
REVIEWED_BOUNDARY_PAIRS: dict[tuple[str, str], tuple[str | None, str | None, str]] = {
    ("product_adapter", "default_data_lake_uri"): (
        "1186920a4e875edee84b813dcebf003b09cca94fae2518a746f8c8a25109fa5e",
        "af820ee7ffafd3817e937e8466182815414007eb2156f828389cd94e6c6400b4",
        "Portable package defaults under the product/cwd; "
        "pipeline adapter may discover its own lake root.",
    ),
    ("product_adapter", "find_lake_runtime_root"): (
        None,
        "0929a43779ac2b6b841824940fb21ef6cd0eb9a72a8dcfe6ac02e405508cce28",
        "Parent-only runtime-root discovery; the installed "
        "package has no parent checkout.",
    ),
    ("product_adapter", "ingest_to_lake"): (
        "5e451090f9202d31d001ff61cce2277d8b07e1fe30930eb6c36db3fabfec1890",
        "8275c71507cd2dcddb1796927d75b41a5a9f9e0cdafbb74c30c09b915629d3e3",
        "Parent loader returns an additional root value; package "
        "loader returns only the three runtime objects.",
    ),
    ("product_adapter", "read_bronze_rows"): (
        "3d219fa73058506facc51f7bee7d0b223dc4e09320737285a6eb3661ea815d28",
        "0b1bd638963221e2c821a958f4c81cb3f944cb23b17fb20f67e666db123944fc",
        "Parent query loader returns an extra unused root value; "
        "package loader omits it.",
    ),
    ("product_adapter", "read_iceberg_rows"): (
        "41a081c542fa82c1c136d363bcf0dd5522b4497e7aa6933811ce4a1c6d06937e",
        "99eada26d2333bd6026f4885058ab3d5176b20f047370349c92d283ff4488e29",
        "Parent Iceberg loader returns an extra unused root value; "
        "package loader omits it.",
    ),
}


def _is_docstring(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _is_import_only(stmts: list[ast.stmt]) -> bool:
    for stmt in stmts:
        if isinstance(stmt, (ast.Import, ast.ImportFrom, ast.Pass)):
            continue
        if _is_bootstrap(stmt):
            continue
        return False
    return True


def _is_bootstrap(node: ast.stmt) -> bool:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return True
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        return all(isinstance(t, ast.Name) and t.id in BOOTSTRAP_NAMES for t in targets)
    if isinstance(node, ast.Expr) and "sys.path" in ast.unparse(node):
        return True
    if isinstance(node, ast.If):
        test = ast.unparse(node.test)
        if "sys.path" in test or "__package__" in test:
            return _is_import_only(node.body) and _is_import_only(node.orelse)
    if isinstance(node, ast.Try):
        handlers = [h.body for h in node.handlers]
        return _is_import_only(node.body) and all(_is_import_only(b) for b in handlers)
    return False


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)
        ):
            body = node.body
            if body and _is_docstring(body[0]):
                node.body = body[1:] or [ast.Pass()]
    return tree


def _normalize(source: str) -> tuple[dict[str, str], list[str]]:
    """Return ({top-level def name: dump}, [other statement dumps])."""
    tree = ast.parse(source)
    _strip_docstrings(tree)  # strips in place
    defs: dict[str, str] = {}
    other: list[str] = []
    for node in tree.body:
        if _is_bootstrap(node):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs[node.name] = _stable_dump(node)
        else:
            other.append(_stable_dump(node))
    return defs, other


def compare_module(name: str, packaged: str, parent: str) -> list[str]:
    """Return human-readable drift findings for one module."""
    pkg_defs, pkg_other = _normalize(packaged)
    par_defs, par_other = _normalize(parent)
    findings: list[str] = []
    reviewed_names = {
        definition for module, definition in REVIEWED_BOUNDARY_PAIRS if module == name
    }
    for def_name in sorted(set(pkg_defs) | set(par_defs) | reviewed_names):
        key = (name, def_name)
        if key in ALLOWED_DIVERGENCE:
            continue
        reviewed = REVIEWED_BOUNDARY_PAIRS.get(key)
        if (
            reviewed
            and reviewed[2]
            and (
                _fingerprint(pkg_defs.get(def_name)),
                _fingerprint(par_defs.get(def_name)),
            )
            == reviewed[:2]
        ):
            continue
        if def_name not in pkg_defs and def_name not in par_defs:
            findings.append(
                f"{name}.{def_name}: reviewed boundary definition missing from both runtimes"
            )
        elif def_name not in par_defs:
            findings.append(f"{name}.{def_name}: only in packaged runtime")
        elif def_name not in pkg_defs:
            findings.append(f"{name}.{def_name}: only in parent (missing from package)")
        elif pkg_defs[def_name] != par_defs[def_name]:
            findings.append(f"{name}.{def_name}: implementation differs")
    if pkg_other != par_other:
        findings.append(f"{name}: module-level statements differ")
    return findings


def find_parent(explicit: str | None) -> Path | None:
    candidate = explicit or os.environ.get("SOLO_DATA_LAKE_ROOT", "")
    if not candidate:
        return None
    parent = Path(candidate).expanduser().resolve() / PARENT_SUBDIR
    return parent if parent.is_dir() else None


def check(package_dir: Path, parent_dir: Path) -> list[str]:
    findings: list[str] = []
    package_modules = {path.stem for path in package_dir.glob("*.py")}
    parent_modules = {path.stem for path in parent_dir.glob("*.py")}
    for name in sorted(parent_modules - package_modules):
        if not ALLOWED_PARENT_ONLY.get(name):
            findings.append(
                f"{name}: only in parent (missing from package; no reviewed reason)"
            )
    for name in sorted(package_modules & ALLOWED_PARENT_ONLY.keys()):
        findings.append(
            f"{name}: now packaged; remove its parent-only exception after review"
        )
    for module_path in sorted(package_dir.glob("*.py")):
        parent_path = parent_dir / module_path.name
        name = module_path.stem
        if not parent_path.is_file():
            findings.append(f"{name}: missing from parent {parent_dir}")
            continue
        findings.extend(
            compare_module(
                name,
                module_path.read_text(encoding="utf-8"),
                parent_path.read_text(encoding="utf-8"),
            )
        )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--parent", help="data-lake checkout (default: $SOLO_DATA_LAKE_ROOT)"
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="exit 0 when no parent checkout is available",
    )
    args = parser.parse_args(argv)
    parent_dir = find_parent(args.parent)
    if parent_dir is None:
        print(
            f"parity: parent checkout not found (set SOLO_DATA_LAKE_ROOT or --parent; "
            f"expected <root>/{PARENT_SUBDIR.as_posix()})",
            file=sys.stderr,
        )
        return 0 if args.allow_missing else 2
    findings = check(PACKAGE_DIR, parent_dir)
    if findings:
        print(f"parity: {len(findings)} drift finding(s) vs {parent_dir}")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    print(f"parity: ok ({len(list(PACKAGE_DIR.glob('*.py')))} modules vs {parent_dir})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
