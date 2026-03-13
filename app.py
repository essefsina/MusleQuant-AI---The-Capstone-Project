"""
MuscleQuant AI - Flask Backend
Run: python3 app.py
Open: http://localhost:8080
"""
from flask import Flask, jsonify, render_template, Response, request, session, redirect, url_for
import serial, serial.tools.list_ports
import time, csv, io, json, math, random, hashlib
from datetime import datetime
from collections import deque
from pathlib import Path
from functools import wraps

app = Flask(__name__)
app.secret_key = 'musclequant-v4-2026'

DATA_DIR   = Path('data')
USERS_FILE = DATA_DIR / 'users.json'
DATA_DIR.mkdir(exist_ok=True)

# ── User storage ──
def load_users():
    if USERS_FILE.exists():
        try: return json.loads(USERS_FILE.read_text())
        except: pass
    return {}

def save_users(u):
    USERS_FILE.write_text(json.dumps(u, indent=2))

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

# ── Serial ──
SERIAL_PORT = 'AUTO'
BAUD_RATE   = 115200
ser = None

def find_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if p.device.upper() == 'COM7': return p.device
    for p in ports:
        if any(k in (p.description or '').lower() for k in ['usb','cp210','ch340']): return p.device
    return ports[0].device if ports else None

def connect_serial():
    global ser, SERIAL_PORT
    port = find_port()
    if not port: print("  SIMULATION mode."); return False
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=1)
        time.sleep(2); SERIAL_PORT = port
        print(f"  Connected on {port}"); return True
    except Exception as e:
        print(f"  Serial error: {e}. SIMULATION mode."); return False

connected = connect_serial()

# ── EMG data ──
emg_history   = deque(maxlen=200)
start_time    = time.time()
csv_log       = []
rep_count     = 0
last_above    = False
WORK_THRESHOLD= 1200
work_samples  = 0
rest_samples  = 0
current_state = "REST"

# ── Auth ──
def login_required(f):
    @wraps(f)
    def d(*a,**k):
        if 'user' not in session: return redirect(url_for('login_page'))
        return f(*a,**k)
    return d

def api_auth(f):
    @wraps(f)
    def d(*a,**k):
        if 'user' not in session: return jsonify({'error':'Not logged in'}),401
        return f(*a,**k)
    return d

# ── EMG processing ──
def get_emg_value():
    global ser, connected
    if connected and ser:
        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                for t in line.replace(',',' ').split():
                    try:
                        mv = float(t)
                        adc = int((mv/3300.0)*4095)
                        return max(0,min(4095,adc)), f'{mv:.6f}'
                    except: pass
        except: connected = False
    t   = time.time()-start_time
    adc = max(0,min(4095,int(600+1800*abs(math.sin(t*0.4))+random.randint(-120,120))))
    return adc, f'{round((adc/4095.0)*3300.0,6):.6f}'

def calc_intensity(v):
    p = int((v/4095)*100)
    if v<500:  return 'Rest', p
    if v<1200: return 'Low', p
    if v<2400: return 'Moderate', p
    if v<3200: return 'High', p
    return 'Peak', p

def calc_fatigue(h):
    if len(h)<40: return 'Insufficient Data', 0
    d=list(h); half=len(d)//2
    f=sum(d[:half])/half; s=sum(d[half:])/half
    if f==0: return 'Normal',0
    drop=((f-s)/f)*100
    if drop>15: return 'Fatigued', int(drop)
    if drop>8:  return 'Mild Fatigue', int(drop)
    return 'Normal', max(0,int(drop))

def update_reps(v):
    global rep_count, last_above
    above = v>WORK_THRESHOLD
    if above and not last_above: rep_count+=1
    last_above=above
    return rep_count

def update_wr(v):
    global work_samples, rest_samples, current_state
    if v>WORK_THRESHOLD: work_samples+=1; current_state='WORK'
    else:                rest_samples+=1; current_state='REST'
    total=work_samples+rest_samples
    wp=int((work_samples/total)*100) if total>0 else 0
    flag='Overworking' if wp>=80 else 'Too Much Rest' if 100-wp>=80 else 'Good Balance'
    return wp, 100-wp, current_state, flag

# ── Auth routes ──
@app.route('/login', methods=['GET'])
def login_page():
    if 'user' in session: return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def do_login():
    d = request.get_json()
    u = (d.get('username') or '').strip().lower()
    p = (d.get('password') or '').strip()
    if not u or not p:
        return jsonify({'status':'error','message':'Please enter username and password'}),400
    users = load_users()
    if u not in users:
        return jsonify({'status':'error','message':'Account not found. Create an account first.'}),401
    if users[u]['password'] != hash_pw(p):
        return jsonify({'status':'error','message':'Wrong password. Please try again.'}),401
    session['user']  = u
    session['name']  = users[u].get('name','')
    session['email'] = users[u].get('email','')
    return jsonify({'status':'ok','user':u,'name':users[u].get('name',u)})

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
        return jsonify({'status':'error','message':'First name, username and password are required'}),400
    if len(p)<6:
        return jsonify({'status':'error','message':'Password must be at least 6 characters'}),400
    users = load_users()
    if u in users:
        return jsonify({'status':'error','message':'Username already taken'}),409
    name = (fn+' '+ln).strip()
    users[u] = {'name':name,'firstname':fn,'lastname':ln,'username':u,
                'password':hash_pw(p),'age':ag,'email':em,
                'created_at':datetime.now().isoformat()}
    save_users(users)
    return jsonify({'status':'ok','name':name})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

# ── API ──
@app.route('/api/data')
@api_auth
def get_data():
    value, raw_mv = get_emg_value()
    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    emg_history.append(value)
    csv_log.append({'timestamp':ts,'emg':value,'mv':raw_mv})
    il,ip = calc_intensity(value)
    fs,fp = calc_fatigue(emg_history)
    reps  = update_reps(value)
    wp,rp,st,rf = update_wr(value)
    return jsonify({'timestamp':ts,'emg':value,'raw_mv':raw_mv,'history':list(emg_history),
        'intensity_label':il,'intensity_pct':ip,'fatigue_status':fs,'fatigue_pct':fp,
        'reps':reps,'work_pct':wp,'rest_pct':rp,'current_state':st,'ratio_flag':rf})

@app.route('/api/status')
@api_auth
def status():
    u    = session.get('user','')
    name = session.get('name', u)
    email= session.get('email','')
    return jsonify({'connected':connected,'port':SERIAL_PORT if connected else 'SIMULATION',
        'mode':'Hardware' if connected else 'Simulation','user':u,'name':name,'email':email})

@app.route('/api/clear')
@api_auth
def clear_data():
    global rep_count,last_above,work_samples,rest_samples,current_state
    emg_history.clear(); csv_log.clear()
    rep_count=0;last_above=False;work_samples=0;rest_samples=0;current_state='REST'
    return jsonify({'status':'cleared'})

@app.route('/api/download_csv')
@api_auth
def download_csv():
    if not csv_log: return 'No data yet.',400
    out = io.StringIO()
    w   = csv.DictWriter(out,fieldnames=['timestamp','emg','mv'])
    w.writeheader(); w.writerows(csv_log)
    return Response(out.getvalue(),mimetype='text/csv',
        headers={'Content-Disposition':f'attachment; filename=emg_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'})

@app.route('/api/save_session', methods=['POST'])
@api_auth
def save_session_data():
    d = request.get_json()
    u = session.get('user','unknown')
    fn= DATA_DIR/f'session_{u}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(fn,'w') as f:
        json.dump({**d,'user':u,'saved_at':datetime.now().isoformat()},f,indent=2)
    return jsonify({'status':'saved'})

@app.route('/api/generate_report', methods=['POST'])
@api_auth
def generate_report():
    data = {}
    if 'csv_file' in request.files:
        f       = request.files['csv_file']
        content = f.read().decode('utf-8')
        rows    = list(csv.DictReader(io.StringIO(content)))
        if not rows: return jsonify({'status':'error','message':'CSV is empty'}),400
        emg_vals=[]
        for row in rows:
            try: emg_vals.append(float(row.get('emg',0)))
            except: pass
        total  = len(emg_vals)
        peak_p = int((max(emg_vals)/4095)*100) if emg_vals else 0
        avg_p  = int((sum(emg_vals)/total/4095)*100) if total>0 else 0
        above=False; reps=0
        for v in emg_vals:
            a=v>WORK_THRESHOLD
            if a and not above: reps+=1
            above=a
        if total>40:
            half=total//2; fst=sum(emg_vals[:half])/half; snd=sum(emg_vals[half:])/half
            drop=((fst-snd)/fst*100) if fst>0 else 0
            fat='Fatigued' if drop>15 else 'Mild Fatigue' if drop>8 else 'Normal'
        else: fat='Normal'
        wc=sum(1 for v in emg_vals if v>WORK_THRESHOLD)
        wp=int((wc/total)*100) if total>0 else 0
        data={'reps':reps,'peak_pct':peak_p,'avg_pct':avg_p,'fatigue':fat,
              'work_pct':wp,'rest_pct':100-wp,'duration':f'{total//10//60:02d}:{total//10%60:02d}',
              'readings':total,'mode':'CSV Upload','muscle':request.form.get('muscle','Unknown')}
    else:
        data = request.get_json() or {}

    muscle  = str(data.get('muscle','Unknown'))
    u       = session.get('user','athlete')
    name    = str(session.get('name', u.capitalize()))
    email   = str(session.get('email',''))
    reps    = int(data.get('reps',0))
    peak_pct= int(data.get('peak_pct',0))
    avg_pct = int(data.get('avg_pct',0))
    fatigue = str(data.get('fatigue','Normal'))
    work_pct= int(data.get('work_pct',0))
    rest_pct= int(data.get('rest_pct',100))
    duration= str(data.get('duration','00:00'))
    readings= int(data.get('readings',0))
    mode    = str(data.get('mode','Live Session'))
    now     = datetime.now()
    now_str = now.strftime('%B %d, %Y at %I:%M %p')
    date_str= now.strftime('%B %d, %Y')

    def badge_html(label):
        good = ['Normal','Good Balance','Optimal','Low Volume']
        warn = ['Mild Fatigue','Overworking','Too Much Rest','High']
        bad  = ['Fatigued']
        if label in bad:   c='#e74c3c';bg='#fdedec'
        elif label in warn:c='#f39c12';bg='#fef9e7'
        else:              c='#27ae60';bg='#eafaf1'
        return '<span style="background:'+bg+';color:'+c+';padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600">'+label+'</span>'

    def bar_html(pct, color):
        return ('<div style="display:flex;align-items:center;gap:10px">'
                '<div style="flex:1;height:6px;background:#f1f5f9;border-radius:3px;overflow:hidden">'
                '<div style="width:'+str(pct)+'%;height:100%;background:'+color+';border-radius:3px"></div></div>'
                '<span style="font-size:12px;color:#94a3b8;width:32px">'+str(pct)+'%</span></div>')

    pk_col = '#e74c3c' if peak_pct>75 else '#f39c12' if peak_pct>50 else '#27ae60'
    av_col = '#e74c3c' if avg_pct>75  else '#f39c12' if avg_pct>50  else '#3498db'
    ft_col = '#e74c3c' if fatigue=='Fatigued' else '#f39c12' if 'Mild' in fatigue else '#27ae60'
    wk_col = '#e74c3c' if work_pct>80 else '#f39c12' if work_pct<20 else '#27ae60'

    tips_map = {
        'Bicep':   ['Focus on slow eccentric (lowering) phase to maximize time under tension',
                    'Keep elbow fixed — avoid swinging to isolate bicep brachii',
                    'Recommended: 3 sets of 8–12 reps at 70% 1RM for hypertrophy'],
        'Tricep':  ['Close-grip pressing targets all 3 tricep heads effectively',
                    'Full extension at the bottom ensures complete muscle activation',
                    'Recommended: Train triceps after chest day for best results'],
        'Forearm': ['Wrist curls build both flexors and extensors equally',
                    'Grip strength directly correlates with forearm EMG amplitude',
                    'Recommended: High-rep training (15–20) with lighter loads'],
        'Shoulder':['Lateral raises should stay below shoulder height to protect rotator cuff',
                    'Keep traps relaxed to isolate the deltoid during raises',
                    'Recommended: Warm up rotator cuff before heavy pressing'],
        'Chest':   ['Wide grip targets pectorals; narrow grip shifts load to triceps',
                    'Incline press recruits upper pec more than flat bench',
                    'Recommended: Full range of motion is critical for peak activation'],
        'Back':    ['Drive elbows down and back — do not pull with biceps',
                    'Scapular retraction before pulling is key for lat engagement',
                    'Recommended: 2:1 pulling to pushing ratio for shoulder health'],
        'Quad':    ['Full depth squat recruits vastus medialis for knee stability',
                    'Knee tracking over toes is critical to avoid joint stress',
                    'Recommended: Compound lifts first, isolation last'],
        'Glutes':  ['Hip thrust has the highest glute EMG activation of any exercise',
                    'Posterior pelvic tilt at the top ensures full contraction',
                    'Recommended: Train glutes 2–3x per week for best hypertrophy'],
        'Calf':    ['Full range of motion — from full stretch to full plantar flexion',
                    'Calves respond best to high frequency (4–5x per week)',
                    'Recommended: Mix seated and standing to target both heads'],
    }
    tips = tips_map.get(muscle, [
        'Maintain proper form throughout the movement',
        'Rest 48–72 hours between sessions for the same muscle group',
        'Progressive overload is the key driver of muscle growth'])

    tip4 = ('Allow 48 hours recovery before training '+muscle+' again.'
            if fatigue!='Normal' else
            'Great recovery! Next session try increasing load by 5–10% for progressive overload.')

    rec_rows = ''
    for i,t in enumerate(tips):
        rec_rows += ('<div style="display:flex;gap:14px;align-items:flex-start;padding:14px 18px;'
                     'background:#f8fafc;border-radius:10px;border-left:3px solid #3b82f6;margin-bottom:10px">'
                     '<div style="width:24px;height:24px;border-radius:50%;background:#3b82f6;color:white;'
                     'display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0">'+str(i+1)+'</div>'
                     '<div style="font-size:14px;color:#334155;line-height:1.6">'+t+'</div></div>')
    rec_rows += ('<div style="display:flex;gap:14px;align-items:flex-start;padding:14px 18px;'
                 'background:#f8fafc;border-radius:10px;border-left:3px solid #f59e0b;margin-bottom:10px">'
                 '<div style="width:24px;height:24px;border-radius:50%;background:#f59e0b;color:white;'
                 'display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0">4</div>'
                 '<div style="font-size:14px;color:#334155;line-height:1.6">'+tip4+'</div></div>')

    fat_note = ('Your fatigue levels are within normal range — great work maintaining consistent output.'
                if fatigue=='Normal' else
                'Mild fatigue detected. Consider increasing rest periods in your next session.'
                if 'Mild' in fatigue else
                'Significant fatigue detected. Prioritize recovery before your next session.')
    wr_note  = ('Your work-to-rest ratio is well balanced.'
                if 30<=work_pct<=70 else
                'Consider adjusting your work-to-rest ratio for optimal muscle adaptation.')

    html = ('<!DOCTYPE html><html lang="en"><head>'
            '<meta charset="UTF-8"/>'
            '<meta name="viewport" content="width=device-width,initial-scale=1.0"/>'
            '<title>MuscleQuant AI Report — '+name+'</title>'
            '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet"/>'
            '<style>'
            '*{margin:0;padding:0;box-sizing:border-box}'
            'body{font-family:Inter,sans-serif;background:#f8fafc;color:#1e293b}'
            '@media print{body{background:white}.no-print{display:none}.page{box-shadow:none;margin:0;border-radius:0}}'
            '.page{max-width:860px;margin:0 auto;background:white;box-shadow:0 4px 40px rgba(0,0,0,.08)}'
            '.header{background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 60%,#0e7490 100%);padding:40px 48px 36px;color:white;position:relative;overflow:hidden}'
            '.header::before{content:"";position:absolute;right:-60px;top:-60px;width:280px;height:280px;border-radius:50%;background:rgba(255,255,255,.04)}'
            '.hdr-top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:28px;position:relative;z-index:1}'
            '.brand{display:flex;align-items:center;gap:14px}'
            '.brand-icon{width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg,#22d3ee,#3b82f6);display:flex;align-items:center;justify-content:center;font-size:24px}'
            '.brand-name{font-size:22px;font-weight:800;letter-spacing:-.5px}'
            '.brand-name em{color:#22d3ee;font-style:normal}'
            '.brand-tag{font-size:11px;color:rgba(255,255,255,.5);letter-spacing:2px;text-transform:uppercase;margin-top:2px}'
            '.hdr-badge{background:rgba(34,211,238,.15);border:1px solid rgba(34,211,238,.3);color:#22d3ee;padding:6px 16px;border-radius:20px;font-size:12px;font-weight:600;letter-spacing:1px}'
            '.hdr-athlete{position:relative;z-index:1}'
            '.hdr-athlete h1{font-size:32px;font-weight:800;letter-spacing:-1px;margin-bottom:4px}'
            '.hdr-athlete h1 span{color:#22d3ee}'
            '.hdr-meta{display:flex;gap:16px;margin-top:10px;flex-wrap:wrap}'
            '.meta-pill{display:flex;align-items:center;gap:7px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);padding:5px 14px;border-radius:20px;font-size:12px;color:rgba(255,255,255,.8)}'
            '.stats-section{padding:32px 48px;background:#f8fafc;border-bottom:1px solid #e2e8f0}'
            '.stats-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}'
            '.stat-card{background:white;border-radius:14px;padding:20px 22px;box-shadow:0 1px 8px rgba(0,0,0,.06);border:1px solid #e2e8f0;text-align:center}'
            '.stat-icon{font-size:26px;margin-bottom:8px}'
            '.stat-val{font-size:32px;font-weight:800;letter-spacing:-1px}'
            '.stat-lbl{font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-top:4px}'
            '.section{padding:28px 48px;border-bottom:1px solid #f1f5f9}'
            '.section-title{font-size:13px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:2px;margin-bottom:18px}'
            '.metrics-table{width:100%;border-collapse:collapse}'
            '.metrics-table th{text-align:left;font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;padding:10px 14px;background:#f8fafc;border-bottom:2px solid #e2e8f0}'
            '.metrics-table td{padding:13px 14px;border-bottom:1px solid #f1f5f9;font-size:14px}'
            '.tech-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}'
            '.tech-item{background:#f8fafc;border-radius:10px;padding:14px 16px;border:1px solid #e2e8f0}'
            '.tech-label{font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px}'
            '.tech-val{font-size:13px;font-weight:600;color:#1e293b}'
            '.footer{padding:24px 48px;background:#0f172a;color:rgba(255,255,255,.4);display:flex;justify-content:space-between;align-items:center}'
            '.footer-brand{font-size:13px;font-weight:700;color:rgba(255,255,255,.7)}'
            '.footer-brand em{color:#22d3ee;font-style:normal}'
            '.footer-note{font-size:11px}'
            '.print-btn{position:fixed;bottom:24px;right:24px;padding:12px 24px;background:linear-gradient(135deg,#22d3ee,#3b82f6);color:white;border:none;border-radius:10px;font-family:Inter,sans-serif;font-size:14px;font-weight:700;cursor:pointer;box-shadow:0 4px 20px rgba(59,130,246,.4)}'
            '</style></head><body>'
            '<div class="page">'

            # HEADER
            '<div class="header">'
            '<div class="hdr-top">'
            '<div class="brand"><div class="brand-icon">&#128170;</div>'
            '<div><div class="brand-name">Muscle<em>Quant</em> AI</div>'
            '<div class="brand-tag">Surface EMG Monitoring Report</div></div></div>'
            '<div class="hdr-badge">SESSION REPORT</div></div>'
            '<div class="hdr-athlete">'
            '<h1>Hey, <span>'+name+'</span> &#128075;</h1>'
            '<p style="color:rgba(255,255,255,.6);font-size:14px;margin-top:4px">Here\'s your complete performance breakdown</p>'
            '<div class="hdr-meta">'
            '<div class="meta-pill">&#128170; '+muscle+'</div>'
            '<div class="meta-pill">&#128197; '+date_str+'</div>'
            '<div class="meta-pill">&#9201; '+now.strftime('%I:%M %p')+'</div>'
            '<div class="meta-pill">&#128202; '+str(readings)+' data points</div>'
            '</div></div></div>'

            # STAT CARDS
            '<div class="stats-section"><div class="stats-grid">'
            '<div class="stat-card"><div class="stat-icon">&#128260;</div>'
            '<div class="stat-val" style="color:#0f172a">'+str(reps)+'</div>'
            '<div class="stat-lbl">Total Reps</div></div>'
            '<div class="stat-card"><div class="stat-icon">&#9889;</div>'
            '<div class="stat-val" style="color:'+pk_col+'">'+str(peak_pct)+'%</div>'
            '<div class="stat-lbl">Peak Intensity</div></div>'
            '<div class="stat-card"><div class="stat-icon">&#9201;</div>'
            '<div class="stat-val" style="color:#0f172a">'+duration+'</div>'
            '<div class="stat-lbl">Duration</div></div>'
            '</div></div>'

            # METRICS TABLE
            '<div class="section"><div class="section-title">Performance Metrics</div>'
            '<table class="metrics-table"><thead><tr>'
            '<th>Metric</th><th>Value</th><th>Visual</th><th>Status</th>'
            '</tr></thead><tbody>'
            '<tr><td style="font-weight:600">Peak Intensity</td>'
            '<td style="font-weight:700;font-size:16px;color:'+pk_col+'">'+str(peak_pct)+'%</td>'
            '<td>'+bar_html(peak_pct,pk_col)+'</td>'
            '<td>'+badge_html('High' if peak_pct>75 else 'Moderate' if peak_pct>40 else 'Low')+'</td></tr>'
            '<tr><td style="font-weight:600">Average Intensity</td>'
            '<td style="font-weight:700;font-size:16px;color:'+av_col+'">'+str(avg_pct)+'%</td>'
            '<td>'+bar_html(avg_pct,av_col)+'</td>'
            '<td>'+badge_html('Optimal' if 30<=avg_pct<=70 else 'Low' if avg_pct<30 else 'High')+'</td></tr>'
            '<tr><td style="font-weight:600">Fatigue Status</td>'
            '<td style="font-weight:700;font-size:16px;color:'+ft_col+'">'+fatigue+'</td>'
            '<td>—</td><td>'+badge_html(fatigue)+'</td></tr>'
            '<tr><td style="font-weight:600">Work Time</td>'
            '<td style="font-weight:700;font-size:16px;color:'+wk_col+'">'+str(work_pct)+'%</td>'
            '<td>'+bar_html(work_pct,wk_col)+'</td>'
            '<td>'+badge_html('Good Balance' if 30<=work_pct<=70 else 'Overworking' if work_pct>70 else 'Too Much Rest')+'</td></tr>'
            '<tr><td style="font-weight:600">Rest Time</td>'
            '<td style="font-weight:700;font-size:16px">'+str(rest_pct)+'%</td>'
            '<td>'+bar_html(rest_pct,'#64748b')+'</td>'
            '<td>'+badge_html('Normal')+'</td></tr>'
            '</tbody></table></div>'

            # MUSCLE ANALYSIS
            '<div class="section"><div class="section-title">&#128170; '+muscle+' Analysis</div>'
            '<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px;padding:18px 22px">'
            '<p style="font-size:14px;line-height:1.7;color:#166534">'
            '<strong>'+name+'</strong>, your '+muscle+' session showed a peak activation of <strong>'+str(peak_pct)+'%</strong>'
            ' with an average of <strong>'+str(avg_pct)+'%</strong> across '+str(readings)+' data points over '+duration+'. '
            +fat_note+' '+wr_note+'</p></div></div>'

            # RECOMMENDATIONS
            '<div class="section"><div class="section-title">Recommendations</div>'
            +rec_rows+'</div>'

            # TECH
            '<div class="section"><div class="section-title">Technical Information</div>'
            '<div class="tech-grid">'
            '<div class="tech-item"><div class="tech-label">Sensor</div><div class="tech-val">MyoWare 2.0</div></div>'
            '<div class="tech-item"><div class="tech-label">Microcontroller</div><div class="tech-val">ESP32</div></div>'
            '<div class="tech-item"><div class="tech-label">Baud Rate</div><div class="tech-val">115200</div></div>'
            '<div class="tech-item"><div class="tech-label">ADC Resolution</div><div class="tech-val">12-bit (0–4095)</div></div>'
            '<div class="tech-item"><div class="tech-label">Sample Rate</div><div class="tech-val">10 Hz</div></div>'
            '<div class="tech-item"><div class="tech-label">Data Source</div><div class="tech-val">'+mode+'</div></div>'
            '</div></div>'

            # FOOTER
            '<div class="footer">'
            '<div class="footer-brand">Muscle<em>Quant</em> AI &mdash; Surface EMG Monitoring</div>'
            '<div class="footer-note">Generated '+now_str+' &middot; Confidential</div>'
            '</div></div>'
            '<button class="print-btn no-print" onclick="window.print()">&#128438; Print / Save PDF</button>'
            '</body></html>')

    return jsonify({'html': html, 'status': 'ok'})

if __name__ == '__main__':
    print('\n'+'='*50)
    print('  MuscleQuant AI — http://localhost:8080')
    print(f'  Mode: {"HARDWARE" if connected else "SIMULATION"}')
    print('='*50+'\n')
    app.run(debug=False, host='0.0.0.0', port=8080)
