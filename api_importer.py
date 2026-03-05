"""
api_importer.py
---------------
Review import module — not included in public repository.

Fetches reviews from marketplace APIs and merges them into per-product
JSON-LD schema files in SCHEMA_DIR.

Interface used by pipeline.py:

    from api_importer import run_import

    result = run_import(
        schema_dir = str(SCHEMA_DIR),
        dry_run    = False,
        since_date = None,       # datetime object or None for daily mode
        product_id = None,       # string or None to process all products
    )

    # result shape:
    # {
    #     "processed":   int,   # number of products processed
    #     "new_reviews": int,   # number of new reviews added across all products
    #     "skipped":     list,  # product IDs that failed or were skipped
    # }

This module is kept private. To adapt this pipeline for your own use,
implement run_import() with the interface above and place it in this file.
"""


def run_import(schema_dir, dry_run=False, since_date=None, product_id=None):
    raise NotImplementedError("API importer not included in public release.")
