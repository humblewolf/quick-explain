#!/usr/bin/env bash
set -e

APP_DIR="/home/humblewolf/work/tool/quick-explain"

cd "$APP_DIR"

exec "$APP_DIR/.venv/bin/python" "$APP_DIR/app.py"
