#!/bin/sh
set -eu

# Blueprints expose the Render Postgres URL as a standard postgresql:// URL.
# The application uses SQLAlchemy's async driver, so normalize it once here.
if [ -n "${DATABASE_CONNECTION_STRING:-}" ]; then
  DB_ASYNC_URL=$(printf "%s" "$DATABASE_CONNECTION_STRING" | sed 's|^postgresql://|postgresql+asyncpg://|')
  export DATABASE_URL="$DB_ASYNC_URL"
  export COMPLIANCE_DATABASE_URL="$DB_ASYNC_URL"
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
