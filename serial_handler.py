import serial
import serial.tools.list_ports
import time
import math
import random

BAUD_RATE = 115200

ser = None
connected = False
start_time = time.time()
SERIAL_PORT = "AUTO"


def find_port():
    ports = list(serial.tools.list_ports.comports())

    for p in ports:
        if p.device.upper() == "COM7":
            return p.device

    for p in ports:
        desc = (p.description or "").lower()
        if any(k in desc for k in ["usb", "cp210", "ch340"]):
            return p.device

    return ports[0].device if ports else None


def connect_serial():
    global ser, connected, SERIAL_PORT

    port = find_port()

    if not port:
        print("No device found → SIMULATION mode")
        connected = False
        return False

    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=1)
        time.sleep(2)
        SERIAL_PORT = port
        connected = True
        print(f"Connected to {port}")
        return True

    except Exception as e:
        print(f"Serial error: {e} → SIMULATION mode")
        connected = False
        return False


def get_emg_value():
    global ser, connected

    if connected and ser:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()

            if line:
                tokens = line.replace(",", " ").split()

                for t in tokens:
                    try:
                        val = float(t)
                        adc = int((val / 3300.0) * 4095)
                        adc = max(0, min(4095, adc))
                        return adc, f"{val:.6f}"
                    except:
                        continue

        except:
            connected = False

    t = time.time() - start_time
    adc = int(600 + 1800 * abs(math.sin(t * 0.4)) + random.randint(-120, 120))
    adc = max(0, min(4095, adc))

    mv = (adc / 4095.0) * 3300.0
    return adc, f"{mv:.6f}"