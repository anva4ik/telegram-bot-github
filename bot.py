import telebot
import feedparser
import schedule
import time
import os
import random
import requests
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = "@my_cheats"

# Опционально (если захочешь GPT-пересказ позже)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN, disable_web_page_preview=True)

RSS_FEEDS = [
    "https://www.reddit.com/r/anticheat/.rss",
    "https://www.reddit.com/r/gamehacks/.rss",
    "https://www.reddit.com/r/ReverseEngineering/.rss",
]

KEYWORDS = [
    "ban", "anticheat", "update", "detect",
    "patch", "security", "wave"
]

BLOCK_WORDS = [
    "download", "link", "sell", "free cheat",
    "discord.gg", ".exe", ".zip"
]

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

def smart_summary(text: str) -> str:
    # Без GPT: аккуратно режем и чистим
    clean = text.replace("\n", " ").strip()
    return (clean[:280] + "...") if len(clean) > 280 else clean

def time_label():
    h = datetime.now().hour
    if 6 <= h < 12:
        return "🌅 Утро"
    if 12 <= h < 18:
        return "🌤 День"
    return "🌙 Вечер"

def send_news():
    posts = fetch_news()
    if not posts:
        print("Нет новых новостей")
        return

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

# ⏰ 3 раза в день
schedule.every().day.at("10:00").do(send_news)
schedule.every().day.at("16:00").do(send_news)
schedule.every().day.at("22:00").do(send_news)

# 🛌 Anti-sleep для Railway
def keep_alive():
    try:
        requests.get("https://google.com", timeout=10)
        print("Ping OK")
    except:
        pass

schedule.every(10).minutes.do(keep_alive)

print("🤖 Super Bot запущен")

while True:
    schedule.run_pending()
    time.sleep(30)
