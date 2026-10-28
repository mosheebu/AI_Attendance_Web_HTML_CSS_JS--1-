# AttendAI — AI Face Attendance Web App

A local Flask web application with HTML, CSS and JavaScript frontend, SQLite attendance storage, webcam face capture and OpenCV LBPH face recognition.

## Requirements
- Windows 10/11
- Python 3.10–3.12 recommended
- A working webcam

## Run on Windows
1. Extract this ZIP to a normal folder, for example `C:\Users\YourName\Downloads\AI_Attendance_Web`.
2. Open PowerShell in that folder. You can open the folder in File Explorer, click the address bar, type `powershell`, and press Enter.
3. Create a virtual environment (recommended):

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, you can skip activation and use `py -m pip` in the next step.

4. Install dependencies:

   ```powershell
   py -m pip install -r requirements.txt
   ```

5. Start the web app:

   ```powershell
   py app.py
   ```

6. Open `http://127.0.0.1:5000` in your browser. Keep the PowerShell window open while using the app.

## Typical workflow
1. Choose **Register student**, enter a numeric ID and name, then submit.
2. The OpenCV webcam window opens separately. Look toward the camera to capture face samples. Press Q to stop early.
3. Return to the web dashboard and click **Train face AI model**.
4. Open **Live attendance** to recognize registered faces.
5. Review saved records in **Attendance records** or **Analytics**.

## Notes
- Keep `haarcascade_frontalface_default.xml` beside `app.py`.
- The app creates `attendance.db` and data folders automatically.
- Parent email notifications are optional and require SMTP environment variables (`SMTP_EMAIL`, `SMTP_APP_PASSWORD`, optionally `SMTP_HOST` and `SMTP_PORT`). Never put email credentials in public source code.
- Camera capture is performed by OpenCV on the computer running Flask, so run the app on the computer whose webcam you want to use.
- This is a local demo. Test recognition in your own environment and obtain appropriate consent before collecting or using anyone's face data.
