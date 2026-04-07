#!/bin/bash
# Refreshes Qwen OAuth token and restarts qwen-code-api
# Run this via cron every 5 hours (before the 6-hour token expires)
# Example: 0 */5 * * * /root/LabAssist/scripts/refresh-qwen-oauth.sh >> /var/log/qwen-oauth-refresh.log 2>&1

set -e

echo "[$(date)] Starting Qwen OAuth refresh..."

# Re-authenticate with Qwen (updates ~/.qwen/oauth_creds.json)
qwen auth qwen-oauth
echo "[$(date)] OAuth authentication successful"

# Restart qwen-code-api to pick up new credentials
docker restart qwen-code-api-qwen-code-api-1
sleep 5

# Reconnect to LabAssist network (lost on restart)
docker network connect labassist_default qwen-code-api-qwen-code-api-1 2>/dev/null || true

# Verify it's working
RESPONSE=$(curl -s http://localhost:42005/health)
echo "[$(date)] Health check: $RESPONSE"

echo "[$(date)] Qwen OAuth refresh complete"
