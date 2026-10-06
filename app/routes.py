import os
import re
import secrets
import smtplib
from email.message import EmailMessage
from uuid import uuid4

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .career import CAREERS, ROADMAPS, match
from .db import get_db

bp = Blueprint('main', __name__)

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app', 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def user():
    return session.get('user_id')


def current_user():
    uid = user()
    if not uid:
        return None
    return get_db().execute('SELECT * FROM users WHERE id = ?', (uid,)).fetchone()


def login_required():
    if not user():
        return redirect(url_for('main.login'))


def get_skills(uid):
    rows = get_db().execute(
        'SELECT s.name, us.level FROM user_skills us JOIN skills s ON s.id = us.skill_id WHERE us.user_id = ?',
        (uid,),
    ).fetchall()
    return {r['name']: r['level'] for r in rows}


def generate_token():
    return secrets.token_urlsafe(32)


def send_email(recipient, subject, body):
    smtp_server = current_app.config.get('MAIL_SERVER')
    if not smtp_server:
        if current_app.config.get('APP_ENV') == 'development':
            current_app.logger.warning('SMTP is not configured; development email only: To=%s Subject=%s\n%s', recipient, subject, body)
        else:
            current_app.logger.error('Email delivery skipped because MAIL_SERVER is not configured')
        return False

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@career-os.local')
    msg['To'] = recipient
    msg.set_content(body)

    port = current_app.config.get('MAIL_PORT', 587)
    username = current_app.config.get('MAIL_USERNAME', '')
    password = current_app.config.get('MAIL_PASSWORD', '')
    use_tls = current_app.config.get('MAIL_USE_TLS', True)
    use_ssl = current_app.config.get('MAIL_USE_SSL', False)
    timeout = current_app.config.get('MAIL_TIMEOUT', 30)

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(smtp_server, port, timeout=timeout) as server:
                if username:
                    server.login(username, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_server, port, timeout=timeout) as server:
                if use_tls:
                    server.starttls()
                if username:
                    server.login(username, password)
                server.send_message(msg)
        return True
    except Exception as exc:
        current_app.logger.exception('SMTP delivery failed')
        return False


def create_verification_token(user_id):
    token = generate_token()
    db = get_db()
    db.execute('DELETE FROM email_verification_tokens WHERE user_id = ?', (user_id,))
    db.execute('INSERT INTO email_verification_tokens(user_id, token) VALUES(?, ?)', (user_id, token))
    db.commit()
    return token


def create_reset_token(user_id):
    token = generate_token()
    db = get_db()
    db.execute('DELETE FROM password_reset_tokens WHERE user_id = ?', (user_id,))
    db.execute('INSERT INTO password_reset_tokens(user_id, token) VALUES(?, ?)', (user_id, token))
    db.commit()
    return token


@bp.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@bp.errorhandler(500)
def server_error(error):
    return render_template('500.html'), 500


@bp.route('/')
def index():
    return redirect(url_for('main.dashboard')) if user() else redirect(url_for('main.login'))


@bp.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'student-career-os'})


@bp.route('/profile', methods=['GET', 'POST'])
def profile():
    r = login_required()
    if r:
        return r

    db = get_db()
    row = current_user()
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        if len(name) >= 2:
            db.execute('UPDATE users SET name = ? WHERE id = ?', (name, user()))
        if 'avatar' in request.files and request.files['avatar'].filename:
            uploaded = request.files['avatar']
            ext = os.path.splitext(uploaded.filename)[1].lower()
            if ext not in {'.png', '.jpg', '.jpeg', '.webp'}:
                flash('Only PNG, JPG, and WEBP images are allowed.', 'error')
            else:
                filename = f'{uuid4().hex}{ext}'
                uploaded.save(os.path.join(UPLOAD_FOLDER, filename))
                db.execute('UPDATE users SET avatar = ? WHERE id = ?', (filename, user()))
                session['avatar'] = filename
                flash('Profile photo updated.', 'success')
        db.commit()
        return redirect(url_for('main.profile'))

    return render_template('profile.html', user=row)


@bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''

        if len(name) < 2:
            flash('Name must be at least 2 characters long.', 'error')
            return render_template('register.html')
        if not EMAIL_RE.match(email):
            flash('Please enter a valid email address.', 'error')
            return render_template('register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('register.html')

        try:
            db = get_db()
            is_admin = int(email == current_app.config.get('ADMIN_EMAIL', ''))
            db.execute(
                'INSERT INTO users(name, email, password, is_verified, is_admin) VALUES(?,?,?,0,?)',
                (name, email, generate_password_hash(password), is_admin),
            )
            user_id = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()['id']
            token = create_verification_token(user_id)
            db.commit()
            verification_link = url_for('main.verify_email', token=token, _external=True)
            email_sent = send_email(email, 'Verify your Career OS account', f'Hi {name},\n\nVerify your email here: {verification_link}\n')
            if email_sent:
                flash('Account created. Please verify your email before logging in.', 'success')
            else:
                flash('Account created, but the verification email could not be sent. Check SMTP settings and resend it.', 'error')
            return redirect(url_for('main.login'))
        except Exception:
            flash('Email already registered.', 'error')
    return render_template('register.html')


@bp.route('/verify/<token>')
def verify_email(token):
    row = get_db().execute('SELECT user_id FROM email_verification_tokens WHERE token = ?', (token,)).fetchone()
    if not row:
        flash('Verification token is invalid or expired.', 'error')
        return redirect(url_for('main.login'))

    get_db().execute('UPDATE users SET is_verified = 1 WHERE id = ?', (row['user_id'],))
    get_db().execute('DELETE FROM email_verification_tokens WHERE token = ?', (token,))
    get_db().commit()
    flash('Email verified successfully. You can now log in.', 'success')
    return redirect(url_for('main.login'))


@bp.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        row = get_db().execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if row and row['is_verified'] == 0:
            token = create_verification_token(row['id'])
            verification_link = url_for('main.verify_email', token=token, _external=True)
            email_sent = send_email(email, 'Verify your Career OS account', f'Hi {row["name"]},\n\nVerify your email here: {verification_link}\n')
            if email_sent:
                flash('Verification email sent again.', 'success')
            else:
                flash('Verification email could not be sent. Check the SMTP configuration and try again.', 'error')
            return redirect(url_for('main.login'))
        flash('No pending verification found for that email.', 'error')
    return render_template('resend_verification.html')


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        row = get_db().execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if row:
            token = create_reset_token(row['id'])
            reset_link = url_for('main.reset_password', token=token, _external=True)
            send_email(email, 'Reset your Career OS password', f'Hi {row["name"]},\n\nReset your password here: {reset_link}\n')
            flash('Password reset link sent to your email.', 'success')
        else:
            flash('If that email exists, a reset link will be sent.', 'success')
        return redirect(url_for('main.login'))
    return render_template('forgot_password.html')


@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    row = get_db().execute('SELECT user_id FROM password_reset_tokens WHERE token = ?', (token,)).fetchone()
    if not row:
        flash('Password reset token is invalid or expired.', 'error')
        return redirect(url_for('main.login'))

    if request.method == 'POST':
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm_password') or ''
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('reset_password.html', token=token)
        if password != confirm:
            flash('Passwords do not match. Please try again.', 'error')
            return render_template('reset_password.html', token=token)
        get_db().execute(
            'UPDATE users SET password = ? WHERE id = ?',
            (generate_password_hash(password), row['user_id']),
        )
        get_db().execute('DELETE FROM password_reset_tokens WHERE token = ?', (token,))
        get_db().commit()
        flash('Password updated successfully. Please log in.', 'success')
        return redirect(url_for('main.login'))

    return render_template('reset_password.html', token=token)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        row = get_db().execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if row and check_password_hash(row['password'], password):
            if row['is_verified'] == 0:
                flash('Please verify your email before logging in.', 'error')
                return redirect(url_for('main.resend_verification'))
            session['user_id'] = row['id']
            session['name'] = row['name']
            session['email'] = row['email']
            session['avatar'] = row['avatar']
            session['is_admin'] = bool(row['is_admin'])
            return redirect(url_for('main.dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))


@bp.route('/dashboard')
def dashboard():
    r = login_required()
    if r:
        return r
    uid = user()
    db = get_db()
    skills = get_skills(uid)
    matches = []
    for c in CAREERS:
        score, got, missing = match(skills, c)
        matches.append({'career': c, 'score': score, 'missing': missing, 'got': got})
    matches.sort(key=lambda x: x['score'], reverse=True)
    projects = db.execute('SELECT * FROM projects WHERE user_id=? ORDER BY id DESC', (uid,)).fetchall()
    certs = db.execute('SELECT * FROM certificates WHERE user_id=? ORDER BY id DESC', (uid,)).fetchall()
    goals = db.execute('SELECT * FROM goals WHERE user_id=? ORDER BY target_date ASC, id DESC', (uid,)).fetchall()
    total = sum(skills.values())
    readiness = min(100, round((len(skills) / 15) * 60 + min(total / (max(len(skills), 1) * 5), 1) * 40)) if skills else 0

    skill_chart = []
    for skill_name, skill_level in sorted(skills.items()):
        skill_chart.append({'name': skill_name, 'value': skill_level})

    chart_labels = [entry['name'] for entry in skill_chart]
    chart_values = [entry['value'] for entry in skill_chart]

    return render_template(
        'dashboard.html',
        skills=skills,
        matches=matches[:4],
        projects=projects,
        certs=certs,
        goals=goals,
        readiness=readiness,
        skill_chart=skill_chart,
        chart_labels=chart_labels,
        chart_values=chart_values,
    )


@bp.route('/skills', methods=['GET', 'POST'])
def skills():
    r = login_required()
    if r:
        return r
    db = get_db()
    uid = user()
    if request.method == 'POST':
        try:
            for sid, val in request.form.items():
                if sid.startswith('skill_'):
                    skill_id = int(sid[6:])
                    level = max(1, min(5, int(val)))
                    db.execute(
                        'INSERT INTO user_skills(user_id,skill_id,level,source) VALUES(?,?,?,?) ON CONFLICT(user_id,skill_id) DO UPDATE SET level=excluded.level',
                        (uid, skill_id, level, 'assessment'),
                    )
            db.commit()
            flash('Skills updated.', 'success')
            return redirect(url_for('main.skills'))
        except (TypeError, ValueError):
            flash('Please enter valid skill levels from 1 to 5.', 'error')
    allskills = db.execute('SELECT * FROM skills ORDER BY name').fetchall()
    existing = get_skills(uid)
    return render_template('skills.html', allskills=allskills, existing=existing)


@bp.route('/careers')
def careers():
    r = login_required()
    if r:
        return r
    skills = get_skills(user())
    data = []
    for c in CAREERS:
        score, got, missing = match(skills, c)
        data.append((c, score, got, missing))
    return render_template('careers.html', data=sorted(data, key=lambda x: x[1], reverse=True))


@bp.route('/career/<path:name>')
def career(name):
    r = login_required()
    if r:
        return r
    if name not in CAREERS:
        return 'Career not found', 404
    score, got, missing = match(get_skills(user()), name)
    return render_template('career.html', name=name, score=score, got=got, missing=missing, roadmap=ROADMAPS[name])


@bp.route('/projects', methods=['GET', 'POST'])
def projects():
    r = login_required()
    if r:
        return r
    db = get_db(); uid = user()
    if request.method == 'POST':
        db.execute(
            'INSERT INTO projects(user_id,title,tech,status,url) VALUES(?,?,?,?,?)',
            (uid, request.form['title'], request.form['tech'], request.form['status'], request.form.get('url', '')),
        )
        db.commit()
        return redirect(url_for('main.projects'))
    rows = db.execute('SELECT * FROM projects WHERE user_id=? ORDER BY id DESC', (uid,)).fetchall()
    return render_template('projects.html', projects=rows)


@bp.route('/projects/delete/<int:pid>', methods=['POST'])
def delete_project(pid):
    get_db().execute('DELETE FROM projects WHERE id=? AND user_id=?', (pid, user()))
    get_db().commit()
    return redirect(url_for('main.projects'))


@bp.route('/certificates', methods=['GET', 'POST'])
def certificates():
    r = login_required()
    if r:
        return r
    db = get_db(); uid = user()
    if request.method == 'POST':
        db.execute(
            'INSERT INTO certificates(user_id,title,issuer,issue_date,url) VALUES(?,?,?,?,?)',
            (uid, request.form['title'], request.form['issuer'], request.form['issue_date'], request.form.get('url', '')),
        )
        db.commit()
        return redirect(url_for('main.certificates'))
    rows = db.execute('SELECT * FROM certificates WHERE user_id=? ORDER BY id DESC', (uid,)).fetchall()
    return render_template('certificates.html', certificates=rows)


@bp.route('/goals', methods=['GET', 'POST'])
def goals():
    r = login_required()
    if r:
        return r
    db = get_db(); uid = user()
    if request.method == 'POST':
        title = (request.form.get('title') or '').strip()
        target_date = request.form.get('target_date') or ''
        status = request.form.get('status') or 'active'
        if title:
            db.execute('INSERT INTO goals(user_id,title,target_date,status) VALUES(?,?,?,?)', (uid, title, target_date, status))
            db.commit()
            flash('Goal saved successfully.', 'success')
        else:
            flash('Goal title is required.', 'error')
        return redirect(url_for('main.goals'))
    rows = db.execute('SELECT * FROM goals WHERE user_id=? ORDER BY target_date ASC, id DESC', (uid,)).fetchall()
    return render_template('goals.html', goals=rows)


@bp.route('/goals/delete/<int:goal_id>', methods=['POST'])
def delete_goal(goal_id):
    get_db().execute('DELETE FROM goals WHERE id=? AND user_id=?', (goal_id, user()))
    get_db().commit()
    flash('Goal removed.', 'success')
    return redirect(url_for('main.goals'))


@bp.route('/resume', methods=['GET', 'POST'])
def resume():
    r = login_required()
    if r:
        return r
    extracted = ''
    filename = ''
    if request.method == 'POST' and 'resume' in request.files:
        f = request.files['resume']
        filename = f.filename or ''
        if not filename:
            flash('Please choose a resume file to upload.', 'error')
        else:
            try:
                ext = filename.lower().split('.')[-1]
                if ext not in {'pdf', 'docx', 'txt'}:
                    raise ValueError('Unsupported file type. Please upload PDF, DOCX, or TXT.')
                if filename.lower().endswith('.pdf'):
                    from PyPDF2 import PdfReader
                    extracted = '\n'.join((p.extract_text() or '') for p in PdfReader(f).pages)
                elif filename.lower().endswith('.docx'):
                    from docx import Document
                    extracted = '\n'.join(p.text for p in Document(f).paragraphs)
                else:
                    extracted = f.read().decode('utf-8', 'ignore')

                db = get_db()
                db.execute('INSERT INTO resumes(user_id,filename,extracted_text) VALUES(?,?,?)', (user(), filename, extracted))
                for s in db.execute('SELECT id,name FROM skills').fetchall():
                    if re.search(r'(?<![a-z])' + re.escape(s['name']) + r'(?![a-z])', extracted, re.I):
                        db.execute(
                            'INSERT INTO user_skills(user_id,skill_id,level,source) VALUES(?,?,3,?) ON CONFLICT(user_id,skill_id) DO UPDATE SET source=excluded.source',
                            (user(), s['id'], 'resume'),
                        )
                db.commit()
                flash('Resume analyzed and matching skills were added.', 'success')
            except Exception as e:
                flash('Could not read that file: ' + str(e), 'error')
    last = get_db().execute('SELECT * FROM resumes WHERE user_id=? ORDER BY id DESC LIMIT 1', (user(),)).fetchone()
    return render_template('resume.html', resume=last)


@bp.route('/admin')
def admin():
    r = login_required()
    if r:
        return r
    user_row = current_user()
    if not user_row or user_row['is_admin'] != 1:
        flash('Admin access required.', 'error')
        return redirect(url_for('main.dashboard'))

    db = get_db()
    total_users = db.execute('SELECT COUNT(*) AS count FROM users').fetchone()['count']
    verified_users = db.execute('SELECT COUNT(*) AS count FROM users WHERE is_verified = 1').fetchone()['count']
    active_jobs = db.execute('SELECT COUNT(*) AS count FROM projects').fetchone()['count']
    total_skills = db.execute('SELECT COUNT(*) AS count FROM skills').fetchone()['count']
    recent_users = db.execute('SELECT id, name, email, created_at FROM users ORDER BY id DESC LIMIT 5').fetchall()
    smtp_ready = all((
        current_app.config.get('MAIL_SERVER'),
        current_app.config.get('MAIL_USERNAME'),
        current_app.config.get('MAIL_PASSWORD'),
        current_app.config.get('MAIL_DEFAULT_SENDER'),
    ))
    return render_template(
        'admin.html',
        total_users=total_users,
        verified_users=verified_users,
        active_jobs=active_jobs,
        total_skills=total_skills,
        recent_users=recent_users,
        smtp_ready=smtp_ready,
    )


@bp.route('/admin/test-email', methods=['POST'])
def test_email():
    r = login_required()
    if r:
        return r

    user_row = current_user()
    if not user_row or user_row['is_admin'] != 1:
        flash('Admin access required.', 'error')
        return redirect(url_for('main.dashboard'))

    recipient = (request.form.get('email') or user_row['email']).strip().lower()
    subject = 'Career OS SMTP test'
    body = (
        f'Hi {user_row["name"]},\n\n'
        'This is a test email from Career OS to validate your SMTP configuration.\n\n'
        'If you received this message, your mail server is correctly configured.\n'
    )

    if send_email(recipient, subject, body):
        flash('SMTP test email sent successfully.', 'success')
    else:
        flash('SMTP test email failed. Check MAIL_SERVER, MAIL_USERNAME, and MAIL_PASSWORD.', 'error')
    return redirect(url_for('main.admin'))
