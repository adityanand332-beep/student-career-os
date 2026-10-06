# Student Career OS

A runnable Flask + SQLite career dashboard for students. This is an actual functional application, not a static demo.

## Features
- User registration/login with hashed passwords
- Skill assessment (1–5 levels) stored in SQLite
- Resume upload and local PDF/DOCX/TXT text extraction
- Automatic skill detection from uploaded resume
- Career matching based on required skills
- Skill-gap analysis + career-specific roadmap
- Project portfolio CRUD
- Certificate tracking
- Job-readiness score calculated from profile data
- Responsive UI

## Run locally
1. Install Python 3.10+
2. `python -m venv .venv`
3. Activate it:
   - Windows: `.venv\Scripts\activate`
   - macOS/Linux: `source .venv/bin/activate`
4. `pip install -r requirements.txt`
5. `python run.py`
6. Open http://127.0.0.1:5000

## Production-ready config
- Copy `.env.example` to `.env` and set a real secret key before deployment.
- Windows PowerShell example: `$env:SECRET_KEY="your-long-random-secret"`
- macOS/Linux example: `export SECRET_KEY="your-long-random-secret"`
- For production deployments, also set:
  - `APP_ENV=production`
  - `PORT=8000`
  - `DATABASE_PATH=./data/career_os.db`
  - `MAIL_SERVER=smtp-relay.brevo.com`
  - `MAIL_PORT=587`
  - `MAIL_USE_TLS=true`
  - `MAIL_USE_SSL=false`
  - `MAIL_USERNAME=your-brevo-smtp-login`
  - `MAIL_PASSWORD=your-brevo-smtp-key`
  - `MAIL_FROM=verified-sender@yourdomain.com`
  - `ADMIN_EMAIL=admin@yourdomain.com`
- The SQLite database is created automatically at `data/career_os.db`.

## SMTP testing
For Brevo, verify a sender address/domain in Brevo, then copy the SMTP login and SMTP key from Brevo's SMTP settings. The SMTP key is not the Brevo API key. Put these values in your untracked `.env` file:

```dotenv
MAIL_SERVER=smtp-relay.brevo.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USE_SSL=false
MAIL_USERNAME=your-brevo-smtp-login
MAIL_PASSWORD=your-brevo-smtp-key
MAIL_FROM=the-sender-address-verified-in-brevo
```

Restart the app after changing `.env`. Sign in as an admin, open `/admin`, enter a recipient address you can access, and click `Send test email`. A successful result confirms SMTP accepted the message; also check the recipient inbox and spam folder. Never commit `.env` or share the SMTP key in chat.

When SMTP is unset in development, the app writes a debug message to the terminal; this does not deliver email.

## Run with Gunicorn
`gunicorn --bind 0.0.0.0:8000 run:app`

## Docker deployment
Build and run:

```bash
docker build -t student-career-os .
docker run -p 8000:8000 --env-file .env student-career-os
```

Or with Docker Compose:

```bash
docker compose up --build
```

## Render deployment
The included `render.yaml` configures a free demo service and its `/health` check. To deploy:

1. Push this project to a GitHub repository. Make sure `.env` is not committed; `.gitignore` excludes it.
2. In Render, choose **New > Blueprint**, connect the repository, and deploy the `render.yaml` blueprint.
3. When Render asks for values, set `ADMIN_EMAIL`, `MAIL_USERNAME`, `MAIL_PASSWORD`, and `MAIL_FROM`. Use the Brevo SMTP login/key and a sender address verified with Brevo.
4. After deployment, open the Render service URL and register using the configured admin email. That new account will receive admin access.
5. Sign in and use `/admin` > **Send test email** to verify SMTP delivery.

The free Render service uses an ephemeral filesystem: SQLite data and uploaded profile/resume files can be lost on redeploy, restart, or instance replacement. Use a persistent disk or migrate the app itself to PostgreSQL before relying on it for real users. `DATABASE_URL` is not yet used as the app's runtime database adapter; the PostgreSQL script only copies data and does not enable PostgreSQL runtime support.

## Railway deployment
A ready-to-use `railway.json` file is included for Railway. Use:

```bash
railway login
railway link
railway up
```

Set these environment variables in the Railway dashboard:
- `APP_ENV=production`
- `PORT=8000`
- `SECRET_KEY`
- `ADMIN_EMAIL`
- `DATABASE_PATH=/tmp/career_os.db`
- `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM`

## PostgreSQL migration
Use the migration utility at `scripts/migrate_to_postgresql.py` to copy SQLite data into PostgreSQL.

Example:

```bash
export DATABASE_URL="postgresql://user:password@host:5432/career_os"
python scripts/migrate_to_postgresql.py
```

This script exports the existing tables from SQLite and imports them into PostgreSQL using `psycopg`.

## VPS deployment
For a Linux VPS, run the app with systemd or nginx + gunicorn:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
gunicorn --bind 0.0.0.0:8000 run:app
```

Keep `.env` outside the repository for production secrets and ensure `APP_ENV=production` and `SECRET_KEY` are set before launch.

## Notes
- Resume parsing is local; no external AI API key is required.
- Career matching is deterministic and based on the skill matrix in `app/career.py`.
- To make the system AI-powered later, add an LLM provider behind a server-side API route; never expose API keys in frontend code.
- Health endpoint: `/health`
