from serial_handler import connect_serial, get_emg_value

connect_serial()

while True:
    val, mv = get_emg_value()
    print(val, mv)