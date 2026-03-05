"""
pipeline.py
-----------
Orchestrates the full Waking Cup review schema pipeline.

Steps:
  1. api_importer   — fetch new Lazada reviews via API, merge into per-product JSON files
  2. aggregate_ratings — recompute aggregateRating for all products
  3. rebuild_master    — rebuild product-schema.json from per-product files
  4. sftp_deploy       — push updated JSON files to Hostinger via SFTP

Designed to run via cron on the InterServer VPS.
Can also be run manually with a .env file in the same directory.

Manual run:
    python pipeline.py

Dry run (no files written, no upload):
    DRY_RUN=true python pipeline.py

Backfill from a date:
    BACKFILL_SINCE=2025-02-28 python pipeline.py
"""

import os
import sys
import json
import logging
import shutil
from pathlib import Path
from datetime import datetime, timezone
from collections import OrderedDict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def load_env(env_file=".env"):
    env_path = Path(__file__).parent / env_file
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

load_env()


# ── Config ────────────────────────────────────────────────────────────────────
REPO_ROOT   = Path(__file__).parent
BASE_DIR    = Path(os.environ.get("BASE_DIR",    REPO_ROOT))
SCHEMA_DIR  = Path(os.environ.get("SCHEMA_DIR",  BASE_DIR / "product_schema"))
BACKUP_DIR  = Path(os.environ.get("BACKUP_DIR",  BASE_DIR / "backups"))

SKIP_DEPLOY     = os.environ.get("SKIP_DEPLOY",     "false").lower() == "true"
DRY_RUN         = os.environ.get("DRY_RUN",         "false").lower() == "true"
BACKFILL_SINCE  = os.environ.get("BACKFILL_SINCE",  "")      # e.g. "2025-02-28"


# ── Step 1: API Import ────────────────────────────────────────────────────────
def step_import():
    from api_importer import run_import
    log.info("── Step 1: API Import ──")

    since_date = None
    if BACKFILL_SINCE:
        since_date = datetime.strptime(BACKFILL_SINCE, "%Y-%m-%d")
        log.info(f"Backfill mode: fetching since {BACKFILL_SINCE}")

    result = run_import(
        schema_dir = str(SCHEMA_DIR),
        dry_run    = DRY_RUN,
        since_date = since_date,
    )
    log.info(
        f"Import complete: {result['processed']} products, "
        f"{result['new_reviews']} new reviews"
    )
    if result.get("skipped"):
        log.warning(f"Skipped products: {result['skipped']}")
    return result


# ── Step 2: Aggregate Ratings ─────────────────────────────────────────────────
def step_aggregate_ratings():
    log.info("── Step 2: Aggregate Ratings ──")

    def _to_number(x):
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, str):
            try:
                return float(x.replace(",", ""))
            except ValueError:
                return None
        return None

    updated = 0
    for json_file in sorted(SCHEMA_DIR.glob("*.json")):
        with open(json_file, "r", encoding="utf-8") as f:
            product = json.load(f)

        reviews = product.get("reviews", [])
        ratings = [
            rv for rv in (
                _to_number(r.get("reviewRating"))
                for r in reviews if isinstance(r, dict)
            ) if rv is not None
        ]

        if not ratings:
            continue

        avg     = round(sum(ratings) / len(ratings), 2)
        new_agg = {
            "@type":       "AggregateRating",
            "ratingValue": avg,
            "reviewCount": len(ratings),
        }

        new_product = OrderedDict()
        for k, v in product.items():
            if k == "aggregateRating":
                continue
            if k == "reviews":
                new_product["aggregateRating"] = new_agg
                new_product[k] = v
            else:
                new_product[k] = v

        if not DRY_RUN:
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(new_product, f, ensure_ascii=False, indent=4)
        updated += 1

    log.info(f"Ratings recomputed for {updated} products")
    return updated


# ── Step 3: Rebuild master product-schema.json ────────────────────────────────
def step_rebuild_master():
    log.info("── Step 3: Rebuild Master Schema ──")

    output_file = BASE_DIR / "product-schema.json"
    products    = []

    for json_file in sorted(SCHEMA_DIR.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("@type") == "Product":
                products.append(data)
        except Exception as e:
            log.warning(f"  Skipped {json_file.name}: {e}")

    if not products:
        log.warning("  No product files found — master schema not written")
        return 0

    if not DRY_RUN:
        output_file.write_text(
            json.dumps(products, ensure_ascii=False, indent=4),
            encoding="utf-8"
        )
        log.info(f"  Wrote {len(products)} products → {output_file.name}")
    else:
        log.info(f"  DRY RUN — would write {len(products)} products → {output_file.name}")

    return len(products)


# ── Step 4: SFTP Deploy ───────────────────────────────────────────────────────
def step_deploy():
    if SKIP_DEPLOY:
        log.info("── Step 4: Deploy SKIPPED (SKIP_DEPLOY=true) ──")
        return {"uploaded": 0, "failed": []}

    log.info("── Step 4: SFTP Deploy ──")

    if DRY_RUN:
        log.info("  DRY RUN — skipping upload")
        return {"uploaded": 0, "failed": []}

    from sftp_deploy import deploy
    master_file = BASE_DIR / "product-schema.json"
    result = deploy(
        str(SCHEMA_DIR),
        master_file=str(master_file) if master_file.exists() else None
    )
    log.info(f"  Deploy complete: {result['uploaded']} files uploaded")
    if result["failed"]:
        log.warning(f"  Failed: {result['failed']}")
    return result


# ── Backup ────────────────────────────────────────────────────────────────────
def backup_schema_dir():
    if DRY_RUN:
        return
    ts          = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"product_schema_{ts}"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(SCHEMA_DIR), str(backup_path))
    log.info(f"Backup → {backup_path}")
    # Keep last 7
    for old in sorted(BACKUP_DIR.glob("product_schema_*"))[:-7]:
        shutil.rmtree(str(old))


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    log.info("═══ Waking Cup Pipeline Start ═══")
    if DRY_RUN:
        log.info("MODE: DRY RUN")
    if BACKFILL_SINCE:
        log.info(f"MODE: BACKFILL since {BACKFILL_SINCE}")

    if not SCHEMA_DIR.exists():
        log.error(f"SCHEMA_DIR not found: {SCHEMA_DIR}. Aborting.")
        sys.exit(1)

    backup_schema_dir()

    import_result   = step_import()
    ratings_updated = step_aggregate_ratings()
    master_count    = step_rebuild_master()
    deploy_result   = step_deploy()

    log.info("═══ Pipeline Complete ═══")
    log.info(f"  New reviews added : {import_result.get('new_reviews', 0)}")
    log.info(f"  Products updated  : {ratings_updated}")
    log.info(f"  Master schema     : {master_count} products")
    log.info(f"  Files deployed    : {deploy_result.get('uploaded', 0)}")


if __name__ == "__main__":
    main()
