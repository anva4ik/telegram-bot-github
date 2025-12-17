import telebot
import feedparser
import schedule
import time
import os
import random
import requests
from datetime import datetime
from threading import Thread

# ===== ПЕРЕМЕННЫЕ =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = "@my_cheats"

bot = telebot.TeleBot(BOT_TOKEN, disable_web_page_preview=True)

# ===== RSS источники =====
RSS_FEEDS = [
    "https://www.reddit.com/r/anticheat/.rss",
    "https://www.reddit.com/r/gamehacks/.rss",
    "https://www.reddit.com/r/ReverseEngineering/.rss",
]

# ===== Ключевые слова =====
KEYWORDS = [
    "ban", "anticheat", "update", "detect",
    "patch", "security", "wave"
]

# ===== Слова для блокировки =====
BLOCK_WORDS = [
    "download", "link", "sell", "free cheat",
    "discord.gg", ".exe", ".zip"
]

# ===== Файл памяти отправленных новостей =====
SENT_FILE = "sent.txt"

def load_sent():
    if not os.path.exists(SENT_FILE):
        return set()
    with open(SENT_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def save_sent(link):
    with open(SENT_FILE, "a", encoding="utf-8") as f:
        f.write(link + "\n")

sent_links = load_sent()

def is_clean(text: str) -> bool:
    t = text.lower()
    return not any(b in t for b in BLOCK_WORDS)

# ===== Получаем новости =====
def fetch_news():
    candidates = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for e in feed.entries:
            text = (e.title + " " + e.get("summary", "")).lower()
            if any(k in text for k in KEYWORDS) and is_clean(text):
                if e.link not in sent_links:
                    candidates.append(e)
    return candidates

# ===== Краткий пересказ =====
def smart_summary(text: str) -> str:
    clean = text.replace("\n", " ").strip()
    return (clean[:280] + "...") if len(clean) > 280 else clean

# ===== Метка времени =====
def time_label():
    h = datetime.now().hour
    if 6 <= h < 12:
        return "🌅 Утро"
    if 12 <= h < 18:
        return "🌤 День"
    return "🌙 Вечер"

# ===== Отправка новости =====
def send_news():
    posts = fetch_news()
    if posts:
        e = random.choice(posts)
        sent_links.add(e.link)
        save_sent(e.link)

        title = e.title.strip()
        summary_raw = e.get("summary", "")
        summary = smart_summary(summary_raw)

        msg = (
            f"{time_label()} | *Cheat / Anti-Cheat News*\n\n"
            f"🔹 *{title}*\n\n"
            f"📌 {summary}\n\n"
            "#news #anticheat #security"
        )

        bot.send_message(CHANNEL_ID, msg, parse_mode="Markdown")
        print("Новость отправлена")
    else:
        print("Нет новых новостей, можно отправить тестовое сообщение")
        # Тестовое сообщение при отсутствии новостей
        test_msg = f"{time_label()} | *Cheat / Anti-Cheat News*\n\n🔹 Тестовое сообщение. Бот работает!"
        bot.send_message(CHANNEL_ID, test_msg, parse_mode="Markdown")
        print("Тестовое сообщение отправлено")

# ===== Anti-sleep для Railway Free =====
def keep_alive():
    while True:
        try:
            requests.get("https://google.com", timeout=10)
            print("Ping OK")
        except:
            pass
        time.sleep(600)  # каждые 10 минут

Thread(target=keep_alive, daemon=True).start()

# ===== Расписание =====
schedule.every().day.at("10:00").do(send_news)
schedule.every().day.at("16:00").do(send_news)
schedule.every().day.at("22:00").do(send_news)

# ===== Сразу отправляем новость при старте =====
send_news()

print("🤖 Super Bot запущен")

# ===== Основной цикл =====
while True:
    schedule.run_pending()
    time.sleep(30)
