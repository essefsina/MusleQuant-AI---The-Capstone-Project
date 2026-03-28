from emg_processor import *

for i in range(100):
    val = 1000 + (i % 50) * 20

    history = add_to_history(val)
    intensity, pct = calc_intensity(val)
    fatigue, f_pct = calc_fatigue(history)
    reps = update_reps(val)
    work, rest, state, flag = update_work_rest(val)

    print(val, intensity, reps, fatigue, flag)