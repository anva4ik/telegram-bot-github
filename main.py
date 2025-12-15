import os
import sqlite3
import json
import requests
import telebot
import openai
from datetime import datetime

# ================= НАСТРОЙКИ =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

FREE_LIMIT = 20
CONTEXT_LIMIT = 8
VECTOR_LIMIT = 5

bot = telebot.TeleBot(BOT_TOKEN)
openai.api_key = OPENAI_API_KEY

# ================= БАЗА ДАННЫХ =================
db = sqlite3.connect("bot.db", check_same_thread=False)
sql = db.cursor()

sql.execute("""
CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY,
  messages INTEGER DEFAULT 0,
  is_premium INTEGER DEFAULT 0
)
""")

sql.execute("""
CREATE TABLE IF NOT EXISTS memory (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  role TEXT,
  content TEXT,
  created_at TEXT
)
""")

sql.execute("""
CREATE TABLE IF NOT EXISTS vectors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  content TEXT,
  embedding TEXT
)
""")

sql.execute("""
CREATE TABLE IF NOT EXISTS profile (
  user_id INTEGER,
  key TEXT,
  value TEXT
)
""")

db.commit()

# ================= ФУНКЦИИ =================
def get_user(uid):
    sql.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    u = sql.fetchone()
    if not u:
        sql.execute("INSERT INTO users (user_id) VALUES (?)", (uid,))
        db.commit()
        return (uid, 0, 0)
    return u

def save_memory(uid, role, text):
    sql.execute(
        "INSERT INTO memory (user_id, role, content, created_at) VALUES (?,?,?,?)",
        (uid, role, text, datetime.now().isoformat())
    )
    db.commit()

def load_memory(uid):
    sql.execute(
        "SELECT role, content FROM memory WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (uid, CONTEXT_LIMIT)
    )
    return [{"role": r[0], "content": r[1]} for r in reversed(sql.fetchall())]

def embed(text):
    e = openai.Embedding.create(
        model="text-embedding-3-small",
        input=text
    )
    return e["data"][0]["embedding"]

def cosine(a,b):
    return sum(x*y for x,y in zip(a,b)) / ( (sum(x*x for x in a)**0.5) * (sum(y*y for y in b)**0.5) )

def save_vector(uid, text):
    emb = embed(text)
    sql.execute(
        "INSERT INTO vectors (user_id, content, embedding) VALUES (?,?,?)",
        (uid, text, json.dumps(emb))
    )
    db.commit()

def search_vectors(uid, text):
    q = embed(text)
    sql.execute("SELECT content, embedding FROM vectors WHERE user_id=?", (uid,))
    scored = []
    for c,e in sql.fetchall():
        sim = cosine(q, json.loads(e))
        scored.append((sim,c))
    scored.sort(reverse=True)
    return [c for _,c in scored[:VECTOR_LIMIT]]

def search_image(q):
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": q, "per_page": 1}
    r = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params)
    d = r.json()
    return d["photos"][0]["src"]["large"] if d.get("photos") else None

def gen_image(p):
    i = openai.Image.create(prompt=p,n=1,size="1024x1024")
    return i["data"][0]["url"]

# ================= ОБРАБОТЧИКИ =================
@bot.message_handler(commands=["start"])
def start(m):
    bot.send_message(
        m.chat.id,
        "🧠 *AI ULTIMATE*\n\nЯ помню диалоги, факты о тебе, ищу информацию через GPT, генерирую изображения и фото.\n\nПросто напиши сообщение, и я отвечу!",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: True)
def chat(m):
    uid = m.from_user.id
    user = get_user(uid)
    text = m.text.strip()

    # лимит сообщений для бесплатных
    if not user[2] and user[1] >= FREE_LIMIT:
        bot.send_message(m.chat.id,"❌ Лимит сообщений исчерпан")
        return

    if text.lower().startswith("запомни"):
        save_memory(uid,"user",text[7:])
        bot.send_message(m.chat.id,"🧠 Запомнил")
        return

    if text.lower().startswith("нарисуй"):
        bot.send_message(m.chat.id,"🎨 Генерирую изображение...")
        img_url = gen_image(text)
        bot.send_photo(m.chat.id,img_url)
        return

    if "фото" in text.lower():
        img = search_image(text)
        if img: bot.send_photo(m.chat.id,img)
        else: bot.send_message(m.chat.id,"❌ Фото не найдено")
        return

    # GPT
    long = search_vectors(uid, text)
    profile = ""  # можно потом добавить персональные факты

    messages = [
        {"role":"system","content":"Ты умный AI, который помнит пользователя."},
        {"role":"system","content":f"Воспоминания:\n{chr(10).join(long)}"},
        *load_memory(uid),
        {"role":"user","content":text}
    ]

    r = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=messages
    )

    ans = r.choices[0].message.content
    save_memory(uid,"user",text)
    save_memory(uid,"assistant",ans)
    save_vector(uid,text)
    sql.execute("UPDATE users SET messages = messages+1 WHERE user_id=?", (uid,))
    db.commit()
    bot.send_message(m.chat.id, ans)

# ================= ЗАПУСК =================
if __name__ == "__main__":
    bot.infinity_polling()
