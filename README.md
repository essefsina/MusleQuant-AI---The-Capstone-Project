# MuscleQuant AI — Capstone Project
> AI-powered surface EMG muscle monitoring dashboard

## Team
| Name | Role |
|------|------|
| Keshav Harit | PM / AI / Frontend |
| Shahriar Fahim | Hardware / ESP32 |
| Gelin Deng | QA / Database |

## Hardware
- MyoWare 2.0 EMG Sensor
- ESP32 microcontroller
- USB-C connection at 115200 baud

## How to Run
```bash
pip install flask pyserial
python3 app.py
```
Open browser → http://localhost:8080

## Features
- Live EMG signal chart
- AI fatigue detection
- Rep counter + session goals
- 9 muscle groups with SVG icons
- Work/rest ratio monitoring
- Professional PDF session reports
- User login & register system
- USB device connection screen

## File Structure
```
MusleQuant-AI/
├── app.py              # Flask backend (Python)
├── requirements.txt    # Python dependencies
├── data/               # User accounts + session JSON
└── templates/
    ├── login.html      # Login + Register page
    └── index.html      # Main EMG dashboard
```

## Database Schema (MySQL)
```sql
CREATE TABLE users (
  id INT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(50) UNIQUE NOT NULL,
  name VARCHAR(100),
  email VARCHAR(100),
  age INT,
  password VARCHAR(64),
  created_at DATETIME
);

CREATE TABLE sessions (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT REFERENCES users(id),
  muscle VARCHAR(50),
  reps INT,
  peak_pct INT,
  fatigue VARCHAR(30),
  work_pct INT,
  duration VARCHAR(10),
  saved_at DATETIME
);
```
