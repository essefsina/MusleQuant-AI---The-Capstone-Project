from collections import deque

MAX_HISTORY = 200
WORK_THRESHOLD = 1200

emg_history = deque(maxlen=MAX_HISTORY)

rep_count = 0
last_above = False

work_samples = 0
rest_samples = 0
current_state = "REST"


def add_to_history(value):
    emg_history.append(value)
    return list(emg_history)


def calc_intensity(value):
    pct = int((value / 4095) * 100)

    if value < 500:
        return "Rest", pct
    if value < 1200:
        return "Low", pct
    if value < 2400:
        return "Moderate", pct
    if value < 3200:
        return "High", pct
    return "Peak", pct


def calc_fatigue(history):
    if len(history) < 40:
        return "Insufficient Data", 0

    data = list(history)
    half = len(data) // 2

    first_half = sum(data[:half]) / half
    second_half = sum(data[half:]) / half

    if first_half == 0:
        return "Normal", 0

    drop = ((first_half - second_half) / first_half) * 100

    if drop > 15:
        return "Fatigued", int(drop)
    if drop > 8:
        return "Mild Fatigue", int(drop)

    return "Normal", max(0, int(drop))


def update_reps(value):
    global rep_count, last_above

    above = value > WORK_THRESHOLD

    if above and not last_above:
        rep_count += 1

    last_above = above
    return rep_count


def update_work_rest(value):
    global work_samples, rest_samples, current_state

    if value > WORK_THRESHOLD:
        work_samples += 1
        current_state = "WORK"
    else:
        rest_samples += 1
        current_state = "REST"

    total = work_samples + rest_samples

    work_pct = int((work_samples / total) * 100) if total > 0 else 0
    rest_pct = 100 - work_pct

    if work_pct >= 80:
        flag = "Overworking"
    elif rest_pct >= 80:
        flag = "Too Much Rest"
    else:
        flag = "Good Balance"

    return work_pct, rest_pct, current_state, flag


def reset_session():
    global rep_count, last_above, work_samples, rest_samples, current_state

    emg_history.clear()
    rep_count = 0
    last_above = False
    work_samples = 0
    rest_samples = 0
    current_state = "REST"