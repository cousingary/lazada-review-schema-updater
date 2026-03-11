"""
memory_logger.py
----------------
Logs Waking Cup pipeline run summaries to the Second Brain (Supabase memories table).
Gives the Second Brain awareness of this pipeline's activity without ingesting product schema data.

Requires in .env:
  SUPABASE_URL
  SUPABASE_SERVICE_KEY
  OPENAI_API_KEY
"""

import hashlib
import logging
import os
from datetime import datetime, timezone

log = logging.getLogger(__name__)

EMBED_MODEL = "text-embedding-3-small"


def log_run(new_reviews: int, products_updated: int, files_deployed: int,
            skipped: list = None, dry_run: bool = False):
    """
    Embed and store a pipeline run summary in the Second Brain memories table.
    Silently skips if SUPABASE_URL / OPENAI_API_KEY are not set.
    """
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("OPENAI_API_KEY"):
        log.debug("Second Brain env vars not set — skipping memory log")
        return

    try:
        import openai
        from supabase import create_client

        openai_client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        supabase      = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

        now      = datetime.now(tz=timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M UTC")
        status   = "DRY RUN" if dry_run else "completed"
        skipped_note = (
            f" ({len(skipped)} products skipped: {', '.join(str(s) for s in skipped[:5])})"
            if skipped else ""
        )

        content = (
            f"[Waking Cup — Lazada Review Pipeline — {date_str}]\n"
            f"Run {status} at {time_str}.\n"
            f"New reviews ingested: {new_reviews}. "
            f"Products with updated ratings: {products_updated}. "
            f"Schema files deployed to Hostinger: {files_deployed}.{skipped_note}\n\n"
            f"Pipeline: fetches Lazada marketplace reviews via API → merges into per-product "
            f"JSON-LD schema files → recomputes aggregateRating → deploys to wakingcup.com "
            f"(Hostinger/WooCommerce) via SFTP. Runs daily at 10:33 Bangkok time. "
            f"Managed by Jeremy for Waking Cup (coffee brand, Thailand)."
        )

        embedding   = openai_client.embeddings.create(input=content, model=EMBED_MODEL).data[0].embedding
        chunk_group = hashlib.md5(f"pipeline:lazada-review-schema-updater:{date_str}".encode()).hexdigest()

        supabase.table("memories").insert({
            "content":     content,
            "embedding":   embedding,
            "source":      "pipeline:lazada-review-schema-updater",
            "project":     "waking-cup",
            "memory_type": "pipeline_run",
            "metadata": {
                "new_reviews":      new_reviews,
                "products_updated": products_updated,
                "files_deployed":   files_deployed,
                "skipped_count":    len(skipped) if skipped else 0,
                "dry_run":          dry_run,
            },
            "source_date": now.isoformat(),
            "chunk_group": chunk_group,
            "created_at":  now.isoformat(),
        }).execute()

        log.info(
            f"Second Brain: run logged "
            f"({new_reviews} new reviews, {products_updated} products updated)"
        )

    except Exception as e:
        log.warning(f"Second Brain logging failed (non-fatal): {e}")
