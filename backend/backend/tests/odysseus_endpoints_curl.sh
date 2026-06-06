#!/usr/bin/env bash
BASE=${BASE:-http://127.0.0.1:8787}
set -e

echo "GET /api/health"
curl -sS "$BASE/api/health" | jq || true

echo "GET /api/odysseus/status"
curl -sS "$BASE/api/odysseus/status" | jq || true

# Upload a text file
TF=$(mktemp)
echo "hola mundo desde test" > "$TF"
echo "POST /api/upload (text)"
curl -sS -F "file=@$TF" "$BASE/api/upload" | jq || true

# Create and upload zip
ZIPF=$(mktemp --suffix=.zip)
zip -j "$ZIPF" "$TF"
echo "POST /api/upload (zip)"
curl -sS -F "file=@$ZIPF" "$BASE/api/upload" | jq || true

# List files
echo "GET /api/odysseus/files"
curl -sS "$BASE/api/odysseus/files" | jq || true

# Analyze
echo "POST /api/odysseus/analyze"
curl -sS -H 'Content-Type: application/json' -d '{"message":"Analiza este proyecto y busca temas: python, ai"}' "$BASE/api/odysseus/analyze" | jq || true

echo "Done"
