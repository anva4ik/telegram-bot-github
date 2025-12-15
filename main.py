import os
import json
import sqlite3
import requests
from datetime import datetime
from math import sqrt
import telebot
import openai
from flask import Flask, request

# ================= НАСТРОЙКИ =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # URL проекта Railway, например https://project-name.up.railway.app/

ADMINS = [7750512181]
FREE_LIMIT = 20
CONTEXT_LIMIT = 8
VECTOR_LIMIT = 5

bot = telebot.TeleBot(BOT_TOKEN)
openai.api_key = OPENAI_API_KEY

app = Flask(__name__)

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
def is_admin(uid): return uid in ADMINS

def get_user(uid):
    sql.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    u = sql.fetchone()
    if not u:
        sql.execute("INSERT INTO users (user_id) VALUES (?)", (uid,))
        db.commit()
        return (uid, 0, 0)
    return u

def inc(uid):
    sql.execute("UPDATE users SET messages = messages+1 WHERE user_id=?", (uid,))
    db.commit()

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
    return sum(x*y for x,y in zip(a,b)) / (sqrt(sum(x*x for x in a))*sqrt(sum(y*y for y in b)))

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

def save_fact(uid, key, value):
    sql.execute("INSERT INTO profile (user_id,key,value) VALUES (?,?,?)",(uid,key,value))
    db.commit()

def load_profile(uid):
    sql.execute("SELECT key,value FROM profile WHERE user_id=?", (uid,))
    return "\n".join([f"{k}: {v}" for k,v in sql.fetchall()])

def gpt_search(query):
    prompt = f"Представь, что нужно найти ссылки и краткое описание по запросу: {query}. Выдай 3 ссылки и краткий текст по каждой, формат: название — ссылка — описание."
    r = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}]
    )
    return r.choices[0].message.content

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
        "🧠 *AI ULTIMATE*\n\nЯ помню диалоги, факты о тебе,\nищу информацию через GPT, генерирую изображения и фото.\n\nПиши 👇",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["admin"])
def admin(m):
    if not is_admin(m.from_user.id): return
    sql.execute("SELECT COUNT(*) FROM users")
    users = sql.fetchone()[0]
    bot.send_message(m.chat.id, f"👑 Пользователей: {users}")

@bot.message_handler(commands=["export"])
def export_mem(m):
    if not is_admin(m.from_user.id): return
    uid = int(m.text.split()[1])
    sql.execute("SELECT role,content FROM memory WHERE user_id=?", (uid,))
    text = "\n\n".join([f"{r}: {c}" for r,c in sql.fetchall()])
    bot.send_message(m.chat.id, text[:4000])

@bot.message_handler(commands=["clear"])
def clear_mem(m):
    if not is_admin(m.from_user.id): return
    uid = int(m.text.split()[1])
    sql.execute("DELETE FROM memory WHERE user_id=?", (uid,))
    sql.execute("DELETE FROM vectors WHERE user_id=?", (uid,))
    sql.execute("DELETE FROM profile WHERE user_id=?", (uid,))
    db.commit()
    bot.send_message(m.chat.id, "🗑 Память очищена")

@bot.message_handler(func=lambda m: True)
def chat(m):
    uid = m.from_user.id
    user = get_user(uid)
    text = m.text.strip()

    # лимит сообщений для бесплатных
    if not user[2] and user[1] >= FREE_LIMIT:
        bot.send_message(m.chat.id,"❌ Лимит исчерпан")
        return

    if text.lower().startswith("запомни"):
        save_fact(uid,"note",text[7:])
        bot.send_message(m.chat.id,"🧠 Запомнил")
        return

    if text.lower().startswith("найди"):
        bot.send_message(m.chat.id, gpt_search(text))
        return

    if text.lower().startswith("нарисуй"):
        bot.send_message(m.chat.id,"🎨 Генерирую...")
        bot.send_photo(m.chat.id, gen_image(text))
        return

    if "фото" in text.lower():
        img = search_image(text)
        if img: bot.send_photo(m.chat.id,img)
        else: bot.send_message(m.chat.id,"❌ Не найдено")
        return

    long = search_vectors(uid, text)
    profile = load_profile(uid)

    messages = [
        {"role":"system","content":"Ты умный AI, который помнит пользователя."},
        {"role":"system","content":f"Профиль:\n{profile}"},
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
    inc(uid)
    bot.send_message(m.chat.id, ans)

# ================= WEBHOOK ДЛЯ RAILWAY =================
@app.route("/", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

# удаляем старый webhook и ставим новый
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

# ================= ЗАПУСК FLASK =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
