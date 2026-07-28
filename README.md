# 🎬 Telegram Cinema Web Platform (FastAPI + SQLite + HTML5 Frontend)

מערכת מלאה (Full-Stack) לצפייה ישירה והורדה של סרטים מתוך ערוץ טלגרם. המערכת כוללת שרת FastAPI מתקדם, מסד נתונים SQLite עם מנגנון חיפוש מהיר FTS5, אינטגרציה עם Pyrogram להזרמת מדיה מטלגרם בזמן אמת, וממשק משתמש מודרני בסגנון נטפליקס.

---

## 📁 מבנה הפרויקט

```text
/home/yonatan/מסמכים/bot/
├── config.py              # הגדרות שרת, טלגרם ומסדי נתונים
├── database.py            # מודול מסד נתונים SQLite עם FTS5 ושאילתות
├── telegram_client.py     # אינטגרציה עם Pyrogram והזרמת Chunk-ים מטלגרם
├── server.py              # שרת FastAPI עם Range Requests, Search & Download APIs
├── bot.py                 # הבוט הקיים בטלגרם לאינדוקס וחיפוש
├── static/                # קבצים סטטיים לעיצוב ולוגיקה
│   ├── css/
│   │   └── style.css      # עיצוב מודרני, Dark Mode, Glassmorphism ורספונסיביות מלאה
│   └── js/
│       └── app.js         # לוגיקת צד לקוח, חיפוש בזמן אמת, ונגן וידאו מודאלי
└── templates/
    └── index.html         # תבנית HTML5 ראשית עם נגן וידאו HTML5
```

---

## 🚀 תכונות עיקריות

### 1. צד השרת (Backend - FastAPI):
* **SQLite & FTS5 Full Text Search**: חיפוש מהיר במיוחד של סרטים לפי שם, ז'אנר ותיאור.
* **HTTP Range Requests Streaming (`/api/stream/{id}`)**: תמיכה מלאה בנגן הווידאו של HTML5 המאפשרת הרצה קדימה ואחורה בזמן (Seeking) ללא צורך בהורדת כל הקובץ מראש.
* **Direct File Download (`/api/download/{id}`)**: נקודת קצה להורדה ישירה למכשיר המשתמש.
* **Pyrogram MTProto Integration**: חיבור ישיר לטלגרם לשליפת קובצי וידאו בזמן אמת.

### 2. צד הלקוח (Frontend):
* **עיצוב מודרני ויוקרתי (Netflix-Style)**: מבוסס Dark Mode, Glassmorphism, ואנימציות מיקרו.
* **תיבת חיפוש דינמית**: חיפוש מיידי בלייב עם Debounce.
* **נגן וידאו מובנה (HTML5 Video Modal)**: חלון צפייה ייעודי שקוף ומודרני הפותח את הווידאו ישירות בדפדפן.
* **רספונסיביות מלאה**: תמיכה מושלמת במכשירים ניידים, טאבלטים ומחשבים אישיים.

---

## 🛠️ הוראות הרצה

להרצת השרת:
```bash
cd /home/yonatan/מסמכים/bot
python3 server.py
```
או באמצעות uvicorn:
```bash
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

לאחר ההרצה, פתח את הדפדפן בכתובת:
`http://localhost:8000`
