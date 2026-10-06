import os
import sqlite3
from flask import current_app, g


def get_db():
    if 'db' not in g:
        db_path = current_app.config.get('DATABASE')
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db:
        db.close()


def init_db(app):
    with app.app_context():
        db = get_db()
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            avatar TEXT,
            is_verified INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS skills(
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS user_skills(
            user_id INTEGER,
            skill_id INTEGER,
            level INTEGER DEFAULT 1,
            source TEXT DEFAULT 'manual',
            PRIMARY KEY(user_id,skill_id)
        );
        CREATE TABLE IF NOT EXISTS assessments(
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            skill TEXT,
            score INTEGER,
            taken_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS resumes(
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            filename TEXT,
            extracted_text TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS projects(
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            title TEXT,
            tech TEXT,
            status TEXT,
            url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS certificates(
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            title TEXT,
            issuer TEXT,
            issue_date TEXT,
            url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS goals(
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            title TEXT,
            target_date TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS email_verification_tokens(
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS password_reset_tokens(
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        ''')

        user_columns = [row[1] for row in db.execute('PRAGMA table_info(users)').fetchall()]
        for column, coltype in [('avatar', 'TEXT'), ('is_verified', 'INTEGER DEFAULT 0'), ('is_admin', 'INTEGER DEFAULT 0')]:
            if column not in user_columns:
                db.execute(f'ALTER TABLE users ADD COLUMN {column} {coltype}')

        skills = [
            'Python','Java','JavaScript','HTML','CSS','React','Node.js','SQL','Git','GitHub',
            'Data Structures','Algorithms','Excel','Power BI','Machine Learning','Pandas','NumPy',
            'Flask','Django','Cybersecurity','Linux','Cloud','Communication','Problem Solving'
        ]
        for s in skills:
            db.execute('INSERT OR IGNORE INTO skills(name) VALUES(?)', (s,))

        admin_email = app.config.get('ADMIN_EMAIL')
        if admin_email:
            db.execute('UPDATE users SET is_admin = 1 WHERE email = ?', (admin_email.lower(),))

        db.commit()
        app.teardown_appcontext(close_db)
