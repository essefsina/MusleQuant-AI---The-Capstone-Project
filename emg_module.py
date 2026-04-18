import serial
import serial.tools.list_ports
import time
import re
from collections import deque
from datetime import datetime
from flask import jsonify

# ── SERIAL CONFIG ──
BAUD_RATE = 115200
ser = None
connected = False

# ── FIND ESP32 PORT ──
def find_port():
    ports = list(serial.tools.list_ports.comports())

    for p in ports:
        desc = (p.description or "").lower()
        if any(k in desc for k in ["cp210", "ch340", "usb serial", "silicon labs"]):
            print("Auto-detected ESP32 on:", p.device)
            return p.device

    print("No ESP32 found")
    return None

# ── CONNECT SERIAL ──
def connect_serial():
    global ser, connected

    port = find_port()

    if not port:
        connected = False
        return

    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=1)
        time.sleep(3)  # allow ESP32 to reset
        ser.reset_input_buffer()  # clear junk
        connected = True
        print("Connected on", port)
    except Exception as e:
        print("Serial error:", e)
        connected = False

connect_serial()

# ── DATA STORAGE ──
emg_history = deque(maxlen=200)
csv_log = []
WORK_THRESHOLD = 150

# ── READ SENSOR ──
def get_emg_value():
    global ser, connected

    if connected and ser:
        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()

            if not line:
                return 0, "0"

            print("RAW:", line)

            numbers = re.findall(r'\d+', line)

            if numbers:
                value = int(numbers[0])

                # baseline shift (rest ≈ 0)
                # small noise filter
                if value < 30:
                    value = 0

                return value, str(value)

            return 0, "0"

        except Exception as e:
            print("SERIAL ERROR:", e)
            connected = False

    return 0, "0"

# ── INTENSITY LOGIC ──
def calc_intensity(value):
    if value < 30:
        return "Rest", 0
    elif value < 120:
        return "Low", 25
    elif value < 300:
        return "Moderate", 50
    elif value < 700:
        return "High", 75
    else:
        return "Peak", 100

# ── API RESPONSE ──
def process_emg_data():
    value, raw = get_emg_value()

    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]

    emg_history.append(value)

    csv_log.append({
        "timestamp": timestamp,
        "emg": value,
        "mv": raw
    })

    label, percent = calc_intensity(value)

    return jsonify({
        "timestamp": timestamp,
        "emg": value,
        "history": list(emg_history),
        "intensity_label": label,
        "intensity_pct": percent
    })

def get_status(session):
    return jsonify({
        "connected": connected,
        "mode": "Hardware" if connected else "Disconnected"
    })

def clear_session_data():
    emg_history.clear()
    csv_log.clear()
    return jsonify({"status": "cleared"})