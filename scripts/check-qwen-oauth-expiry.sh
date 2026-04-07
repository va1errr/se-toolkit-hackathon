#!/bin/bash
# Monitors Qwen OAuth token expiry and notifies when it's about to expire
# Run this via cron every 30 minutes

EXPIRY_MS=$(python3 -c "import json; print(json.load(open('/root/.qwen/oauth_creds.json'))['expiry_date'])")
EXPIRY_S=$((EXPIRY_MS / 1000))
NOW=$(date +%s)
REMAINING=$((EXPIRY_S - NOW))
REMAINING_MIN=$((REMAINING / 60))

if [ "$REMAINING" -le 1800 ] && [ "$REMAINING" -gt 0 ]; then
    echo "[$(date)] ⚠️  Qwen OAuth token expires in ${REMAINING_MIN} minutes. Run: qwen auth qwen-oauth && docker restart qwen-code-api-qwen-code-api-1 && docker network connect labassist_default qwen-code-api-qwen-code-api-1 2>/dev/null || true"
elif [ "$REMAINING" -le 0 ]; then
    echo "[$(date)] 🚨 Qwen OAuth token EXPIRED. Run: qwen auth qwen-oauth && docker restart qwen-code-api-qwen-code-api-1 && docker network connect labassist_default qwen-code-api-qwen-code-api-1 2>/dev/null || true"
fi
