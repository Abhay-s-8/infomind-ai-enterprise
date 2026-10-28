#!/bin/sh
# Container entrypoint: migrate, optional first-run bootstrap, then serve.
#   INITIAL_ADMIN_EMAIL + INITIAL_ADMIN_PASSWORD  create that administrator if it does not exist yet
#   RESET_ADMIN_PASSWORD=true                     also set that existing administrator's password to INITIAL_ADMIN_PASSWORD
#                                                 (use once, then set it back to false)
#   AUTO_TRAIN=true                               train the classifier on synthetic data if none is active
#   AUTO_REINDEX=true                             rebuild the vector index from stored text when it is incomplete
#   SEED_DEMO=true                                add the synthetic demo documents (needs the admin above)
# Hosts such as Render provide $PORT; locally it defaults to 8000.
set -e

# Start as root only long enough to fix ownership of a mounted data directory (hosts such as Render mount
# persistent disks as root), then re-run this script as the unprivileged user. DATA_DIR is optional.
if [ "$(id -u)" = "0" ]; then
  if [ -n "$DATA_DIR" ]; then mkdir -p "$DATA_DIR" && chown -R appuser:appuser "$DATA_DIR"; fi
  exec env HOME=/home/appuser setpriv --reuid=appuser --regid=appuser --init-groups sh "$0" "$@"
fi

alembic upgrade head

if [ -n "$INITIAL_ADMIN_EMAIL" ] && [ -n "$INITIAL_ADMIN_PASSWORD" ]; then
  if [ "$RESET_ADMIN_PASSWORD" = "true" ]; then  # one-shot: set it back to false after the deploy that applies it
    python -m app.cli create-admin --email "$INITIAL_ADMIN_EMAIL" --reset-password
  else
    python -m app.cli create-admin --email "$INITIAL_ADMIN_EMAIL" --if-missing
  fi
fi

# Bootstrap conveniences must never keep the API from starting.
if [ "$AUTO_TRAIN" = "true" ]; then
  python -m app.cli train --if-missing || echo "WARNING: automatic training failed; train from the Classification page."
fi
if [ "$AUTO_REINDEX" = "true" ]; then  # database persists but the vector store is on temporary storage
  python -m app.cli reindex --if-needed || echo "WARNING: vector reindex failed; reprocess documents or restart."
fi
if [ "$SEED_DEMO" = "true" ] && [ -n "$INITIAL_ADMIN_EMAIL" ]; then
  python -m app.cli seed-demo --email "$INITIAL_ADMIN_EMAIL" || echo "WARNING: demo seeding failed."
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
