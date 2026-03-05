"""
sftp_deploy.py
--------------
Pushes Waking Cup product schema files to Hostinger via SFTP.

Two deploy targets (one SFTP connection):
  1. Master file:   product-schema.json
                    → /home/u797980862/domains/jeremylamkin.com/public_html/product-schema.json
  2. Per-product:   product_schema/*.json
                    → /home/u797980862/domains/jeremylamkin.com/public_html/product-schema/

Required environment variables (set as GitHub Secrets in production):
    SFTP_HOST      - server hostname or IP
    SFTP_PORT      - SSH port (default 22)
    SFTP_USER      - SSH username
    SFTP_PASSWORD  - password auth (or use SFTP_KEY_PATH for key auth)
    SFTP_KEY_PATH  - path to private key file (optional, preferred over password)
"""

import os
import logging
from pathlib import Path

log = logging.getLogger(__name__)

REMOTE_PUBLIC_HTML = "/home/u797980862/domains/jeremylamkin.com/public_html"
REMOTE_MASTER_FILE = f"{REMOTE_PUBLIC_HTML}/product-schema.json"
REMOTE_SCHEMA_DIR  = f"{REMOTE_PUBLIC_HTML}/product-schema"


def get_sftp_client():
    try:
        import paramiko
    except ImportError:
        raise RuntimeError("paramiko not installed. Run: pip install paramiko")

    host     = os.environ.get("SFTP_HOST")
    port     = int(os.environ.get("SFTP_PORT", 22))
    user     = os.environ.get("SFTP_USER")
    password = os.environ.get("SFTP_PASSWORD")
    key_path = os.environ.get("SFTP_KEY_PATH")

    if not host or not user:
        raise ValueError("SFTP_HOST and SFTP_USER environment variables are required.")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    if key_path and Path(key_path).exists():
        pkey = paramiko.Ed25519Key.from_private_key_file(key_path)
        ssh.connect(host, port=port, username=user, pkey=pkey)
        log.info(f"Connected to {host}:{port} via key auth")
    elif password:
        ssh.connect(host, port=port, username=user, password=password)
        log.info(f"Connected to {host}:{port} via password auth")
    else:
        raise ValueError("Provide either SFTP_KEY_PATH or SFTP_PASSWORD.")

    return ssh.open_sftp(), ssh


def deploy(schema_dir: str, master_file: str = None) -> dict:
    """
    Upload all *.json files from schema_dir to REMOTE_SCHEMA_DIR.
    Optionally upload master_file to REMOTE_MASTER_FILE.
    Returns summary dict.
    """
    schema_dir = Path(schema_dir)
    files = sorted(schema_dir.glob("*.json"))

    if not files:
        log.warning(f"No JSON files found in {schema_dir}")

    sftp, ssh = get_sftp_client()
    summary = {"uploaded": 0, "failed": []}

    try:
        # 1. Master product-schema.json
        if master_file:
            master_path = Path(master_file)
            if master_path.exists():
                try:
                    sftp.put(str(master_path), REMOTE_MASTER_FILE)
                    log.info(f"  Uploaded master: {master_path.name} → {REMOTE_MASTER_FILE}")
                    summary["uploaded"] += 1
                except Exception as e:
                    log.error(f"  Failed master: {e}")
                    summary["failed"].append(master_path.name)
            else:
                log.warning(f"  Master file not found, skipping: {master_path}")

        # 2. Per-product files
        for local_path in files:
            remote_path = f"{REMOTE_SCHEMA_DIR}/{local_path.name}"
            try:
                sftp.put(str(local_path), remote_path)
                log.info(f"  Uploaded: {local_path.name} → {remote_path}")
                summary["uploaded"] += 1
            except Exception as e:
                log.error(f"  Failed: {local_path.name} — {e}")
                summary["failed"].append(local_path.name)

    finally:
        sftp.close()
        ssh.close()

    return summary


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Deploy Waking Cup schema files via SFTP.")
    parser.add_argument("--schema-dir", required=True, help="Local product_schema/ directory")
    parser.add_argument("--master", help="Local path to master product-schema.json (optional)")
    args = parser.parse_args()

    result = deploy(args.schema_dir, master_file=args.master)

    print("\n=== Deploy Summary ===")
    print(f"Uploaded: {result['uploaded']}")
    if result["failed"]:
        print(f"Failed:   {result['failed']}")
