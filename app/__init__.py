import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask
from .db import init_db

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def create_app():
    app = Flask(__name__)
    app_env = os.environ.get('APP_ENV', 'development').lower()
    default_db = str(BASE_DIR / 'data' / 'career_os.db')
    database_path = os.environ.get('DATABASE_PATH') or os.environ.get('DATABASE_URL') or default_db

    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY') or os.urandom(32).hex(),
        DATABASE=database_path,
        DATABASE_URL=os.environ.get('DATABASE_URL', ''),
        APP_ENV=app_env,
        ADMIN_EMAIL=os.environ.get('ADMIN_EMAIL', '').lower(),
        DEBUG=(app_env == 'development'),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        MAIL_SERVER=os.environ.get('MAIL_SERVER', ''),
        MAIL_PORT=int(os.environ.get('MAIL_PORT', '587')),
        MAIL_USE_TLS=os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true',
        MAIL_USE_SSL=os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true',
        MAIL_USERNAME=os.environ.get('MAIL_USERNAME', ''),
        MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD', ''),
        MAIL_DEFAULT_SENDER=os.environ.get('MAIL_FROM', 'noreply@career-os.local'),
        MAIL_TIMEOUT=int(os.environ.get('MAIL_TIMEOUT', '30')),
    )

    if app_env == 'production':
        app.config['SESSION_COOKIE_SECURE'] = True
        app.config['PREFERRED_URL_SCHEME'] = 'https'

    database_dir = os.path.dirname(app.config['DATABASE'])
    if database_dir and not app.config['DATABASE'].startswith('postgres') and not app.config['DATABASE'].startswith('postgresql'):
        os.makedirs(database_dir, exist_ok=True)

    init_db(app)
    from .routes import bp
    app.register_blueprint(bp)
    return app
