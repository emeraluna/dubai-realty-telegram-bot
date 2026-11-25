#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 --version >/dev/null
python3 scripts/bootstrap_local.py
echo ""
echo "Next: edit .env (TELEGRAM_BOT_TOKEN, optional Apify/DLD tokens), then:"
echo "  python3 -m bot.main"
echo "  python3 -m cli resolve-owner '<PF URL>'"