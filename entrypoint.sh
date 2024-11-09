#!/bin/sh

if [ "$APP_MODE" = "WEB" ]; then
    if [ "$FLASK_ENV" = "development" ]; then
        poetry run flask --app daps_webui run --host 0.0.0.0 --port=5000 --debug
    else
        poetry run gunicorn -w 2 -b 0.0.0.0:8000 daps_webui:app
    fi
else
    poetry run python main.py
fi
