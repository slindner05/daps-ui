from flask_migrate import upgrade

from daps_webui import app

with app.app_context():
    print("Applying database migrations...")
    upgrade()
    print("Database migrations applied")
