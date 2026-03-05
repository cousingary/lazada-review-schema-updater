#!/bin/bash
# setup_vps.sh
# One-time setup for the Waking Cup pipeline on a fresh Ubuntu VPS (InterServer).
# Run as root or with sudo.
#
# Usage:
#   chmod +x setup_vps.sh
#   sudo ./setup_vps.sh

set -e

PROJECT_DIR="/home/wcpipeline"
VENV_DIR="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"
BACKUP_DIR="$PROJECT_DIR/backups"
SCHEMA_DIR="$PROJECT_DIR/product_schema"
INPUT_DIR="$PROJECT_DIR/input"

echo "=== Waking Cup Pipeline — VPS Setup ==="

# ── 1. System dependencies ────────────────────────────────────────────────────
echo "[1] Installing system packages..."
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv

# ── 2. Project user (optional hardening — skip if running as your own user) ───
# Uncomment if you want a dedicated service user:
# id -u wcpipeline &>/dev/null || useradd -m -s /bin/bash wcpipeline

# ── 3. Directory structure ────────────────────────────────────────────────────
echo "[2] Creating directories..."
mkdir -p "$PROJECT_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$BACKUP_DIR"
mkdir -p "$SCHEMA_DIR"
mkdir -p "$INPUT_DIR"

# ── 4. Python virtual environment ─────────────────────────────────────────────
echo "[3] Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet paramiko

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Copy pipeline files to $PROJECT_DIR:"
echo "     scp pipeline.py api_importer.py sftp_deploy.py requirements.txt root@YOUR_VPS_IP:$PROJECT_DIR/"
echo ""
echo "  2. Copy your product_schema/ JSON files:"
echo "     scp -r product_schema/ root@YOUR_VPS_IP:$PROJECT_DIR/"
echo ""
echo "  3. Create the .env file:"
echo "     nano $PROJECT_DIR/.env"
echo "     (see .env.example for required variables)"
echo ""
echo "  4. Test the pipeline:"
echo "     cd $PROJECT_DIR && DRY_RUN=true $VENV_DIR/bin/python pipeline.py"
echo ""
echo "  5. Run the backfill:"
echo "     cd $PROJECT_DIR && BACKFILL_SINCE=2025-02-28 $VENV_DIR/bin/python pipeline.py"
echo ""
echo "  6. Install the cron job:"
echo "     crontab -e"
echo "     Add this line (runs daily at 9am Bangkok time = 2am UTC):"
echo "     0 2 * * * cd $PROJECT_DIR && $VENV_DIR/bin/python pipeline.py >> $LOG_DIR/pipeline.log 2>&1"
