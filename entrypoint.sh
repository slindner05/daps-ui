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

echo "Running db migrate script..."
python /code/migrate_db.py || {
	echo "Failed to migrate database. Exiting."
	exit 1
}

if [ "$APP_MODE" = "WEB" ]; then
	if [ "$FLASK_ENV" = "development" ]; then
		echo "Starting Flask in development mode as $PUID:$PGID"
		exec gosu appuser poetry run flask --app daps_webui:app run --host 0.0.0.0 --port=5000 --debug
	else
		echo "Starting Gunicorn in production mode as $PUID:$PGID"
		exec gosu appuser poetry run gunicorn --timeout 90 -w 6 -b 0.0.0.0:8000 --access-logfile '-' --error-logfile '-' daps_webui:app
	fi
else
	echo "Running main.py as $PUID:$PGID"
	exec gosu appuser poetry run python main.py
fi
