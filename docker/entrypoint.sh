#!/bin/sh
# Container entrypoint: apply database migrations, then serve.
# The server writes to deployment_config and reads casbin_rule during startup,
# so the schema must exist before uvicorn accepts its first request.
set -eu

echo "hivemind: applying database migrations (alembic upgrade head)"
alembic upgrade head

echo "hivemind: starting uvicorn on 0.0.0.0:8000"
exec uvicorn hivemind.server.main:app --host 0.0.0.0 --port 8000 "$@"
