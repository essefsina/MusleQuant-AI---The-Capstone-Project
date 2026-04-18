import json, hashlib
from flask import request, jsonify, session, redirect, url_for, render_template
from functools import wraps
from pathlib import Path
from datetime import datetime

DATA_DIR = Path('data')
USERS_FILE = DATA_DIR / 'users.json'
DATA_DIR.mkdir(exist_ok=True)

def load_users():
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text())
        except:
            pass
    return {}

def save_users(u):
    USERS_FILE.write_text(json.dumps(u, indent=2))

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


# ── AUTH DECORATORS ──
def login_required(f):
    @wraps(f)
    def d(*a, **k):
        if 'user' not in session:
            return redirect(url_for('login_page'))
        return f(*a, **k)
    return d

def api_auth(f):
    @wraps(f)
    def d(*a, **k):
        if 'user' not in session:
            return jsonify({'error': 'Not logged in'}), 401
        return f(*a, **k)
    return d


# ── ROUTES ──
def auth_routes(app):

    @app.route('/login', methods=['GET'])
    def login_page():
        if 'user' in session:
            return redirect(url_for('index'))
        return render_template('login.html')

    @app.route('/login', methods=['POST'])
    def do_login():
        d = request.get_json()
        u = (d.get('username') or '').strip().lower()
        p = (d.get('password') or '').strip()

        if not u or not p:
            return jsonify({
                'status': 'error',
                'message': 'Please enter username and password'
            }), 400

        users = load_users()

        if u not in users:
            return jsonify({
                'status': 'error',
                'message': 'Account not found. Create an account first.'
            }), 401

        if users[u]['password'] != hash_pw(p):
            return jsonify({
                'status': 'error',
                'message': 'Wrong password. Please try again.'
            }), 401

        session['user']  = u
        session['name']  = users[u].get('name', '')
        session['email'] = users[u].get('email', '')

        return jsonify({
            'status': 'ok',
            'user': u,
            'name': users[u].get('name', u)
        })


    @app.route('/register', methods=['POST'])
    def do_register():
        d  = request.get_json()
        fn = (d.get('firstname') or '').strip()
        ln = (d.get('lastname')  or '').strip()
        u  = (d.get('username')  or '').strip().lower()
        p  = (d.get('password')  or '').strip()
        ag = (d.get('age')       or '').strip()
        em = (d.get('email')     or '').strip().lower()

        if not fn or not u or not p:
            return jsonify({
                'status': 'error',
                'message': 'First name, username and password are required'
            }), 400

        if len(p) < 6:
            return jsonify({
                'status': 'error',
                'message': 'Password must be at least 6 characters'
            }), 400

        users = load_users()

        if u in users:
            return jsonify({
                'status': 'error',
                'message': 'Username already taken'
            }), 409

        name = (fn + ' ' + ln).strip()

        users[u] = {
            'name': name,
            'firstname': fn,
            'lastname': ln,
            'username': u,
            'password': hash_pw(p),
            'age': ag,
            'email': em,
            'created_at': datetime.now().isoformat()
        }

        save_users(users)

        return jsonify({
            'status': 'ok',
            'name': name
        })


    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login_page'))