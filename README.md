# Lazada review schema updater

Automated review schema pipeline for Lazada reviews on [Waking Cup](https://wakingcup.com). Fetches marketplace reviews via API, updates per-product JSON-LD schema files, and deploys them to the production server via SFTP.

---

## What it does

1. **API Import** — fetches new reviews from marketplace APIs and merges them into per-product JSON-LD files, with deduplication
2. **Aggregate Ratings** — recomputes `aggregateRating` for each product from live review data
3. **Rebuild Master Schema** — consolidates per-product files into a single `product-schema.json`
4. **SFTP Deploy** — pushes updated files to Hostinger via key-authenticated SFTP

Runs daily via cron. Can also be triggered manually or in backfill mode.

---

## Stack

- Python 3.12
- `paramiko` for SFTP deployment
- WooCommerce on Hostinger (deploy target)
- Custom JSON-LD schema system (not WooCommerce native reviews)

---

## Directory structure

```
/home/wcpipeline/
├── pipeline.py           # Orchestrator — runs all four steps in sequence
├── api_importer.py       # Review fetch and merge (not included in public repo)
├── sftp_deploy.py        # SFTP deploy via paramiko
├── .env                  # Credentials and config (never committed)
├── product_schema/       # Per-product JSON-LD files (one per SKU)
├── backups/              # Rolling backups of product_schema/ (last 7 runs)
└── logs/
    └── pipeline.log      # Cron output
```

---

## Setup

### 1. VPS user and directories

```bash
sudo useradd -m -s /bin/bash wcpipeline
sudo mkdir -p /home/wcpipeline/{product_schema,backups,logs}
sudo chown -R wcpipeline:wcpipeline /home/wcpipeline
```

### 2. Python environment

```bash
sudo su wcpipeline
cd /home/wcpipeline
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install paramiko
```

### 3. Environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
nano .env
```

### 4. SFTP key auth (recommended over password)

Generate a key pair on the VPS:

```bash
ssh-keygen -t ed25519 -f /home/wcpipeline/.ssh/hostinger_key -N ""
```

Add the contents of `hostinger_key.pub` to your Hostinger SSH Keys panel, then set `SFTP_KEY_PATH` in `.env`.

### 5. Deploy pipeline files

```bash
scp pipeline.py sftp_deploy.py your_user@YOUR_VPS_IP:/home/wcpipeline/
scp -r product_schema/ your_user@YOUR_VPS_IP:/home/wcpipeline/
```

---

## Running

```bash
# Standard run
cd /home/wcpipeline && venv/bin/python pipeline.py

# Dry run (no files written, no upload)
DRY_RUN=true venv/bin/python pipeline.py

# Backfill from a date
BACKFILL_SINCE=2025-01-01 venv/bin/python pipeline.py

# Skip deploy (import and rebuild only)
SKIP_DEPLOY=true venv/bin/python pipeline.py
```

---

## Cron

Runs daily at 09:00 Bangkok time (02:00 UTC):

```
33 3 * * * cd /home/wcpipeline && venv/bin/python pipeline.py >> /home/wcpipeline/logs/pipeline.log 2>&1
```

---

## Environment variables

See `.env.example` for the full list. Required variables:

| Variable | Description |
|---|---|
| `LAZADA_APP_KEY` | Lazada Open Platform app key |
| `LAZADA_APP_SECRET` | Lazada Open Platform app secret |
| `LAZADA_ACCESS_TOKEN` | Lazada seller access token |
| `SFTP_HOST` | Hostinger server IP |
| `SFTP_PORT` | SSH port (Hostinger default: 65002) |
| `SFTP_USER` | Hostinger SSH username |
| `SFTP_KEY_PATH` | Path to private key file |

---

## Note on api_importer.py

The review import module is not included in this repository. It handles authenticated API calls to marketplace review endpoints and is kept private. The stub included here documents its interface — `run_import()` — which `pipeline.py` calls directly.

If you are adapting this pipeline for your own use, you will need to implement your own importer that returns:

```python
{
    "processed": int,   # number of products processed
    "new_reviews": int, # number of new reviews added
    "skipped": list     # product IDs that failed or were skipped
}
```

---

## License

Private. Not licensed for reuse.
