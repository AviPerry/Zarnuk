# משדר זרנוק

מערכת Web לניהול, ניטור ושליטה במכשירי STM32 דרך MQTT ומודם סלולרי.

## מה יש כרגע

- ממשק עברי מלא עם דף כניסה.
- `Admin / Admin123` כברירת מחדל.
- מסך בית עם חיפוש, הוספה ומחיקה של התקנים.
- Dashboard לכל התקן עם:
  - `online / offline`
  - מדדי `Ir` ו-`V1`
  - פקודות `ON / OFF`
  - הגדרת זרם ותדר
  - התראות
- Backend עם:
  - FastAPI
  - WebSocket
  - ניהול state פר התקן
  - ניתוב MQTT לפי topics פר התקן
  - תמיכה בטלמטריה בפורמט legacy של הבקר: `ch,I,V,F,STATUS`

## הרצה מקומית

```powershell
C:\Users\97252\AppData\Local\Programs\Python\Python311\python.exe -m pip install -r requirements.txt
C:\Users\97252\AppData\Local\Programs\Python\Python311\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

פתיחה:

- `http://127.0.0.1:8000/login`

## משתני סביבה חשובים

הפרויקט משתמש ב-`.env`.

דוגמאות עיקריות:

- `MQTT_ENABLED=true`
- `MQTT_HOST=broker.hivemq.com`
- `MQTT_PORT=1883`
- `MQTT_TLS=false`
- `AUTH_USERNAME=Admin`
- `AUTH_PASSWORD=Admin123`

## פריסה ל-Render

הוספתי קובץ [`render.yaml`](./render.yaml), כך שאפשר לפרוס כ-`Web Service`.

מה לבחור ב-Render:

1. `New +`
2. `Blueprint` אם Render מזהה את `render.yaml`
3. אם לא, `Web Service`

הגדרות ידניות אם צריך:

- Build Command:
  - `pip install -r requirements.txt`
- Start Command:
  - `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Environment Variables שכדאי להגדיר ב-Render:

- `MQTT_ENABLED=true`
- `MQTT_HOST=broker.hivemq.com`
- `MQTT_PORT=1883`
- `MQTT_TLS=false`
- `MQTT_CLIENT_ID=zeliger-web-backend`
- `AUTH_USERNAME=Admin`
- `AUTH_PASSWORD=Admin123` או סיסמה חזקה יותר

## הכנה ל-GitHub

הוספתי:

- `.gitignore`
- `render.yaml`

מה עדיין צריך ממך:

1. ליצור repository חדש ב-GitHub
2. להריץ:

```powershell
git init
git add .
git commit -m "Initial deployable version"
git branch -M main
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

אחרי שהקוד ב-GitHub, אפשר לחבר את ה-repo ל-Render.
