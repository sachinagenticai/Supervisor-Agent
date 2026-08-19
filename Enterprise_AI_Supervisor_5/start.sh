#!/usr/bin/env sh
set -eu

PORT_VALUE="${PORT:-8501}"

exec streamlit run app.py \
  --server.address=0.0.0.0 \
  --server.port="$PORT_VALUE" \
  --server.headless=true \
  --browser.gatherUsageStats=false
