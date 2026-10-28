from flask import Flask, render_template, request, redirect, url_for, flash, Response
from pathlib import Path
from datetime import datetime
from email.message import EmailMessage
import os, sqlite3, smtplib, threading, shutil, time
import cv2
import numpy as np

BASE = Path(__file__).resolve().parent
DATA = BASE / 'data'
FACES = DATA / 'faces'
MEDICAL = DATA / 'medical_photos'
MODEL = DATA / 'trainer.yml'
DB = BASE / 'attendance.db'
CASCADE_FILE = BASE / 'haarcascade_frontalface_default.xml'
for folder in (DATA, FACES, MEDICAL): folder.mkdir(parents=True, exist_ok=True)
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'change-this-local-demo-key')


def get_db():
    con = sqlite3.connect(DB, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute('CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY, name TEXT NOT NULL)')
    con.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL,
        name TEXT NOT NULL, date TEXT NOT NULL, time TEXT NOT NULL,
        UNIQUE(student_id, date))''')
    cols = {r['name'] for r in con.execute('PRAGMA table_info(students)')}
    for col in ('parent_email', 'medical_issue', 'medical_photo'):
        if col not in cols:
            con.execute(f"ALTER TABLE students ADD COLUMN {col} TEXT DEFAULT ''")
    con.commit()
    return con


def get_detector():
    if not CASCADE_FILE.exists():
        raise RuntimeError('haarcascade_frontalface_default.xml file app.py ke saath hona chahiye.')
    detector = cv2.CascadeClassifier(str(CASCADE_FILE))
    if detector.empty(): raise RuntimeError('Face detector load nahi hua. XML file dobara extract karein.')
    return detector


def send_parent_email(parent_email, student_name, sid, when):
    sender = os.environ.get('SMTP_EMAIL', '').strip()
    password = os.environ.get('SMTP_APP_PASSWORD', '').strip()
    if not parent_email or not sender or not password:
        if parent_email: print('Parent email nahi bheja: SMTP_EMAIL aur SMTP_APP_PASSWORD set karein.')
        return
    msg = EmailMessage()
    msg['Subject'] = f'Attendance marked: {student_name}'
    msg['From'] = sender
    msg['To'] = parent_email
    msg.set_content(
        f'Hello Parent/Guardian,\n\nAttendance has been marked for {student_name} (Student ID: {sid}).\n'
        f'Date: {when.strftime("%d-%m-%Y")}\nTime: {when.strftime("%I:%M:%S %p")}\n\n'
        'This is an automated attendance notification. If you believe this is an error, please contact the school.'
    )
    try:
        host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
        port = int(os.environ.get('SMTP_PORT', '587'))
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls(); server.login(sender, password); server.send_message(msg)
        print(f'Attendance email sent to {parent_email}')
    except Exception as exc:
        print(f'Parent email send error: {exc}')


def mark_attendance(sid):
    con = get_db()
    student = con.execute('SELECT id,name,parent_email FROM students WHERE id=?', (int(sid),)).fetchone()
    if not student:
        con.close(); return None, False
    now = datetime.now()
    try:
        con.execute('INSERT INTO attendance(student_id,name,date,time) VALUES(?,?,?,?)',
                    (student['id'], student['name'], now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S')))
        con.commit(); inserted = True
    except sqlite3.IntegrityError:
        inserted = False
    con.close()
    if inserted and student['parent_email']:
        threading.Thread(target=send_parent_email,
                         args=(student['parent_email'], student['name'], student['id'], now), daemon=True).start()
    return student['name'], inserted


@app.route('/')
def index():
    con = get_db()
    today = datetime.now().strftime('%Y-%m-%d')
    stats = {
        'students': con.execute('SELECT COUNT(*) FROM students').fetchone()[0],
        'present': con.execute('SELECT COUNT(*) FROM attendance WHERE date=?', (today,)).fetchone()[0],
        'records': con.execute('SELECT COUNT(*) FROM attendance').fetchone()[0],
    }
    recent = con.execute('SELECT student_id,name,date,time FROM attendance ORDER BY date DESC,time DESC LIMIT 6').fetchall()
    con.close()
    return render_template('index.html', stats=stats, recent=recent, today=today)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET': return render_template('register.html')
    sid_text = request.form.get('student_id', '').strip()
    name = request.form.get('name', '').strip()
    parent_email = request.form.get('parent_email', '').strip()
    medical_issue = request.form.get('medical_issue', '').strip()
    if not sid_text.isdigit() or not name:
        flash('Numeric Student ID aur student ka naam zaroori hai.', 'error')
        return redirect(url_for('register'))
    if parent_email and ('@' not in parent_email or '.' not in parent_email.split('@')[-1]):
        flash('Parent/Guardian email address sahi nahi lag raha.', 'error')
        return redirect(url_for('register'))
    sid = int(sid_text)
    saved_photo = ''
    upload = request.files.get('medical_photo')
    if upload and upload.filename:
        ext = Path(upload.filename).suffix.lower()
        if ext not in ('.jpg', '.jpeg', '.png', '.bmp'):
            flash('Medical photo JPG, JPEG, PNG ya BMP honi chahiye.', 'error')
            return redirect(url_for('register'))
        saved = MEDICAL / f'student_{sid}{ext}'
        upload.save(saved); saved_photo = str(saved)
    con = get_db()
    con.execute('''INSERT INTO students(id,name,parent_email,medical_issue,medical_photo) VALUES(?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET name=excluded.name,parent_email=excluded.parent_email,
                   medical_issue=excluded.medical_issue,
                   medical_photo=CASE WHEN excluded.medical_photo='' THEN students.medical_photo ELSE excluded.medical_photo END''',
                (sid, name, parent_email, medical_issue, saved_photo))
    con.commit(); con.close()
    try:
        detector = get_detector()
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) if hasattr(cv2, 'CAP_DSHOW') else cv2.VideoCapture(0)
        if not cap.isOpened(): cap.release(); cap = cv2.VideoCapture(0)
        if not cap.isOpened(): raise RuntimeError('Webcam open nahi hua. Windows Settings mein camera permission check karein.')
        for p in FACES.glob(f'User.{sid}.*.jpg'):
            try: p.unlink()
            except OSError: pass
        count = 0
        flash('Camera window mein face ko camera ki taraf rakhein. 30 samples capture honge; Q dabakar stop kar sakte hain.', 'info')
        while count < 30:
            ok, frame = cap.read()
            if not ok: break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(gray, 1.2, 5, minSize=(80, 80))
            for (x, y, w, h) in faces:
                count += 1
                cv2.imwrite(str(FACES / f'User.{sid}.{count}.jpg'), gray[y:y+h, x:x+w])
                cv2.rectangle(frame, (x,y), (x+w,y+h), (60,230,180), 2)
                cv2.putText(frame, f'Samples: {count}/30', (x, max(25,y-10)), cv2.FONT_HERSHEY_SIMPLEX, .7, (255,255,255), 2)
                if count >= 30: break
            cv2.imshow('Register Student - Q to stop', frame)
            if cv2.waitKey(60) & 0xFF == ord('q'): break
        cap.release(); cv2.destroyAllWindows()
        if count:
            flash(f'{name} save ho gaya. {count} face samples capture hue. Ab Train Face AI Model karein.', 'success')
        else:
            flash('Student details save hue, lekin face sample capture nahi hua. Webcam/lighting check karke dobara register karein.', 'error')
    except Exception as exc:
        try: cap.release()
        except Exception: pass
        cv2.destroyAllWindows()
        flash(f'Student details save hue, lekin camera capture error: {exc}', 'error')
    return redirect(url_for('register'))


@app.route('/train', methods=['POST'])
def train():
    if not hasattr(cv2, 'face'):
        flash('opencv-contrib-python install karein: py -m pip install -r requirements.txt', 'error')
        return redirect(url_for('index'))
    images, ids = [], []
    for path in FACES.glob('User.*.*.jpg'):
        parts = path.stem.split('.')
        if len(parts) != 3: continue
        try: sid = int(parts[1])
        except ValueError: continue
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is not None: images.append(image); ids.append(sid)
    if not images:
        flash('Pehle student register karke face samples capture karein.', 'error')
        return redirect(url_for('index'))
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(images, np.array(ids, dtype=np.int32)); recognizer.write(str(MODEL))
    flash(f'AI model train ho gaya: {len(images)} face samples.', 'success')
    return redirect(url_for('index'))


@app.route('/attendance/live')
def live_attendance():
    if not MODEL.exists():
        flash('Live attendance se pehle Train Face AI Model par click karein.', 'error')
        return redirect(url_for('index'))
    return render_template('live.html')


def generate_frames():
    detector = get_detector()
    recognizer = cv2.face.LBPHFaceRecognizer_create(); recognizer.read(str(MODEL))
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) if hasattr(cv2, 'CAP_DSHOW') else cv2.VideoCapture(0)
    if not cap.isOpened(): cap.release(); cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        yield b''; return
    last_marked = {}
    con = get_db()
    known_names = {int(r['id']): r['name'] for r in con.execute('SELECT id,name FROM students')}
    con.close()
    try:
        while True:
            ok, frame = cap.read()
            if not ok: break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(gray, 1.2, 5, minSize=(80,80))
            for (x,y,w,h) in faces:
                sid, confidence = recognizer.predict(gray[y:y+h, x:x+w])
                label = 'Unknown face'
                color = (70,90,240)
                if confidence < 65:
                    student_name = known_names.get(int(sid))
                    if student_name:
                        label = student_name
                        color = (60,220,160)
                        now_ts = time.time()
                        if now_ts - last_marked.get(int(sid), 0) > 3:
                            mark_attendance(sid)
                            last_marked[int(sid)] = now_ts
                    else:
                        label = 'Unknown face'
                cv2.rectangle(frame, (x,y), (x+w,y+h), color, 2)
                cv2.putText(frame, label, (x, max(24,y-10)), cv2.FONT_HERSHEY_SIMPLEX, .58, (255,255,255), 2)
            cv2.putText(frame, datetime.now().strftime('%d %b %Y  %I:%M:%S %p'), (15,30), cv2.FONT_HERSHEY_SIMPLEX, .65, (255,255,255), 2)
            ok, buffer = cv2.imencode('.jpg', frame)
            if not ok: continue
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    finally:
        cap.release()


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/attendance')
def attendance():
    con = get_db()
    rows = con.execute('SELECT student_id,name,date,time FROM attendance ORDER BY date DESC,time DESC').fetchall()
    con.close()
    return render_template('attendance.html', rows=rows)


@app.route('/analytics')
def analytics():
    con = get_db()
    today = datetime.now().strftime('%Y-%m-%d')
    total = con.execute('SELECT COUNT(*) FROM students').fetchone()[0]
    present = con.execute('SELECT COUNT(*) FROM attendance WHERE date=?', (today,)).fetchone()[0]
    records = con.execute('SELECT COUNT(*) FROM attendance').fetchone()[0]
    students = con.execute('''SELECT s.id,s.name,COUNT(a.id) AS days FROM students s
                              LEFT JOIN attendance a ON a.student_id=s.id GROUP BY s.id,s.name ORDER BY s.id''').fetchall()
    con.close()
    return render_template('analytics.html', total=total, present=present, records=records, students=students, today=today)


if __name__ == '__main__':
    get_db().close()
    print('\nAI Attendance Web app: http://127.0.0.1:5000')
    app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)
