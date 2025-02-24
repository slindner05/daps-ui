#!/bin/sh

PUID=${PUID:-1000}
PGID=${PGID:-1000}

if [ "$(getent group appgroup | cut -d: -f3)" != "$PGID" ]; then
    echo "Updating group appgroup GID to $PGID"
    groupmod -o -g "$PGID" appgroup
fi

if [ "$(id -u appuser)" != "$PUID" ]; then
    echo "Updating user appuser UID to $PUID"
    usermod -o -u "$PUID" -g "$PGID" appuser
fi

if [ ! -d /config ]; then
    echo "Creating /config directory"
    mkdir -p /config
fi

chown -R appuser:appgroup /config

if [ "$APP_MODE" = "WEB" ]; then
    if [ "$FLASK_ENV" = "development" ]; then
        echo "Starting scheduler.py.."
        gosu appuser python /code/scheduler.py &
        echo "Starting Flask in development mode as $PUID:$PGID"
        exec gosu appuser flask --app daps_webui:app run --host 0.0.0.0 --port=5000 --debug
    else
        gosu appuser python /code/migrate_db.py || {
            echo "Failed to migrate database. Exiting."
            exit 1
        }
        echo "Starting scheduler.py.."
        gosu appuser python /code/scheduler.py &
        echo "Starting Gunicorn in production mode as $PUID:$PGID"
        exec gosu appuser gunicorn --timeout 1800 -w 3 --preload -b 0.0.0.0:8000 daps_webui:app

    fi
else
    echo "Running main.py as $PUID:$PGID"
    exec gosu appuser python main.py
fi
