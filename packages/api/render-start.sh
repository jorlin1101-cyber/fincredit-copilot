#!/bin/sh
set -eu

# Share the same libpq URL (including its TLS settings) across API and migrations.
if [ -n "${DATABASE_CONNECTION_STRING:-}" ]; then
  export DATABASE_URL="$DATABASE_CONNECTION_STRING"
  export COMPLIANCE_DATABASE_URL="$DATABASE_CONNECTION_STRING"
fi

if [ -n "${S3_HOSTPORT:-}" ]; then
  export S3_ENDPOINT="http://$S3_HOSTPORT"
fi

if [ -n "${MCP_HOSTPORT:-}" ]; then
  export MCP_RISK_SERVER_URL="http://$MCP_HOSTPORT/mcp"
fi

cd /app/packages/db
alembic upgrade head

cd /app/packages/api
exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-10000}"
