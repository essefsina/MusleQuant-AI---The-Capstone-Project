from flask import Flask, jsonify
from datetime import datetime

from serial_handler import connect_serial, get_emg_value
from emg_processor import (
    add_to_history,
    calc_intensity,
    calc_fatigue,
    update_reps,
    update_work_rest,
    reset_session
)

app = Flask(__name__)

# connect to ESP32 (or simulation)
connect_serial()


@app.route('/')
def home():
    return "MuscleQuant Backend Running"


@app.route('/api/data')
def get_data():
    value, raw_mv = get_emg_value()

    history = add_to_history(value)

    intensity_label, intensity_pct = calc_intensity(value)
    fatigue_status, fatigue_pct = calc_fatigue(history)
    reps = update_reps(value)
    work_pct, rest_pct, state, flag = update_work_rest(value)

    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]

    return jsonify({
        'timestamp': ts,
        'emg': value,
        'raw_mv': raw_mv,
        'history': history,
        'intensity_label': intensity_label,
        'intensity_pct': intensity_pct,
        'fatigue_status': fatigue_status,
        'fatigue_pct': fatigue_pct,
        'reps': reps,
        'work_pct': work_pct,
        'rest_pct': rest_pct,
        'current_state': state,
        'ratio_flag': flag
    })


@app.route('/api/reset')
def reset():
    reset_session()
    return jsonify({'status': 'reset'})


if __name__ == '__main__':
    app.run(debug=True, port=8080)