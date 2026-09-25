#!/bin/sh
set -e

# Only the web container runs migrations; the worker just waits for the DB.
if [ "$RUN_MIGRATIONS" = "1" ]; then
  python manage.py migrate --noinput
  python manage.py ensure_bucket
  if [ "$SEED_DATA" = "1" ]; then
    python manage.py seed_data
  fi
fi

exec "$@"
