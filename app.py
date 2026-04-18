from flask import Flask, render_template

from auth_module import auth_routes, login_required, api_auth
from emg_module import process_emg_data, get_status, clear_session_data
from report_module import download_csv_file, save_session, generate_report

app = Flask(__name__)
app.secret_key = 'musclequant-v4-2026'


# ── REGISTER AUTH ROUTES ──
auth_routes(app)


# ── MAIN PAGE ──
@app.route('/')
@login_required
def index():
    return render_template('index.html')


# ── API ROUTES ──
@app.route('/api/data')
@api_auth
def get_data():
    return process_emg_data()


@app.route('/api/status')
@api_auth
def status():
    from flask import session
    return get_status(session)


@app.route('/api/clear')
@api_auth
def clear_data():
    return clear_session_data()


@app.route('/api/download_csv')
@api_auth
def download_csv():
    return download_csv_file()


@app.route('/api/save_session', methods=['POST'])
@api_auth
def save_data():
    from flask import request, session
    return save_session(request, session)


@app.route('/api/generate_report', methods=['POST'])
@api_auth
def report():
    from flask import request, session
    return generate_report(request, session)


# ── RUN SERVER ──
if __name__ == '__main__':
    print("\n" + "="*50)
    print("  MuscleQuant AI — http://localhost:8080")
    print("="*50 + "\n")

    app.run(debug=False, host='0.0.0.0', port=8080)